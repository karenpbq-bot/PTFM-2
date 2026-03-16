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

    # --- FILA DE ACCIONES (CONTROL TOTAL) ---
    st.divider()
    # Ajustamos a 5 columnas para que el espacio sea aprovechado por las métricas y botones solicitados
    act1, act2, act3, act4, act5 = st.columns([1.5, 1, 1, 1.3, 1.3])
    
    # 1. Fecha
    f_reg = act1.date_input("Fecha Registro", datetime.now(), format="DD/MM/YYYY")
    
    # 2. Avance Parcial
    act2.metric("Av. Parcial", f"{p_par}%")

    # 3. Avance Global
    act3.metric("Av. Global", f"{p_tot}%")
    
    # 4. Botón Guardar Avance
    if act4.button("💾 Guardar Avance", type="primary", use_container_width=True):
        ahora = datetime.now()
        f_hoy = ahora.strftime("%d/%m/%Y")
        try:
            # A. Unificar cambios pendientes con lo que ya hay en BD
            cambios_pendientes_df = pd.DataFrame(st.session_state.cambios_pendientes)
            if not cambios_pendientes_df.empty:
                cambios_pendientes_df = cambios_pendientes_df.rename(columns={'pid': 'producto_id'})
            
            # Combinamos para saber cuál es el hito máximo REAL de cada producto
            df_total = pd.concat([segs[['producto_id', 'hito']], cambios_pendientes_df[['producto_id', 'hito']]]).drop_duplicates()
            
            lote_final = []
            for pid in prods_all['id'].tolist():
                hitos_p = df_total[df_total['producto_id'] == pid]['hito'].tolist()
                if hitos_p:
                    # Encontrar el índice más alto alcanzado
                    idxs = [HITOS_LIST.index(h) for h in hitos_p if h in HITOS_LIST]
                    max_idx = max(idxs)
                    
                    # REGLA DE CASCADA: Rellenar todo desde 0 hasta el máximo hito
                    for i in range(max_idx + 1):
                        hito_nombre = HITOS_LIST[i]
                        # Solo agregamos si no existe en la base de datos original
                        en_db = not segs[(segs['producto_id'] == pid) & (segs['hito'] == hito_nombre)].empty
                        if not en_db:
                            lote_final.append({"producto_id": pid, "hito": hito_nombre, "fecha": f_hoy})

            # B. Upsert masivo
            if lote_final:
                df_to_save = pd.DataFrame(lote_final).drop_duplicates()
                supabase.table("seguimiento").upsert(df_to_save.to_dict(orient='records'), on_conflict="producto_id, hito").execute()

            # C. Recalcular Avance Global y Limpiar
            res_f = supabase.table("seguimiento").select("producto_id, hito").in_("producto_id", prods_all['id'].tolist()).execute()
            nuevo_av = calc_avance(prods_all, pd.DataFrame(res_f.data))
            supabase.table("proyectos").update({"avance": nuevo_av}).eq("id", id_p).execute()
            
            st.session_state.cambios_pendientes = [] 
            st.success(f"✅ ¡Proyecto actualizado al {nuevo_av}%!")
            st.rerun()
        except Exception as e:
            st.error(f"Error en Guardado/Cascada: {e}")

    # 5. Botón Descartar (Mismas dimensiones que Guardar)
    if act5.button("🗑️ Descartar último avance", type="secondary", use_container_width=True):
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
    
    # 4. Botón Guardar Avance
    if act4.button("💾 Guardar Avance", type="primary", use_container_width=True):
        ahora = datetime.now()
        f_hoy = ahora.strftime("%d/%m/%Y")
        try:
            # A. Unificar cambios pendientes con lo que ya hay en BD
            cambios_pendientes_df = pd.DataFrame(st.session_state.cambios_pendientes)
            if not cambios_pendientes_df.empty:
                cambios_pendientes_df = cambios_pendientes_df.rename(columns={'pid': 'producto_id'})
            
            # Combinamos para saber cuál es el hito máximo REAL de cada producto
            df_total = pd.concat([segs[['producto_id', 'hito']], cambios_pendientes_df[['producto_id', 'hito']]]).drop_duplicates()
            
            lote_final = []
            for pid in prods_all['id'].tolist():
                hitos_p = df_total[df_total['producto_id'] == pid]['hito'].tolist()
                if hitos_p:
                    # Encontrar el índice más alto alcanzado
                    idxs = [HITOS_LIST.index(h) for h in hitos_p if h in HITOS_LIST]
                    max_idx = max(idxs)
                    
                    # REGLA DE CASCADA: Rellenar todo desde 0 hasta el máximo hito
                    for i in range(max_idx + 1):
                        hito_nombre = HITOS_LIST[i]
                        # Solo agregamos si no existe en la base de datos original
                        en_db = not segs[(segs['producto_id'] == pid) & (segs['hito'] == hito_nombre)].empty
                        if not en_db:
                            lote_final.append({"producto_id": pid, "hito": hito_nombre, "fecha": f_hoy})

            # B. Upsert masivo
            if lote_final:
                df_to_save = pd.DataFrame(lote_final).drop_duplicates()
                supabase.table("seguimiento").upsert(df_to_save.to_dict(orient='records'), on_conflict="producto_id, hito").execute()

            # C. Recalcular Avance Global y Limpiar
            res_f = supabase.table("seguimiento").select("producto_id, hito").in_("producto_id", prods_all['id'].tolist()).execute()
            nuevo_av = calc_avance(prods_all, pd.DataFrame(res_f.data))
            supabase.table("proyectos").update({"avance": nuevo_av}).eq("id", id_p).execute()
            
            st.session_state.cambios_pendientes = [] 
            st.success(f"✅ ¡Proyecto actualizado al {nuevo_av}%!")
            st.rerun()
        except Exception as e:
            st.error(f"Error en Guardado/Cascada: {e}")
            
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
