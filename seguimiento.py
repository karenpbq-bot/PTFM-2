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

    # --- F. CÁLCULO DE AVANCE ---
    def calc_avance(df_m, df_s):
        if df_m.empty: return 0.0
        ids_v = df_m['id'].tolist()
        db_v = df_s[df_s['producto_id'].isin(ids_v)].drop_duplicates(subset=['producto_id', 'hito'])
        pts_db = sum([pesos.get(h, 0) for h in db_v['hito']])
        pts_mem = sum([pesos.get(c['hito'], 0) for c in st.session_state.cambios_pendientes if c['pid'] in ids_v and db_v[(db_v['producto_id']==c['pid']) & (db_v['hito']==c['hito'])].empty])
        return round((pts_db + pts_mem) / len(df_m), 2)

    p_tot, p_par = calc_avance(prods_all, segs), calc_avance(df_f, segs)

    # --- G. FILA DE ACCIONES ---
    st.divider()
    rol_u = str(st.session_state.get('rol', 'Supervisor')).strip().lower()
    es_jefe = rol_u in ["admin", "gerente", "administrador"]

    cols_acc = st.columns([1.5, 0.7, 0.7, 0.8, 1, 1])
    f_reg = cols_acc[0].date_input("Fecha Registro", datetime.now(), format="DD/MM/YYYY")
    cols_acc[1].metric("Av. Parcial", f"{p_par}%")
    cols_acc[2].metric("Av. Global", f"{p_tot}%")
    
    if cols_acc[3].button("🔄 Refrescar", use_container_width=True):
        st.session_state.cambios_pendientes = []
        st.session_state.ref_matriz += 1
        st.cache_data.clear(); st.rerun()

    if cols_acc[4].button("💾 GUARDAR AVANCES", type="primary", use_container_width=True):
        if st.session_state.cambios_pendientes or st.session_state.get('borrados_pendientes'):
            try:
                with st.status("🚀 Sincronizando...") as status:
                    f_str = f_reg.strftime("%d/%m/%Y")
                    
                    # 1. ELIMINACIONES (Solo Admin/Gerente)
                    if es_jefe and st.session_state.get('borrados_pendientes'):
                        for b in st.session_state.borrados_pendientes:
                            supabase.table("seguimiento").delete().eq("producto_id", b['pid']).eq("hito", b['hito']).execute()
                        st.session_state.borrados_pendientes = []

                    # 2. INSERCIONES/ACTUALIZACIONES
                    if st.session_state.cambios_pendientes:
                        lote = [{"producto_id": int(c['pid']), "hito": str(c['hito']), "fecha": f_str} for c in st.session_state.cambios_pendientes]
                        # Intento robusto para evitar error PGRST204
                        try:
                            lote_sup = [dict(d, supervisor_id=supervisor_id) for d in lote]
                            supabase.table("seguimiento").upsert(lote_sup, on_conflict="producto_id, hito").execute()
                        except:
                            supabase.table("seguimiento").upsert(lote, on_conflict="producto_id, hito").execute()

                    # 3. NOTAS
                    if st.session_state.notas_pendientes:
                        for pid, txt in st.session_state.notas_pendientes.items():
                            supabase.table("seguimiento").upsert({"producto_id": int(pid), "hito": HITOS_LIST[0], "observaciones": str(txt)}, on_conflict="producto_id, hito").execute()
                    
                    from base_datos import sincronizar_avances_estructural
                    sincronizar_avances_estructural(df_p_all[df_p_all['id'] == id_p].iloc[0]['codigo'])
                    status.update(label="✅ Éxito al guardar", state="complete")
                
                st.session_state.cambios_pendientes = []
                st.session_state.notas_pendientes = {}
                st.session_state.ref_matriz += 1
                st.cache_data.clear(); st.rerun()
            except Exception as e:
                st.error(f"❌ Error crítico: {e}")
        else:
            st.warning("No hay cambios para guardar.")

    if cols_acc[5].button("🚫 Limpiar Selección", use_container_width=True):
        st.session_state.cambios_pendientes = []
        st.session_state.ref_matriz += 1; st.rerun()

    # --- H. MATRIZ DINÁMICA ---
    if 'borrados_pendientes' not in st.session_state: st.session_state.borrados_pendientes = []

    st.markdown('<div class="sticky-top">', unsafe_allow_html=True)
    cols_h = st.columns([2.5] + [0.7]*8 + [1.5])
    cols_h[0].write("**Producto**")
    for i, h in enumerate(HITOS_LIST): cols_h[i+1].write(MAPEO_HITOS[h])
    cols_h[-1].write("**Notas**")
    st.markdown('</div>', unsafe_allow_html=True)

    def render_matriz(df_r):
        with st.form(key=f"f_v_{df_r.index[0]}_{st.session_state.ref_matriz}"):
            res_form = {}
            for _, p in df_r.iterrows():
                cols = st.columns([2.5] + [0.7]*8 + [1.5])
                cols[0].write(f"<p style='font-size:11px;'>{p['ubicacion']} | {p['tipo']}</p>", unsafe_allow_html=True)
                for i, h in enumerate(HITOS_LIST):
                    en_db = not segs[(segs['producto_id'] == p['id']) & (segs['hito'] == h)].empty
                    en_mem = any(c['pid'] == p['id'] and c['hito'] == h for c in st.session_state.cambios_pendientes)
                    en_borrado = any(b['pid'] == p['id'] and b['hito'] == h for b in st.session_state.borrados_pendientes)
                    
                    bloqueado = (en_db and not es_jefe)
                    k = f"{p['id']}_{h}"
                    # El valor del checkbox es True si está en DB (y no marcado para borrar) O si está en memoria roja
                    val = (en_db and not en_borrado) or en_mem
                    res_form[k] = cols[i+1].checkbox("", key=f"c_{k}_{st.session_state.ref_matriz}", value=val, disabled=bloqueado, label_visibility="collapsed")
                
                n_db = segs[(segs['producto_id'] == p['id']) & (segs['hito'] == HITOS_LIST[0])]['observaciones'].iloc[0] if not segs[(segs['producto_id'] == p['id']) & (segs['hito'] == HITOS_LIST[0])].empty else ""
                n_act = st.session_state.notas_pendientes.get(str(p['id']), n_db if pd.notnull(n_db) else "")
                st.session_state.notas_pendientes[str(p['id'])] = cols[-1].text_input("N", value=n_act, key=f"nt_{p['id']}_{st.session_state.ref_matriz}", label_visibility="collapsed")

            if st.form_submit_button("📎 Confirmar marcaciones de este grupo", use_container_width=True):
                for key_id, valor_check in res_form.items():
                    pid_f, hito_f = key_id.split("_", 1)
                    pid_f = int(pid_f)
                    ya_en_db = not segs[(segs['producto_id'] == pid_f) & (segs['hito'] == hito_f)].empty
                    
                    # 1. Lógica de Adición a Memoria Roja
                    if valor_check and not ya_en_db:
                        if not any(c['pid'] == pid_f and c['hito'] == hito_f for c in st.session_state.cambios_pendientes):
                            st.session_state.cambios_pendientes.append({"pid": pid_f, "hito": hito_f})
                        st.session_state.borrados_pendientes = [b for b in st.session_state.borrados_pendientes if not (b['pid'] == pid_f and b['hito'] == hito_f)]
                    
                    # 2. Lógica de Marcado para Borrar (Solo Admin/Gerente)
                    elif not valor_check and ya_en_db and es_jefe:
                        if not any(b['pid'] == pid_f and b['hito'] == hito_f for b in st.session_state.borrados_pendientes):
                            st.session_state.borrados_pendientes.append({"pid": pid_f, "hito": hito_f})
                        st.session_state.cambios_pendientes = [c for c in st.session_state.cambios_pendientes if not (c['pid'] == pid_f and c['hito'] == hito_f)]
                    
                    # 3. Quitar de Memoria Roja si se desmarca
                    elif not valor_check and not ya_en_db:
                        st.session_state.cambios_pendientes = [c for c in st.session_state.cambios_pendientes if not (c['pid'] == pid_f and c['hito'] == hito_f)]
                st.rerun()

    st.markdown('<div class="scroll-area">', unsafe_allow_html=True)
    if agrupar_por != "Sin grupo":
        campo = "ubicacion" if agrupar_por == "Ubicación" else "tipo"
        for n, g in df_f.groupby(campo):
            st.markdown(f"**📂 {n}**"); render_matriz(g)
    else: render_matriz(df_f)
    st.markdown('</div>', unsafe_allow_html=True)
