import streamlit as st
import pandas as pd
from datetime import datetime
import io
from base_datos import conectar, obtener_proyectos, obtener_productos_por_proyecto, obtener_seguimiento, obtener_pesos_seguimiento

def mostrar(supervisor_id=None):
    st.markdown("""
        <style>
        .report-title { font-size: 28px; font-weight: bold; color: #1E3A8A; margin-bottom: 0.5rem; }
        [data-testid="stMetricValue"] { color: #1E3A8A !important; font-weight: bold !important; font-size: 24px !important; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<p class="report-title">📋 Panel de Seguimiento de Avances por Producto</p>', unsafe_allow_html=True)
    
    # 1. SELECCIÓN DE PROYECTO CON MEMORIA EN SESIÓN
    nombre_proyecto_actual = st.session_state.get('p_nom_sel_seguimiento', "Ninguno")
    
    with st.expander(f"🎯 Proyecto Activo: {nombre_proyecto_actual}", expanded=not st.session_state.get('id_p_sel_seguimiento')):
        c1, c2 = st.columns([2, 1])
        bus_p = c1.text_input("Filtrar por nombre o código del proyecto:", key="bus_proy_seguimiento")
        df_p_all = obtener_proyectos(bus_p)
        
        # Si es supervisor, filtrar solo sus proyectos asignados
        rol_u = str(st.session_state.get('rol', 'Supervisor')).strip().lower()
        if rol_u not in ["admin", "gerente", "administrador"] and not df_p_all.empty:
            df_p_all = df_p_all[df_p_all['supervisor_id'] == supervisor_id]

        if not df_p_all.empty:
            opciones = {f"[{r['codigo']}] {r['proyecto_text']}": r['id'] for _, r in df_p_all.iterrows()}
            lista_opc = ["-- Seleccionar --"] + list(opciones.keys())
            
            p_actual = st.session_state.get('p_nom_sel_seguimiento', "-- Seleccionar --")
            idx_s = lista_opc.index(p_actual) if p_actual in lista_opc else 0
            
            sel_n = c2.selectbox("Proyecto:", lista_opc, index=idx_s, key="sel_proy_seguimiento_master")
            
            if sel_n != p_actual:
                st.session_state.id_p_sel_seguimiento = opciones[sel_n] if sel_n != "-- Seleccionar --" else None
                st.session_state.p_nom_sel_seguimiento = sel_n
                st.rerun()
        else:
            st.warning("⚠️ No se encontraron proyectos asignados."); return

    if not st.session_state.get('id_p_sel_seguimiento'):
        st.info("💡 Seleccione un proyecto en el panel superior para desplegar el despiece de melamina."); return

    id_p = st.session_state.id_p_sel_seguimiento
    productos = obtener_productos_por_proyecto(id_p)
    
    if productos.empty:
        st.info("📂 Este proyecto no registra despieces de melamina aún."); return

    # 2. SECCIÓN DE MÉTRICAS GLOBALES
    pesos = obtener_pesos_seguimiento()
    supabase = conectar()
    
    # Obtener el estado actual de hitos de todos los productos del proyecto (Una sola consulta)
    res_seg_proy = supabase.table("seguimiento").select("producto_id, hito").in_("producto_id", productos['id'].tolist()).execute()
    df_seg_proy = pd.DataFrame(res_seg_proy.data) if res_seg_proy.data else pd.DataFrame(columns=['producto_id', 'hito'])
    
    total_muebles = len(productos)
    suma_avances = 0.0
    
    for _, prod in productos.iterrows():
        hit_prod = df_seg_proy[df_seg_proy['producto_id'] == prod['id']]['hito'].tolist()
        pct_prod = sum([pesos.get(h, 0) for h in hit_prod])
        suma_avances += pct_prod
        
    avance_global_proyecto = round(suma_avances / total_muebles, 2) if total_muebles > 0 else 0.0
    
    # Guardar avance en Supabase
    try:
        supabase.table("proyectos").update({"avance": float(avance_global_proyecto)}).eq("id", id_p).execute()
    except:
        pass

    m1, m2 = st.columns(2)
    m1.metric("📦 Cantidad de Muebles", f"{total_muebles} Unidades")
    m2.metric("📈 Avance Real del Proyecto", f"{avance_global_proyecto}%")

    # =========================================================================
    # AJUSTE CONCENTRADO: GESTIÓN OFFLINE DE IMPORTACIÓN / EXPORTACIÓN SANEADA
    # =========================================================================
    with st.expander("⚙️ Gestión Offline (Importar / Exportar Excel)"):
        tab_export, tab_import = st.tabs(["📥 Descargar Formato de Avance", "📤 Subir Excel de Supervisión"])
        
        with tab_export:
            st.write("Descargue el listado completo de piezas. Las columnas de hitos mostrarán 'X' si ya fueron completadas.")
            
            # Reconstrucción horizontal temporal exclusiva para el reporte Excel
            df_excel = productos[['id', 'ubicacion', 'tipo', 'ml', 'ctd']].copy()
            for hito_col in pesos.keys():
                df_excel[hito_col] = ""
                
            for idx, r_ex in df_excel.iterrows():
                h_registrados = df_seg_proy[df_seg_proy['producto_id'] == r_ex['id']]['hito'].tolist()
                for hr in h_registrados:
                    if hr in df_excel.columns:
                        df_excel.loc[idx, hr] = "X"
            
            df_excel = df_excel.rename(columns={
                'id': 'ID Pieza', 'ubicacion': 'Ubicación', 'tipo': 'Tipo Mueble', 'ml': 'ML', 'ctd': 'Cantidad'
            })
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_excel.to_excel(writer, index=False, sheet_name="Sheet1")
                
            st.download_button(
                "📥 Descargar Reporte Base Excel", 
                data=output.getvalue(), 
                file_name=f"Seguimiento_Offline_{id_p}.xlsx", 
                use_container_width=True
            )
            
        with tab_import:
            st.write("Suba la planilla Excel con las marcaciones 'X' o 'x' en los hitos correspondientes.")
            f_subida = st.file_uploader("Seleccione archivo .xlsx", type=["xlsx"], key="excel_uploader_seguimiento")
            
            if f_subida and st.button("🚀 Procesar Sincronización Masiva"):
                try:
                    df_imp = pd.read_excel(f_subida)
                    df_imp = df_imp.dropna(subset=['ID Pieza']) # Blindaje contra filas vacías
                    
                    # Obtener historial de fechas existentes en Supabase para no perder la trazabilidad real
                    res_fechas_orig = supabase.table("seguimiento").select("producto_id, hito, fecha, observaciones").in_("producto_id", productos['id'].tolist()).execute()
                    dict_fechas_orig = {}
                    dict_obs_orig = {}
                    if res_fechas_orig.data:
                        for f_orig in res_fechas_orig.data:
                            dict_fechas_orig[(int(f_orig['producto_id']), str(f_orig['hito']).strip())] = f_orig['fecha']
                            dict_obs_orig[(int(f_orig['producto_id']), str(f_orig['hito']).strip())] = f_orig['observaciones']
                    
                    lote_delete_ids = []
                    lote_insert_rows = []
                    now_str = datetime.now().isoformat()
                    
                    for _, row_imp in df_imp.iterrows():
                        pid_ex = int(float(str(row_imp['ID Pieza']).strip()))
                        lote_delete_ids.append(pid_ex)
                        
                        # Evaluar cada uno de los hitos vigentes del sistema
                        for hito_nombre in pesos.keys():
                            val_celda = str(row_imp.get(hito_nombre, '')).strip().upper()
                            # Tolerancia absoluta a X, x, SI, si, 1 o TRUE
                            is_marcado = val_celda in ["X", "1", "SI", "TRUE"]
                            
                            if is_marcado:
                                # Conservar fecha histórica si existía, de lo contrario colocar hora actual
                                fecha_guardado = dict_fechas_orig.get((pid_ex, hito_nombre), now_str)
                                obs_guardado = dict_obs_orig.get((pid_ex, hito_nombre), None)
                                
                                # SANEADO: Inserción directa sin la columna supervisor_id
                                lote_insert_rows.append({
                                    "producto_id": pid_ex,
                                    "hito": hito_nombre,
                                    "fecha": fecha_guardado,
                                    "observaciones": obs_guardado
                                })
                                
                    if lote_delete_ids:
                        # Limpiar historial previo del lote de productos cargados
                        supabase.table("seguimiento").delete().in_("producto_id", lote_delete_ids).execute()
                        
                        # Guardar la nueva matriz consolidada
                        if lote_insert_rows:
                            supabase.table("seguimiento").insert(lote_insert_rows).execute()
                            
                        st.success("🎉 ¡Sincronización externa procesada con éxito!"); st.cache_data.clear(); st.rerun()
                except Exception as e:
                    st.error(f"Error crítico al procesar el archivo Excel: {e}")
    # =========================================================================

    # 3. FILTROS VISUALES (SE MANTIENE DISEÑO ORIGINAL NATIIVO)
    st.divider()
    c_f1, c_f2 = st.columns([4, 4])
    f_ubic = c_f1.text_input("🔍 Filtrar por Ambiente / Ubicación:", key="txt_f_u")
    f_tipo = c_f2.text_input("🪵 Filtrar por Tipo de Mueble:", key="txt_f_t")

    df_filtrado = productos.copy()
    if f_ubic: df_filtrado = df_filtrado[df_filtrado['ubicacion'].astype(str).str.contains(f_ubic, case=False)]
    if f_tipo: df_filtrado = df_filtrado[df_filtrado['tipo'].astype(str).str.contains(f_tipo, case=False)]

    # 4. CONSTRUCCIÓN DE LA GRILLA INTERACTIVA UNITARIA
    for _, prod in df_filtrado.iterrows():
        id_prod = prod['id']
        df_seg = obtener_seguimiento(id_prod)
        hitos_logrados = df_seg['hito'].tolist() if not df_seg.empty else []
        
        # Recuperar la primera observación válida que tenga guardada la pieza
        obs_actual = "-"
        if not df_seg.empty and 'observaciones' in df_seg.columns:
            df_obs_validas = df_seg.dropna(subset=['observaciones'])
            df_obs_validas = df_obs_validas[df_obs_validas['observaciones'].str.strip() != ""]
            if not df_obs_validas.empty:
                obs_actual = df_obs_validas.iloc[0]['observaciones']

        pct_avance = sum([pesos.get(h, 0) for h in hitos_logrados])
        
        # Configurar color semafórico nativo
        if pct_avance == 100: color_card = "🟢"
        elif pct_avance > 0: color_card = "🟡"
        else: color_card = "⚪"

        with st.container(border=True):
            col_info, col_check = st.columns([5, 5])
            
            with col_info:
                st.markdown(f"### {color_card} Mueble ID: {prod['codigo_etiqueta']}")
                st.markdown(f"**Ubicación:** {prod['ubicacion']} | **Tipo:** {prod['tipo']}")
                st.markdown(f"**Metraje:** {prod['ml']} ml | **Cantidad:** {prod['ctd']} Unid")
                st.markdown(f"**Progreso Unitario:** `{pct_avance}%` | **Obs. Actual:** *{obs_actual}*")
            
            with col_check:
                # Inicializar el multiselect con lo que ya está guardado en Supabase
                seleccionados = st.multiselect(
                    "Hitos completados en obra:",
                    options=list(pesos.keys()),
                    default=hitos_logrados,
                    key=f"hitos_{id_prod}"
                )
                
                obs_input = st.text_input(
                    "Agregar observación de campo:", 
                    value="" if obs_actual == "-" else obs_actual, 
                    key=f"obs_{id_prod}",
                    placeholder="Escriba fallas, retrasos o detalles de instalación..."
                )
                
                # Botón de guardado manual por pieza
                if seleccionados != hitos_logrados or (obs_input != ("" if obs_actual == "-" else obs_actual)):
                    if st.button("💾 Actualizar Mueble", key=f"btn_{id_prod}", type="primary", use_container_width=True):
                        try:
                            # 1. Purgar hitos anteriores del producto
                            supabase.table("seguimiento").delete().eq("producto_id", id_prod).execute()
                            
                            # 2. Re-insertar la nueva selección (SANEADO: Sin enviar supervisor_id)
                            if seleccionados:
                                lote_insert = []
                                now_iso = datetime.now().isoformat()
                                
                                for hito_nombre in seleccionados:
                                    # Mantener fecha original si ya existía el hito
                                    f_hist = df_seg[df_seg['hito'] == hito_nombre]['fecha'].values[0] if hito_nombre in hitos_logrados else now_iso
                                    
                                    lote_insert.append({
                                        "producto_id": int(id_prod),
                                        "hito": str(hito_nombre),
                                        "fecha": str(f_hist),
                                        "observaciones": str(obs_input).strip() if obs_input else None
                                    })
                                supabase.table("seguimiento").insert(lote_insert).execute()
                                
                            st.success(f"🎉 Mueble {prod['codigo_etiqueta']} sincronizado."); st.cache_data.clear(); st.rerun()
                        except Exception as e:
                            st.error(f"Falla al guardar hito: {e}")
