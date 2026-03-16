import streamlit as st
import pandas as pd
from datetime import datetime
import io
from base_datos import conectar, obtener_proyectos, obtener_productos_por_proyecto, obtener_seguimiento, guardar_seguimiento

# =========================================================
# 1. CONFIGURACIÓN Y DICCIONARIOS MAESTROS
# =========================================================
MAPEO_HITOS = {
    "Diseñado": "🗺️", "Fabricado": "🪚", "Material en Obra": "🚛",
    "Material en Ubicación": "📍", "Instalación de Estructura": "📦", 
    "Instalación de Puertas o Frentes": "🗄️", "Revisión y Observaciones": "🔍", "Entrega": "🤝"
}

HITOS_LIST = list(MAPEO_HITOS.keys())

# =========================================================
# 2. LÓGICA DE CASCADA Y SEGURIDAD
# =========================================================
def registrar_hitos_cascada(p_id, hito_final, fecha_str):
    supabase = conectar()
    try:
        safe_p_id = int(p_id)
        idx_limite = HITOS_LIST.index(hito_final)
        hitos_a_marcar = HITOS_LIST[:idx_limite + 1]
        
        existentes = supabase.table("seguimiento").select("hito").eq("producto_id", safe_p_id).execute()
        hitos_con_data = [r['hito'] for r in existentes.data] if existentes.data else []

        for h in hitos_a_marcar:
            if h not in hitos_con_data:
                supabase.table("seguimiento").upsert({
                    "producto_id": safe_p_id, "hito": str(h), "fecha": str(fecha_str)
                }, on_conflict="producto_id, hito").execute()
    except Exception as e:
        st.error(f"Error en cascada: {e}")

# =========================================================
# 3. INTERFAZ PRINCIPAL
# =========================================================
def mostrar(supervisor_id=None):
    st.markdown("""
        <style>
        .sticky-top { position: sticky; top: 0; background: white; z-index: 1000; padding: 10px 0; border-bottom: 3px solid #FF8C00; }
        .scroll-area { max-height: 550px; overflow-y: auto; border: 1px solid #eee; padding: 10px; border-radius: 5px; }
        [data-testid="stMetricValue"] { color: #FF8C00 !important; font-weight: bold !important; font-size: 24px !important; }
        </style>
    """, unsafe_allow_html=True)
    
    supabase = conectar()

    # --- TÍTULO DINÁMICO (CORREGIDO) ---
    nombre_proy = st.session_state.get('p_nom_sel', "Ninguno")
    st.markdown(f"### Seguimiento de Avances")
    st.markdown(f"<p style='font-size: 16px; color: #666; margin-top: -15px;'>{nombre_proy}</p>", unsafe_allow_html=True)

    # --- BÚSQUEDA DE PROYECTO ---
    with st.expander("Búsqueda de Proyecto", expanded=not st.session_state.get('id_p_sel')):
        c1, c2 = st.columns([2, 1])
        bus_p = c1.text_input("🔍 Escribe nombre, código o cliente...", key="bus_seg_v2")
        df_p_all = obtener_proyectos(bus_p)
        
        if supervisor_id and not df_p_all.empty:
            df_p_all = df_p_all[df_p_all['supervisor_id'] == supervisor_id]

        if not df_p_all.empty:
            opciones = {f"[{r['codigo']}] {r['proyecto_text']} - {r['cliente']}": r['id'] for _, r in df_p_all.iterrows()}
            lista_opc = ["-- Seleccionar --"] + list(opciones.keys())
            idx_s = lista_opc.index(st.session_state.p_nom_sel) if st.session_state.get('p_nom_sel') in lista_opc else 0
            sel_n = c2.selectbox("Seleccione Proyecto:", lista_opc, index=idx_s)
            
            if sel_n != "-- Seleccionar --":
                st.session_state.id_p_sel = opciones[sel_n]
                st.session_state.p_nom_sel = sel_n
            else:
                st.session_state.id_p_sel = None

    if not st.session_state.get('id_p_sel'):
        st.info("💡 Por favor, seleccione un proyecto."); return

    id_p = st.session_state.id_p_sel
    prods_all = obtener_productos_por_proyecto(id_p)
    if prods_all.empty: st.warning("Sin productos."); return

    # Carga de Seguimiento
    segs_res = supabase.table("seguimiento").select("*").in_("producto_id", prods_all['id'].tolist()).execute()
    segs = pd.DataFrame(segs_res.data) if segs_res.data else pd.DataFrame(columns=['producto_id','hito','fecha','observaciones'])

    # --- CONFIGURACIÓN AVANZADA Y HERRAMIENTAS ---
    with st.expander("CONFIGURACIÓN AVANZADA Y HERRAMIENTAS", expanded=False):
        t1, t2, t3, t4 = st.tabs(["⚖️ Ponderación", "🔍 Filtros", "📥 Importar", "📤 Exportación"])
        with t1:
            cols_w = st.columns(4)
            pesos = {h: cols_w[i % 4].number_input(f"{h} (%)", value=12.5, step=0.5, key=f"p_{h}") for i, h in enumerate(HITOS_LIST)}
        with t2:
            f1, f2, f3 = st.columns(3)
            agrupar_por = f1.selectbox("Agrupar por:", ["Sin grupo", "Ubicación", "Tipo"])
            bus_c1 = f2.text_input("Filtro Primario:")
            bus_c2 = f3.text_input("Refinar Búsqueda:")
        with t3:
            f_av = st.file_uploader("Subir Excel", type=["xlsx", "csv"])
            if f_av and st.button("🚀 Iniciar Importación"):
                df_imp = pd.read_excel(f_av) if f_av.name.endswith('xlsx') else pd.read_csv(f_av)
                for _, r_ex in df_imp.iterrows():
                    match = prods_all[(prods_all['ubicacion'].astype(str) == str(r_ex.get('Ubicacion',''))) & (prods_all['tipo'].astype(str) == str(r_ex.get('Tipo','')))]
                    if not match.empty:
                        pid = match.iloc[0]['id']
                        for h in reversed(HITOS_LIST):
                            if pd.notnull(r_ex.get(h)) and str(r_ex.get(h)).strip() != "":
                                registrar_hitos_cascada(pid, h, str(r_ex.get(h)))
                                break
                st.success("Importado."); st.rerun()
        with t4:
            df_exp = prods_all.copy()
            for h in HITOS_LIST: df_exp[h] = df_exp['id'].apply(lambda x: segs[(segs['producto_id']==x) & (segs['hito']==h)]['fecha'].iloc[0] if not segs[(segs['producto_id']==x) & (segs['hito']==h)].empty else "")
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_exp[['ubicacion', 'tipo', 'ctd', 'ml'] + HITOS_LIST].to_excel(writer, index=False)
            st.download_button("📥 Descargar Avance (Excel)", data=output.getvalue(), file_name=f"Avance_{id_p}.xlsx", use_container_width=True)

    # Filtrado y Avances
    df_f = prods_all.copy()
    if bus_c1: df_f = df_f[df_f['ubicacion'].str.contains(bus_c1, case=False) | df_f['tipo'].str.contains(bus_c1, case=False)]
    if bus_c2: df_f = df_f[df_f['ubicacion'].str.contains(bus_c2, case=False) | df_f['tipo'].str.contains(bus_c2, case=False)]

    def calc_avance(df_m, df_s):
        if df_m.empty: return 0.0
        puntos = sum([pesos.get(h, 0) for h in df_s[df_s['producto_id'].isin(df_m['id'].tolist())]['hito']])
        return round(puntos / len(df_m), 2)

    p_tot, p_par = calc_avance(prods_all, segs), calc_avance(df_f, segs)

    # --- ACCIONES E INDICADORES (D/M/Y) ---
    st.divider()
    act1, act2, act3, act4 = st.columns([1.5, 1.2, 1.2, 1.5])
    f_reg = act1.date_input("Fecha Registro", datetime.now(), format="DD/MM/YYYY"))
    act2.metric("Avance Parcial", f"{p_par}%")
    act3.metric("Avance Global", f"{p_tot}%")
    
    if act4.button("💾 Guardar Avance", type="primary", use_container_width=True):
        f_cierre = datetime.now().strftime("%d/%m/%Y")
        supabase.table("proyectos").update({"avance": p_tot}).eq("id", id_p).execute()
        try: supabase.table("cierres_diarios").insert({"proyecto_id": id_p, "fecha": f_cierre, "hora": datetime.now().strftime("%H:%M:%S")}).execute()
        except: pass
        st.success(f"Guardado el {f_cierre}"); st.rerun()

    # --- MATRIZ CON STICKY HEADER ---
    st.markdown('<div class="sticky-top">', unsafe_allow_html=True)
    cols_h = st.columns([2.5] + [0.7]*8 + [1.5])
    cols_h[0].write("**Producto**")
    for i, h in enumerate(HITOS_LIST):
        with cols_h[i+1]:
            st.write(MAPEO_HITOS[h])
            if st.button("✅", key=f"bk_{h}"):
                for pid in df_f['id'].tolist(): registrar_hitos_cascada(pid, h, f_reg.strftime("%d/%m/%Y"))
                st.rerun()
    cols_h[-1].write("**Notas**")
    st.markdown('</div>', unsafe_allow_html=True)

    # --- ÁREA DE PRODUCTOS (SCROLL) ---
    st.markdown('<div class="scroll-area">', unsafe_allow_html=True)
    
    def render_matriz(df_r):
        rol = st.session_state.get('rol', 'Supervisor')
        for _, p in df_r.iterrows():
            cols = st.columns([2.5] + [0.7]*8 + [1.5])
            
            # REQUERIMIENTO: Ubicación, Tipo y ML en la misma línea
            cols[0].write(f"**{p['ubicacion']}** {p['tipo']} {p['ml']}ml")
            
            for i, h in enumerate(HITOS_LIST):
                m_data = segs[(segs['producto_id'] == p['id']) & (segs['hito'] == h)]
                existe = not m_data.empty
                tiene_post = not segs[(segs['producto_id'] == p['id']) & (segs['hito'].isin(HITOS_LIST[i+1:]))].empty
                
                # Definición de bloqueo
                bloqueado = (existe and rol == "Supervisor") or tiene_post
                
                # LÓGICA ÁGIL SIN RERUN
                if cols[i+1].checkbox("", key=f"c_{p['id']}_{h}", value=existe, disabled=bloqueado, label_visibility="collapsed"):
                    if not existe:
                        registrar_hitos_cascada(p['id'], h, f_reg.strftime("%d/%m/%Y"))
                        st.toast(f"✅ {h} marcado", icon="✔️")
                elif existe and not bloqueado:
                    conectar().table("seguimiento").delete().eq("producto_id", p['id']).eq("hito", h).execute()
                    st.toast(f"🗑️ {h} eliminado", icon="ℹ️")
            
            # REQUERIMIENTO: Recuperar columna de Notas
            n_val = m_data['observaciones'].iloc[0] if (existe and 'observaciones' in m_data.columns and pd.notnull(m_data['observaciones'].iloc[0])) else ""
            nueva_n = cols[-1].text_input("N", value=n_val, key=f"obs_{p['id']}", label_visibility="collapsed")
            
            if nueva_n != n_val:
                conectar().table("seguimiento").update({"observaciones": nueva_n}).eq("producto_id", p['id']).eq("hito", HITOS_LIST[0]).execute()

    if agrupar_por != "Sin grupo":
        for n, g in df_f.groupby(agrupar_por.lower()):
            st.markdown(f"**📂 {n}**")
            render_matriz(g)
    else:
        render_matriz(df_f)
    
    st.markdown('</div>', unsafe_allow_html=True)
