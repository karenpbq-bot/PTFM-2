import streamlit as st
import pandas as pd
from datetime import datetime
import io
from base_datos import conectar, obtener_proyectos, obtener_productos_por_proyecto, obtener_seguimiento, obtener_pesos_seguimiento

# 1. CONFIGURACIÓN VISUAL (ICONOS SOLICITADOS)
MAPEO_HITOS = {
    "Diseñado": "🗺️", "Fabricado": "🪚", "Material en Obra": "🚛",
    "Material en Ubicación": "📍", "Instalación de Estructura": "📦", 
    "Instalación de Puertas o Frentes": "🗄️", "Revisión y Observaciones": "🔍", "Entrega": "👍" 
}
HITOS_LIST = list(MAPEO_HITOS.keys())

def mostrar(supervisor_id=None):
    # --- A. ESTADOS DE SESIÓN (BUFFER DE ALTO RENDIMIENTO) ---
    if 'cambios_pendientes' not in st.session_state:
        st.session_state.cambios_pendientes = [] # Checks ROJOS en memoria
    if 'ref_matriz' not in st.session_state:
        st.session_state.ref_matriz = 0

    supabase = conectar()
    rol_u = str(st.session_state.get('rol', 'Supervisor')).strip().lower()
    es_jefe = rol_u in ["admin", "gerente", "administrador"]

    # --- B. SELECCIÓN DE PROYECTO (CON FILTRO DE SEGURIDAD) ---
    st.markdown("### 📋 Módulo de Seguimiento")
    
    with st.expander("🔍 Selección de Proyecto", expanded=not st.session_state.get('id_p_sel')):
        c1, c2 = st.columns([2, 1])
        bus_p = c1.text_input("Filtrar proyecto:", key="bus_seg_VMASTER_FINAL")
        df_p_all = obtener_proyectos(bus_p)
        
        # Seguridad: El Supervisor solo ve sus proyectos
        if not es_jefe and not df_p_all.empty:
            df_p_all = df_p_all[df_p_all['supervisor_id'] == supervisor_id]

        if not df_p_all.empty:
            opciones = {f"[{r['codigo']}] {r['proyecto_text']}": r['id'] for _, r in df_p_all.iterrows()}
            lista_opc = ["-- Seleccionar --"] + list(opciones.keys())
            p_actual = st.session_state.get('p_nom_sel', "-- Seleccionar --")
            idx_s = lista_opc.index(p_actual) if p_actual in lista_opc else 0
            sel_n = c2.selectbox("Proyecto:", lista_opc, index=idx_s)
            
            if sel_n != p_actual:
                st.session_state.id_p_sel = opciones[sel_n] if sel_n != "-- Seleccionar --" else None
                st.session_state.p_nom_sel = sel_n
                st.session_state.cambios_pendientes = []
                st.rerun()
        else:
            st.warning("No se encontraron proyectos asignados."); return

    if not st.session_state.get('id_p_sel'):
        st.info("💡 Seleccione un proyecto."); return

    # --- C. CARGA DE DATOS ---
    id_p = st.session_state.id_p_sel
    prods_all = obtener_productos_por_proyecto(id_p)
    res_db = supabase.table("seguimiento").select("*").in_("producto_id", prods_all['id'].tolist()).execute()
    segs = pd.DataFrame(res_db.data) if res_db.data else pd.DataFrame(columns=['producto_id','hito','fecha','observaciones'])
    
    # --- D. SECCIÓN DE CONFIGURACIÓN AVANZADA (RESTAURADA) ---
    pesos = obtener_pesos_seguimiento()

    with st.expander("⚙️ Herramientas y Gestión Masiva"):
        t1, t2, t3, t4 = st.tabs(["⚖️ Ponderación", "🔍 Filtros", "📥 Importar", "📤 Exportación"])
        with t1:
            cols_w = st.columns(4)
            for i, h in enumerate(HITOS_LIST):
                pesos[h] = cols_w[i % 4].number_input(f"{h} (%)", value=float(pesos.get(h, 12.5)), key=f"pw_{h}")
        with t2:
            f1, f2 = st.columns(2)
            bus_u = f1.text_input("Ubicación (ej: 701)")
            bus_t = f2.text_input("Tipo")
        with t3:
            st.write("**Importación desde Excel**")
            f_av = st.file_uploader("Subir .xlsx", type=["xlsx"], key="up_excel_seg")
            if f_av and st.button("🚀 Iniciar Importación"):
                # Lógica de importación ya validada en base_datos
                pass
        with t4:
            df_exp = prods_all.copy()
            for h in HITOS_LIST: 
                df_exp[h] = df_exp['id'].apply(lambda x: segs[(segs['producto_id']==x) & (segs['hito']==h)]['fecha'].iloc[0] if not segs[(segs['producto_id']==x) & (segs['hito']==h)].empty else "")
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_exp.to_excel(writer, index=False)
            st.download_button("📥 Descargar Reporte", data=output.getvalue(), file_name=f"Avance_{id_p}.xlsx", use_container_width=True)

    # --- E. FILTRADO DE VISTA ---
    df_f = prods_all.copy()
    if 'bus_u' in locals() and bus_u: df_f = df_f[df_f['ubicacion'].astype(str).str.contains(bus_u, case=False)]
    if 'bus_t' in locals() and bus_t: df_f = df_f[df_f['tipo'].astype(str).str.contains(bus_t, case=False)]

    # --- F. CABECERA DE MATRIZ Y BOTONES (SIN RECARGAS AL MARCAR) ---
    st.divider()
    col_t, col_b1, col_b2, col_b3, col_b4 = st.columns([1.5, 1, 1, 1, 1])
    col_t.markdown("#### Matriz de Seguimiento")
    
    btn_marcar = col_b1.button("✅ Guardar Marcación", use_container_width=True)
    btn_db = col_b2.button("🚀 Guardar Avances", type="primary", use_container_width=True)
    btn_clean = col_b3.button("🧹 Limpiar Marcación", use_container_width=True)
    btn_delete = col_b4.button("🗑️ Borrar Avances", use_container_width=True) if es_jefe else None

    # --- G. PREPARACIÓN DE TABLA COMPACTA (LÓGICA ROJO/GRIS) ---
    # Orden solicitado: codigo_etiqueta primero
    df_editor = df_f[['id', 'codigo_etiqueta', 'ubicacion', 'tipo', 'ml', 'ctd']].copy()
    
    for h_nom in HITOS_LIST:
        simb = MAPEO_HITOS[h_nom]
        en_db = df_editor['id'].apply(lambda x: True if not segs[(segs['producto_id'] == x) & (segs['hito'] == h_nom)].empty else False)
        en_mem = df_editor['id'].apply(lambda x: True if any(c['pid'] == x and c['hito'] == h_nom for c in st.session_state.cambios_pendientes) else False)
        df_editor[simb] = en_db | en_mem

    df_editor['Observaciones'] = df_editor['id'].apply(
        lambda x: segs[(segs['producto_id'] == x) & (segs['hito'] == HITOS_LIST[0])]['observaciones'].iloc[0] if not segs[(segs['producto_id'] == x) & (segs['hito'] == HITOS_LIST[0])].empty else ""
    )

    # --- H. DATA EDITOR (AISLADO PARA 160+ CLICS SIN LAG) ---
    cambios_df = st.data_editor(
        df_editor,
        column_config={
            "id": None,
            "codigo_etiqueta": st.column_config.TextColumn("Código ID", disabled=True),
            "ubicacion": st.column_config.TextColumn("Ubicación", disabled=True),
            "tipo": st.column_config.TextColumn("Tipo", disabled=True),
            "ml": st.column_config.NumberColumn("ML", disabled=True),
            "ctd": st.column_config.NumberColumn("Cant.", disabled=True),
            "Observaciones": st.column_config.TextColumn("Observaciones", width="large"),
            **{MAPEO_HITOS[h]: st.column_config.CheckboxColumn(MAPEO_HITOS[h]) for h in HITOS_LIST}
        },
        hide_index=True,
        use_container_width=True,
        key=f"matriz_VMASTER_{st.session_state.ref_matriz}" # Key estática controlada
    )

    # --- I. PROCESAMIENTO DE BOTONES ---

    # 1. GUARDAR MARCACIÓN (LOCAL)
    if btn_marcar:
        nuevos_pendientes = []
        for idx, row in cambios_df.iterrows():
            pid = int(row['id'])
            for h_nom in HITOS_LIST:
                simb = MAPEO_HITOS[h_nom]
                en_db = not segs[(segs['producto_id'] == pid) & (segs['hito'] == h_nom)].empty
                if bool(row[simb]) and not en_db:
                    nuevos_pendientes.append({"pid": pid, "hito": h_nom})
        st.session_state.cambios_pendientes = nuevos_pendientes
        st.rerun()

    # 2. GUARDAR AVANCES (SUPABASE - UPSERT INTELIGENTE)
    if btn_db:
        if not st.session_state.cambios_pendientes:
            st.warning("No hay marcaciones nuevas para guardar."); st.stop()
        
        lote_upsert = []
        fecha_str = datetime.now().strftime("%d/%m/%Y")
        for p in st.session_state.cambios_pendientes:
            match_db = segs[(segs['producto_id'] == p['pid']) & (segs['hito'] == p['hito'])]
            obs_final = str(match_db['observaciones'].iloc[0]) if not match_db.empty else ""
            if p['hito'] == HITOS_LIST[0]: # Solo el hito 0 guarda la nota del editor
                obs_final = str(cambios_df[cambios_df['id'] == p['pid']]['Observaciones'].iloc[0])

            lote_upsert.append({
                "producto_id": p['pid'], "hito": p['hito'], "fecha": fecha_str, 
                "observaciones": obs_final, "supervisor_id": supervisor_id
            })
        
        if lote_upsert:
            try:
                supabase.table("seguimiento").upsert(lote_upsert, on_conflict="producto_id, hito").execute()
                # Motor de sincronización estructural
                from base_datos import sincronizar_avances_estructural
                p_cod = st.session_state.p_nom_sel.split(']')[0][1:]
                sincronizar_avances_estructural(p_cod)
                
                st.session_state.cambios_pendientes = []
                st.cache_data.clear(); st.session_state.ref_matriz += 1
                st.success("✅ Avances sincronizados.")
                st.rerun()
            except Exception as e: st.error(f"Error: {e}")

    # 3. LIMPIAR MARCACIÓN (Solo los rojos)
    if btn_clean:
        st.session_state.cambios_pendientes = []
        st.session_state.ref_matriz += 1; st.rerun()

    # 4. BORRAR AVANCES (SOLO ADMIN)
    if btn_delete and es_jefe:
        lote_del = []
        for idx, row in cambios_df.iterrows():
            pid = int(row['id'])
            for h_nom in HITOS_LIST:
                simb = MAPEO_HITOS[h_nom]
                if not row[simb] and not segs[(segs['producto_id'] == pid) & (segs['hito'] == h_nom)].empty:
                    lote_del.append({"pid": pid, "hito": h_nom})
        if lote_del:
            for d in lote_del:
                supabase.table("seguimiento").delete().eq("producto_id", d['pid']).eq("hito", d['hito']).execute()
            st.cache_data.clear(); st.session_state.ref_matriz += 1; st.rerun()

    # --- J. MÉTRICAS FINALES ---
    def calc_v(df_m, df_s, pend):
        if df_m.empty: return 0.0
        ids = df_m['id'].tolist()
        db_v = df_s[df_s['producto_id'].isin(ids)].drop_duplicates(subset=['producto_id', 'hito'])
        pts = sum([pesos.get(h, 0) for h in db_v['hito']])
        for p in pend:
            if p['pid'] in ids and df_s[(df_s['producto_id'] == p['pid']) & (df_s['hito'] == p['hito'])].empty:
                pts += pesos.get(p['hito'], 0)
        return round(pts / len(df_m), 2)

    st.divider()
    m1, m2 = st.columns(2)
    m1.metric("Avance Parcial", f"{calc_v(df_f, segs, st.session_state.cambios_pendientes)}%")
    m2.metric("Avance Global", f"{calc_v(prods_all, segs, st.session_state.cambios_pendientes)}%")
