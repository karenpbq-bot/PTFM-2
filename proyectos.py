import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from base_datos import crear_proyecto, obtener_proyectos, eliminar_proyecto_completo, obtener_supervisores, conectar

def mostrar():
    st.title("📁 Gestión de Proyectos Nuevo")
    
    tab1, tab2, tab3 = st.tabs(["🆕 Registrar Proyecto Nuevo", "📋 Listado y Búsqueda", "📦 Matriz de Productos"])

    # =========================================================
    # PESTAÑA 1: REGISTRAR PROYECTO NUEVO
    # =========================================================
    with tab1:
        st.subheader("Configuración y Cronograma Planificado")

        # --- LÓGICA DE CONTROL DE ESTADOS DE FECHAS (CALLBACKS) ---
        # Inicialización segura de fechas globales por defecto
        if "f_ini_global" not in st.session_state:
            st.session_state.f_ini_global = date.today()
        if "f_fin_global" not in st.session_state:
            st.session_state.f_fin_global = date.today() + timedelta(days=30)

        etapas_lista = ["Diseño", "Fabricación", "Traslado", "Instalación", "Entrega"]
        
        # Inicialización de las fechas de las etapas enlazadas
        for et in etapas_lista:
            if f"ini_{et}" not in st.session_state:
                st.session_state[f"ini_{et}"] = st.session_state.f_ini_global
            if f"fin_{et}" not in st.session_state:
                st.session_state[f"fin_{et}"] = st.session_state.f_fin_global

        # Callback 1: Si cambia Inicio Global, actualiza los inicios cuidando que no superen al fin actual
        def al_cambiar_inicio_global():
            nuevo_ini = st.session_state.f_ini_global
            for et in etapas_lista:
                st.session_state[f"ini_{et}"] = nuevo_ini
                # Control de seguridad contra colisiones
                if st.session_state[f"fin_{et}"] < nuevo_ini:
                    st.session_state[f"fin_{et}"] = nuevo_ini

        # Callback 2: Si cambia Término Global, actualiza los fines cuidando que no sean menores al inicio actual
        def al_cambiar_fin_global():
            nuevo_fin = st.session_state.f_fin_global
            for et in etapas_lista:
                st.session_state[f"fin_{et}"] = nuevo_fin
                # Control de seguridad contra colisiones
                if st.session_state[f"ini_{et}"] > nuevo_fin:
                    st.session_state[f"ini_{et}"] = nuevo_fin

        # Callback 3: Si cambia el Inicio de Fabricación, sincroniza automáticamente Traslado, Instalación y Entrega
        def al_cambiar_inicio_fabricacion():
            nuevo_ini_fab = st.session_state["ini_Fabricación"]
            for et in ["Traslado", "Instalación", "Entrega"]:
                st.session_state[f"ini_{et}"] = nuevo_ini_fab
                if st.session_state[f"fin_{et}"] < nuevo_ini_fab:
                    st.session_state[f"fin_{et}"] = nuevo_ini_fab


        # 1. DATOS BÁSICOS
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            codigo = c1.text_input("Código (DNI)", placeholder="Ej: PTF-001")
            nombre = c2.text_input("Nombre del Proyecto")
            cliente = c3.text_input("Cliente")
            
            par = c1.text_input("Partida")
            df_sups = obtener_supervisores()
            dict_sups = {r['nombre_real']: r['id'] for _, r in df_sups.iterrows()}
            sup_nom = c2.selectbox("Responsable:", options=list(dict_sups.keys()))
            
            # Cantidad de tableros estimados
            total_tableros_proy = c3.number_input("Número Total de Tableros:", min_value=1, value=10, step=1)
            
            # Inputs globales vinculados de forma segura
            f_ini = c1.date_input(
                "Fecha Inicio Global", 
                key="f_ini_global", 
                on_change=al_cambiar_inicio_global, 
                format="DD/MM/YYYY"
            )
            f_fin = c2.date_input(
                "Fecha Término Global", 
                key="f_fin_global", 
                on_change=al_cambiar_fin_global, 
                format="DD/MM/YYYY"
            )

        # 2. SECCIÓN PLEGABLE DE CRONOGRAMA EN FORMATO MATRIZ (Protegida contra desbordamientos)
        with st.expander("📅 Configurar Fechas y Traslapes por Etapa", expanded=True):
            st.info("💡 Las etapas operativas se sincronizan automáticamente en cascada según las fechas globales y de producción.")
            
            fechas_etapas = {}
            
            # Encabezados de nuestra matriz compacta
            col_hdr_etapa, col_hdr_ini, col_hdr_fin = st.columns([2, 3, 3])
            col_hdr_etapa.markdown("**Etapa**")
            col_hdr_ini.markdown("**Fecha Inicio**")
            col_hdr_fin.markdown("**Fecha Fin**")
            st.markdown("<hr style='margin: 0.5em 0px 1em 0px;'>", unsafe_allow_html=True)

            # --- 1. FILA: DISEÑO ---
            c_et1, c_ini1, c_fin1 = st.columns([2, 3, 3])
            c_et1.markdown("<div style='padding-top: 0.5em;'><b>Diseño</b></div>", unsafe_allow_html=True)
            
            # Dinamismo seguro: Usamos variables intermedias calculadas de session_state para aislar los límites
            val_ini_dis = st.session_state["ini_Diseño"]
            val_fin_dis = st.session_state["fin_Diseño"]
            
            ini_dis = c_ini1.date_input("Inicio Diseño", value=val_ini_dis, min_value=f_ini, max_value=f_fin, format="DD/MM/YYYY", key="ini_Diseño", label_visibility="collapsed")
            fin_dis = c_fin1.date_input("Fin Diseño", value=val_fin_dis, min_value=ini_dis, max_value=f_fin, format="DD/MM/YYYY", key="fin_Diseño", label_visibility="collapsed")
            fechas_etapas["Diseño"] = {"Inicio": ini_dis, "Fin": fin_dis, "Días": max(1, (fin_dis - ini_dis).days + 1)}

            # --- 2. FILA: FABRICACIÓN ---
            c_et2, c_ini2, c_fin2 = st.columns([2, 3, 3])
            c_et2.markdown("<div style='padding-top: 0.5em;'><b>Fabricación</b></div>", unsafe_allow_html=True)
            
            val_ini_fab = st.session_state["ini_Fabricación"]
            val_fin_fab = st.session_state["fin_Fabricación"]
            
            ini_fab = c_ini2.date_input("Inicio Fabricación", value=val_ini_fab, min_value=f_ini, max_value=f_fin, format="DD/MM/YYYY", key="ini_Fabricación", on_change=al_cambiar_inicio_fabricacion, label_visibility="collapsed")
            fin_fab = c_fin2.date_input("Fin Fabricación", value=val_fin_fab, min_value=ini_fab, max_value=f_fin, format="DD/MM/YYYY", key="fin_Fabricación", label_visibility="collapsed")
            fechas_etapas["Fabricación"] = {"Inicio": ini_fab, "Fin": fin_fab, "Días": max(1, (fin_fab - ini_fab).days + 1)}

            # --- 3. FILAS: TRASLADO, INSTALACIÓN Y ENTREGA ---
            etapas_dependientes = ["Traslado", "Instalación", "Entrega"]
            for et in etapas_dependientes:
                c_et, c_ini, c_fin = st.columns([2, 3, 3])
                c_et.markdown(f"<div style='padding-top: 0.5em;'><b>{et}</b></div>", unsafe_allow_html=True)
                
                val_ini_et = st.session_state[f"ini_{et}"]
                val_fin_et = st.session_state[f"fin_{et}"]
                
                ini_et = c_ini.date_input(f"Inicio {et}", value=val_ini_et, min_value=f_ini, max_value=f_fin, format="DD/MM/YYYY", key=f"ini_{et}", label_visibility="collapsed")
                fin_et = c_fin.date_input(f"Fin {et}", value=val_fin_et, min_value=ini_et, max_value=f_fin, format="DD/MM/YYYY", key=f"fin_{et}", label_visibility="collapsed")
                
                fechas_etapas[et] = {
                    "Inicio": ini_et,
                    "Fin": fin_et,
                    "Días": max(1, (fin_et - ini_et).days + 1)
                }

            # Guardamos los días de fabricación reales para las métricas operativas
            st.session_state.dias_fab_calculados = fechas_etapas["Fabricación"]["Días"]

        # 3. CARD INFORMATIVA DE OPERACIONES Y BOTÓN DE REGISTRO
        st.markdown("<br>", unsafe_allow_html=True)
        
        dias_fabricacion_reales = st.session_state.dias_fab_calculados
        tableros_por_dia = total_tableros_proy / dias_fabricacion_reales
        
        col_m1, col_m2 = st.columns(2)
        col_m1.metric(
            label="📅 Plazo Real de Fabricación Configurado:",
            value=f"{dias_fabricacion_reales} días útiles",
            help="Días calendario asignados a la Fabricación."
        )
        col_m2.metric(
            label="🪚 Exigencia de Corte en Taller:",
            value=f"{tableros_por_dia:.2f} tableros / día",
            help="Carga diaria del área de optimización."
        )
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("🚀 REGISTRAR PROYECTO NUEVO", type="primary"):
            if not codigo or not nombre:
                st.warning("El Código y Nombre son obligatorios.")
            elif (st.session_state.f_fin_global - st.session_state.f_ini_global).days <= 0:
                st.error("La fecha de término global debe ser posterior a la de inicio.")
            else:
                try:
                    # Empaquetamos los datos en formato ISO nativo para Supabase
                    datos_nube = {
                        "codigo": codigo,
                        "proyecto_text": nombre,
                        "cliente": cliente,
                        "partida": par,
                        "total_tableros": int(total_tableros_proy),
                        "f_ini": st.session_state.f_ini_global.isoformat(),
                        "f_fin": st.session_state.f_fin_global.isoformat(),
                        "supervisor_id": dict_sups[sup_nom],
                        "estatus": "Activo",
                        "avance": 0,
                        "p_dis_i": fechas_etapas["Diseño"]["Inicio"].isoformat(), 
                        "p_dis_f": fechas_etapas["Diseño"]["Fin"].isoformat(),
                        "p_fab_i": fechas_etapas["Fabricación"]["Inicio"].isoformat(), 
                        "p_fab_f": fechas_etapas["Fabricación"]["Fin"].isoformat(),
                        "p_tra_i": fechas_etapas["Traslado"]["Inicio"].isoformat(), 
                        "p_tra_f": fechas_etapas["Traslado"]["Fin"].isoformat(),
                        "p_ins_i": fechas_etapas["Instalación"]["Inicio"].isoformat(), 
                        "p_ins_f": fechas_etapas["Instalación"]["Fin"].isoformat(),
                        "p_ent_i": fechas_etapas["Entrega"]["Inicio"].isoformat(), 
                        "p_ent_f": fechas_etapas["Entrega"]["Fin"].isoformat()
                    }
                    
                    conectar().table("proyectos").insert(datos_nube).execute()
                    st.success(f"✅ Proyecto {codigo} registrado con éxito en la base de datos.")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error técnico al guardar en Supabase: {e}")
                        
    with tab2:
        st.subheader("Listado Maestro")
        bus = st.text_input("🔍 Buscar...", placeholder="Escribe código, nombre o cliente")
        df_p = obtener_proyectos(bus)
        
        if not df_p.empty:
            # 1. Se muestra la tabla de proyectos encontrados
            st.dataframe(df_p[['codigo', 'proyecto_text', 'cliente', 'partida', 'avance']], hide_index=True)

            # === SELECCIÓN PARA GESTIÓN Y ELIMINACIÓN ===
            st.divider()
            opciones_proy = df_p['proyecto_display'].tolist()
            seleccionado = st.selectbox("🎯 Selecciona Proyecto para Eliminar:", ["-- Seleccionar --"] + opciones_proy, key="sel_eliminar_proy")

            if seleccionado != "-- Seleccionar --":
                # Extraemos el ID del proyecto seleccionado
                id_sel = df_p[df_p['proyecto_display'] == seleccionado]['id'].values[0]
                st.session_state.id_p_sel = id_sel
                
                st.success(f"✅ Proyecto '{seleccionado}' seleccionado.")
                
                # --- NUEVA ZONA DE PELIGRO (Punto 1 de tus requerimientos) ---
                with st.expander("🚫 Zona de Peligro"):
                    st.write("Esta acción eliminará el proyecto y TODOS sus registros asociados (Productos, Seguimientos e Incidencias).")
                    # Checkbox de seguridad adicional
                    confirmar = st.checkbox(f"Confirmo que deseo borrar permanentemente el proyecto {seleccionado}")
                    
                    if st.button("🔥 Eliminar Proyecto Completo", type="primary", disabled=not confirmar):
                        if eliminar_proyecto_completo(id_sel):
                            st.success("Proyecto eliminado con éxito.")
                            st.session_state.id_p_sel = None # Limpiamos la selección
                            st.rerun()
                
                st.info("Ahora puedes ir a la pestaña **'📦 Matriz de Productos'** para cargar el Excel o agregar ítems manualmente.")
                
            # === INSERCIÓN AQUÍ: SELECCIÓN PARA MATRIZ ===
            st.divider()
            opciones_proy = df_p['proyecto_display'].tolist()
            seleccionado = st.selectbox("🎯 Selecciona para gestionar Matriz de Productos:", ["-- Seleccionar --"] + opciones_proy, key="sel_matriz_proy")

            if seleccionado != "-- Seleccionar --":
                id_sel = df_p[df_p['proyecto_display'] == seleccionado]['id'].values[0]
                st.session_state.id_p_sel = id_sel
                st.success(f"Proyecto '{seleccionado}' seleccionado para Matriz.")
            if seleccionado != "-- Seleccionar --":
                # Extraemos el ID del proyecto seleccionado
                id_sel = df_p[df_p['proyecto_display'] == seleccionado]['id'].values[0]
                st.session_state.id_p_sel = id_sel
                
                st.success(f"✅ Proyecto '{seleccionado}' seleccionado.")
                st.info("Ahora puedes ir a la pestaña **'📦 Matriz de Productos'** para cargar el Excel o agregar ítems manualmente.")
    
    with tab3:
        if st.session_state.get('id_p_sel'):
            # 0. Recuperar info del proyecto para el título y código base
            info_p = df_p[df_p['id'] == st.session_state.id_p_sel].iloc[0]
            nombre_proyecto = info_p['proyecto_display']
            p_cod_base = info_p['codigo'] # El prefijo del proyecto (ej: PTF-001)
            
            st.subheader(f"📦 Matriz de Productos: {nombre_proyecto}")

            # --- 1. SECCIÓN: AGREGAR PRODUCTO (MANUAL) ---
            with st.expander("➕ Agregar Producto", expanded=False):
                with st.form("form_producto_manual", clear_on_submit=True):
                    c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
                    u = c1.text_input("Ubicación")
                    t = c2.text_input("Tipo")
                    c = c3.number_input("Cantidad", min_value=1, value=1, step=1)
                    m = c4.number_input("ML", min_value=0.0, format="%.2f")
                    
                    if st.form_submit_button("Guardar Producto"):
                        if u and t:
                            try:
                                # CONSULTA CORRELATIVO ACTUAL
                                res_c = conectar().table("productos").select("id", count="exact").eq("proyecto_id", st.session_state.id_p_sel).execute()
                                nuevo_n = (res_c.count if res_c.count else 0) + 1
                                etiqueta = f"{p_cod_base}-{str(nuevo_n).zfill(4)}"

                                datos_producto = {
                                    "proyecto_id": int(st.session_state.id_p_sel),
                                    "codigo_etiqueta": etiqueta, # <--- NUEVA COLUMNA
                                    "ubicacion": str(u).strip(),
                                    "tipo": str(t).strip(),
                                    "ctd": int(c),
                                    "ml": float(m)
                                }
                                conectar().table("productos").insert(datos_producto).execute()
                                st.success(f"✅ Guardado con código: {etiqueta}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error técnico al guardar: {e}")

            # --- 2. SECCIÓN: IMPORTAR LISTA DE PRODUCTOS (EXCEL) ---
            with st.expander("📥 Importar Lista de Productos"):
                f_up = st.file_uploader("Subir Excel", type=["xlsx", "csv"])
                if f_up and st.button("🚀 Iniciar Importación Masiva"):
                    try:
                        df_ex = pd.read_csv(f_up) if f_up.name.endswith('csv') else pd.read_excel(f_up)
                        df_ex = df_ex.dropna(subset=['UBICACION', 'TIPO'])
                        
                        # CONSULTA CORRELATIVO ACTUAL PARA EMPEZAR LA SERIE
                        res_count = conectar().table("productos").select("id", count="exact").eq("proyecto_id", st.session_state.id_p_sel).execute()
                        conteo_actual = res_count.count if res_count.count else 0
                        
                        lote = []
                        # Usamos i para el correlativo sumando al conteo actual
                        for i, (index, r) in enumerate(df_ex.iterrows(), start=1):
                            correlativo = str(conteo_actual + i).zfill(4)
                            codigo_etiqueta = f"{p_cod_base}-{correlativo}"
                            
                            lote.append({
                                "proyecto_id": int(st.session_state.id_p_sel),
                                "codigo_etiqueta": codigo_etiqueta, # <--- NUEVA COLUMNA
                                "ubicacion": str(r['UBICACION']).strip(),
                                "tipo": str(r['TIPO']).strip(),
                                "ctd": int(r['CTD']),
                                "ml": float(r['Medidas (ml)']) # Asegúrate que el Excel tenga este nombre exacto
                            })
                        
                        conectar().table("productos").insert(lote).execute()
                        st.success(f"✅ Se cargaron {len(lote)} productos nuevos con códigos correlativos.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al importar: {e}")

            # --- 3. VISUALIZACIÓN DE LA MATRIZ ---
            st.divider()
            # Añadimos codigo_etiqueta a la consulta
            res_p = conectar().table("productos").select("codigo_etiqueta, ubicacion, tipo, ctd, ml").eq("proyecto_id", st.session_state.id_p_sel).order("codigo_etiqueta").execute()
            
            if res_p.data:
                df_matriz = pd.DataFrame(res_p.data)
                mapeo = {
                    'codigo_etiqueta': 'Código ID',
                    'ubicacion': 'Ubicación',
                    'tipo': 'Tipo',
                    'ctd': 'Cantidad',
                    'ml': 'ML'
                }
                df_unificado = df_matriz.rename(columns=mapeo)
                st.dataframe(df_unificado, hide_index=True, use_container_width=True)
                
                c1, c2 = st.columns(2)
                c1.info(f"**Total Piezas:** {int(df_unificado['Cantidad'].sum())}")
                c2.info(f"**Total Metraje:** {df_unificado['ML'].sum():.2f} ml")

                if st.button("🗑️ Vaciar Matriz del Proyecto", type="primary"):
                    conectar().table("productos").delete().eq("proyecto_id", st.session_state.id_p_sel).execute()
                    st.rerun()
            else:
                st.info("La matriz está vacía.")
        else:
            st.info("⚠️ Selecciona un proyecto en la pestaña 'Listado y Búsqueda' para gestionar su matriz.")
