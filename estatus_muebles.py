import streamlit as st
import pandas as pd
from datetime import datetime
import io
from base_datos import conectar, obtener_proyectos, obtener_productos_por_proyecto

def mostrar(supervisor_id=None):
    # CSS inyectado y optimizado para pantallas móviles (fuentes más compactas y reducción de paddings)
    st.markdown("""
        <style>
        .report-title { font-size: 22px; font-weight: bold; color: #1E3A8A; margin-bottom: 0.2rem; }
        [data-testid="stMetricValue"] { color: #1E3A8A !important; font-weight: bold !important; font-size: 20px !important; }
        div[data-testid="stMetric"] { padding: 5px; }
        /* Forzar compactación en contenedores de tablas Streamlit para móviles */
        .stDataEditor { font-size: 12px; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<p class="report-title">🪚 Matriz de Estatus Móvil</p>', unsafe_allow_html=True)
    
    supabase = conectar()
    rol_u = str(st.session_state.get('rol', 'Supervisor')).strip().lower()
    es_jefe = rol_u in ["admin", "gerente", "administrador"]

    # --- A. SELECCIÓN DE PROYECTO ---
    nombre_p_act = st.session_state.get('p_nom_sel_estatus', "Ninguno")
    
    with st.expander(f"🎯 Proyecto: {nombre_p_act}", expanded=not st.session_state.get('id_p_sel_estatus')):
        c1, c2 = st.columns([1, 1])
        bus_p = c1.text_input("Filtrar:", key="bus_estatus_muebles")
        df_p_all = obtener_proyectos(bus_p)
        
        if not es_jefe and not df_p_all.empty:
            df_p_all = df_p_all[df_p_all['supervisor_id'] == supervisor_id]

        if not df_p_all.empty:
            opciones = {f"[{r['codigo']}] {r['proyecto_text']}": r['id'] for _, r in df_p_all.iterrows()}
            lista_opc = ["-- Seleccionar --"] + list(opciones.keys())
            p_actual = st.session_state.get('p_nom_sel_estatus', "-- Seleccionar --")
            idx_s = lista_opc.index(p_actual) if p_actual in lista_opc else 0
            sel_n = c2.selectbox("Proyecto:", lista_opc, index=idx_s, key="sel_proy_estatus_m_master")
            
            if sel_n != p_actual:
                st.session_state.id_p_sel_estatus = opciones[sel_n] if sel_n != "-- Seleccionar --" else None
                st.session_state.p_nom_sel_estatus = sel_n
                st.rerun()
        else:
            st.warning("⚠️ Sin proyectos asignados."); return

    if not st.session_state.get('id_p_sel_estatus'):
        st.info("💡 Seleccione un proyecto arriba."); return

    id_p = st.session_state.id_p_sel_estatus
    prods_all = obtener_productos_por_proyecto(id_p)
    
    if prods_all.empty:
        st.info("📂 Proyecto sin despieces aún."); return

    # --- B. CARGA DE ESTATUS DESDE SUPABASE ---
    res_db = supabase.table("estatus_muebles").select("*").in_("producto_id", prods_all['id'].tolist()).execute()
    df_estatus_db = pd.DataFrame(res_db.data) if res_db.data else pd.DataFrame(columns=['producto_id', 'en_proceso', 'culminado', 'entregado', 'observaciones'])

   # --- C. CÁLCULO DE LAS 5 MÉTRICAS EN FILA (INCLUYENDO ML) ---
    # Extraemos también 'ml' para los cálculos de metraje
    df_metricas = prods_all[['id', 'ml']].copy()
    df_metricas = df_metricas.merge(df_estatus_db, left_on='id', right_on='producto_id', how='left')
    df_metricas['en_proceso'] = df_metricas['en_proceso'].fillna(False).astype(bool)
    df_metricas['culminado'] = df_metricas['culminado'].fillna(False).astype(bool)
    df_metricas['entregado'] = df_metricas['entregado'].fillna(False).astype(bool)
    df_metricas['ml'] = pd.to_numeric(df_metricas['ml'], errors='coerce').fillna(0.0)

    # Conteo por unidades (muebles)
    total_muebles = len(df_metricas)
    cant_pendiente = len(df_metricas[(df_metricas['en_proceso'] == False) & (df_metricas['culminado'] == False) & (df_metricas['entregado'] == False)])
    cant_proceso = len(df_metricas[df_metricas['en_proceso'] == True])
    cant_culminado = len(df_metricas[df_metricas['culminado'] == True])
    cant_entregado = len(df_metricas[df_metricas['entregado'] == True])

    # Nuevo Cálculo: Porcentaje de Avance en Metros Lineales (ML)
    ml_totales_proyecto = df_metricas['ml'].sum()
    # Consideramos avanzado en ML cualquier mueble que esté Culminado o Entregado
    df_avanzados_ml = df_metricas[(df_metricas['culminado'] == True) | (df_metricas['entregado'] == True)]
    ml_logrados = df_avanzados_ml['ml'].sum()
    
    pct_avance_ml = (ml_logrados / ml_totales_proyecto * 100) if ml_totales_proyecto > 0 else 0.0

    # Desplegamos 5 columnas en la interfaz superior
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("⏳ Pend.", f"{((cant_pendiente)/total_muebles)*100:.0f}%")
    m2.metric("🪚 Proc.", f"{((cant_proceso)/total_muebles)*100:.0f}%")
    m3.metric("📦 Culm.", f"{((cant_culminado)/total_muebles)*100:.0f}%")
    m4.metric("✅ Entr.", f"{((cant_entregado)/total_muebles)*100:.0f}%")
    m5.metric("📏 Avance ML", f"{pct_avance_ml:.1f}%")
    
    # --- D. GESTIÓN OFFLINE CON EXCEL ---
    with st.expander("⚙️ Importar / Exportar Excel"):
        tab_exp, tab_imp = st.tabs(["📥 Descargar", "📤 Subir"])
        
        with tab_exp:
            # Replicar exactamente las columnas del formato horizontal simplificado solicitado
            df_excel = pd.DataFrame()
            df_excel['id'] = prods_all['id']
            df_excel['ubicacion'] = prods_all['ubicacion'].fillna("-").astype(str)
            df_excel['tipo'] = prods_all['tipo'].fillna("-").astype(str)
            df_excel['ml'] = prods_all['ml'].fillna(0.0).astype(float)
            df_excel['ctd'] = prods_all['ctd'].fillna(1).astype(int)
            
            # Inicializar celdas de hitos horizontales en blanco
            df_excel['Instalado'] = ""
            df_excel['Revisión y Observaciones'] = ""
            df_excel['Entrega'] = ""
            df_excel['Observaciones'] = ""
            
            # Rellenar con "si" si la base de datos registra la etapa completada
            for idx, row_ex in df_excel.iterrows():
                pid_ex = row_ex['id']
                match_db = df_estatus_db[df_estatus_db['producto_id'] == pid_ex]
                
                if not match_db.empty:
                    r_db = match_db.iloc[0]
                    if bool(r_db.get('en_proceso', False)): df_excel.loc[idx, 'Instalado'] = "si"
                    if bool(r_db.get('culminado', False)): df_excel.loc[idx, 'Revisión y Observaciones'] = "si"
                    if bool(r_db.get('entregado', False)): df_excel.loc[idx, 'Entrega'] = "si"
                    
                    obs_db = r_db.get('observaciones', None)
                    if obs_db and str(obs_db).strip() not in ["", "nan", "None", "-"]:
                        df_excel.loc[idx, 'Observaciones'] = str(obs_db).strip()
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_excel.to_excel(writer, index=False, sheet_name="Sheet1")
            st.download_button("📥 Descargar Excel", data=output.getvalue(), file_name=f"Estatus_Offline_{id_p}.xlsx", use_container_width=True)
            
        with tab_imp:
            f_subida = st.file_uploader("Seleccione .xlsx", type=["xlsx"], key="excel_uploader_estatus")
            if f_subida and st.button("🚀 Sincronizar Masivo"):
                try:
                    df_imp = pd.read_excel(f_subida)
                    df_imp.columns = df_imp.columns.str.strip()
                    
                    # Soporte dual si la columna viene mapeada como 'id' o 'ID Pieza'
                    col_id_maestra = 'id' if 'id' in df_imp.columns else ('ID Pieza' if 'ID Pieza' in df_imp.columns else None)
                    if not col_id_maestra:
                        st.error("❌ Estructura de archivo incorrecta. Falta la columna de identificación maestra 'id'.")
                        st.stop()
                        
                    df_imp = df_imp.dropna(subset=[col_id_maestra])
                    
                    # MAPEO DE PREVALENCIA: Obtener el estado actual en Supabase para no borrar ni reescribir hitos del pasado
                    dict_db_actual = {r['producto_id']: r for r in df_estatus_db.to_dict(orient='records')} if not df_estatus_db.empty else {}
                    
                    lote_excel_upsert = []
                    lote_fechas_upsert = []
                    
                    res_fechas = supabase.table("fechas_hitos_muebles").select("*").in_("producto_id", prods_all['id'].tolist()).execute()
                    dict_fechas = {f['producto_id']: f for f in res_fechas.data} if res_fechas.data else {}
                    
                    now_str = datetime.now().isoformat()
                    
                    for _, r in df_imp.iterrows():
                        try:
                            pid_ex = int(float(str(r[col_id_maestra]).strip()))
                        except:
                            continue
                        
                        # Interpretación flexible y tolerante del archivo muestra (Acepta X, x, SI, si)
                        excel_proc = str(r.get('Instalado', '')).strip().upper() in ["X", "1", "SI", "TRUE"]
                        excel_culm = str(r.get('Revisión y Observaciones', '')).strip().upper() in ["X", "1", "SI", "TRUE"]
                        excel_entr = str(r.get('Entrega', '')).strip().upper() in ["X", "1", "SI", "TRUE"]
                        
                        obs_ex = str(r.get('Observaciones', '')).strip()
                        if obs_ex in ["nan", "None", "", "-"]: obs_ex = None
                        
                        # Recuperar estados actuales de Supabase
                        reg_db = dict_db_actual.get(pid_ex, {})
                        db_proc = bool(reg_db.get('en_proceso', False))
                        db_culm = bool(reg_db.get('culminado', False))
                        db_entr = bool(reg_db.get('entregado', False))
                        db_obs = reg_db.get('observaciones', None)
                        
                        # LÓGICA DE PREVALENCIA: Solo se cambia a True si en Supabase estaba en False y en el Excel viene marcado.
                        # NUNCA se revierte un True anterior a False mediante la importación.
                        nuevo_proc = db_proc or excel_proc
                        nuevo_culm = db_culm or excel_culm
                        nuevo_entr = db_entr or excel_entr
                        nuevo_obs = db_obs if db_obs else obs_ex
                        
                        # Recuperar historial de fechas
                        f_existente = dict_fechas.get(pid_ex, {})
                        f_proc = f_existente.get('fecha_proceso')
                        f_culm = f_existente.get('fecha_culminado')
                        f_entr = f_existente.get('fecha_entregado')
                        
                        # Cascada cronológica de fechas solo para los hitos que acaban de activarse
                        if nuevo_entr and not db_entr:
                            if not nuevo_proc: nuevo_proc = True; f_proc = now_str if not f_proc else f_proc
                            if not nuevo_culm: nuevo_culm = True; f_culm = now_str if not f_culm else f_culm
                            if not f_entr: f_entr = now_str
                        elif nuevo_culm and not db_culm:
                            if not nuevo_proc: nuevo_proc = True; f_proc = now_str if not f_proc else f_proc
                            if not f_culm: f_culm = now_str
                        elif nuevo_proc and not db_proc:
                            if not f_proc: f_proc = now_str

                        lote_excel_upsert.append({
                            "producto_id": pid_ex, 
                            "en_proceso": nuevo_proc, 
                            "culminado": nuevo_culm, 
                            "entregado": nuevo_entr,
                            "observaciones": nuevo_obs, 
                            "supervisor_id": supervisor_id, 
                            "updated_at": now_str
                        })
                        
                        if nuevo_proc or nuevo_culm or nuevo_entr:
                            lote_fechas_upsert.append({
                                "producto_id": pid_ex, 
                                "fecha_proceso": f_proc, 
                                "fecha_culminado": f_culm, 
                                "fecha_entregado": f_entr
                            })
                    
                    if lote_excel_upsert:
                        supabase.table("estatus_muebles").upsert(lote_excel_upsert, on_conflict="producto_id").execute()
                        if lote_fechas_upsert:
                            supabase.table("fechas_hitos_muebles").upsert(lote_fechas_upsert, on_conflict="producto_id").execute()
                        
                        # Recalcular el avance del proyecto basado en la matriz consolidada completa
                        res_total = supabase.table("estatus_muebles").select("en_proceso, culminado, entregado").in_("producto_id", prods_all['id'].tolist()).execute()
                        if res_total.data:
                            suma_avances_totales = sum([(30.0 if x['en_proceso'] else 0.0) + (60.0 if x['culminado'] else 0.0) + (10.0 if x['entregado'] else 0.0) for x in res_total.data])
                            promedio_avance_global = round(suma_avances_totales / len(prods_all), 2)
                            supabase.table("proyectos").update({"avance": float(promedio_avance_global)}).eq("id", id_p).execute()
                            
                        st.success("🎉 Sincronización incremental completada. Historial blindado."); st.cache_data.clear(); st.rerun()
                except Exception as e:
                    st.error(f"Error al procesar la planilla: {e}")
                    
    # --- E. FILTROS COMPACTOS ---
    c_f1, c_f2 = st.columns(2)
    f_ubic = c_f1.text_input("🔍 Ubicación:", key="txt_f_u")
    f_tipo = c_f2.text_input("🪵 Mueble:", key="txt_f_t")

    df_filtrado = prods_all.copy()
    if f_ubic: df_filtrado = df_filtrado[df_filtrado['ubicacion'].astype(str).str.contains(f_ubic, case=False)]
    if f_tipo: df_filtrado = df_filtrado[df_filtrado['tipo'].astype(str).str.contains(f_tipo, case=False)]

    # --- F. CONSTRUCCIÓN DE LA MATRIZ REDUCIDA ---
    df_grid = pd.DataFrame()
    df_grid['id'] = df_filtrado['id']
    df_grid['Ubicacion'] = df_filtrado['ubicacion'].fillna("-").astype(str)
    df_grid['Mueble'] = df_filtrado['tipo'].fillna("-").astype(str)
    df_grid['ml'] = df_filtrado['ml'].fillna(0.0).astype(float)
    
    df_grid = df_grid.merge(df_estatus_db[['producto_id', 'en_proceso', 'culminado', 'entregado', 'observaciones']], left_on='id', right_on='producto_id', how='left')
    df_grid['en_proceso'] = df_grid['en_proceso'].fillna(False).astype(bool)
    df_grid['culminado'] = df_grid['culminado'].fillna(False).astype(bool)
    df_grid['entregado'] = df_grid['entregado'].fillna(False).astype(bool)
    df_grid['Observaciones'] = df_grid['observaciones'].fillna("-").astype(str)

    # REQUERIMIENTO: Solo se mantiene el ícono puro eliminando textos redundantes de porcentajes
    def asignar_semaforo(row):
        if row['entregado']: return "✳️"
        elif row['culminado']: return "🟢"
        elif row['en_proceso']: return "🟡"
        return "⚪"

    df_grid['🚦'] = df_grid.apply(asignar_semaforo, axis=1)

    # --- G. RENDERIZADO DEL DATAFRAME CONFIGURADO PARA ANCHOS MÍNIMOS ---
    cambios_grid = st.data_editor(
        df_grid[['id', '🚦', 'Ubicacion', 'Mueble', 'ml', 'en_proceso', 'culminado', 'entregado', 'Observaciones']],
        column_config={
            "id": None, 
            "🚦": st.column_config.TextColumn("🚦", disabled=True),
            "Ubicacion": st.column_config.TextColumn("Ubicación", disabled=True),
            "Mueble": st.column_config.TextColumn("Tipo Mueble", disabled=True),
            "ml": st.column_config.NumberColumn("ml", format="%.2f", disabled=True),
            "en_proceso": st.column_config.CheckboxColumn("🪚"),
            "culminado": st.column_config.CheckboxColumn("📦"),
            "entregado": st.column_config.CheckboxColumn("✅"),
            "Observaciones": st.column_config.TextColumn("Obs.", disabled=False)
        },
        hide_index=True,
        use_container_width=True,
        key=f"grid_unrestricted_muebles_{id_p}"
    )

    # --- H. MOTOR DE GUARDADO CON LOGICA DE CASCADA CRONOLÓGICA ---
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 Guardar Cambios", type="primary", use_container_width=True):
        if not cambios_grid.equals(df_grid[['id', '🚦', 'Ubicacion', 'Mueble', 'ml', 'en_proceso', 'culminado', 'entregado', 'Observaciones']]):
            lote_upsert = []
            lote_fechas = []
            suma_avances_manual = 0.0
            
            res_f_check = supabase.table("fechas_hitos_muebles").select("*").in_("producto_id", prods_all['id'].tolist()).execute()
            dict_fechas_check = {f['producto_id']: f for f in res_f_check.data} if res_f_check.data else {}

            for index, row in cambios_grid.iterrows():
                pid = int(row['id'])
                bool_proceso = bool(row['en_proceso'])
                bool_culminado = bool(row['culminado'])
                bool_entregado = bool(row['entregado'])
                obs_txt = str(row['Observaciones']).strip()
                
                match_orig = df_grid[df_grid['id'] == pid].iloc[0]
                orig_proceso = bool(match_orig['en_proceso'])
                orig_culminado = bool(match_orig['culminado'])
                orig_entregado = bool(match_orig['entregado'])
                
                now_iso = datetime.now().isoformat()
                
                fechas_previas = dict_fechas_check.get(pid, {})
                ts_proc = fechas_previas.get('fecha_proceso')
                ts_culm = fechas_previas.get('fecha_culminado')
                ts_entr = fechas_previas.get('fecha_entregado')

                if bool_entregado and not orig_entregado:
                    if not bool_proceso: bool_proceso = True; ts_proc = now_iso if not ts_proc else ts_proc
                    if not bool_culminado: bool_culminado = True; ts_culm = now_iso if not ts_culm else ts_culm
                    if not ts_entr: ts_entr = now_iso
                elif bool_culminado and not orig_culminado:
                    if not bool_proceso: bool_proceso = True; ts_proc = now_iso if not ts_proc else ts_proc
                    if not ts_culm: ts_culm = now_iso
                elif bool_proceso and not orig_proceso:
                    if not ts_proc: ts_proc = now_iso

                avance_m = (30.0 if bool_proceso else 0.0) + (60.0 if bool_culminado else 0.0) + (10.0 if bool_entregado else 0.0)
                suma_avances_manual += avance_m
                
                if (bool_proceso != orig_proceso or bool_culminado != orig_culminado or 
                    bool_entregado != orig_entregado or obs_txt != str(match_orig['Observaciones'])):
                    
                    lote_upsert.append({
                        "producto_id": pid, "en_proceso": bool_proceso, "culminado": bool_culminado, "entregado": bool_entregado,
                        "observaciones": obs_txt if obs_txt != "-" else None, "supervisor_id": supervisor_id, "updated_at": now_iso
                    })
                    if bool_proceso or bool_culminado or bool_entregado:
                        lote_fechas.append({
                            "producto_id": pid, "fecha_proceso": ts_proc, "fecha_culminado": ts_culm, "fecha_entregado": ts_entr
                        })
            
            if lote_upsert:
                try:
                    supabase.table("estatus_muebles").upsert(lote_upsert, on_conflict="producto_id").execute()
                    if lote_fechas:
                        supabase.table("fechas_hitos_muebles").upsert(lote_fechas, on_conflict="producto_id").execute()
                    
                    promedio_global = round(suma_avances_manual / total_muebles, 2)
                    supabase.table("proyectos").update({"avance": float(promedio_global)}).eq("id", id_p).execute()
                    st.success("🎉 Datos sincronizados con éxito."); st.cache_data.clear(); st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")
        else:
            st.info("ℹ️ No se detectaron modificaciones.")
