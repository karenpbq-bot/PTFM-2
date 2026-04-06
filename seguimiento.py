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
    # --- A. MEMORIA TEMPORAL ---
    if 'cambios_pendientes' not in st.session_state:
        st.session_state.cambios_pendientes = []
    if 'notas_pendientes' not in st.session_state:
        st.session_state.notas_pendientes = {}

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
    nombre_proy_act = st.session_state.get('p_nom_sel', "Ninguno")
    st.markdown("### Seguimiento de Avances")
    st.markdown(f"<p style='font-size: 16px; color: #666; margin-top: -15px;'>{nombre_proy_act}</p>", unsafe_allow_html=True)

    with st.expander("🔍 Búsqueda de Proyecto", expanded=not st.session_state.get('id_p_sel')):
        c1, c2 = st.columns([2, 1])
        bus_p = c1.text_input("Escribe nombre, código o cliente...", key="bus_seg_v2")
        df_p_all = obtener_proyectos(bus_p)
        
        if supervisor_id and not df_p_all.empty:
            df_p_all = df_p_all[df_p_all['supervisor_id'] == supervisor_id]

        if not df_p_all.empty:
            opciones = {f"[{r['codigo']}] {r['proyecto_text']} - {r['cliente']}": r['id'] for _, r in df_p_all.iterrows()}
            lista_opc = ["-- Seleccionar --"] + list(opciones.keys())
            idx_s = lista_opc.index(st.session_state.p_nom_sel) if st.session_state.get('p_nom_sel') in lista_opc else 0
            sel_n = c2.selectbox("Seleccione Proyecto:", lista_opc, index=idx_s, key="sel_proy_seg")
            
            if sel_n != "-- Seleccionar --":
                st.session_state.id_p_sel = opciones[sel_n]
                st.session_state.p_nom_sel = sel_n
            else:
                st.session_state.id_p_sel = None

    if not st.session_state.get('id_p_sel'):
        st.info("💡 Por favor, seleccione un proyecto."); return

    # --- D. CARGA DE DATOS (FRESH DATA SIN CACHÉ) ---
    id_p = st.session_state.id_p_sel
    prods_all = obtener_productos_por_proyecto(id_p)
    if prods_all.empty: st.warning("Sin productos."); return

    res_db = supabase.table("seguimiento").select("*").in_("producto_id", prods_all['id'].tolist()).execute()
    segs = pd.DataFrame(res_db.data) if res_db.data else pd.DataFrame(columns=['producto_id','hito','fecha','observaciones'])

    # --- E. HERRAMIENTAS ---
    pesos_base = obtener_pesos_seguimiento()
    pesos = {h: float(pesos_base.get(h, 12.5)) for h in HITOS_LIST}

    with st.expander("⚙️ Configuración Avanzada y Herramientas"):
        t1, t2, t3, t4 = st.tabs(["⚖️ Ponderación", "🔍 Filtros", "📥 Importar", "📤 Exportación"])
        
        with t1:
            cols_w = st.columns(4)
            for i, h in enumerate(HITOS_LIST):
                pesos[h] = cols_w[i % 4].number_input(f"{h} (%)", value=pesos[h], step=0.5, key=f"peso_{h}")
        
        with t2:
            f1, f2, f3 = st.columns(3)
            agrupar_por = f1.selectbox("Agrupar por:", ["Sin grupo", "Ubicación", "Tipo"], key="agrupar_seg")
            bus_c1 = f2.text_input("Filtro Primario:", key="f_pri_seg")
            bus_c2 = f3.text_input("Refinar Búsqueda:", key="f_ref_seg")

        # ... (T3 Importar y T4 Exportar se mantienen con tu lógica original)

    # --- FILTRADO ---
    df_f = prods_all.copy()
    if bus_c1: df_f = df_f[df_f['ubicacion'].str.contains(bus_c1, case=False) | df_f['tipo'].str.contains(bus_c1, case=False)]
    if bus_c2: df_f = df_f[df_f['ubicacion'].str.contains(bus_c2, case=False) | df_f['tipo'].str.contains(bus_c2, case=False)]

    # --- F. CÁLCULO DE AVANCE (LÓGICA BLINDADA) ---
    def calc_avance(df_m, df_s):
        if df_m.empty: return 0.0
        ids_v = df_m['id'].tolist()
        db_v = df_s[df_s['producto_id'].isin(ids_v)].drop_duplicates(subset=['producto_id', 'hito'])
        p_db = sum([pesos.get(h, 0) for h in db_v['hito']])
        # Sumamos memoria solo si el hito no está ya en DB
        p_mem = 0
        for c in st.session_state.cambios_pendientes:
            if c['pid'] in ids_v:
                ya_esta = not db_v[(db_v['producto_id'] == c['pid']) & (db_v['hito'] == c['hito'])].empty
                if not ya_esta: p_mem += pesos.get(c['hito'], 0)
        return round((p_db + p_mem) / len(df_m), 2)

    p_tot, p_par = calc_avance(prods_all, segs), calc_avance(df_f, segs)

    # --- G. FILA DE ACCIONES ---
    st.divider()
    rol_usuario = str(st.session_state.get('rol', 'Supervisor')).strip().lower()
    es_jefe = rol_usuario in ["admin", "gerente", "administrador"]

    cols_acc = st.columns([1.5, 0.8, 0.8, 1, 1, 1])
    f_reg = cols_acc[0].date_input("Fecha Registro", datetime.now(), format="DD/MM/YYYY")
    cols_acc[1].metric("Av. Parcial", f"{p_par}%")
    cols_acc[2].metric("Av. Global", f"{p_tot}%")
    
    if cols_acc[3].button("🔄 Refrescar", use_container_width=True):
        st.cache_data.clear(); st.rerun()

    if cols_acc[4].button("💾 Guardar Avances", type="primary", use_container_width=True):
        if st.session_state.cambios_pendientes or st.session_state.notas_pendientes:
            with st.status("🚀 Sincronizando Avances...") as status:
                f_hoy = f_reg.strftime("%d/%m/%Y")
                # Guardar Hitos
                if st.session_state.cambios_pendientes:
                    lote = [{"producto_id": int(c['pid']), "hito": c['hito'], "fecha": f_hoy} for c in st.session_state.cambios_pendientes]
                    supabase.table("seguimiento").upsert(lote, on_conflict="producto_id, hito").execute()
                # Guardar Notas
                if st.session_state.notas_pendientes:
                    for pid, txt in st.session_state.notas_pendientes.items():
                        supabase.table("seguimiento").upsert({"producto_id": int(pid), "hito": HITOS_LIST[0], "observaciones": txt}, on_conflict="producto_id, hito").execute()
                
                from base_datos import sincronizar_avances_estructural
                p_cod = df_p_all[df_p_all['id'] == id_p].iloc[0]['codigo']
                sincronizar_avances_estructural(p_cod)
                status.update(label="✅ Avance guardado", state="complete")
            
            st.session_state.cambios_pendientes = []
            st.session_state.notas_pendientes = {}
            st.cache_data.clear(); st.rerun()

    if cols_acc[5].button("🚫 Limpiar Selección", use_container_width=True):
        st.session_state.cambios_pendientes = []; st.rerun()

    # --- H. MATRIZ (CON FORMULARIO PARA EVITAR PARPADEO) ---
    st.markdown('<div class="sticky-top">', unsafe_allow_html=True)
    cols_h = st.columns([2.5] + [0.7]*8 + [1.5])
    cols_h[0].write("**Producto**")
    for i, h in enumerate(HITOS_LIST): cols_h[i+1].write(MAPEO_HITOS[h])
    cols_h[-1].write("**Notas**")
    st.markdown('</div>', unsafe_allow_html=True)

    def render_matriz(df_r):
        # El formulario permite marcar todo y procesar en un solo 'Confirmar'
        with st.form(key=f"form_grupo_{df_r.index[0]}"):
            for _, p in df_r.iterrows():
                cols = st.columns([2.5] + [0.7]*8 + [1.5])
                cols[0].write(f"<p style='font-size:11px;'>{p['ubicacion']} | {p['tipo']}</p>", unsafe_allow_html=True)
                
                for i, h in enumerate(HITOS_LIST):
                    en_db = not segs[(segs['producto_id'] == p['id']) & (segs['hito'] == h)].empty
                    idx_mem = next((idx for idx, d in enumerate(st.session_state.cambios_pendientes) if d["pid"] == p['id'] and d["hito"] == h), None)
                    
                    existe = en_db or (idx_mem is not None)
                    bloqueado = (en_db and not es_jefe) # Gris si ya está en DB
                    
                    if cols[i+1].checkbox("", key=f"c_{p['id']}_{h}", value=existe, disabled=bloqueado, label_visibility="collapsed"):
                        if not existe: st.session_state.cambios_pendientes.append({"pid": p['id'], "hito": h})
                    elif idx_mem is not None:
                        st.session_state.cambios_pendientes.pop(idx_mem)

                # Notas
                n_db = segs[(segs['producto_id'] == p['id']) & (segs['hito'] == HITOS_LIST[0])]['observaciones'].iloc[0] if not segs[(segs['producto_id'] == p['id']) & (segs['hito'] == HITOS_LIST[0])].empty else ""
                n_act = st.session_state.notas_pendientes.get(str(p['id']), n_db if pd.notnull(n_db) else "")
                nueva = cols[-1].text_input("N", value=n_act, key=f"nt_{p['id']}", label_visibility="collapsed")
                if nueva != n_act: st.session_state.notas_pendientes[str(p['id'])] = nueva

            if st.form_submit_button("📎 Confirmar marcaciones de este grupo", use_container_width=True):
                st.rerun()

    # --- EJECUCIÓN FINAL ---
    st.markdown('<div class="scroll-area">', unsafe_allow_html=True)
    if agrupar_por != "Sin grupo":
        campo = "ubicacion" if agrupar_por == "Ubicación" else "tipo"
        for n, g in df_f.groupby(campo):
            st.markdown(f"**📂 {n}**"); render_matriz(g)
    else: render_matriz(df_f)
    st.markdown('</div>', unsafe_allow_html=True)
