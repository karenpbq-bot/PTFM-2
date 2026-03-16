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
def registrar_hito_individual(p_id, hito, fecha_str):
    supabase = conectar()
    try:
        supabase.table("seguimiento").upsert({
            "producto_id": int(p_id), 
            "hito": str(hito), 
            "fecha": str(fecha_str)
        }, on_conflict="producto_id, hito").execute()
    except Exception as e:
        st.error(f"Error al registrar: {e}")

# =========================================================
# 3. INTERFAZ PRINCIPAL
# =========================================================
def mostrar(supervisor_id=None):
    # --- 1. MEMORIA TEMPORAL ---
    if 'cambios_pendientes' not in st.session_state:
        st.session_state.cambios_pendientes = []

    # --- 2. TÍTULOS Y ESTILOS ---
    # Mantenemos el CSS para que los porcentajes se vean naranja y el encabezado sea fijo
    st.markdown("""
        <style>
        .sticky-top { position: sticky; top: 0; background: white; z-index: 1000; padding: 10px 0; border-bottom: 3px solid #FF8C00; }
        .scroll-area { max-height: 550px; overflow-y: auto; border: 1px solid #eee; padding: 10px; border-radius: 5px; }
        [data-testid="stMetricValue"] { color: #FF8C00 !important; font-weight: bold !important; font-size: 24px !important; }
        </style>
    """, unsafe_allow_html=True)

    nombre_proy = st.session_state.get('p_nom_sel', "Ninguno")
    st.markdown("### Seguimiento de Avances")
    st.markdown(f"<p style='font-size: 16px; color: #666; margin-top: -15px;'>{nombre_proy}</p>", unsafe_allow_html=True)

    supabase = conectar()

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
            bus_c1, bus_c2 = f2.text_input("Filtro Primario:"), f3.text_input("Refinar Búsqueda:")
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

    # --- ACCIONES E INDICADORES (FECHA CORREGIDA) ---
    st.divider()
    act1, act2, act3, act4, act5 = st.columns([1.5, 1, 1, 1.2, 1.2])
    
    # 1. Calendario con formato corregido
    f_reg = act1.date_input("Fecha Registro", datetime.now(), format="DD/MM/YYYY")
    
    # 2. Métrica de cambios en espera (Pendientes)
    n_pendientes = len(st.session_state.cambios_pendientes)
    act2.metric("Pendientes", n_pendientes)
    
    # 3. Avance Global
    act3.metric("Avance Global", f"{p_tot}%")
    
    if act4.button("💾 Guardar Avance", type="primary", use_container_width=True):
        ahora = datetime.now()
        f_hoy = ahora.strftime("%d/%m/%Y")
        
        try:
            lote_total = []
            # 1. Agregamos lo pendiente
            if st.session_state.cambios_pendientes:
                for c in st.session_state.cambios_pendientes:
                    lote_total.append({"producto_id": c['pid'], "hito": c['hito'], "fecha": f_hoy})

            # 2. Consultar BD y unir con cambios actuales para la Cascada
            res_s = supabase.table("seguimiento").select("producto_id, hito").in_("producto_id", prods_all['id'].tolist()).execute()
            df_actualizado = pd.concat([pd.DataFrame(res_s.data), pd.DataFrame(lote_total)[['producto_id', 'hito']]]) if lote_total else pd.DataFrame(res_s.data)
            
            # 3. Lógica de cascada sobre la unión de datos
            if not df_actualizado.empty:
                for pid in prods_all['id'].tolist():
                    hitos_p = df_actualizado[df_actualizado['producto_id'] == pid]['hito'].unique().tolist()
                    if hitos_p:
                        max_idx = max([HITOS_LIST.index(h) for h in hitos_p])
                        for i in range(max_idx):
                            if HITOS_LIST[i] not in hitos_p:
                                lote_total.append({"producto_id": pid, "hito": HITOS_LIST[i], "fecha": f_hoy})

            # 4. Upsert y Recalcular Avance
            if lote_total:
                df_final = pd.DataFrame(lote_total).drop_duplicates(subset=['producto_id', 'hito'])
                supabase.table("seguimiento").upsert(df_final.to_dict(orient='records'), on_conflict="producto_id, hito").execute()

            # RECALCULAR AVANCE CON DATOS NUEVOS
            res_final = supabase.table("seguimiento").select("producto_id, hito").in_("producto_id", prods_all['id'].tolist()).execute()
            avance_final = calc_avance(prods_all, pd.DataFrame(res_final.data))
            
            supabase.table("proyectos").update({"avance": avance_final}).eq("id", id_p).execute()
            st.session_state.cambios_pendientes = []
            st.success(f"✅ ¡Avance del {avance_final}% guardado exitosamente!")
            st.rerun()

        except Exception as e:
            st.error(f"Error: {e}")

    # 5. Botón Descartar (Limpia la memoria temporal)
    if act5.button("🗑️ Descartar", type="secondary", use_container_width=True):
        st.session_state.cambios_pendientes = []
        st.rerun()
        
    # --- MATRIZ CON STICKY HEADER ---
    st.markdown('<div class="sticky-top">', unsafe_allow_html=True)
    cols_h = st.columns([2.5] + [0.7]*8 + [1.5])
    cols_h[0].write("**Producto**")
    for i, h in enumerate(HITOS_LIST):
        with cols_h[i+1]:
            st.write(MAPEO_HITOS[h])
            if st.button("✅", key=f"bk_{h}"):
                for pid in df_f['id'].tolist():
                    # Marcamos en memoria solo si no está en BD y no está ya en memoria
                    en_db = not segs[(segs['producto_id'] == pid) & (segs['hito'] == h)].empty
                    ya_en_memoria = any(c['pid'] == pid and c['hito'] == h for c in st.session_state.cambios_pendientes)
                    if not en_db and not ya_en_memoria:
                        st.session_state.cambios_pendientes.append({"pid": pid, "hito": h})
                # Usamos st.toast para avisar en lugar de rerun, manteniendo los filtros intactos
                st.toast(f"Columna {h} marcada para guardar.")
    cols_h[-1].write("**Notas**")
    st.markdown('</div>', unsafe_allow_html=True)

    # --- ÁREA DE PRODUCTOS (SCROLL) ---
    st.markdown('<div class="scroll-area">', unsafe_allow_html=True)
    
    def render_matriz(df_r):
        rol = st.session_state.get('rol', 'Supervisor')
        for _, p in df_r.iterrows():
            cols = st.columns([2.5] + [0.7]*8 + [1.5])
            # Producto y ML en la misma línea
            cols[0].write(f"**{p['ubicacion']}** {p['tipo']} {p['ml']}ml")
            
            for i, h in enumerate(HITOS_LIST):
                m_data = segs[(segs['producto_id'] == p['id']) & (segs['hito'] == h)]
                en_db = not m_data.empty
                
                # REVISIÓN: Buscamos si el registro está en la memoria temporal
                # Lo guardamos en una variable para poder manipularlo si el usuario desmarca
                pendiente = next((c for c in st.session_state.cambios_pendientes if c['pid'] == p['id'] and c['hito'] == h), None)
                existe = en_db or (pendiente is not None)
                
                tiene_post = not segs[(segs['producto_id'] == p['id']) & (segs['hito'].isin(HITOS_LIST[i+1:]))].empty
                bloqueado = (en_db and rol == "Supervisor") or tiene_post
                
                # Checkbox con lógica dual (Base de datos + Memoria)
                if cols[i+1].checkbox("", key=f"c_{p['id']}_{h}", value=existe, disabled=bloqueado, label_visibility="collapsed"):
                    if not existe:
                        st.session_state.cambios_pendientes.append({"pid": p['id'], "hito": h})
                        st.rerun() # Rerun necesario para actualizar el contador de "Pendientes" arriba
                else:
                    # Si el usuario desmarca algo que estaba en memoria (pero no en BD todavía)
                    if pendiente:
                        st.session_state.cambios_pendientes.remove(pendiente)
                        st.rerun()
                    # Si el usuario desmarca algo que YA estaba en BD (Solo Admin)
                    elif en_db and not bloqueado:
                        conectar().table("seguimiento").delete().eq("producto_id", p['id']).eq("hito", h).execute()
                        st.rerun()
            
            # Notas (Mantenemos tu lógica)
            n_val = m_data['observaciones'].iloc[0] if (en_db and 'observaciones' in m_data.columns and pd.notnull(m_data['observaciones'].iloc[0])) else ""
            nueva_n = cols[-1].text_input("N", value=n_val, key=f"obs_{p['id']}", label_visibility="collapsed")
            if nueva_n != n_val:
                conectar().table("seguimiento").update({"observaciones": nueva_n}).eq("producto_id", p['id']).eq("hito", HITOS_LIST[0]).execute()

    # --- 3. RENDERIZADO DE MATRIZ CON LÓGICA DE AGRUPACIÓN ---
    if agrupar_por != "Sin grupo":
        # Mapeamos el nombre visible al nombre real de la columna en la BD
        campo_real = "ubicacion" if agrupar_por == "Ubicación" else "tipo"
        
        # Verificamos que la columna existe en el dataframe antes de agrupar
        if campo_real in df_f.columns:
            for n, g in df_f.groupby(campo_real):
                st.markdown(f"**📂 {agrupar_por}: {n}**")
                render_matriz(g)
        else:
            render_matriz(df_f)
    else:
        render_matriz(df_f)
    st.markdown('</div>', unsafe_allow_html=True)
