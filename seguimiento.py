import streamlit as st
import pandas as pd
from datetime import datetime
from base_datos import conectar, obtener_proyectos, obtener_productos_por_proyecto, obtener_pesos_seguimiento

# 1. CONFIGURACIÓN VISUAL
MAPEO_HITOS = {
    "Diseñado": "🗺️", "Fabricado": "🪚", "Material en Obra": "🚛",
    "Material en Ubicación": "📍", "Instalación de Estructura": "📦", 
    "Instalación de Puertas o Frentes": "🗄️", "Revisión y Observaciones": "🔍", "Entrega": "🤝"
}
HITOS_LIST = list(MAPEO_HITOS.keys())

def mostrar(supervisor_id=None):
    # --- A. ESTADOS DE SESIÓN ---
    if 'cambios_pendientes' not in st.session_state:
        st.session_state.cambios_pendientes = []  # Almacena los checks rojos
    if 'ref_matriz' not in st.session_state:
        st.session_state.ref_matriz = 0

    st.markdown("""
        <style>
        [data-testid="stMetricValue"] { color: #FF8C00 !important; font-weight: bold !important; font-size: 22px !important; }
        .stDataEditor { border: 1px solid #ddd; border-radius: 8px; }
        /* Estilo para simular checks rojos (vía configuración de columna) */
        </style>
    """, unsafe_allow_html=True)

    supabase = conectar()

    # --- B. SELECCIÓN DE PROYECTO ---
    nombre_p_act = st.session_state.get('p_nom_sel', "Ninguno")
    st.markdown(f"### Seguimiento: {nombre_p_act}")

    with st.expander("🔍 Proyecto", expanded=not st.session_state.get('id_p_sel')):
        c1, c2 = st.columns([2, 1])
        bus_p = c1.text_input("Buscar proyecto...", key="bus_seg_vPRO")
        df_p_all = obtener_proyectos(bus_p)
        if not df_p_all.empty:
            opciones = {f"[{r['codigo']}] {r['proyecto_text']}": r['id'] for _, r in df_p_all.iterrows()}
            lista_opc = ["-- Seleccionar --"] + list(opciones.keys())
            idx_s = lista_opc.index(st.session_state.p_nom_sel) if st.session_state.get('p_nom_sel') in lista_opc else 0
            sel_n = c2.selectbox("Proyecto:", lista_opc, index=idx_s)
            if sel_n != "-- Seleccionar --":
                st.session_state.id_p_sel, st.session_state.p_nom_sel = opciones[sel_n], sel_n
                st.session_state.cambios_pendientes = []
                st.rerun()

    if not st.session_state.get('id_p_sel'):
        st.info("💡 Seleccione un proyecto."); return

    # --- C. CARGA DE DATOS ---
    id_p = st.session_state.id_p_sel
    prods_all = obtener_productos_por_proyecto(id_p)
    res_db = supabase.table("seguimiento").select("*").in_("producto_id", prods_all['id'].tolist()).execute()
    segs = pd.DataFrame(res_db.data) if res_db.data else pd.DataFrame(columns=['producto_id','hito','fecha','observaciones'])
    
    rol_u = str(st.session_state.get('rol', 'Supervisor')).strip().lower()
    es_jefe = rol_u in ["admin", "gerente", "administrador"]
    pesos = obtener_pesos_seguimiento()

    # --- D. FILTROS ---
    with st.sidebar:
        st.header("⚙️ Filtros")
        bus_u = st.text_input("Ubicación (ej: 701)")
        bus_t = st.text_input("Tipo")

    df_f = prods_all.copy()
    if bus_u: df_f = df_f[df_f['ubicacion'].astype(str).str.contains(bus_u, case=False)]
    if bus_t: df_f = df_f[df_f['tipo'].astype(str).str.contains(bus_t, case=False)]

    # --- E. CABECERA DE MATRIZ Y BOTONES ---
    col_t, col_b1, col_b2, col_b3, col_b4 = st.columns([1.5, 1, 1, 1, 1])
    col_t.subheader("Matriz de Seguimiento")
    
    # Botón 1: Guardar Marcación (Actualiza UI y % localmente)
    btn_marcar = col_b1.button("✅ Guardar Marcación", use_container_width=True)
    
    # Botón 2: Guardar Avances (Actualiza Supabase)
    btn_db = col_b2.button("🚀 Guardar Avances", type="primary", use_container_width=True)
    
    # Botón 3: Limpiar Marcación (Solo rojos)
    btn_clean = col_b3.button("🧹 Limpiar Marcación", use_container_width=True)
    
    # Botón 4: Borrar Avances (Solo Admin/Gerente)
    btn_delete = None
    if es_jefe:
        btn_delete = col_b4.button("🗑️ Borrar Avances", use_container_width=True)

    # --- F. PREPARACIÓN DE LA TABLA COMPACTA ---
    # Columnas: codigo_etiqueta, Ubicación, Tipo, Ml, Cant, 8 hitos, Observaciones
    df_editor = df_f[['id', 'codigo_etiqueta', 'ubicacion', 'tipo', 'ml', 'ctd']].copy()
    
    for h_nom in HITOS_LIST:
        simb = MAPEO_HITOS[h_nom]
        # Check Gris (En DB)
        en_db = df_editor['id'].apply(lambda x: True if not segs[(segs['producto_id'] == x) & (segs['hito'] == h_nom)].empty else False)
        # Check Rojo (En Memoria)
        en_mem = df_editor['id'].apply(lambda x: True if any(c['pid'] == x and c['hito'] == h_nom for c in st.session_state.cambios_pendientes) else False)
        df_editor[simb] = en_db | en_mem

    df_editor['Observaciones'] = df_editor['id'].apply(
        lambda x: segs[(segs['producto_id'] == x) & (segs['hito'] == HITOS_LIST[0])]['observaciones'].iloc[0] 
        if not segs[(segs['producto_id'] == x) & (segs['hito'] == HITOS_LIST[0])].empty else ""
    )

    # Lógica de Avance
    def calc_avance(df_m, df_s, pendientes):
        if df_m.empty: return 0.0
        ids_v = df_m['id'].tolist()
        db_v = df_s[df_s['producto_id'].isin(ids_v)].drop_duplicates(subset=['producto_id', 'hito'])
        pts = sum([pesos.get(h, 0) for h in db_v['hito']])
        # Sumar puntos de marcaciones rojas que no estén en DB
        for p in pendientes:
            if p['pid'] in ids_v:
                # Si el hito no está en DB, sumamos el peso
                if df_s[(df_s['producto_id'] == p['pid']) & (df_s['hito'] == p['hito'])].empty:
                    pts += pesos.get(p['hito'], 0)
        return round(pts / len(df_m), 2)

    # --- G. RENDERIZADO DE MATRIZ ---
    with st.container():
        # Configuramos deshabilitados: Info básica siempre. 
        # Hitos bloqueados si están en Gris y el usuario es Supervisor.
        disabled_cols = ['id', 'codigo_etiqueta', 'ubicacion', 'tipo', 'ml', 'ctd']
        
        cambios_df = st.data_editor(
            df_editor,
            column_config={
                "id": None,
                "codigo_etiqueta": st.column_config.TextColumn("Código Etiqueta", disabled=True),
                "ubicacion": st.column_config.TextColumn("Ubicación", disabled=True),
                "tipo": st.column_config.TextColumn("Tipo", disabled=True),
                "ml": st.column_config.NumberColumn("ML", disabled=True),
                "ctd": st.column_config.NumberColumn("Cant.", disabled=True),
                "Observaciones": st.column_config.TextColumn("Observaciones"),
                **{MAPEO_HITOS[h]: st.column_config.CheckboxColumn(MAPEO_HITOS[h]) for h in HITOS_LIST}
            },
            hide_index=True,
            use_container_width=True,
            key=f"editor_v12_{st.session_state.ref_matriz}"
        )

    # --- H. PROCESAMIENTO DE BOTONES ---
    
    # 1. GUARDAR MARCACIÓN (Local)
    if btn_marcar:
        nuevos_pendientes = []
        for idx, row in cambios_df.iterrows():
            pid = int(row['id'])
            for h_nom in HITOS_LIST:
                simb = MAPEO_HITOS[h_nom]
                v_orig_db = not segs[(segs['producto_id'] == pid) & (segs['hito'] == h_nom)].empty
                v_editor = bool(row[simb])
                # Si se marcó algo que no está en DB, va a cambios_pendientes
                if v_editor and not v_orig_db:
                    nuevos_pendientes.append({"pid": pid, "hito": h_nom})
        st.session_state.cambios_pendientes = nuevos_pendientes
        st.rerun()

    # 2. GUARDAR AVANCES (Supabase)
    if btn_db:
        if not st.session_state.cambios_pendientes:
            st.warning("No hay marcaciones rojas para guardar."); st.stop()
            
        lote_upsert = []
        f_reg = datetime.now().strftime("%d/%m/%Y")
        
        for p in st.session_state.cambios_pendientes:
            # Upsert Inteligente: buscar nota actual
            match_seg = segs[(segs['producto_id'] == p['pid']) & (segs['hito'] == p['hito'])]
            obs_actual = match_seg['observaciones'].iloc[0] if not match_seg.empty else ""
            
            lote_upsert.append({
                "producto_id": p['pid'], "hito": p['hito'], "fecha": f_reg,
                "observaciones": obs_actual, "supervisor_id": supervisor_id
            })
        
        if lote_upsert:
            supabase.table("seguimiento").upsert(lote_upsert, on_conflict="producto_id, hito").execute()
            st.session_state.cambios_pendientes = []
            st.cache_data.clear(); st.session_state.ref_matriz += 1; st.rerun()

    # 3. LIMPIAR MARCACIÓN (Solo rojos)
    if btn_clean:
        st.session_state.cambios_pendientes = []
        st.session_state.ref_matriz += 1; st.rerun()

    # 4. BORRAR AVANCES (Admin/Gerente)
    if btn_delete:
        lote_del = []
        for idx, row in cambios_df.iterrows():
            pid = int(row['id'])
            for h_nom in HITOS_LIST:
                simb = MAPEO_HITOS[h_nom]
                if not row[simb]: # Si se desmarcó en el editor
                    lote_del.append({"pid": pid, "hito": h_nom})
        
        for d in lote_del:
            supabase.table("seguimiento").delete().eq("producto_id", d['pid']).eq("hito", d['hito']).execute()
        
        st.cache_data.clear(); st.session_state.ref_matriz += 1; st.rerun()

    # Métricas al final para reflejar cambios tras 'Guardar Marcación'
    st.divider()
    m1, m2 = st.columns(2)
    m1.metric("Avance Parcial (con marcaciones)", f"{calc_avance(df_f, segs, st.session_state.cambios_pendientes)}%")
    m2.metric("Avance Global", f"{calc_avance(prods_all, segs, st.session_state.cambios_pendientes)}%")
