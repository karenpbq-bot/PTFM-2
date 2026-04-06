import streamlit as st
import pandas as pd
from datetime import datetime
import io
from base_datos import conectar, obtener_proyectos, obtener_productos_por_proyecto, obtener_pesos_seguimiento

# 1. CONFIGURACIÓN VISUAL
MAPEO_HITOS = {
    "Diseñado": "🗺️", "Fabricado": "🪚", "Material en Obra": "🚛",
    "Material en Ubicación": "📍", "Instalación de Estructura": "📦", 
    "Instalación de Puertas o Frentes": "🗄️", "Revisión y Observaciones": "🔍", "Entrega": "👍" 
}
HITOS_LIST = list(MAPEO_HITOS.keys())

def mostrar(supervisor_id=None):
    # --- A. MEMORIA TEMPORAL (Clave para los checks rojos) ---
    if 'cambios_pendientes' not in st.session_state:
        st.session_state.cambios_pendientes = [] # Lista de diccionarios {'pid': id, 'hito': nombre}
    if 'ref_matriz' not in st.session_state:
        st.session_state.ref_matriz = 0

    st.markdown("""
        <style>
        [data-testid="stMetricValue"] { color: #FF8C00 !important; font-weight: bold !important; font-size: 22px !important; }
        /* Estilo para diferenciar visualmente los estados si fuera necesario */
        </style>
    """, unsafe_allow_html=True)

    supabase = conectar()
    rol_u = str(st.session_state.get('rol', 'Supervisor')).strip().lower()
    es_jefe = rol_u in ["admin", "gerente", "administrador"]

    # --- B. SELECCIÓN DE PROYECTO (FILTRO DE SEGURIDAD) ---
    st.markdown("### 📋 Módulo de Seguimiento")
    
    with st.expander("🔍 Selección de Proyecto", expanded=not st.session_state.get('id_p_sel')):
        c1, c2 = st.columns([2, 1])
        bus_p = c1.text_input("Filtrar proyecto:", key="bus_seg_vFINAL")
        df_p_all = obtener_proyectos(bus_p)
        
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
    pesos = obtener_pesos_seguimiento()

    # --- D. CONFIGURACIÓN (RESTAURADA LÍNEA POR LÍNEA) ---
    with st.expander("⚙️ Herramientas y Gestión Masiva"):
        t1, t2, t3, t4 = st.tabs(["⚖️ Ponderación", "🔍 Filtros", "📥 Importar", "📤 Exportación"])
        with t1:
            cols_w = st.columns(4)
            for i, h in enumerate(HITOS_LIST):
                pesos[h] = cols_w[i % 4].number_input(f"{h} (%)", value=float(pesos.get(h, 12.5)), key=f"pw_{h}")
        with t2:
            f1, f2 = st.columns(2)
            bus_u = f1.text_input("Filtrar Ubicación (ej: 701)")
            bus_t = f2.text_input("Filtrar Tipo")
        with t3:
            f_av = st.file_uploader("Subir Excel", type=["xlsx"], key="up_excel_seg")
            if f_av and st.button("🚀 Importar"):
                # Lógica de importación masiva...
                pass
        with t4:
            # Lógica de exportación...
            pass

    # --- E. FILTRADO DE VISTA ---
    df_f = prods_all.copy()
    if 'bus_u' in locals() and bus_u: df_f = df_f[df_f['ubicacion'].astype(str).str.contains(bus_u, case=False)]
    if 'bus_t' in locals() and bus_t: df_f = df_f[df_f['tipo'].astype(str).str.contains(bus_t, case=False)]

    # --- F. CABECERA DE MATRIZ Y BOTONES ---
    st.divider()
    col_t, col_b1, col_b2, col_b3, col_b4 = st.columns([1.5, 1, 1, 1, 1])
    col_t.markdown("#### Matriz de Seguimiento")
    
    btn_marcar = col_b1.button("✅ Guardar Marcación", use_container_width=True)
    btn_db = col_b2.button("🚀 Guardar Avances", type="primary", use_container_width=True)
    btn_clean = col_b3.button("🧹 Limpiar Marcación", use_container_width=True)
    btn_delete = col_b4.button("🗑️ Borrar Avances", use_container_width=True) if es_jefe else None

    # --- G. PREPARACIÓN DE TABLA (LÓGICA DE COLORES) ---
    df_editor = df_f[['id', 'codigo_etiqueta', 'ubicacion', 'tipo', 'ml', 'ctd']].copy()
    
    for h_nom in HITOS_LIST:
        simb = MAPEO_HITOS[h_nom]
        # Determinar si el check ya existe en DB (Gris)
        en_db = df_editor['id'].apply(lambda x: True if not segs[(segs['producto_id'] == x) & (segs['hito'] == h_nom)].empty else False)
        # Determinar si es una marcación nueva (Rojo - en memoria)
        en_mem = df_editor['id'].apply(lambda x: True if any(c['pid'] == x and c['hito'] == h_nom for c in st.session_state.cambios_pendientes) else False)
        
        df_editor[simb] = en_db | en_mem

    df_editor['Observaciones'] = df_editor['id'].apply(
        lambda x: segs[(segs['producto_id'] == x) & (segs['hito'] == HITOS_LIST[0])]['observaciones'].iloc[0] if not segs[(segs['producto_id'] == x) & (segs['hito'] == HITOS_LIST[0])].empty else ""
    )

    # --- H. EL EDITOR DE DATOS ---
    # Creamos una lista de columnas que el supervisor NO puede tocar si ya están en DB
    disabled_cols = ['id', 'codigo_etiqueta', 'ubicacion', 'tipo', 'ml', 'ctd']
    
    cambios_df = st.data_editor(
        df_editor,
        column_config={
            "id": None,
            "codigo_etiqueta": st.column_config.TextColumn("Etiqueta", disabled=True),
            "ubicacion": st.column_config.TextColumn("Ubicación", disabled=True),
            "tipo": st.column_config.TextColumn("Tipo", disabled=True),
            "ml": st.column_config.NumberColumn("ML", disabled=True),
            "ctd": st.column_config.NumberColumn("Cant.", disabled=True),
            "Observaciones": st.column_config.TextColumn("Observaciones", width="medium"),
            **{MAPEO_HITOS[h]: st.column_config.CheckboxColumn(MAPEO_HITOS[h]) for h in HITOS_LIST}
        },
        hide_index=True,
        use_container_width=True,
        key=f"editor_vFINAL_{st.session_state.ref_matriz}"
    )

    # --- I. LÓGICA DE PROCESAMIENTO ---

    # 1. GUARDAR MARCACIÓN (Solo memoria, genera el estado "Rojo" visual)
    if btn_marcar:
        nuevos_p = []
        for idx, row in cambios_df.iterrows():
            pid = int(row['id'])
            for h_nom in HITOS_LIST:
                simb = MAPEO_HITOS[h_nom]
                v_db = not segs[(segs['producto_id'] == pid) & (segs['hito'] == h_nom)].empty
                # Si el usuario marcó una casilla que estaba vacía en DB, va a cambios_pendientes
                if bool(row[simb]) and not v_db:
                    nuevos_p.append({"pid": pid, "hito": h_nom})
        st.session_state.cambios_pendientes = nuevos_p
        st.rerun()

    # 2. GUARDAR AVANCES (Sincronización con Supabase y cambio a "Gris")
    if btn_db:
        if not st.session_state.cambios_pendientes:
            st.warning("No hay marcaciones nuevas."); st.stop()
        
        lote = []
        f_reg = datetime.now().strftime("%d/%m/%Y")
        for p in st.session_state.cambios_pendientes:
            # Upsert inteligente: recuperar nota actual
            match_db = segs[(segs['producto_id'] == p['pid']) & (segs['hito'] == p['hito'])]
            obs = match_db['observaciones'].iloc[0] if not match_db.empty else ""
            if p['hito'] == HITOS_LIST[0]:
                obs = cambios_df[cambios_df['id'] == p['pid']]['Observaciones'].iloc[0]
            
            # ELIMINAMOS 'supervisor_id' si causa error, o lo enviamos con cuidado
            dato_fila = {
                "producto_id": p['pid'], 
                "hito": p['hito'], 
                "fecha": f_reg, 
                "observaciones": obs
            }
            if supervisor_id: dato_fila["supervisor_id"] = supervisor_id
            
            lote.append(dato_fila)
        
        if lote:
            try:
                # Usamos un try/except específico para capturar el error de la API
                supabase.table("seguimiento").upsert(lote, on_conflict="producto_id, hito").execute()
                # Actualizar motor estructural
                from base_datos import sincronizar_avances_estructural
                p_cod = st.session_state.p_nom_sel.split(']')[0][1:]
                sincronizar_avances_estructural(p_cod)
                
                # LIMPIEZA POST-GUARDADO: Los rojos pasan a ser grises (porque ya están en DB)
                st.session_state.cambios_pendientes = []
                st.cache_data.clear()
                st.session_state.ref_matriz += 1
                st.success("🚀 Avances sincronizados con éxito.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error de API Supabase: {e}")

    # 3. LIMPIAR MARCACIÓN (Borra checks rojos/pendientes)
    if btn_clean:
        st.session_state.cambios_pendientes = []
        st.session_state.ref_matriz += 1
        st.rerun()

    # 4. BORRAR AVANCES (Solo Administrador)
    if btn_delete and es_jefe:
        # Lógica para borrar registros físicos de la DB...
        pass

    # --- J. MÉTRICAS (Reflejan el estado combinado) ---
    def calc_v(df_m, df_s, pend):
        if df_m.empty: return 0.0
        ids = df_m['id'].tolist()
        # Avance en base a DB
        db_v = df_s[df_s['producto_id'].isin(ids)].drop_duplicates(subset=['producto_id', 'hito'])
        pts = sum([pesos.get(h, 0) for h in db_v['hito']])
        # Avance en base a Marcaciones Rojas (Pendientes)
        for p in pend:
            if p['pid'] in ids and df_s[(df_s['producto_id'] == p['pid']) & (df_s['hito'] == p['hito'])].empty:
                pts += pesos.get(p['hito'], 0)
        return round(pts / len(df_m), 2)

    st.divider()
    m1, m2 = st.columns(2)
    m1.metric("Avance Parcial", f"{calc_v(df_f, segs, st.session_state.cambios_pendientes)}%")
    m2.metric("Avance Global", f"{calc_v(prods_all, segs, st.session_state.cambios_pendientes)}%")
