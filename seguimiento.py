import streamlit as st
import pandas as pd
from datetime import datetime
import io
from base_datos import conectar, obtener_proyectos, obtener_productos_por_proyecto, obtener_seguimiento, obtener_pesos_seguimiento

# =========================================================
# 1. CONFIGURACIÓN Y DICCIONARIOS MAESTROS
# =========================================================
MAPEO_HITOS = {
    "Diseñado": "🗺️", "Fabricado": "🪚", "Material en Obra": "🚛",
    "Material en Ubicación": "📍", "Instalación de Estructura": "📦", 
    "Instalación de Puertas o Frentes": "🗄️", "Revisión y Observaciones": "🔍", "Entrega": "🤝"
}
HITOS_LIST = list(MAPEO_HITOS.keys())

def mostrar(supervisor_id=None):
    # --- A. MEMORIA TEMPORAL (SESIÓN) ---
    if 'cambios_pendientes' not in st.session_state:
        st.session_state.cambios_pendientes = []
    if 'notas_pendientes' not in st.session_state:
        st.session_state.notas_pendientes = {}

    # --- B. ESTILOS CSS ---
    st.markdown("""
        <style>
        .sticky-top { position: sticky; top: 0; background: white; z-index: 1000; padding: 10px 0; border-bottom: 3px solid #FF8C00; }
        .scroll-area { max-height: 550px; overflow-y: auto; border: 1px solid #eee; padding: 10px; border-radius: 5px; }
        [data-testid="stMetricValue"] { color: #FF8C00 !important; font-weight: bold !important; font-size: 24px !important; }
        </style>
    """, unsafe_allow_html=True)

    supabase = conectar()

    # --- C. SELECCIÓN DE PROYECTO ---
    nombre_p_act = st.session_state.get('p_nom_sel', "Ninguno")
    st.markdown("### Seguimiento de Avances")
    st.markdown(f"<p style='color: #666; margin-top: -15px;'>{nombre_p_act}</p>", unsafe_allow_html=True)

    with st.expander("🔍 Selector de Proyecto", expanded=not st.session_state.get('id_p_sel')):
        c1, c2 = st.columns([2, 1])
        bus_p = c1.text_input("Buscar proyecto...", key="bus_seg_v2")
        df_p_all = obtener_proyectos(bus_p)
        
        if supervisor_id and not df_p_all.empty:
            df_p_all = df_p_all[df_p_all['supervisor_id'] == supervisor_id]

        if not df_p_all.empty:
            opciones = {f"[{r['codigo']}] {r['proyecto_text']}": r['id'] for _, r in df_p_all.iterrows()}
            lista_opc = ["-- Seleccionar --"] + list(opciones.keys())
            idx_s = lista_opc.index(st.session_state.p_nom_sel) if st.session_state.get('p_nom_sel') in lista_opc else 0
            sel_n = c2.selectbox("Proyecto:", lista_opc, index=idx_s, key="sel_proy_seg")
            
            if sel_n != "-- Seleccionar --":
                st.session_state.id_p_sel = opciones[sel_n]
                st.session_state.p_nom_sel = sel_n
            else:
                st.session_state.id_p_sel = None

    if not st.session_state.get('id_p_sel'):
        st.info("💡 Seleccione un proyecto para comenzar."); return

    # --- D. CARGA DE DATOS (FRESH DATA) ---
    id_p = st.session_state.id_p_sel
    prods_all = obtener_productos_por_proyecto(id_p)
    if prods_all.empty: st.warning("El proyecto no tiene productos."); return

    segs_res = supabase.table("seguimiento").select("*").in_("producto_id", prods_all['id'].tolist()).execute()
    segs = pd.DataFrame(segs_res.data) if segs_res.data else pd.DataFrame(columns=['producto_id','hito','fecha','observaciones'])

    # --- E. PONDERACIÓN Y HERRAMIENTAS ---
    pesos_base = obtener_pesos_seguimiento()
    pesos = {h: float(pesos_base.get(h, 12.5)) for h in HITOS_LIST}

    with st.expander("⚙️ Herramientas de Gestión"):
        t1, t2, t3, t4 = st.tabs(["⚖️ Ponderación", "🔍 Filtros", "📥 Importar", "📤 Exportar"])
        
        with t1:
            st.write("**Pesos de Avance (Lectura)**")
            cols_w = st.columns(4)
            for i, h in enumerate(HITOS_LIST):
                pesos[h] = cols_w[i % 4].number_input(f"{h} (%)", value=pesos[h], step=0.5, key=f"p_in_{h}")
        
        with t2:
            f1, f2 = st.columns(2)
            agrupar_por = f1.selectbox("Agrupar por:", ["Sin grupo", "Ubicación", "Tipo"])
            bus_filt = f2.text_input("Filtrar por nombre/tipo:", key="filt_matriz")

        with t3:
            st.write("**Carga masiva desde Excel**")
            f_av = st.file_uploader("Subir archivo", type=["xlsx", "csv"], key="up_excel")
            if f_av and st.button("🚀 Procesar Excel"):
                try:
                    df_imp = pd.read_excel(f_av) if f_av.name.endswith('xlsx') else pd.read_csv(f_av)
                    lote_imp = []
                    for _, r_ex in df_imp.iterrows():
                        u_ex, t_ex = str(r_ex.get('Ubicacion','')).strip(), str(r_ex.get('Tipo','')).strip()
                        match = prods_all[(prods_all['ubicacion'].astype(str).str.strip() == u_ex) & (prods_all['tipo'].astype(str).str.strip() == t_ex)]
                        if not match.empty:
                            pid = int(match.iloc[0]['id'])
                            for h_nom in HITOS_LIST:
                                if pd.notnull(r_ex.get(h_nom)) and str(r_ex.get(h_nom)).strip().upper() in ["X", "1", "SI", "OK"]:
                                    lote_imp.append({"producto_id": pid, "hito": h_nom, "fecha": datetime.now().strftime("%d/%m/%Y")})
                    if lote_imp:
                        supabase.table("seguimiento").upsert(lote_imp, on_conflict="producto_id, hito").execute()
                        st.success(f"Importados {len(lote_imp)} registros."); st.cache_data.clear(); st.rerun()
                except Exception as e: st.error(f"Error: {e}")

        with t4:
            df_exp = prods_all.copy()
            for h in HITOS_LIST: 
                df_exp[h] = df_exp['id'].apply(lambda x: segs[(segs['producto_id']==x) & (segs['hito']==h)]['fecha'].iloc[0] if not segs[(segs['producto_id']==x) & (segs['hito']==h)].empty else "")
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_exp[['ubicacion', 'tipo', 'ctd', 'ml'] + HITOS_LIST].to_excel(writer, index=False)
            st.download_button("📥 Descargar Avance", data=output.getvalue(), file_name=f"Avance_{id_p}.xlsx", use_container_width=True)

    # Filtrado lógico
    df_f = prods_all.copy()
    if bus_filt:
        df_f = df_f[df_f['ubicacion'].str.contains(bus_filt, case=False) | df_f['tipo'].str.contains(bus_filt, case=False)]

    # --- F. LÓGICA DE AVANCE ---
    def calc_avance(df_m, df_s):
        if df_m.empty: return 0.0
        ids_v = df_m['id'].tolist()
        db_v = df_s[df_s['producto_id'].isin(ids_v)].drop_duplicates(subset=['producto_id', 'hito'])
        p_db = sum([pesos.get(h, 0) for h in db_v['hito']])
        p_mem = sum([pesos.get(c['hito'], 0) for c in st.session_state.cambios_pendientes if c['pid'] in ids_v and db_v[(db_v['producto_id']==c['pid']) & (db_v['hito']==c['hito'])].empty])
        return round((p_db + p_mem) / len(df_m), 2)

    p_tot, p_par = calc_avance(prods_all, segs), calc_avance(df_f, segs)

    # --- G. ACCIONES PRINCIPALES ---
    st.divider()
    rol_u = str(st.session_state.get('rol', 'Supervisor')).strip().lower()
    es_jefe = rol_u in ["admin", "gerente", "administrador"]

    c1, c2, c3, c4, c5 = st.columns([1.5, 0.8, 0.8, 1, 1])
    f_reg = c1.date_input("Fecha Registro", datetime.now(), format="DD/MM/YYYY")
    c2.metric("Av. Parcial", f"{p_par}%")
    c3.metric("Av. Global", f"{p_tot}%")

    if c4.button("💾 GUARDAR", type="primary", use_container_width=True):
        if st.session_state.cambios_pendientes or st.session_state.notas_pendientes:
            with st.status("Sincronizando...") as s:
                f_str = f_reg.strftime("%d/%m/%Y")
                if st.session_state.cambios_pendientes:
                    lote = [{"producto_id": int(c['pid']), "hito": c['hito'], "fecha": f_str} for c in st.session_state.cambios_pendientes]
                    supabase.table("seguimiento").upsert(lote, on_conflict="producto_id, hito").execute()
                for pid, txt in st.session_state.notas_pendientes.items():
                    supabase.table("seguimiento").upsert({"producto_id": int(pid), "hito": HITOS_LIST[0], "observaciones": txt}, on_conflict="producto_id, hito").execute()
                from base_datos import sincronizar_avances_estructural
                p_cod = df_p_all[df_p_all['id'] == id_p].iloc[0]['codigo']
                sincronizar_avances_estructural(p_cod)
                s.update(label="✅ Sincronizado!", state="complete")
            st.session_state.cambios_pendientes, st.session_state.notas_pendientes = [], {}
            st.cache_data.clear(); st.rerun()

    if c5.button("🚫 LIMPIAR", use_container_width=True):
        st.session_state.cambios_pendientes, st.session_state.notas_pendientes = [], {}
        st.rerun()

    # --- H. MATRIZ DINÁMICA ---
    st.markdown('<div class="sticky-top">', unsafe_allow_html=True)
    cols_h = st.columns([2.5] + [0.7]*8 + [1.5])
    cols_h[0].write("**Producto**")
    for i, h in enumerate(HITOS_LIST): cols_h[i+1].write(MAPEO_HITOS[h])
    cols_h[-1].write("**Notas**")
    st.markdown('</div>', unsafe_allow_html=True)

    def render_matriz(df_r):
        for _, p in df_r.iterrows():
            cols = st.columns([2.5] + [0.7]*8 + [1.5])
            cols[0].write(f"<p style='font-size:12px;'><b>{p['ubicacion']}</b> | {p['tipo']}</p>", unsafe_allow_html=True)
            for i, h in enumerate(HITOS_LIST):
                en_db = not segs[(segs['producto_id'] == p['id']) & (segs['hito'] == h)].empty
                idx_mem = next((idx for idx, d in enumerate(st.session_state.cambios_pendientes) if d["pid"] == p['id'] and d["hito"] == h), None)
                existe, bloq = (en_db or idx_mem is not None), (en_db and not es_jefe)
                if cols[i+1].checkbox("", key=f"c_{p['id']}_{h}", value=existe, disabled=bloq, label_visibility="collapsed"):
                    if not existe: st.session_state.cambios_pendientes.append({"pid": p['id'], "hito": h}); st.rerun()
                else:
                    if idx_mem is not None: st.session_state.cambios_pendientes.pop(idx_mem); st.rerun()
            n_db = segs[(segs['producto_id'] == p['id']) & (segs['hito'] == HITOS_LIST[0])]['observaciones'].iloc[0] if not segs[(segs['producto_id'] == p['id']) & (segs['hito'] == HITOS_LIST[0])].empty else ""
            n_act = st.session_state.notas_pendientes.get(str(p['id']), n_db if pd.notnull(n_db) else "")
            nueva = cols[-1].text_input("N", value=n_act, key=f"nt_{p['id']}", label_visibility="collapsed")
            if nueva != n_act: st.session_state.notas_pendientes[str(p['id'])] = nueva

    st.markdown('<div class="scroll-area">', unsafe_allow_html=True)
    if agrupar_por != "Sin grupo":
        campo = "ubicacion" if agrupar_por == "Ubicación" else "tipo"
        for n, g in df_f.groupby(campo):
            st.markdown(f"**📂 {n}**"); render_matriz(g)
    else: render_matriz(df_f)
    st.markdown('</div>', unsafe_allow_html=True)
