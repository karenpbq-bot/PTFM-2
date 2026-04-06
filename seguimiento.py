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
    with st.expander("⚙️ Configuración Avanzada y Herramientas"):
        t1, t2, t3, t4 = st.tabs(["⚖️ Ponderación", "🔍 Filtros", "📥 Importar", "📤 Exportación"])
        
        # --- Definición de Pesos (Garantiza que el % no sea 0) ---
        pesos_base = obtener_pesos_seguimiento() # Trae los pesos desde base_datos.py
    
        with t1:
            cols_w = st.columns(4)
            # Creamos un diccionario para guardar lo que el usuario escriba, 
            # pero si no escribe nada, usa el valor de pesos_base
            pesos = {}
            for i, h in enumerate(HITOS_LIST):
                val_base = pesos_base.get(h, 12.5)
                pesos[h] = cols_w[i % 4].number_input(f"{h} (%)", value=float(val_base), step=0.5, key=f"peso_{h}")
        
        with t2:
            f1, f2, f3 = st.columns(3)
            agrupar_por = f1.selectbox("Agrupar por:", ["Sin grupo", "Ubicación", "Tipo"], key="agrupar_seg")
            bus_c1 = f1.text_input("Filtro Primario:", key="f_pri_seg") # Movido a f1 para evitar duplicidad de columnas
            bus_c2 = f2.text_input("Refinar Búsqueda:", key="f_ref_seg")

        with t3:
            f_av = st.file_uploader("Subir Excel", type=["xlsx", "csv"], key="uploader_excel")
            if f_av and st.button("🚀 Iniciar Importación Excel"):
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
        
        ids_visibles = df_m['id'].tolist()
        # 1. Puntos de lo que ya está en la Base de Datos
        segs_visibles = df_s[df_s['producto_id'].isin(ids_visibles)]
        puntos_db = sum([pesos.get(h, 0) for h in segs_visibles['hito']])
        
        # 2. Puntos de lo que tienes marcado en ROJO (pendientes de guardar)
        # Filtramos los cambios pendientes que pertenecen a los productos visibles
        cambios_visibles = [c for c in st.session_state.cambios_pendientes if c['pid'] in ids_visibles]
        puntos_memoria = sum([pesos.get(c['hito'], 0) for c in cambios_visibles])
        
        # Total / Cantidad de productos
        return round((puntos_db + puntos_memoria) / len(df_m), 2)

    # El cálculo global usa 'prods_all' (todos) y el parcial usa 'df_f' (los filtrados)
    p_tot = calc_avance(prods_all, segs)
    p_par = calc_avance(df_f, segs)

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

    # --- Guardar Avances (BLOQUE CORREGIDO: Protección Anti-Borrado)
    if cols_acc[4].button("💾 Guardar Avances", type="primary", use_container_width=True):
        f_hoy = f_reg.strftime("%d/%m/%Y")
        try:
            if st.session_state.cambios_pendientes or st.session_state.notas_pendientes:
                with st.status("🚀 Sincronizando Avances...", expanded=True) as status:
                    
                    # A. CONSULTA DE SEGURIDAD (Obtenemos la realidad de la DB en este instante)
                    # Esto evita usar el DataFrame 'segs' inicial que puede estar desactualizado
                    res_seg_actual = supabase.table("seguimiento").select("producto_id, hito").in_("producto_id", prods_all['id'].tolist()).execute()
                    df_db_actual = pd.DataFrame(res_seg_actual.data) if res_seg_actual.data else pd.DataFrame(columns=['producto_id','hito'])

                    # B. GUARDADO DE NOTAS
                    if st.session_state.notas_pendientes:
                        st.write("📝 Guardando notas...")
                        for pid_n, txt in st.session_state.notas_pendientes.items():
                            supabase.table("seguimiento").upsert({
                                "producto_id": int(pid_n), "hito": HITOS_LIST[0], "observaciones": txt
                            }, on_conflict="producto_id, hito").execute()

                    # C. GUARDADO DE HITOS (SOLO LOS QUE NO EXISTEN EN LA DB)
                    if st.session_state.cambios_pendientes:
                        st.write("📦 Verificando integridad de datos...")
                        lote_final = []
                        for c in st.session_state.cambios_pendientes:
                            # Filtro estricto: Si el hito ya está en la DB actual, lo ignoramos
                            ya_esta_en_nube = not df_db_actual[(df_db_actual['producto_id'] == c['pid']) & (df_db_actual['hito'] == c['hito'])].empty
                            
                            if not ya_esta_en_nube:
                                lote_final.append({
                                    "producto_id": int(c['pid']), 
                                    "hito": c['hito'], 
                                    "fecha": f_hoy
                                })
                        
                        if lote_final:
                            st.write(f"🚀 Subiendo {len(lote_final)} hitos nuevos...")
                            chunk_size = 50 
                            for i in range(0, len(lote_final), chunk_size):
                                chunk = lote_final[i:i + chunk_size]
                                supabase.table("seguimiento").upsert(chunk, on_conflict="producto_id, hito").execute()
                        else:
                            st.write("ℹ️ Los hitos marcados ya estaban registrados anteriormente.")

                    # D. SINCRONIZACIÓN DEL GANTT (Motor optimizado)
                    st.write("📊 Actualizando Tablero de Control...")
                    from base_datos import sincronizar_avances_estructural
                    p_cod = df_p_all[df_p_all['id'] == id_p].iloc[0]['codigo']
                    sincronizar_avances_estructural(p_cod)
                    
                    status.update(label="✅ Avance guardado y protegido con éxito", state="complete")

                # LIMPIEZA Y REFRESCO FORZADO
                st.session_state.cambios_pendientes = []
                st.session_state.notas_pendientes = {}
                st.cache_data.clear() # CRÍTICO: Limpia el caché para que al recargar lea los nuevos datos
                st.rerun()
            else:
                st.info("No hay cambios pendientes por guardar.")
        except Exception as e:
            st.error(f"❌ Error crítico en la comunicación: {e}")

    # Botón Descartar (Columna 5)
    if cols_acc[5].button("🚫 Limpiar Selección", use_container_width=True):
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
    
    # --- G. MATRIZ (Cabecera con Botón de Marcado Grupal Filtrado) ---
    st.markdown('<div class="sticky-top">', unsafe_allow_html=True)
    cols_h = st.columns([2.5] + [0.7]*8 + [1.5])
    cols_h[0].write("**Producto**")
    
    for i, h in enumerate(HITOS_LIST):
        with cols_h[i+1]:
            st.write(MAPEO_HITOS[h])
            # BOTÓN GRUPAL: ✅ (Solo actúa sobre 'df_f', los filtrados)
            if st.button("✅", key=f"btn_all_{h}"):
                f_hoy = f_reg.strftime("%d/%m/%Y")
                lote_grupal = []
                for pid in df_f['id'].tolist():
                    if segs[(segs['producto_id'] == pid) & (segs['hito'] == h)].empty:
                        lote_grupal.append({"producto_id": int(pid), "hito": h, "fecha": f_hoy})
                
                if lote_grupal:
                    try:
                        supabase.table("seguimiento").upsert(lote_grupal, on_conflict="producto_id, hito").execute()
                        from base_datos import sincronizar_avances_estructural
                        p_cod = df_p_all[df_p_all['id'] == id_p].iloc[0]['codigo']
                        sincronizar_avances_estructural(p_cod)
                        st.success(f"✅ {h} marcado en productos filtrados.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    cols_h[-1].write("**Notas**")
    st.markdown('</div>', unsafe_allow_html=True)

    # --- FUNCIÓN PARA FILAS INDIVIDUALES ---
    def render_matriz(df_r):
        rol_local = str(st.session_state.get('rol', 'Supervisor')).strip().lower()
        es_jefe_m = rol_local in ["admin", "gerente", "administrador"]

        # IMPORTANTE: Usamos un st.form para agrupar todos los clics y evitar que la app "piense" con cada uno
        # Le ponemos un nombre único al formulario para evitar conflictos
        with st.form(key=f"form_matriz_{df_r.iloc[0]['id'] if not df_r.empty else 'vacia'}"):
            for _, p in df_r.iterrows():
                cols = st.columns([2.5] + [0.7]*8 + [1.5])
                cols[0].write(f"{p['ubicacion']} | {p['tipo']} | **{p['ml']} ML**")
                
                for i, h in enumerate(HITOS_LIST):
                    # 1. Estado real en Base de Datos
                    en_db = not segs[(segs['producto_id'] == p['id']) & (segs['hito'] == h)].empty
                    
                    # 2. Estado en memoria temporal
                    idx_mem = next((idx for idx, d in enumerate(st.session_state.cambios_pendientes) 
                                  if d["pid"] == p['id'] and d["hito"] == h), None)
                    
                    existe = en_db or (idx_mem is not None)
                    
                    # Bloqueo: Si ya está en DB y no es jefe, deshabilitamos
                    bloqueado = (en_db and not es_jefe_m)

                    # KEY ÚNICA: Sin rerun automático
                    # Al estar dentro de un form, el checkbox NO hará que la app piense
                    check_val = cols[i+1].checkbox("", key=f"c_{p['id']}_{h}", value=existe, disabled=bloqueado, label_visibility="collapsed")
                    
                    # Guardamos la intención en una lista temporal si el valor cambió respecto a 'existe'
                    if check_val and not existe:
                        if not any(d["pid"] == p['id'] and d["hito"] == h for d in st.session_state.cambios_pendientes):
                            st.session_state.cambios_pendientes.append({"pid": p['id'], "hito": h})
                    elif not check_val and idx_mem is not None:
                        st.session_state.cambios_pendientes.pop(idx_mem)

                # Notas (dentro del form también para que no refresque)
                n_db = segs[(segs['producto_id'] == p['id']) & (segs['hito'] == HITOS_LIST[0])]['observaciones'].iloc[0] if not segs[(segs['producto_id'] == p['id']) & (segs['hito'] == HITOS_LIST[0])].empty else ""
                n_act = st.session_state.notas_pendientes.get(str(p['id']), n_db if pd.notnull(n_db) else "")
                nueva = cols[-1].text_input("N", value=n_act, key=f"nt_{p['id']}", label_visibility="collapsed")
                if nueva != n_act: st.session_state.notas_pendientes[str(p['id'])] = nueva

            # Botón de confirmación local para el formulario (es obligatorio en st.form)
            # Lo llamamos "Preparar estos cambios"
            submit_local = st.form_submit_button("📎 Confirmar marcaciones de este grupo", use_container_width=True)
            if submit_local:
                st.rerun() # Aquí recién la app "piensa" una sola vez para anotar todo en memoria roja

    # --- EJECUCIÓN FINAL ---
    st.markdown('<div class="scroll-area">', unsafe_allow_html=True)
    if agrupar_por != "Sin grupo":
        campo = "ubicacion" if agrupar_por == "Ubicación" else "tipo"
        for n, g in df_f.groupby(campo):
            st.markdown(f"**📂 {agrupar_por}: {n}**")
            render_matriz(g)
    else: 
        render_matriz(df_f)
    st.markdown('</div>', unsafe_allow_html=True)
