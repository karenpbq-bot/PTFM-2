import streamlit as st
import pandas as pd
from datetime import datetime
from base_datos import conectar, obtener_proyectos, obtener_productos_por_proyecto, obtener_pesos_seguimiento

# 1. CONFIGURACIÓN VISUAL (ICONOS)
MAPEO_HITOS = {
    "Diseñado": "🗺️", 
    "Fabricado": "🪚", 
    "Material en Obra": "🚛",
    "Material en Ubicación": "📍", 
    "Instalación de Estructura": "📦", 
    "Instalación de Puertas o Frentes": "🗄️", 
    "Revisión y Observaciones": "🔍", 
    "Entrega": "👍" 
}
HITOS_LIST = list(MAPEO_HITOS.keys())

def mostrar(supervisor_id=None):
    # --- A. ESTADOS DE SESIÓN E INTEGRIDAD ---
    if 'cambios_pendientes' not in st.session_state:
        st.session_state.cambios_pendientes = []
    if 'ref_matriz' not in st.session_state:
        st.session_state.ref_matriz = 0
    if 'id_p_sel' not in st.session_state:
        st.session_state.id_p_sel = None
    if 'p_nom_sel' not in st.session_state:
        st.session_state.p_nom_sel = "-- Seleccionar --"

    supabase = conectar()
    rol_u = str(st.session_state.get('rol', 'Supervisor')).strip().lower()
    es_jefe = rol_u in ["admin", "gerente", "administrador"]

    st.markdown(f"### 📋 Módulo de Seguimiento")

    # --- B. SELECCIÓN DE PROYECTO CON FILTRO DE SEGURIDAD ---
    # REGLA DE SEGURIDAD: Si no es jefe, solo ve proyectos asignados a su supervisor_id
    with st.expander("🔍 Selección de Proyecto", expanded=(not st.session_state.id_p_sel)):
        c1, c2 = st.columns([2, 1])
        bus_p = c1.text_input("Filtrar por nombre o código:", key="bus_seg_vFINAL")
        
        # Obtenemos proyectos filtrando por supervisor si corresponde
        df_p_all = obtener_proyectos(bus_p)
        if not es_jefe and not df_p_all.empty:
            df_p_all = df_p_all[df_p_all['supervisor_id'] == supervisor_id]

        if not df_p_all.empty:
            opciones = {f"[{r['codigo']}] {r['proyecto_text']}": r['id'] for _, r in df_p_all.iterrows()}
            lista_opc = ["-- Seleccionar --"] + list(opciones.keys())
            
            # Evitamos el bucle de "pensado" comparando antes de asignar
            idx_s = lista_opc.index(st.session_state.p_nom_sel) if st.session_state.p_nom_sel in lista_opc else 0
            sel_n = c2.selectbox("Elija proyecto:", lista_opc, index=idx_s)
            
            if sel_n != st.session_state.p_nom_sel:
                if sel_n == "-- Seleccionar --":
                    st.session_state.id_p_sel = None
                    st.session_state.p_nom_sel = "-- Seleccionar --"
                else:
                    st.session_state.id_p_sel = opciones[sel_n]
                    st.session_state.p_nom_sel = sel_n
                st.session_state.cambios_pendientes = []
                st.rerun()
        else:
            st.warning("No tienes proyectos asignados o no se encontraron coincidencias.")

    if not st.session_state.id_p_sel:
        st.info("💡 Por favor, seleccione un proyecto para visualizar la matriz."); return

    # --- C. CARGA DE DATOS ---
    id_p = st.session_state.id_p_sel
    prods_all = obtener_productos_por_proyecto(id_p)
    
    if prods_all.empty:
        st.error("Este proyecto no tiene productos registrados."); return

    res_db = supabase.table("seguimiento").select("*").in_("producto_id", prods_all['id'].tolist()).execute()
    segs = pd.DataFrame(res_db.data) if res_db.data else pd.DataFrame(columns=['producto_id','hito','fecha','observaciones'])
    pesos = obtener_pesos_seguimiento()

    # --- D. FILTROS DE VISTA (UBICACIÓN / TIPO) ---
    with st.sidebar:
        st.header("⚙️ Filtros de Matriz")
        bus_u = st.text_input("Ubicación (ej: 701)")
        bus_t = st.text_input("Tipo de Mueble")
        if st.button("🗑️ Limpiar Filtros"):
            st.rerun()

    df_f = prods_all.copy()
    if bus_u: df_f = df_f[df_f['ubicacion'].astype(str).str.contains(bus_u, case=False)]
    if bus_t: df_f = df_f[df_f['tipo'].astype(str).str.contains(bus_t, case=False)]

    # --- E. CABECERA Y BOTONES DE ACCIÓN ---
    st.divider()
    col_t, col_b1, col_b2, col_b3, col_b4 = st.columns([1.5, 1, 1, 1, 1])
    col_t.markdown(f"**Proyecto Actual:** {st.session_state.p_nom_sel}")
    
    btn_marcar = col_b1.button("✅ Guardar Marcación", use_container_width=True, help="Fija los checks rojos en la vista local")
    btn_db = col_b2.button("🚀 Guardar Avances", type="primary", use_container_width=True, help="Sincroniza definitivamente con la Nube")
    btn_clean = col_b3.button("🧹 Limpiar Marcación", use_container_width=True, help="Elimina solo los checks rojos aún no guardados")
    
    btn_delete = None
    if es_jefe:
        btn_delete = col_b4.button("🗑️ Borrar Avances", use_container_width=True)

    # --- F. CONSTRUCCIÓN DE LA MATRIZ ---
    # Orden solicitado: codigo_etiqueta, ubicacion, tipo, ml, ctd
    df_editor = df_f[['id', 'codigo_etiqueta', 'ubicacion', 'tipo', 'ml', 'ctd']].copy()
    
    for h_nom in HITOS_LIST:
        simb = MAPEO_HITOS[h_nom]
        en_db = df_editor['id'].apply(lambda x: True if not segs[(segs['producto_id'] == x) & (segs['hito'] == h_nom)].empty else False)
        en_mem = df_editor['id'].apply(lambda x: True if any(c['pid'] == x and c['hito'] == h_nom for c in st.session_state.cambios_pendientes) else False)
        df_editor[simb] = en_db | en_mem

    df_editor['Observaciones'] = df_editor['id'].apply(
        lambda x: segs[(segs['producto_id'] == x) & (segs['hito'] == HITOS_LIST[0])]['observaciones'].iloc[0] 
        if not segs[(segs['producto_id'] == x) & (segs['hito'] == HITOS_LIST[0])].empty else ""
    )

    # Lógica de cálculo de porcentajes
    def calc_avance(df_m, df_s, pendientes):
        if df_m.empty: return 0.0
        ids_v = df_m['id'].tolist()
        # Avance real en DB
        db_v = df_s[df_s['producto_id'].isin(ids_v)].drop_duplicates(subset=['producto_id', 'hito'])
        pts = sum([pesos.get(h, 0) for h in db_v['hito']])
        # Sumar marcaciones rojas (en memoria)
        for p in pendientes:
            if p['pid'] in ids_v:
                if df_s[(df_s['producto_id'] == p['pid']) & (df_s['hito'] == p['hito'])].empty:
                    pts += pesos.get(p['hito'], 0)
        return round(pts / len(df_m), 2)

    # --- G. RENDERIZADO DEL DATA EDITOR ---
    # El editor es libre para marcar (Fluidez), la restricción viene en el procesado
    cambios_df = st.data_editor(
        df_editor,
        column_config={
            "id": None,
            "codigo_etiqueta": st.column_config.TextColumn("Etiqueta", disabled=True),
            "ubicacion": st.column_config.TextColumn("Ubicación", disabled=True),
            "tipo": st.column_config.TextColumn("Tipo", disabled=True),
            "ml": st.column_config.NumberColumn("ML", disabled=True),
            "ctd": st.column_config.NumberColumn("Cant.", disabled=True),
            "Observaciones": st.column_config.TextColumn("Observaciones", width="large"),
            **{MAPEO_HITOS[h]: st.column_config.CheckboxColumn(MAPEO_HITOS[h]) for h in HITOS_LIST}
        },
        hide_index=True,
        use_container_width=True,
        key=f"matriz_seg_v_{st.session_state.ref_matriz}"
    )

    # --- H. ACCIONES DE LOS BOTONES ---

    # 1. GUARDAR MARCACIÓN: Captura lo que el usuario marcó en pantalla
    if btn_marcar:
        nuevos_pendientes = []
        for idx, row in cambios_df.iterrows():
            pid = int(row['id'])
            for h_nom in HITOS_LIST:
                simb = MAPEO_HITOS[h_nom]
                v_db = not segs[(segs['producto_id'] == pid) & (segs['hito'] == h_nom)].empty
                if bool(row[simb]) and not v_db:
                    nuevos_pendientes.append({"pid": pid, "hito": h_nom})
        st.session_state.cambios_pendientes = nuevos_pendientes
        st.rerun()

    # 2. GUARDAR AVANCES: Sincronización Upsert con Supabase
    if btn_db:
        if not st.session_state.cambios_pendientes:
            st.warning("No hay marcaciones nuevas para subir a la nube."); st.stop()
            
        lote_upsert = []
        fecha_registro = datetime.now().strftime("%d/%m/%Y")
        
        for p in st.session_state.cambios_pendientes:
            # Upsert inteligente: mantenemos notas si ya existen
            match_seg = segs[(segs['producto_id'] == p['pid']) & (segs['hito'] == p['hito'])]
            obs_prev = str(match_seg['observaciones'].iloc[0]) if not match_seg.empty else ""
            
            # Si el hito es Diseño, tomamos la nota actual del editor
            if p['hito'] == HITOS_LIST[0]:
                obs_prev = str(cambios_df[cambios_df['id'] == p['pid']]['Observaciones'].iloc[0])

            lote_upsert.append({
                "producto_id": p['pid'], 
                "hito": p['hito'], 
                "fecha": fecha_registro,
                "observaciones": obs_prev, 
                "supervisor_id": supervisor_id
            })
        
        if lote_upsert:
            try:
                supabase.table("seguimiento").upsert(lote_upsert, on_conflict="producto_id, hito").execute()
                # Sincronizar avances estructurales (Gantt)
                from base_datos import sincronizar_avances_estructural
                p_cod = st.session_state.p_nom_sel.split(']')[0][1:]
                sincronizar_avances_estructural(p_cod)
                
                st.session_state.cambios_pendientes = []
                st.cache_data.clear()
                st.session_state.ref_matriz += 1
                st.success("✅ Datos guardados correctamente en la nube.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

    # 3. LIMPIAR MARCACIÓN: Resetea los checks rojos
    if btn_clean:
        st.session_state.cambios_pendientes = []
        st.session_state.ref_matriz += 1
        st.rerun()

    # 4. BORRAR AVANCES: Solo para Administradores
    if btn_delete and es_jefe:
        lote_del = []
        for idx, row in cambios_df.iterrows():
            pid = int(row['id'])
            for h_nom in HITOS_LIST:
                simb = MAPEO_HITOS[h_nom]
                # Si se desmarcó una casilla que estaba en DB (Gris)
                if not row[simb] and not segs[(segs['producto_id'] == pid) & (segs['hito'] == h_nom)].empty:
                    lote_del.append({"pid": pid, "hito": h_nom})
        
        if lote_del:
            for d in lote_del:
                supabase.table("seguimiento").delete().eq("producto_id", d['pid']).eq("hito", d['hito']).execute()
            st.cache_data.clear()
            st.session_state.ref_matriz += 1
            st.rerun()

    # --- I. MÉTRICAS FINALES ---
    st.divider()
    m1, m2 = st.columns(2)
    m1.metric("Avance Parcial (Ubicación)", f"{calc_avance(df_f, segs, st.session_state.cambios_pendientes)}%")
    m2.metric("Avance Global del Proyecto", f"{calc_avance(prods_all, segs, st.session_state.cambios_pendientes)}%")
