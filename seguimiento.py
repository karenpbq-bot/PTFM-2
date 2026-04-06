import streamlit as st
import pandas as pd
from datetime import datetime
import io
from base_datos import conectar, obtener_proyectos, obtener_productos_por_proyecto, obtener_pesos_seguimiento

# 1. ICONOS ACTUALIZADOS (Pulgar arriba para Entrega)
MAPEO_HITOS = {
    "Diseñado": "🗺️", "Fabricado": "🪚", "Material en Obra": "🚛",
    "Material en Ubicación": "📍", "Instalación de Estructura": "📦", 
    "Instalación de Puertas o Frentes": "🗄️", "Revisión y Observaciones": "🔍", "Entrega": "👍" 
}
HITOS_LIST = list(MAPEO_HITOS.keys())

def mostrar(supervisor_id=None):
    # --- A. GESTIÓN DE MEMORIA (Buffer para evitar el "pensado") ---
    if 'pendientes_red' not in st.session_state:
        st.session_state.pendientes_red = [] # Checks en rojo (Memoria)
    if 'ref_matriz' not in st.session_state:
        st.session_state.ref_matriz = 0

    supabase = conectar()
    rol_u = str(st.session_state.get('rol', 'Supervisor')).strip().lower()
    es_jefe = rol_u in ["admin", "gerente", "administrador"]

    # --- B. SELECCIÓN DE PROYECTO (Seguridad por Supervisor) ---
    st.markdown("### Seguimiento de Avances")
    
    with st.expander("🔍 Selección de Proyecto", expanded=not st.session_state.get('id_p_sel')):
        c1, c2 = st.columns([2, 1])
        bus_p = c1.text_input("Filtrar proyecto:", key="bus_seg_VMASTER")
        df_p_all = obtener_proyectos(bus_p)
        
        # Filtro de Seguridad: Supervisor solo ve lo suyo
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
                st.session_state.pendientes_red = [] 
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

    # --- D. TÍTULO Y BOTONES (A la misma altura) ---
    st.divider()
    col_t, col_b1, col_b2, col_b3, col_b4 = st.columns([1.5, 1, 1, 1, 1])
    col_t.markdown("#### Matriz de Seguimiento")
    
    # Botón 1: Solo lee el editor y llena el session_state (Checks Rojos)
    btn_marcar = col_b1.button("✅ Guardar Marcación", use_container_width=True)
    # Botón 2: Sincroniza session_state con Supabase (Cambia a Gris)
    btn_db = col_b2.button("🚀 Guardar Avances", type="primary", use_container_width=True)
    # Botón 3: Limpia los rojos que no se han guardado
    btn_clean = col_b3.button("🧹 Limpiar Marcación", use_container_width=True)
    # Botón 4: Borrar físicos de DB (Solo Admin)
    btn_delete = col_b4.button("🗑️ Borrar Avances", use_container_width=True) if es_jefe else None

    # --- E. FILTROS ---
    with st.sidebar:
        st.header("⚙️ Filtros")
        bus_u = st.text_input("Ubicación (ej: 701)")
        bus_t = st.text_input("Tipo")

    df_f = prods_all.copy()
    if bus_u: df_f = df_f[df_f['ubicacion'].astype(str).str.contains(bus_u, case=False)]
    if bus_t: df_f = df_f[df_f['tipo'].astype(str).str.contains(bus_t, case=False)]

    # --- F. PREPARACIÓN DE MATRIZ ---
    # Columnas ordenadas: codigo_etiqueta, ubicación, tipo, ml, ctd
    df_editor = df_f[['id', 'codigo_etiqueta', 'ubicacion', 'tipo', 'ml', 'ctd']].copy()
    
    for h_nom in HITOS_LIST:
        simb = MAPEO_HITOS[h_nom]
        en_db = df_editor['id'].apply(lambda x: True if not segs[(segs['producto_id'] == x) & (segs['hito'] == h_nom)].empty else False)
        en_mem = df_editor['id'].apply(lambda x: True if any(c['pid'] == x and c['hito'] == h_nom for c in st.session_state.pendientes_red) else False)
        df_editor[simb] = en_db | en_mem

    df_editor['Observaciones'] = df_editor['id'].apply(
        lambda x: segs[(segs['producto_id'] == x) & (segs['hito'] == HITOS_LIST[0])]['observaciones'].iloc[0] if not segs[(segs['producto_id'] == x) & (segs['hito'] == HITOS_LIST[0])].empty else ""
    )

    # --- G. DATA EDITOR (AISLADO) ---
    # Usamos una key estática dentro del renderizado para evitar recargas al hacer clic
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
        key=f"editor_vFINAL_{st.session_state.ref_matriz}"
    )

    # --- H. LÓGICA DE BOTONES (PROCESAMIENTO POSTERIOR) ---

    # 1. GUARDAR MARCACIÓN (LOCAL)
    if btn_marcar:
        nuevos_r = []
        for idx, row in cambios_df.iterrows():
            pid = int(row['id'])
            for h_nom in HITOS_LIST:
                simb = MAPEO_HITOS[h_nom]
                v_db = not segs[(segs['producto_id'] == pid) & (segs['hito'] == h_nom)].empty
                if bool(row[simb]) and not v_db:
                    nuevos_r.append({"pid": pid, "hito": h_nom})
        st.session_state.pendientes_red = nuevos_r
        st.rerun()

    # 2. GUARDAR AVANCES (DB)
    if btn_db:
        if not st.session_state.pendientes_red:
            st.warning("No hay marcaciones nuevas."); st.stop()
        
        lote = []
        f_reg = datetime.now().strftime("%d/%m/%Y")
        for p in st.session_state.pendientes_red:
            # Upsert inteligente: recuperar nota actual del editor
            obs = str(cambios_df[cambios_df['id'] == p['pid']]['Observaciones'].iloc[0]) if p['hito'] == HITOS_LIST[0] else ""
            
            lote.append({
                "producto_id": p['pid'], "hito": p['hito'], "fecha": f_reg, 
                "observaciones": obs, "supervisor_id": supervisor_id
            })
        
        if lote:
            try:
                supabase.table("seguimiento").upsert(lote, on_conflict="producto_id, hito").execute()
                # Sincronizar Gantt
                from base_datos import sincronizar_avances_estructural
                p_cod = st.session_state.p_nom_sel.split(']')[0][1:]
                sincronizar_avances_estructural(p_cod)
                
                st.session_state.pendientes_red = []
                st.cache_data.clear()
                st.session_state.ref_matriz += 1 # Esto refresca la matriz y pone los checks en gris
                st.success("🚀 Avances sincronizados.")
                st.rerun()
            except Exception as e:
                st.error(f"Falla al guardar: {e}")

    # 3. LIMPIAR MARCACIÓN (BORRA ROJOS)
    if btn_clean:
        st.session_state.pendientes_red = []
        st.session_state.ref_matriz += 1
        st.rerun()

    # 4. BORRAR AVANCES (SOLO ADMIN)
    if btn_delete and es_jefe:
        for idx, row in cambios_df.iterrows():
            pid = int(row['id'])
            for h_nom in HITOS_LIST:
                if not row[MAPEO_HITOS[h_nom]] and not segs[(segs['producto_id'] == pid) & (segs['hito'] == h_nom)].empty:
                    supabase.table("seguimiento").delete().eq("producto_id", pid).eq("hito", h_nom).execute()
        st.cache_data.clear(); st.session_state.ref_matriz += 1; st.rerun()

    # --- I. MÉTRICAS (Reflejan cambios tras Guardar Marcación) ---
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
    m1.metric("Avance Parcial", f"{calc_v(df_f, segs, st.session_state.pendientes_red)}%")
    m2.metric("Avance Global", f"{calc_v(prods_all, segs, st.session_state.pendientes_red)}%")
