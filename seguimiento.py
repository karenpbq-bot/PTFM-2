import streamlit as st
import pandas as pd
from datetime import date
from base_datos import obtener_proyectos, conectar, actualizar_avance_real

# 1. DICCIONARIO MAESTRO DE ICONOS (FUNCIONALIDAD PRESERVADA)
MAPEO_HITOS = {
    "Diseñado": "🗺️", 
    "Fabricado": "🪚",
    "Material en Obra": "🚛",
    "Material en Ubicación": "📍",
    "Instalación de Estructura": "📦", 
    "Instalación de Puertas o Frentes": "🗄️",
    "Revisión y Observaciones": "🔍",
    "Entrega": "🤝"
}

# 2. LEYENDA TÉCNICA (FUNCIONALIDAD PRESERVADA)
LEYENDA_DETALLADA = {
    "🗺️": "Diseño (Plano Técnico)",
    "🪚": "Fabricación (Taller)",
    "🚛": "En Obra (Descargado)",
    "📍": "En Ubicación (Frente de trabajo)",
    "📦": "Estructura (Cajón base)",
    "🗄️": "Frentes (Mueble cerrado)",
    "🔍": "Revisión y atención de Observaciones (Post-instalación)",
    "🤝": "Entrega (Conformidad Cliente)"
}

def mostrar(supervisor_id=None):
    st.header("📈 Panel de Seguimiento Matricial")

    def mostrar(supervisor_id=None):
        st.header("📈 Panel de Seguimiento Matricial")

    # --- SECCIÓN 1: SELECCIÓN DE PROYECTO (SIMPLIFICADA) ---
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        bus_p = c1.text_input("🔍 Buscar proyecto o cliente...", key="bus_seg_proy", placeholder="Escriba nombre o cliente...")
        
        # Switch para ver todos o solo activos (Sustituye al selectbox anterior)
        ver_todos = c2.toggle("Ver todos", value=False, help="Muestra también proyectos cerrados")
        
        # Filtrado lógico desde base_datos
        df_p = obtener_proyectos(bus_p, supervisor_id=supervisor_id)
        if not ver_todos:
            df_p = df_p[df_p['estatus'] == 'Activo']

    if df_p.empty:
        st.info("No se encontraron proyectos."); return

    opciones = {f"{r['proyecto_text']} — {r['cliente']}": r['id'] for _, r in df_p.iterrows()}
    sel_p_nom = st.selectbox("Seleccione Proyecto:", ["Seleccione..."] + list(opciones.keys()))

    # --- VALIDACIÓN CRÍTICA PARA DEFINIR p_data ---
    if sel_p_nom == "Seleccione...":
        st.write("Seleccione un proyecto para ver los detalles."); return

    # Definición de p_data (Aquí se soluciona el NameError)
    id_p = opciones[sel_p_nom]
    p_data = df_p[df_p['id'] == id_p].iloc[0]

    # --- SECCIÓN 2: HERRAMIENTAS Y FILTROS (REPLEGABLE) ---
    with st.expander("🛠️ Configuración de Avance y Filtros de Producto", expanded=False):
        f1, f2 = st.columns(2)
        fecha_avance = f1.date_input("📅 Fecha de registro:", date.today())
        bus_prod = f2.text_input("🔍 Buscar producto...", placeholder="Ej: Cocina, MDF, Cajón")
        
        f3, f4 = st.columns(2)
        solo_pendientes = f3.toggle("🔴 Ver solo pendientes", value=False)
        
        opciones_filtro = {"Sin grupo": None, "Ubicación": "ubicacion", "Tipo": "tipo"}
        label_agrupar = f4.radio("📂 Agrupar por:", list(opciones_filtro.keys()), horizontal=True)
        columna_tecnica = opciones_filtro[label_agrupar]
        
        st.info("💡 **Guía:** " + " | ".join([f"{k} {v}" for k, v in LEYENDA_DETALLADA.items()]))

    # --- SECCIÓN 3: CABECERA DE CONTROL (MÉTRICAS) ---
    st.divider()
    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        st.title(f"🚀 {p_data['proyecto_text']}")
        st.subheader(f"👤 Cliente: {p_data['cliente']}")
    with col_t2:
        st.metric("Avance Total", f"{int(p_data['avance'])}%")
        st.progress(p_data['avance']/100)

        # --- SECCIÓN 4: CARGA DE DATOS EN TIEMPO REAL ---
    HITOS_LIST = list(MAPEO_HITOS.keys())
        
        # Forzamos una conexión nueva cada vez que se entra a este bloque
    with conectar() as conn_viva:
            prods = pd.read_sql_query("SELECT * FROM productos WHERE proyecto_id=?", conn_viva, params=(id_p,))
            
            # RELECTURA CRÍTICA: Aquí es donde se "pintan" los checks
            query_viva = "SELECT s.* FROM seguimiento s JOIN productos p ON s.producto_id = p.id WHERE p.proyecto_id = ?"
            segs = pd.read_sql_query(query_viva, conn_viva, params=(id_p,))

        # Filtros de búsqueda (se aplican sobre los datos frescos)
    if bus_prod:
            prods = prods[prods['ubicacion'].str.contains(bus_prod, case=False, na=False) | 
                          prods['tipo'].str.contains(bus_prod, case=False, na=False)]

    if solo_pendientes:
            def esta_pendiente(p_id):
                num_checks = len(segs[segs['producto_id'] == p_id])
                return num_checks < len(HITOS_LIST)
            prods = prods[prods['id'].apply(esta_pendiente)]

    # --- LÓGICA DE SEGURIDAD Y PERMISOS ---
    with conectar() as conn:
            cierre = conn.execute(
                "SELECT 1 FROM cierres_diarios WHERE proyecto_id = ? AND fecha = ?",
                (id_p, fecha_avance.isoformat())
            ).fetchone()
        
    esta_guardado = cierre is not None
    user_rol = st.session_state.get('rol', 'Supervisor')
    es_jefe = user_rol in ['Administrador', 'Gerente']

    # Definimos quien puede editar
    bloqueo_edicion = esta_guardado and not es_jefe

    # --- SECCIÓN 5: MARCADO RÁPIDO (SIN BOTÓN REFRESCAR) ---
    st.divider()
    st.write("### ⚡ Marcado Rápido")
    st.caption(f"Presiona ✅ para marcar los {len(prods)} ítems filtrados.")
        
        # RELECTURA CRÍTICA (Directa de DB antes de pintar)
    with conectar() as conn_fresca:
            query_fresca = "SELECT s.* FROM seguimiento s JOIN productos p ON s.producto_id = p.id WHERE p.proyecto_id = ?"
            segs = pd.read_sql_query(query_fresca, conn_fresca, params=(id_p,))

        # Contenedor de la matriz
    with st.container(border=True):
            cols_h = st.columns([2.5] + [1]*8)
            cols_h[0].write("**Producto**")
            
            for i, hito in enumerate(HITOS_LIST):
                with cols_h[i+1]:
                    # El botón se deshabilita solo si el reporte está guardado y no eres jefe
                    if st.button("✅", key=f"bulk_{hito}", use_container_width=True, disabled=bloqueo_edicion):
                        if not prods.empty:
                            # ... (tu código de INSERT OR IGNORE se mantiene igual)
                            ids_filtrados = prods['id'].tolist()
                            f_str = fecha_avance.isoformat()
                            with conectar() as conn:
                                for p_id in ids_filtrados:
                                    conn.execute(
                                        "INSERT OR IGNORE INTO seguimiento (producto_id, hito, fecha) VALUES (?,?,?)",
                                        (p_id, hito, f_str)
                                    )
                                    # INYECCIÓN INSTANTÁNEA: Marcamos el estado en memoria
                                    st.session_state[f"mat_{p_id}_{hito}"] = True
                                conn.commit()
                            
                            actualizar_avance_real(id_p)
                            st.toast(f"¡{hito} actualizado!", icon="🚀")
                            st.rerun() 
                    
                    st.write(f"**{MAPEO_HITOS[hito]}**")

    # --- SECCIÓN 6: RENDERIZADO DE MATRIZ (REACTIVIDAD TOTAL) ---
    grupos = [None] if columna_tecnica is None else prods[columna_tecnica].unique()

    for g in grupos:
            if g: 
                st.markdown(f"#### 📁 {label_agrupar}: {g}")
            
            df_mostrar = prods if columna_tecnica is None else prods[prods[columna_tecnica] == g]

            for _, prod in df_mostrar.iterrows():
                with st.container(border=True):
                    cols = st.columns([2.5] + [1]*8)
                    cols[0].markdown(f"**{prod['ubicacion']}** \n {prod['tipo']}")
                    
                    for i, hito in enumerate(HITOS_LIST):
                        # 1. Identificadores y estado actual
                        key_check = f"mat_{prod['id']}_{hito}"
                        en_db = not segs[(segs['producto_id'] == prod['id']) & (segs['hito'] == hito)].empty
                        
                        # 2. Inicialización de memoria (Solo si no existe)
                        if key_check not in st.session_state:
                            st.session_state[key_check] = en_db

                        # --- EL CANDADO PREVENTIVO ---
                        user_rol = st.session_state.get('rol', 'Supervisor')
                        
                        # REGLA: Si ya está marcado (en_db) y NO es jefe, el check se bloquea.
                        # Esto impide que el supervisor siquiera pueda intentar desmarcarlo.
                        bloqueado = en_db and user_rol not in ['Administrador', 'Gerente']

                        # 3. DIBUJO DEL CHECKBOX CON 'DISABLED'
                        # Al usar 'disabled', evitamos que el usuario genere el conflicto de estado
                        # En la Sección 6, dentro del bucle de hitos:
                        if cols[i+1].checkbox("Ok", key=key_check, label_visibility="collapsed", disabled=bloqueo_edicion):
                            if not en_db:
                                with conectar() as conn:
                                    conn.execute("INSERT OR IGNORE INTO seguimiento (producto_id, hito, fecha) VALUES (?,?,?)",
                                                (prod['id'], hito, fecha_avance.isoformat()))
                                    conn.commit()
                                actualizar_avance_real(id_p)
                                st.rerun()
                        else:
                            if en_db:
                                # El 'disabled' del checkbox ya protege esta acción para supervisores si está guardado
                                with conectar() as conn:
                                    conn.execute("DELETE FROM seguimiento WHERE producto_id=? AND hito=?", (prod['id'], hito))
                                    conn.commit()
                                actualizar_avance_real(id_p)
                                st.rerun()
    st.divider()
    if not esta_guardado:
        if st.button("💾 Guardar Avance", use_container_width=True, type="primary"):
            with conectar() as conn:
                user_id = st.session_state.get('usuario_id', 0)
                conn.execute("INSERT INTO cierres_diarios (proyecto_id, fecha, cerrado_por) VALUES (?,?,?)",
                            (id_p, fecha_avance.isoformat(), user_id))
                conn.commit()
            st.success("✅ Avance guardado y protegido."); st.rerun()
    else:
        st.warning(f"🔐 Reporte guardado. Edición limitada a Gerencia.")
        if es_jefe:
            if st.button("🔓 Reabrir Reporte para Edición", use_container_width=True):
                with conectar() as conn:
                    conn.execute("DELETE FROM cierres_diarios WHERE proyecto_id=? AND fecha=?", 
                                (id_p, fecha_avance.isoformat()))
                    conn.commit()
                st.rerun()

        # --- SECCIÓN 7: EXPORTACIÓN (FUNCIONALIDAD PRESERVADA) ---
    st.divider()
    csv = prods.copy()
    for h in HITOS_LIST:
            csv[h] = csv['id'].apply(lambda x: "SI" if not segs[(segs['producto_id'] == x) & (segs['hito'] == h)].empty else "NO")
    st.download_button(
            "📥 Descargar Reporte de Avance (CSV)", 
            csv.to_csv(index=False).encode('utf-8'), 
            f"Seguimiento_{p_data['proyecto_text']}.csv",
            use_container_width=True
        )