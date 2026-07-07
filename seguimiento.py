import streamlit as st
import pandas as pd
from datetime import datetime
import io
from base_datos import conectar, obtener_proyectos, obtener_productos_por_proyecto

def mostrar(supervisor_id=None):
    st.markdown("""
        <style>
        .report-title { font-size: 24px; font-weight: bold; color: #1E3A8A; margin-bottom: 0.5rem; }
        .stDataEditor { font-size: 12px; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<p class="report-title">📋 Seguimiento Horizontal de Obras</p>', unsafe_allow_html=True)
    
    supabase = conectar()
    rol_u = str(st.session_state.get('rol', 'Supervisor')).strip().lower()
    es_jefe = rol_u in ["admin", "gerente", "administrador"]

    # --- A. SELECCIÓN DE PROYECTO ---
    nombre_p_act = st.session_state.get('p_nom_sel_seguimiento', "Ninguno")
    
    with st.expander(f"🎯 Proyecto Activo: {nombre_p_act}", expanded=not st.session_state.get('id_p_sel_seguimiento')):
        c1, c2 = st.columns([2, 1])
        bus_p = c1.text_input("Filtrar proyecto por nombre o código:", key="bus_proy_seguimiento")
        df_p_all = obtener_proyectos(bus_p)
        
        if not es_jefe and not df_p_all.empty:
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
        st.info("💡 Seleccione un proyecto arriba para desplegar el panel de avances."); return

    id_p = st.session_state.id_p_sel_seguimiento
    prods_all = obtener_productos_por_proyecto(id_p)
    
    if prods_all.empty:
        st.info("📂 Este proyecto no registra despieces de melamina aún."); return

    # --- B. CARGA VERTICAL DE SEGUIMIENTO DESDE SUPABASE ---
    ids_productos_lote = prods_all['id'].tolist()
    res_db = supabase.table("seguimiento").select("producto_id, hito, fecha, observaciones").in_("producto_id", ids_productos_lote).execute()
    df_seg_db = pd.DataFrame(res_db.data) if res_db.data else pd.DataFrame(columns=['producto_id', 'hito', 'fecha', 'observaciones'])

    # --- C. CONSTRUCCIÓN DE LA MATRIZ HORIZONTAL SIMPLIFICADA ---
    # Convertimos los hitos verticales en columnas horizontales tal como el reporte muestra del usuario
    dict_instalado = {}
    dict_revision = {}
    dict_entrega = {}
    dict_obs_text = {}

    if not df_seg_db.empty:
        for _, row_s in df_seg_db.iterrows():
            pid_s = row_s['producto_id']
            hito_s = str(row_s['hito']).strip()
            obs_s = str(row_s['observaciones']).strip() if row_s['observaciones'] else ""
            
            if hito_s == "Instalado": dict_instalado[pid_s] = "si"
            elif hito_s == "Revisión y Observaciones": dict_revision[pid_s] = "si"
            elif hito_s == "Entrega": dict_entrega[pid_s] = "si"
            
            if obs_s and obs_s != "nan" and obs_s != "-":
                dict_obs_text[pid_s] = obs_s

    df_grid = pd.DataFrame()
    df_grid['id'] = prods_all['id']
    df_grid['ubicacion'] = prods_all['ubicacion'].fillna("-").astype(str)
    df_grid['tipo'] = prods_all['tipo'].fillna("-").astype(str)
    df_grid['ml'] = prods_all['ml'].fillna(0.0).astype(float)
    df_grid['ctd'] = prods_all['ctd'].fillna(1).astype(int)
    
    # Mapeo horizontal integrado
    df_grid['Instalado'] = df_grid['id'].map(dict_instalado).fillna("")
    df_grid['Revisión y Observaciones'] = df_grid['id'].map(dict_revision).fillna("")
    df_grid['Entrega'] = df_grid['id'].map(dict_entrega).fillna("")
    df_grid['Observaciones'] = df_grid['id'].map(dict_obs_text).fillna("")

    # --- D. EXPANDER DE GESTIÓN OFFLINE CON MATRIZ HORIZONTAL MAESTRA ---
    with st.expander("⚙️ Importar / Exportar Reporte de Seguimiento Simplificado"):
        tab_exp, tab_imp = st.tabs(["📥 Descargar Formato", "📤 Subir Avances Completados"])
        
        with tab_exp:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_grid.to_excel(writer, index=False, sheet_name="Sheet1")
            st.download_button(
                "📥 Descargar Reporte de Seguimiento", 
                data=output.getvalue(), 
                file_name=f"Reporte_Seguimiento_{id_p}.xlsx", 
                use_container_width=True
            )
            
        with tab_imp:
            f_subida = st.file_uploader("Seleccione el archivo excel de seguimiento modificado:", type=["xlsx"], key="excel_uploader_seg_simplificado")
            if f_subida and st.button("🚀 Sincronizar Cambios de Obras"):
                try:
                    df_imp = pd.read_excel(f_subida)
                    df_imp.columns = df_imp.columns.str.strip()
                    
                    if 'id' not in df_imp.columns:
                        st.error("❌ Archivo inválido. Falta la columna matriz de control 'id'.")
                        st.stop()
                        
                    # Diccionario de fechas previas en Supabase para proteger el registro histórico real
                    dict_fechas_historicas = {}
                    if not df_seg_db.empty:
                        for _, r_db in df_seg_db.iterrows():
                            dict_fechas_historicas[(r_db['producto_id'], r_db['hito'])] = r_db['fecha']

                    lote_delete_ids = []
                    lote_insert_rows = []
                    now_str = datetime.now().isoformat()

                    for _, r in df_imp.iterrows():
                        pid_ex = int(r['id'])
                        
                        # Captura flexible tolerante a X, x, SI, si
                        v_ins = str(r.get('Instalado', '')).strip().upper() in ["X", "1", "SI", "TRUE"]
                        v_rev = str(r.get('Revisión y Observaciones', '')).strip().upper() in ["X", "1", "SI", "TRUE"]
                        v_ent = str(r.get('Entrega', '')).strip().upper() in ["X", "1", "SI", "TRUE"]
                        
                        obs_ex = str(r.get('Observaciones', '')).strip()
                        if obs_ex in ["nan", "None", "", "-"]: obs_ex = None
                        
                        lote_delete_ids.append(pid_ex)
                        
                        # Lista de mapeo para procesamiento iterativo limpio
                        mapeo_hitos = [
                            ("Instalado", v_ins),
                            ("Revisión y Observaciones", v_rev),
                            ("Entrega", v_ent)
                        ]
                        
                        for hito_nombre, activo in mapeo_hitos:
                            if activo:
                                # PROTECCIÓN HISTÓRICA: Si ya existía fecha, se mantiene; si es nuevo, toma 'now'
                                f_orig = dict_fechas_historicas.get((pid_ex, hito_nombre), now_str)
                                lote_insert_rows.append({
                                    "producto_id": pid_ex,
                                    "hito": hito_nombre,
                                    "fecha": f_orig,
                                    "observaciones": obs_ex
                                })

                    if lote_delete_ids:
                        # 1. Limpieza del lote afectado para reescribir de forma controlada
                        supabase.table("seguimiento").delete().in_("producto_id", lote_delete_ids).execute()
                        
                        # 2. Inserción masiva de hitos en formato vertical limpio (Sin supervisor_id)
                        if lote_insert_rows:
                            supabase.table("seguimiento").insert(lote_insert_rows).execute()
                        
                        st.success("🎉 ¡Avances sincronizados correctamente! Historial cronológico blindado."); st.cache_data.clear(); st.rerun()
                except Exception as e:
                    st.error(f"Falla al procesar el archivo excel: {e}")

    # --- E. RENDIMIENTO DE LA INTERFAZ VISUAL (DATAFRAME EDITABLE DIRECTO) ---
    st.divider()
    st.markdown("#### 📱 Cuadrícula de Avances en Vivo")
    
    cambios_grid = st.data_editor(
        df_grid,
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "ubicacion": st.column_config.TextColumn("Ubicación", disabled=True),
            "tipo": st.column_config.TextColumn("Tipo Mueble", disabled=True),
            "ml": st.column_config.NumberColumn("ml", format="%.2f", disabled=True),
            "ctd": st.column_config.NumberColumn("ctd", format="%d", disabled=True),
            "Instalado": st.column_config.SelectboxColumn("🪚 Instalado", options=["", "si"]),
            "Revisión y Observaciones": st.column_config.SelectboxColumn("🔍 Revisión", options=["", "si"]),
            "Entrega": st.column_config.SelectboxColumn("✅ Entrega", options=["", "si"]),
            "Observaciones": st.column_config.TextColumn("Notas de Obra", disabled=False)
        },
        hide_index=True,
        use_container_width=True,
        key=f"grid_seguimiento_horizontal_{id_p}"
    )

    # --- F. MOTOR DE GUARDADO MANUAL DIRECTO DESDE CELULAR ---
    if st.button("💾 Guardar Cambios Realizados", type="primary", use_container_width=True):
        if not cambios_grid.equals(df_grid):
            try:
                dict_fechas_historicas = {}
                if not df_seg_db.empty:
                    for _, r_db in df_seg_db.iterrows():
                        dict_fechas_historicas[(r_db['producto_id'], r_db['hito'])] = r_db['fecha']

                lote_delete_manual = []
                lote_insert_manual = []
                now_iso = datetime.now().isoformat()

                for index, row in cambios_grid.iterrows():
                    pid_m = int(row['id'])
                    
                    c_ins = str(row['Instalado']).strip().lower() == "si"
                    c_rev = str(row['Revisión y Observaciones']).strip().lower() == "si"
                    c_ent = str(row['Entrega']).strip().lower() == "si"
                    
                    obs_m = str(row['Observaciones']).strip()
                    if obs_m in ["nan", "None", "", "-"]: obs_m = None
                    
                    lote_delete_manual.append(pid_m)
                    
                    mapeo_manual = [
                        ("Instalado", c_ins),
                        ("Revisión y Observaciones", c_rev),
                        ("Entrega", c_ent)
                    ]
                    
                    for h_nom, activo_m in mapeo_manual:
                        if activo_m:
                            f_orig_m = dict_fechas_historicas.get((pid_m, h_nom), now_iso)
                            lote_insert_manual.append({
                                "producto_id": pid_m,
                                "hito": h_nom,
                                "fecha": f_orig_m,
                                "observaciones": obs_m
                            })

                if lote_delete_manual:
                    supabase.table("seguimiento").delete().in_("producto_id", lote_delete_manual).execute()
                    if lote_insert_manual:
                        supabase.table("seguimiento").insert(lote_insert_manual).execute()
                    st.success("🎉 Cambios guardados con éxito."); st.cache_data.clear(); st.rerun()
            except Exception as e:
                st.error(f"Error al guardar la información: {e}")
