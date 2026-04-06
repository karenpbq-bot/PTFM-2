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
    # --- A. ESTADOS DE SESIÓN ---
    if 'cambios_pendientes' not in st.session_state:
        st.session_state.cambios_pendientes = []
    if 'notas_pendientes' not in st.session_state:
        st.session_state.notas_pendientes = {}
    if 'ref_matriz' not in st.session_state:
        st.session_state.ref_matriz = 0

    # --- B. ESTILOS ---
    st.markdown("""
        <style>
        .sticky-top { position: sticky; top: 0; background: white; z-index: 1000; padding: 10px 0; border-bottom: 3px solid #FF8C00; }
        .scroll-area { max-height: 550px; overflow-y: auto; border: 1px solid #eee; padding: 10px; border-radius: 5px; }
        [data-testid="stMetricValue"] { color: #FF8C00 !important; font-weight: bold !important; font-size: 24px !important; }
        </style>
    """, unsafe_allow_html=True)

    supabase = conectar()

    # --- C. BÚSQUEDA DE PROYECTO ---
    nombre_p_act = st.session_state.get('p_nom_sel', "Ninguno")
    st.markdown("### Seguimiento de Avances")
    st.markdown(f"<p style='font-size: 16px; color: #666; margin-top: -15px;'>{nombre_p_act}</p>", unsafe_allow_html=True)

    with st.expander("🔍 Búsqueda de Proyecto", expanded=not st.session_state.get('id_p_sel')):
        c1, c2 = st.columns([2, 1])
        bus_p = c1.text_input("Escribe nombre, código o cliente...", key="bus_seg_vFINAL")
        df_p_all = obtener_proyectos(bus_p)
        if supervisor_id and not df_p_all.empty:
            df_p_all = df_p_all[df_p_all['supervisor_id'] == supervisor_id]

        if not df_p_all.empty:
            opciones = {f"[{r['codigo']}] {r['proyecto_text']} - {r['cliente']}": r['id'] for _, r in df_p_all.iterrows()}
            lista_opc = ["-- Seleccionar --"] + list(opciones.keys())
            idx_s = lista_opc.index(st.session_state.p_nom_sel) if st.session_state.get('p_nom_sel') in lista_opc else 0
            sel_n = c2.selectbox("Seleccione Proyecto:", lista_opc, index=idx_s)
            if sel_n != "-- Seleccionar --":
                st.session_state.id_p_sel, st.session_state.p_nom_sel = opciones[sel_n], sel_n
            else: st.session_state.id_p_sel = None

    if not st.session_state.get('id_p_sel'):
        st.info("💡 Por favor, seleccione un proyecto."); return

    # --- D. CARGA DE DATOS ---
    id_p = st.session_state.id_p_sel
    prods_all = obtener_productos_por_proyecto(id_p)
    res_db = supabase.table("seguimiento").select("*").in_("producto_id", prods_all['id'].tolist()).execute()
    segs = pd.DataFrame(res_db.data) if res_db.data else pd.DataFrame(columns=['producto_id','hito','fecha','observaciones'])

    # --- E. HERRAMIENTAS (RECUPERADAS: IMPORT/EXPORT/PESOS/FILTROS) ---
    pesos_base = obtener_pesos_seguimiento()
    pesos = {h: float(pesos_base.get(h, 12.5)) for h in HITOS_LIST}

    with st.expander("⚙️ Herramientas y Gestión Masiva"):
        t1, t2, t3, t4 = st.tabs(["⚖️ Ponderación", "🔍 Filtros", "📥 Importar", "📤 Exportación"])
        with t1:
            cols_w = st.columns(4)
            for i, h in enumerate(HITOS_LIST):
                pesos[h] = cols_w[i % 4].number_input(f"{h} (%)", value=pesos[h], step=0.5, key=f"pw_{h}")
        with t2:
            f1, f2, f3 = st.columns(3)
            agrupar_por = f1.selectbox("Agrupar por:", ["Sin grupo", "Ubicación", "Tipo"])
            bus_c1 = f2.text_input("Filtro Primario:", key="f_pri_final")
            bus_c2 = f3.text_input("Refinar Búsqueda:", key="f_ref_final")
        with t3:
            st.write("**Actualización masiva desde Excel**")
            f_av = st.file_uploader("Subir archivo (.xlsx)", type=["xlsx"], key="up_excel_final")
            if f_av and st.button("🚀 Iniciar Importación"):
                try:
                    df_imp = pd.read_excel(f_av)
                    lote_imp = []
                    for _, r_ex in df_imp.iterrows():
                        u, t = str(r_ex.get('ubicacion','')).strip(), str(r_ex.get('tipo','')).strip()
                        match = prods_all[(prods_all['ubicacion'].astype(str).str.strip() == u) & (prods_all['tipo'].astype(str).str.strip() == t)]
                        if not match.empty:
                            pid = int(match.iloc[0]['id'])
                            for h_nom in HITOS_LIST:
                                if h_nom in r_ex and pd.notnull(r_ex[h_nom]) and str(r_ex[h_nom]).strip().upper() in ["X", "1", "SI"]:
                                    lote_imp.append({"producto_id": pid, "hito": h_nom, "fecha": datetime.now().strftime("%d/%m/%Y"), "supervisor_id": supervisor_id})
                    if lote_imp:
                        supabase.table("seguimiento").upsert(lote_imp, on_conflict="producto_id, hito").execute()
                        st.success("Importación completada."); st.cache_data.clear(); st.rerun()
                except Exception as e: st.error(f"Error: {e}")
        with t4:
            df_exp = prods_all.copy()
            for h in HITOS_LIST: 
                df_exp[h] = df_exp['id'].apply(lambda x: segs[(segs['producto_id']==x) & (segs['hito']==h)]['fecha'].iloc[0] if not segs[(segs['producto_id']==x) & (segs['hito']==h)].empty else "")
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_exp[['ubicacion', 'tipo', 'ctd', 'ml'] + HITOS_LIST].to_excel(writer, index=False)
            st.download_button("📥 Descargar Reporte", data=output.getvalue(), file_name=f"Avance_{id_p}.xlsx", use_container_width=True)

    # FILTRADO
    df_f = prods_all.copy()
    if bus_c1: df_f = df_f[df_f['ubicacion'].str.contains(bus_c1, case=False) | df_f['tipo'].str.contains(bus_c1, case=False)]
    if bus_c2: df_f = df_f[df_f['ubicacion'].str.contains(bus_c2, case=False) | df_f['tipo'].str.contains(bus_c2, case=False)]

    # --- F. PREPARACIÓN DE LA TABLA Y CÁLCULOS ---
    def calc_avance(df_m, df_s):
        if df_m.empty: return 0.0
        ids_v = df_m['id'].tolist()
        # Filtramos solo lo que está en la DB
        db_v = df_s[df_s['producto_id'].isin(ids_v)].drop_duplicates(subset=['producto_id', 'hito'])
        pts_db = sum([pesos.get(h, 0) for h in db_v['hito']])
        return round(pts_db / len(df_m), 2)

    # Determinación de Rol
    rol_u = str(st.session_state.get('rol', 'Supervisor')).strip().lower()
    es_jefe = rol_u in ["admin", "gerente", "administrador"]

    # Construcción de la matriz base (Lectura real de segs)
    df_editor = df_f.copy()
    for h in HITOS_LIST:
        df_editor[h] = df_editor['id'].apply(
            lambda x: True if not segs[(segs['producto_id'] == x) & (segs['hito'] == h)].empty else False
        )
    
    # Notas integradas en la matriz
    df_editor['Notas'] = df_editor['id'].apply(
        lambda x: segs[(segs['producto_id'] == x) & (segs['hito'] == HITOS_LIST[0])]['observaciones'].iloc[0] if not segs[(segs['producto_id'] == x) & (segs['hito'] == HITOS_LIST[0])].empty else ""
    )

    # --- G. MÉTRICAS ---
    st.divider()
    c1, c2, c3, c4 = st.columns([1.5, 1, 1, 1])
    f_reg = c1.date_input("Fecha de Registro", datetime.now(), format="DD/MM/YYYY")
    
    p_tot, p_par = calc_avance(prods_all, segs), calc_avance(df_f, segs)
    c2.metric("Av. Parcial", f"{p_par}%")
    c3.metric("Av. Global", f"{p_tot}%")

    if c4.button("🔄 Refrescar", use_container_width=True):
        st.cache_data.clear(); st.rerun()

    # --- H. MATRIZ INTELIGENTE ---
    cols_fijas = ['id', 'ubicacion', 'tipo', 'ctd', 'ml']
    
    cambios_df = st.data_editor(
        df_editor,
        column_config={
            "id": None,
            "ubicacion": st.column_config.TextColumn("Ubicación", disabled=True),
            "tipo": st.column_config.TextColumn("Tipo", disabled=True),
            "ctd": st.column_config.NumberColumn("Cant.", disabled=True),
            "ml": st.column_config.NumberColumn("ML", disabled=True),
            "Notas": st.column_config.TextColumn("Notas", width="medium"),
            **{h: st.column_config.CheckboxColumn(h) for h in HITOS_LIST}
        },
        disabled=cols_fijas, # Los hitos quedan libres para marcar
        hide_index=True,
        use_container_width=True,
        key=f"ed_{id_p}_{st.session_state.ref_matriz}"
    )

    # --- I. GUARDADO MASIVO ---
    if st.button("💾 GUARDAR CAMBIOS EN NUBE", type="primary", use_container_width=True):
        lote_ins, lote_del, lote_not = [], [], []

        for idx in range(len(df_editor)):
            pid = int(df_editor.iloc[idx]['id'])
            for h in HITOS_LIST:
                v_orig = bool(df_editor.iloc[idx][h])
                v_nuev = bool(cambios_df.iloc[idx][h])

                if v_nuev and not v_orig:
                    lote_ins.append({"producto_id": pid, "hito": h, "fecha": f_reg.strftime("%d/%m/%Y")})
                elif not v_nuev and v_orig and es_jefe:
                    lote_del.append({"pid": pid, "hito": h})
            
            # Comparación de Notas
            n_orig, n_nuev = str(df_editor.iloc[idx]['Notas']), str(cambios_df.iloc[idx]['Notas'])
            if n_nuev != n_orig: lote_not.append({"pid": pid, "txt": n_nuev})

        if lote_ins or lote_del or lote_not:
            try:
                with st.status("📡 Grabando...") as status:
                    for d in lote_del:
                        supabase.table("seguimiento").delete().eq("producto_id", d['pid']).eq("hito", d['hito']).execute()
                    if lote_ins:
                        try:
                            lote_f = [dict(x, supervisor_id=supervisor_id) for x in lote_ins]
                            supabase.table("seguimiento").upsert(lote_f, on_conflict="producto_id, hito").execute()
                        except:
                            supabase.table("seguimiento").upsert(lote_ins, on_conflict="producto_id, hito").execute()
                    for n in lote_not:
                        supabase.table("seguimiento").upsert({"producto_id": n['pid'], "hito": HITOS_LIST[0], "observaciones": n['txt']}, on_conflict="producto_id, hito").execute()
                    
                    from base_datos import sincronizar_avances_estructural
                    sincronizar_avances_estructural(df_p_all[df_p_all['id'] == id_p].iloc[0]['codigo'])
                    status.update(label="✅ Éxito", state="complete")
                st.cache_data.clear(); st.session_state.ref_matriz += 1; st.rerun()
            except Exception as e: st.error(f"Fallo: {e}")
        else:
            st.info("No se detectaron cambios nuevos para guardar.")
