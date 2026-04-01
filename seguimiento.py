import streamlit as st
import pandas as pd
from datetime import datetime
import io
from base_datos import conectar, obtener_proyectos, obtener_productos_por_proyecto, obtener_seguimiento

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
# 2. INTERFAZ PRINCIPAL
# =========================================================
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

    # --- D. CARGA DE DATOS ---
    id_p = st.session_state.id_p_sel
    prods_all = obtener_productos_por_proyecto(id_p)
    if prods_all.empty: st.warning("Sin productos."); return

    # Cargamos seguimiento una sola vez al inicio
    segs_res = supabase.table("seguimiento").select("*").in_("producto_id", prods_all['id'].tolist()).execute()
    segs = pd.DataFrame(segs_res.data) if segs_res.data else pd.DataFrame(columns=['producto_id','hito','fecha','observaciones'])

    # --- E. HERRAMIENTAS ---
    with st.expander("⚙️ CONFIGURACIÓN AVANZADA Y HERRAMIENTAS"):
        t1, t2, t3, t4 = st.tabs(["⚖️ Ponderación", "🔍 Filtros", "📥 Importar", "📤 Exportación"])
        
        with t1:
            cols_w = st.columns(4)
            pesos = {h: cols_w[i % 4].number_input(f"{h} (%)", value=12.5, step=0.5, key=f"peso_{h}") for i, h in enumerate(HITOS_LIST)}
        
        with t2:
            f1, f2, f3 = st.columns(3)
            agrupar_por = f1.selectbox("Agrupar por:", ["Sin grupo", "Ubicación", "Tipo"], key="agrupar_seg")
            bus_c1 = f1.text_input("Filtro Primario:", key="f_pri_seg") # Movido a f1 para evitar duplicidad de columnas
            bus_c2 = f2.text_input("Refinar Búsqueda:", key="f_ref_seg")

        with t3:
            f_av = st.file_uploader("Subir Excel", type=["xlsx", "csv"], key="uploader_excel")
            if f_av and st.button("🚀 Iniciar Importación con Fechas del Excel"):
                try:
                    df_imp = pd.read_excel(f_av) if f_av.name.endswith('xlsx') else pd.read_csv(f_av)
                    lote_imp = []
                    
                    for _, r_ex in df_imp.iterrows():
                        # Buscamos el producto por Ubicación y Tipo
                        match = prods_all[
                            (prods_all['ubicacion'].astype(str).str.strip() == str(r_ex.get('Ubicacion','')).strip()) & 
                            (prods_all['tipo'].astype(str).str.strip() == str(r_ex.get('Tipo','')).strip())
                        ]
                        
                        if not match.empty:
                            pid = int(match.iloc[0]['id'])
                            
                            for h_nom in HITOS_LIST:
                                val_fecha = r_ex.get(h_nom)
                                
                                # Si la celda tiene contenido
                                if pd.notnull(val_fecha) and str(val_fecha).strip() != "":
                                    try:
                                        # FORZAMOS conversión a fecha para validar formato
                                        # Esto convierte tanto objetos Excel como texto "15/03/2024"
                                        fecha_dt = pd.to_datetime(val_fecha, dayfirst=True, errors='coerce')
                                        
                                        if pd.notnull(fecha_dt):
                                            f_str = fecha_dt.strftime("%d/%m/%Y")
                                            lote_imp.append({
                                                "producto_id": pid, 
                                                "hito": h_nom, 
                                                "fecha": f_str
                                            })
                                    except:
                                        continue # Si la fecha es basura, la ignora para no romper la API
                    
                    if lote_imp:
                        # Convertimos a DataFrame para eliminar duplicados accidentales
                        df_lote = pd.DataFrame(lote_imp).drop_duplicates(subset=['producto_id', 'hito'])
                        
                        # Ejecución en Supabase
                        supabase.table("seguimiento").upsert(
                            df_lote.to_dict(orient='records'), 
                            on_conflict="producto_id, hito"
                        ).execute()
                        
                        # Sincronización con el Gantt
                        from base_datos import sincronizar_avances_estructural
                        p_cod = df_p_all[df_p_all['id'] == id_p].iloc[0]['codigo']
                        sincronizar_avances_estructural(p_cod)
                        
                        st.success(f"✅ Se actualizaron {len(df_lote)} hitos con fechas reales.")
                        st.rerun()
                    else:
                        st.warning("No se encontraron coincidencias entre el Excel y los productos del proyecto.")
                
                except Exception as e:
                    st.error(f"Error procesando el archivo: {e}")

        with t4:
            df_exp = prods_all.copy()
            for h in HITOS_LIST: df_exp[h] = df_exp['id'].apply(lambda x: segs[(segs['producto_id']==x) & (segs['hito']==h)]['fecha'].iloc[0] if not segs[(segs['producto_id']==x) & (segs['hito']==h)].empty else "")
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_exp[['ubicacion', 'tipo', 'ctd', 'ml'] + HITOS_LIST].to_excel(writer, index=False)
            st.download_button("📥 Descargar Avance (Excel)", data=output.getvalue(), file_name=f"Avance_{id_p}.xlsx", use_container_width=True)

    # Filtrado
    df_f = prods_all.copy()
    if bus_c1: df_f = df_f[df_f['ubicacion'].str.contains(bus_c1, case=False) | df_f['tipo'].str.contains(bus_c1, case=False)]
    if bus_c2: df_f = df_f[df_f['ubicacion'].str.contains(bus_c2, case=False) | df_f['tipo'].str.contains(bus_c2, case=False)]

    def calc_avance(df_m, df_s):
        if df_m.empty: return 0.0
        puntos = sum([pesos.get(h, 0) for h in df_s[df_s['producto_id'].isin(df_m['id'].tolist())]['hito']])
        return round(puntos / len(df_m), 2)

    p_tot, p_par = calc_avance(prods_all, segs), calc_avance(df_f, segs)

    # --- F. FILA DE ACCIONES (INTEGRACIÓN CORREGIDA) ---
    st.divider()
    
    # Capturamos el rol y lo normalizamos
    rol_usuario = str(st.session_state.get('rol', 'Supervisor')).strip().lower()
    es_jefe = rol_usuario in ["admin", "gerente", "administrador"]

    # Definimos columnas: 7 columnas si es jefe (para que quepa el botón de borrar)
    if es_jefe:
        cols_acc = st.columns([1.5, 0.8, 0.8, 1, 1, 1, 1])
    else:
        cols_acc = st.columns([1.5, 0.8, 0.8, 1.2, 1.2, 1.2])

    f_reg = cols_acc[0].date_input("Fecha Registro", datetime.now(), format="DD/MM/YYYY", key="f_reg_u")
    cols_acc[1].metric("Av. Parcial", f"{p_par}%")
    cols_acc[2].metric("Av. Global", f"{p_tot}%")
    
    # Botón Refrescar (Columna 3)
    if cols_acc[3].button("🔄 Refrescar", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # Botón Guardar (Columna 4)
    if cols_acc[4].button("💾 Guardar", type="primary", use_container_width=True, key="btn_save_final_v2"):
        f_hoy = f_reg.strftime("%d/%m/%Y")
        try:
            # --- A. GUARDAR NOTAS SI EXISTEN ---
            if st.session_state.notas_pendientes:
                for pid_n, texto in st.session_state.notas_pendientes.items():
                    supabase.table("seguimiento").upsert(
                        {"producto_id": int(pid_n), "hito": HITOS_LIST[0], "observaciones": texto},
                        on_conflict="producto_id, hito"
                    ).execute()
                st.session_state.notas_pendientes = {}

            # --- B. GUARDAR HITOS Y RECALCULAR ---
            if st.session_state.cambios_pendientes:
                lote_save = []
                for cambio in st.session_state.cambios_pendientes:
                    lote_save.append({"producto_id": cambio['pid'], "hito": cambio['hito'], "fecha": f_hoy})
                
                # 1. Guardar hitos
                supabase.table("seguimiento").upsert(lote_save, on_conflict="producto_id, hito").execute()
                
                # 2. Recalcular porcentajes
                from base_datos import sincronizar_avances_estructural
                p_cod_actual = df_p_all[df_p_all['id'] == id_p].iloc[0]['codigo']
                sincronizar_avances_estructural(p_cod_actual)
                
                # 3. Limpiar y refrescar
                st.session_state.cambios_pendientes = []
                st.success("✅ Avance guardado y porcentajes actualizados.")
                st.rerun()
            else:
                st.info("Hitos guardados o sin cambios nuevos.")
                st.rerun()
                
        except Exception as e:
            st.error(f"Error al sincronizar: {e}")

    # Botón Descartar (Columna 5)
    if cols_acc[5].button("🚫 Descartar", use_container_width=True):
        st.session_state.cambios_pendientes, st.session_state.notas_pendientes = [], {}
        st.rerun()

    # NUEVO: Botón Borrar Todo (Columna 6 - Solo para Admin/Gerente)
    if es_jefe:
        if cols_acc[6].button("🔥 Borrar Todo", type="secondary", use_container_width=True):
            ids_p = prods_all['id'].tolist()
            supabase.table("seguimiento").delete().in_("producto_id", ids_p).execute()
            from base_datos import sincronizar_avances_estructural
            p_cod = df_p_all[df_p_all['id'] == id_p].iloc[0]['codigo']
            sincronizar_avances_estructural(p_cod)
            st.warning("⚠️ Avance del proyecto reseteado.")
            st.rerun()
    
    # --- G. MATRIZ ---
    def render_matriz(df_r):
        # 1. Definimos el rol localmente (Limpieza total)
        rol_local = str(st.session_state.get('rol', 'Supervisor')).strip().lower()
        es_jefe_m = rol_local in ["admin", "gerente", "administrador"]

        for _, p in df_r.iterrows():
            cols = st.columns([2.5] + [0.7]*8 + [1.5])
            
            # Identificación del producto
            cols[0].write(f"{p['ubicacion']} | {p['tipo']} | **{p['ml']} ML**")
            
            for i, h in enumerate(HITOS_LIST):
                # Estado de base de datos
                en_db = not segs[(segs['producto_id'] == p['id']) & (segs['hito'] == h)].empty
                
                # Cascada visual
                tiene_post_db = not segs[(segs['producto_id'] == p['id']) & (segs['hito'].isin(HITOS_LIST[i+1:]))].empty
                idx_mem = next((idx for idx, d in enumerate(st.session_state.cambios_pendientes) if d["pid"] == p['id'] and d["hito"] == h), None)
                
                existe = en_db or tiene_post_db or (idx_mem is not None)
                
                # Regla de bloqueo: Jefe nunca bloqueado, Supervisor bloqueado si ya está en DB
                bloqueado = False if es_jefe_m else (en_db or tiene_post_db)

                # Key dinámica para evitar errores de duplicidad
                key_chx = f"v_chk_{p['id']}_{h}_{'1' if existe else '0'}"

                if cols[i+1].checkbox("", key=key_chx, value=existe, disabled=bloqueado, label_visibility="collapsed"):
                    if not existe:
                        # Acción: Marcar
                        for idx_p in range(i + 1):
                            h_p = HITOS_LIST[idx_p]
                            if segs[(segs['producto_id'] == p['id']) & (segs['hito'] == h_p)].empty:
                                if not any(d["pid"] == p['id'] and d["hito"] == h_p for d in st.session_state.cambios_pendientes):
                                    st.session_state.cambios_pendientes.append({"pid": p['id'], "hito": h_p})
                        st.rerun()
                else:
                    if existe:
                        # Acción: Desmarcar (Solo si es Jefe)
                        if idx_mem is not None:
                            st.session_state.cambios_pendientes.pop(idx_mem)
                        elif en_db and es_jefe_m:
                            supabase.table("seguimiento").delete().eq("producto_id", p['id']).eq("hito", h).execute()
                            from base_datos import sincronizar_avances_estructural
                            p_cod = df_p_all[df_p_all['id'] == id_p].iloc[0]['codigo']
                            sincronizar_avances_estructural(p_cod)
                        st.rerun()

            # Gestión de Notas
            n_db = segs[(segs['producto_id'] == p['id']) & (segs['hito'] == HITOS_LIST[0])]['observaciones'].iloc[0] if not segs[(segs['producto_id'] == p['id']) & (segs['hito'] == HITOS_LIST[0])].empty else ""
            n_act = st.session_state.notas_pendientes.get(str(p['id']), n_db if pd.notnull(n_db) else "")
            nueva = cols[-1].text_input("N", value=n_act, key=f"nt_{p['id']}", label_visibility="collapsed")
            if nueva != n_act: 
                st.session_state.notas_pendientes[str(p['id'])] = nueva

    # --- RENDERIZADO FINAL (Fuera de la función render_matriz) ---
    if agrupar_por != "Sin grupo":
        campo = "ubicacion" if agrupar_por == "Ubicación" else "tipo"
        for n, g in df_f.groupby(campo):
            st.markdown(f"**📂 {agrupar_por}: {n}**")
            render_matriz(g)
    else: 
        render_matriz(df_f)
    
    st.markdown('</div>', unsafe_allow_html=True)
