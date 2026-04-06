import streamlit as st
import pandas as pd
from datetime import datetime
import io
from base_datos import conectar, obtener_proyectos, obtener_productos_por_proyecto, obtener_pesos_seguimiento

# 1. MAPEO DE ICONOS (Pulgar arriba para Entrega)
MAPEO_HITOS = {
    "Diseñado": "🗺️", "Fabricado": "🪚", "Material en Obra": "🚛",
    "Material en Ubicación": "📍", "Instalación de Estructura": "📦", 
    "Instalación de Puertas o Frentes": "🗄️", "Revisión y Observaciones": "🔍", "Entrega": "👍" 
}
HITOS_LIST = list(MAPEO_HITOS.keys())

def mostrar(supervisor_id=None):
    # --- A. GESTIÓN DE MEMORIA (Buffer para evitar recargas constantes) ---
    if 'cambios_pendientes' not in st.session_state:
        st.session_state.cambios_pendientes = [] # Checks Rojos
    if 'ref_matriz' not in st.session_state:
        st.session_state.ref_matriz = 0

    supabase = conectar()
    rol_u = str(st.session_state.get('rol', 'Supervisor')).strip().lower()
    es_jefe = rol_u in ["admin", "gerente", "administrador"]

    # --- B. SELECCIÓN DE PROYECTO CON FILTRO DE SEGURIDAD ---
    # Recuperamos el ID que viene del app_principal para mantener coherencia
    id_p_actual = st.session_state.get('id_p_sel')
    
    st.markdown("### Seguimiento de Avances")
    
    with st.expander("🔍 Selección de Proyecto", expanded=not id_p_actual):
        c1, c2 = st.columns([2, 1])
        bus_p = c1.text_input("Buscar proyecto:", key="bus_seg_VMASTER")
        df_p_all = obtener_proyectos(bus_p)
        
        # Seguridad: Solo ver proyectos propios si es Supervisor
        if not es_jefe and not df_p_all.empty:
            df_p_all = df_p_all[df_p_all['supervisor_id'] == supervisor_id]

        if not df_p_all.empty:
            opciones = {f"[{r['codigo']}] {r['proyecto_text']}": r['id'] for _, r in df_p_all.iterrows()}
            lista_opc = ["-- Seleccionar --"] + list(opciones.keys())
            
            p_nom_actual = st.session_state.get('p_nom_sel', "-- Seleccionar --")
            idx_s = lista_opc.index(p_nom_actual) if p_nom_actual in lista_opc else 0
            
            sel_n = c2.selectbox("Proyecto:", lista_opc, index=idx_s)
            
            if sel_n != p_nom_actual:
                if sel_n == "-- Seleccionar --":
                    st.session_state.id_p_sel = None
                    st.session_state.p_nom_sel = "-- Seleccionar --"
                else:
                    st.session_state.id_p_sel = opciones[sel_n]
                    st.session_state.p_nom_sel = sel_n
                st.session_state.cambios_pendientes = []
                st.rerun()

    if not st.session_state.get('id_p_sel'):
        st.info("💡 Seleccione un proyecto para visualizar la matriz."); return

    # --- C. CARGA Y FILTRADO DE DATOS ---
    id_p = st.session_state.id_p_sel
    prods_all = obtener_productos_por_proyecto(id_p)
    res_db = supabase.table("seguimiento").select("*").in_("producto_id", prods_all['id'].tolist()).execute()
    segs = pd.DataFrame(res_db.data) if res_db.data else pd.DataFrame(columns=['producto_id','hito','fecha','observaciones'])
    pesos = obtener_pesos_seguimiento()

    with st.sidebar:
        st.header("⚙️ Filtros")
        bus_u = st.text_input("Ubicación (ej: 701)")
        bus_t = st.text_input("Tipo")

    df_f = prods_all.copy()
    if bus_u: df_f = df_f[df_f['ubicacion'].astype(str).str.contains(bus_u, case=False)]
    if bus_t: df_f = df_f[df_f['tipo'].astype(str).str.contains(bus_t, case=False)]

    # --- D. BOTONES DE ACCIÓN (A la altura del título) ---
    col_t, col_b1, col_b2, col_b3, col_b4 = st.columns([1.5, 1, 1, 1, 1])
    col_t.markdown("#### Matriz de Seguimiento")
    
    # 1. Guardar Marcación (Fija checks rojos y actualiza % sin ir a DB)
    btn_marcar = col_b1.button("✅ Guardar Marcación", use_container_width=True)
    # 2. Guardar Avances (Sincroniza con Supabase)
    btn_db = col_b2.button("🚀 Guardar Avances", type="primary", use_container_width=True)
    # 3. Limpiar Marcación (Borra rojos)
    btn_clean = col_b3.button("🧹 Limpiar Marcación", use_container_width=True)
    # 4. Borrar Avances (Solo Admin/Gerente - Borra Grises)
    btn_delete = col_b4.button("🗑️ Borrar Avances", use_container_width=True) if es_jefe else None

    # --- E. CONSTRUCCIÓN DE LA MATRIZ (ORDEN SOLICITADO) ---
    # Columnas: codigo_etiqueta, ubicación, tipo, ml, ctd
    df_editor = df_f[['id', 'codigo_etiqueta', 'ubicacion', 'tipo', 'ml', 'ctd']].copy()
    
    for h_nom in HITOS_LIST:
        simb = MAPEO_HITOS[h_nom]
        en_db = df_editor['id'].apply(lambda x: True if not segs[(segs['producto_id'] == x) & (segs['hito'] == h_nom)].empty else False)
        en_mem = df_editor['id'].apply(lambda x: True if any(c['pid'] == x and c['hito'] == h_nom for c in st.session_state.cambios_pendientes) else False)
        df_editor[simb] = en_db | en_mem

    # Notas vinculadas al hito Diseño
    df_editor['Observaciones'] = df_editor['id'].apply(
        lambda x: segs[(segs['producto_id'] == x) & (segs['hito'] == HITOS_LIST[0])]['observaciones'].iloc[0] 
        if not segs[(segs['producto_id'] == x) & (segs['hito'] == HITOS_LIST[0])].empty else ""
    )

    # --- F. RENDERIZADO DEL DATA EDITOR (Sin Form para fluidez total) ---
    # La clave es la 'key' dinámica: solo cambia cuando guardamos en DB o limpiamos
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
        key=f"editor_MASTER_{id_p}_{st.session_state.ref_matriz}"
    )

    # --- G. LÓGICA DE PROCESAMIENTO ---

    # 1. GUARDAR MARCACIÓN
    if btn_marcar:
        nuevos_pendientes = []
        for idx, row in cambios_df.iterrows():
            pid = int(row['id'])
            for h_nom in HITOS_LIST:
                simb = MAPEO_HITOS[h_nom]
                en_db = not segs[(segs['producto_id'] == pid) & (segs['hito'] == h_nom)].empty
                # Si está marcado en editor y no existe en DB -> Es una marcación roja nueva
                if bool(row[simb]) and not en_db:
                    nuevos_pendientes.append({"pid": pid, "hito": h_nom})
        st.session_state.cambios_pendientes = nuevos_pendientes
        st.rerun()

    # 2. GUARDAR AVANCES (DB)
    if btn_db:
        if not st.session_state.cambios_pendientes:
            st.warning("⚠️ No hay marcaciones nuevas para guardar."); st.stop()
        
        lote_ins = []
        fecha_str = datetime.now().strftime("%d/%m/%Y")
        for p in st.session_state.cambios_pendientes:
            # Preservar notas existentes para no borrarlas al marcar hitos
            match_seg = segs[(segs['producto_id'] == p['pid']) & (segs['hito'] == p['hito'])]
            obs_actual = str(match_seg['observaciones'].iloc[0]) if not match_seg.empty else ""
            
            # Si es el hito 0, capturamos la observación del editor
            if p['hito'] == HITOS_LIST[0]:
                obs_actual = str(cambios_df[cambios_df['id'] == p['pid']]['Observaciones'].iloc[0])

            lote_ins.append({
                "producto_id": p['pid'], "hito": p['hito'], "fecha": fecha_str, 
                "observaciones": obs_actual, "supervisor_id": supervisor_id
            })
        
        if lote_ins:
            supabase.table("seguimiento").upsert(lote_ins, on_conflict="producto_id, hito").execute()
            from base_datos import sincronizar_avances_estructural
            sincronizar_avances_estructural(st.session_state.p_nom_sel.split(']')[0][1:])
            st.session_state.cambios_pendientes = []
            st.cache_data.clear(); st.session_state.ref_matriz += 1; st.rerun()

    # 3. LIMPIAR MARCACIÓN (Solo Rojos)
    if btn_clean:
        st.session_state.cambios_pendientes = []
        st.session_state.ref_matriz += 1; st.rerun()

    # 4. BORRAR AVANCES (SOLO ADMIN)
    if btn_delete and es_jefe:
        for idx, row in cambios_df.iterrows():
            pid = int(row['id'])
            for h_nom in HITOS_LIST:
                simb = MAPEO_HITOS[h_nom]
                if not row[simb] and not segs[(segs['producto_id'] == pid) & (segs['hito'] == h_nom)].empty:
                    supabase.table("seguimiento").delete().eq("producto_id", pid).eq("hito", h_nom).execute()
        st.cache_data.clear(); st.session_state.ref_matriz += 1; st.rerun()

    # --- H. MÉTRICAS (Reflejan cambios tras 'Guardar Marcación') ---
    def calc_avance(df_m, df_s, pend):
        if df_m.empty: return 0.0
        ids = df_m['id'].tolist()
        db_v = df_s[df_s['producto_id'].isin(ids)].drop_duplicates(subset=['producto_id', 'hito'])
        pts = sum([pesos.get(h, 0) for h in db_v['hito']])
        # Sumar marcaciones rojas
        for p in pend:
            if p['pid'] in ids and df_s[(df_s['producto_id'] == p['pid']) & (df_s['hito'] == p['hito'])].empty:
                pts += pesos.get(p['hito'], 0)
        return round(pts / len(df_m), 2)

    st.divider()
    m1, m2 = st.columns(2)
    m1.metric("Avance Parcial (con marcaciones)", f"{calc_avance(df_f, segs, st.session_state.cambios_pendientes)}%")
    m2.metric("Avance Global", f"{calc_v(prods_all, segs, st.session_state.cambios_pendientes)}%")
