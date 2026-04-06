import streamlit as st
import pandas as pd
from datetime import datetime
import io
from base_datos import conectar, obtener_proyectos, obtener_productos_por_proyecto, obtener_seguimiento, obtener_pesos_seguimiento

# 1. CONFIGURACIÓN
MAPEO_HITOS = {
    "Diseñado": "🗺️", "Fabricado": "🪚", "Material en Obra": "🚛",
    "Material en Ubicación": "📍", "Instalación de Estructura": "📦", 
    "Instalación de Puertas o Frentes": "🗄️", "Revisión y Observaciones": "🔍", "Entrega": "🤝"
}
HITOS_LIST = list(MAPEO_HITOS.keys())

def mostrar(supervisor_id=None):
    if 'ref_matriz' not in st.session_state:
        st.session_state.ref_matriz = 0

    st.markdown("""
        <style>
        .sticky-top { position: sticky; top: 0; background: white; z-index: 1000; padding: 10px 0; border-bottom: 3px solid #FF8C00; }
        [data-testid="stMetricValue"] { color: #FF8C00 !important; font-weight: bold !important; font-size: 22px !important; }
        </style>
    """, unsafe_allow_html=True)

    supabase = conectar()

    # --- 2. SELECCIÓN DE PROYECTO ---
    nombre_p_act = st.session_state.get('p_nom_sel', "Ninguno")
    st.markdown(f"### Seguimiento: {nombre_p_act}")

    with st.expander("🔍 Seleccionar Proyecto", expanded=not st.session_state.get('id_p_sel')):
        c1, c2 = st.columns([2, 1])
        bus_p = c1.text_input("Buscar proyecto...", key="bus_v_final")
        df_p_all = obtener_proyectos(bus_p)
        
        if not df_p_all.empty:
            opciones = {f"[{r['codigo']}] {r['proyecto_text']}": r['id'] for _, r in df_p_all.iterrows()}
            lista_opc = ["-- Seleccionar --"] + list(opciones.keys())
            idx_s = lista_opc.index(st.session_state.p_nom_sel) if st.session_state.get('p_nom_sel') in lista_opc else 0
            sel_n = c2.selectbox("Proyecto:", lista_opc, index=idx_s)
            if sel_n != "-- Seleccionar --":
                st.session_state.id_p_sel, st.session_state.p_nom_sel = opciones[sel_n], sel_n
                st.rerun()

    if not st.session_state.get('id_p_sel'):
        st.info("💡 Seleccione un proyecto."); return

    # --- 3. CARGA DE DATOS ---
    id_p = st.session_state.id_p_sel
    prods_all = obtener_productos_por_proyecto(id_p)
    # Cargamos TODO el seguimiento incluyendo observaciones y supervisor_id
    res_db = supabase.table("seguimiento").select("*").in_("producto_id", prods_all['id'].tolist()).execute()
    segs = pd.DataFrame(res_db.data) if res_db.data else pd.DataFrame(columns=['producto_id','hito','fecha','observaciones','supervisor_id'])

    # --- 4. FILTROS ---
    with st.sidebar:
        st.header("⚙️ Filtros de Vista")
        bus_u = st.text_input("Ubicación (ej: 701)")
        bus_t = st.text_input("Tipo")
        if st.button("🔄 Forzar Sincronización DB"):
            st.cache_data.clear(); st.rerun()

    df_f = prods_all.copy()
    if bus_u: df_f = df_f[df_f['ubicacion'].astype(str).str.contains(bus_u, case=False)]
    if bus_t: df_f = df_f[df_f['tipo'].astype(str).str.contains(bus_t, case=False)]

    # Usamos los pesos reales de base_datos
    pesos = obtener_pesos_seguimiento()
    
    def calc_avance(df_m, df_s):
        if df_m.empty: return 0.0
        ids_v = df_m['id'].tolist()
        db_v = df_s[df_s['producto_id'].isin(ids_v)].drop_duplicates(subset=['producto_id', 'hito'])
        pts_db = sum([pesos.get(h, 0) for h in db_v['hito']])
        return round(pts_db / len(df_m), 2)

    # --- 5. PREPARACIÓN DE MATRIZ ---
    df_editor = df_f.copy()
    for h in HITOS_LIST:
        df_editor[h] = df_editor['id'].apply(lambda x: True if not segs[(segs['producto_id'] == x) & (segs['hito'] == h)].empty else False)
    
    # Nota: vinculamos la nota al hito "Diseñado" (Hito 0) como estándar de almacenamiento
    df_editor['Notas'] = df_editor['id'].apply(
        lambda x: segs[(segs['producto_id'] == x) & (segs['hito'] == HITOS_LIST[0])]['observaciones'].iloc[0] 
        if not segs[(segs['producto_id'] == x) & (segs['hito'] == HITOS_LIST[0])].empty else ""
    )

    # --- 6. FORMULARIO DE GUARDADO ---
    st.divider()
    c1, c2, c3 = st.columns([1.5, 1, 1])
    f_reg = c1.date_input("Fecha aplicación", datetime.now(), format="DD/MM/YYYY")
    c2.metric("Av. Parcial", f"{calc_avance(df_f, segs)}%")
    c3.metric("Av. Global", f"{calc_avance(prods_all, segs)}%")

    # IMPORTANTE: st.form evita que la app "piense" en cada click
    with st.form(key=f"f_save_{id_p}_{st.session_state.ref_matriz}"):
        cambios_df = st.data_editor(
            df_editor,
            column_config={
                "id": None,
                "ubicacion": st.column_config.TextColumn("Ubicación", disabled=True),
                "tipo": st.column_config.TextColumn("Tipo", disabled=True),
                "ctd": st.column_config.NumberColumn("Cant.", disabled=True),
                "ml": st.column_config.NumberColumn("ML", disabled=True),
                **{h: st.column_config.CheckboxColumn(h) for h in HITOS_LIST}
            },
            disabled=['id', 'ubicacion', 'tipo', 'ctd', 'ml'],
            hide_index=True,
            use_container_width=True
        )
        submitted = st.form_submit_button("💾 GUARDAR CAMBIOS DEFINITIVOS", type="primary", use_container_width=True)

    if submitted:
        lote_upsert = []
        lote_delete = []
        rol_u = str(st.session_state.get('rol', 'Supervisor')).strip().lower()
        es_jefe = rol_u in ["admin", "gerente", "administrador"]

        # Procesamos por ID de producto (No por índice, para evitar errores con filtros)
        for _, row in cambios_df.iterrows():
            pid = int(row['id'])
            original_row = df_editor[df_editor['id'] == pid].iloc[0]
            
            for h in HITOS_LIST:
                v_orig = bool(original_row[h])
                v_nuev = bool(row[h])
                
                # Caso A: Marcar nuevo hito o mantener uno existente (evitando borrar notas)
                if v_nuev:
                    # Buscamos si ya existe el registro en la DB para preservar su info
                    match_db = segs[(segs['producto_id'] == pid) & (segs['hito'] == h)]
                    fecha_val = match_db['fecha'].iloc[0] if not match_db.empty else f_reg.strftime("%d/%m/%Y")
                    obs_val = row['Notas'] if h == HITOS_LIST[0] else (match_db['observaciones'].iloc[0] if not match_db.empty else "")
                    
                    lote_upsert.append({
                        "producto_id": pid,
                        "hito": h,
                        "fecha": fecha_val,
                        "observaciones": obs_val,
                        "supervisor_id": supervisor_id
                    })
                
                # Caso B: Desmarcar (Solo Jefes)
                elif not v_nuev and v_orig and es_jefe:
                    lote_delete.append({"pid": pid, "hito": h})

        try:
            with st.status("📡 Sincronizando con Supabase...") as status:
                if lote_delete:
                    for d in lote_delete:
                        supabase.table("seguimiento").delete().eq("producto_id", d['pid']).eq("hito", d['hito']).execute()
                
                if lote_upsert:
                    supabase.table("seguimiento").upsert(lote_upsert, on_conflict="producto_id, hito").execute()
                
                # Actualizar motor estructural
                from base_datos import sincronizar_avances_estructural
                sincronizar_avances_estructural(st.session_state.p_nom_sel.split(']')[0][1:])
                
                status.update(label="✅ Éxito: Datos protegidos y guardados", state="complete")
            
            st.cache_data.clear()
            st.session_state.ref_matriz += 1
            st.rerun()
        except Exception as e:
            st.error(f"Error crítico: {e}")
