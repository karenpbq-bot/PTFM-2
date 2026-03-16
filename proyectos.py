import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from base_datos import crear_proyecto, obtener_proyectos, eliminar_proyecto, obtener_supervisores, conectar

def mostrar():
    st.title("📁 Gestión de Proyectos Nuevo")
    
    # Modifica la línea de tabs:
    tab1, tab2, tab3, tab4 = st.tabs(["🆕 Registrar", "📋 Listado", "📦 Matriz", "📈 Métricas"])

    with tab1:
        st.subheader("Configuración y Cronograma Planificado")
        
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
            
            f_ini = c1.date_input("Fecha Inicio Global", value=date.today())
            f_fin = c2.date_input("Fecha Término Global", value=date.today() + timedelta(days=30))

        # 2. PONDERACIÓN DE ETAPAS
        st.write("### ⚖️ Distribución de Tiempo por Etapa (%)")
        etapas_nombres = ["Diseño", "Fabricación", "Traslado", "Instalación", "Entrega"]
        defaults = [15, 40, 10, 25, 10]
        pcts = {}
        cols_pct = st.columns(5)

        for i, et in enumerate(etapas_nombres):
            pcts[et] = cols_pct[i].number_input(f"{et} %", 0, 100, defaults[i])

        # 3. LÓGICA DE CÁLCULO Y PREVISUALIZACIÓN
        st.divider()
        dias_totales = (f_fin - f_ini).days

        if dias_totales <= 0:
            st.error("La fecha de término debe ser posterior a la de inicio.")
        else:
            cronograma_data = []
            fecha_aux = f_ini
            for et in etapas_nombres:
                dias_etapa = round(dias_totales * (pcts[et] / 100))
                f_f = fecha_aux + timedelta(days=max(0, dias_etapa - 1))
                cronograma_data.append({
                    "Etapa": et, 
                    "Inicio": fecha_aux, 
                    "Fin": f_f, 
                    "Días": dias_etapa
                })
                fecha_aux = f_f + timedelta(days=1)

            # RENDERIZADO DE PREVISUALIZACIÓN
            df_previs = pd.DataFrame(cronograma_data)
            # Formateamos solo para la tabla visual
            df_visual = df_previs.copy()
            df_visual["Inicio"] = df_visual["Inicio"].apply(lambda x: x.strftime("%d/%m/%Y"))
            df_visual["Fin"] = df_visual["Fin"].apply(lambda x: x.strftime("%d/%m/%Y"))

            st.write("#### 🔍 Previsualización del Cronograma Planificado")
            st.table(df_visual[["Etapa", "Inicio", "Fin", "Días"]])

            # Seccion 4 - UBICACIÓN: proyectos.py (Sección del botón de registro)

            # 4. BOTÓN DE REGISTRO
            if st.button("🚀 REGISTRAR PROYECTO NUEVO"):
                if not codigo or not nombre:
                    st.warning("El Código y Nombre son obligatorios.")
                elif sum(pcts.values()) != 100:
                    st.error(f"La suma de porcentajes debe ser 100% (Actual: {sum(pcts.values())}%)")
                else:
                    try:
                        # Preparamos el diccionario con todas las fechas como TEXTO ISO
                        datos_nube = {
                            "codigo": codigo,
                            "proyecto_text": nombre,
                            "cliente": cliente,
                            "partida": par,
                            "f_ini": f_ini.isoformat(),
                            "f_fin": f_fin.isoformat(),
                            "supervisor_id": dict_sups[sup_nom],
                            "estatus": "Activo",
                            "avance": 0,
                            "p_dis_i": cronograma_data[0]["Inicio"].isoformat(), 
                            "p_dis_f": cronograma_data[0]["Fin"].isoformat(),
                            "p_fab_i": cronograma_data[1]["Inicio"].isoformat(), 
                            "p_fab_f": cronograma_data[1]["Fin"].isoformat(),
                            "p_tra_i": cronograma_data[2]["Inicio"].isoformat(), 
                            "p_tra_f": cronograma_data[2]["Fin"].isoformat(),
                            "p_ins_i": cronograma_data[3]["Inicio"].isoformat(), 
                            "p_ins_f": cronograma_data[3]["Fin"].isoformat(),
                            "p_ent_i": cronograma_data[4]["Inicio"].isoformat(), 
                            "p_ent_f": cronograma_data[4]["Fin"].isoformat()
                        }
                        
                        # Ejecución del insert
                        conectar().table("proyectos").insert(datos_nube).execute()
                        st.success(f"✅ Proyecto {codigo} registrado.")
                        st.balloons()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar en nube: {e}")
                        
    with tab2:
        st.subheader("Listado Maestro")
        bus = st.text_input("🔍 Buscar...", placeholder="Escribe código, nombre o cliente")
        df_p = obtener_proyectos(bus)
        
        if not df_p.empty:
            # 1. Se muestra la tabla de proyectos encontrados
            st.dataframe(df_p[['codigo', 'proyecto_text', 'cliente', 'partida', 'avance']], hide_index=True)

            # === INSERCIÓN AQUÍ: SELECCIÓN PARA MATRIZ ===
            st.divider()
            opciones_proy = df_p['proyecto_display'].tolist()
            seleccionado = st.selectbox("🎯 Selecciona para gestionar Matriz de Productos:", ["-- Seleccionar --"] + opciones_proy)

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
            # 0. Recuperar nombre del proyecto para el título
            info_p = df_p[df_p['id'] == st.session_state.id_p_sel].iloc[0]
            nombre_proyecto = info_p['proyecto_display']
            
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
                                # LIMPIEZA DE DATOS (Evita el TypeError)
                                datos_producto = {
                                    "proyecto_id": int(st.session_state.id_p_sel),
                                    "ubicacion": str(u).strip(),
                                    "tipo": str(t).strip(),
                                    "ctd": int(c),
                                    "ml": float(m)
                                }
                                conectar().table("productos").insert(datos_producto).execute()
                                st.success("✅ Producto guardado"); st.rerun()
                            except Exception as e:
                                st.error(f"Error técnico al guardar: {e}")

            # --- 2. SECCIÓN: IMPORTAR LISTA DE PRODUCTOS ---
            with st.expander("📥 Importar Lista de Productos"):
                f_up = st.file_uploader("Subir Excel", type=["xlsx", "csv"])
                if f_up and st.button("🚀 Iniciar Importación Masiva"):
                    df_ex = pd.read_csv(f_up) if f_up.name.endswith('csv') else pd.read_excel(f_up)
                    # Limpiamos filas vacías
                    df_ex = df_ex.dropna(subset=['UBICACION', 'TIPO'])
                    lote = []
                    for _, r in df_ex.iterrows():
                        # LIMPIEZA DE DATOS DEL EXCEL
                        lote.append({
                            "proyecto_id": int(st.session_state.id_p_sel),
                            "ubicacion": str(r['UBICACION']).strip(),
                            "tipo": str(r['TIPO']).strip(),
                            "ctd": int(r['CTD']),
                            "ml": float(r['Medidas (ml)'])
                        })
                    conectar().table("productos").insert(lote).execute()
                    st.success(f"Se cargaron {len(lote)} productos"); st.rerun()

            # --- 3. VISUALIZACIÓN DE LA MATRIZ (4 COLUMNAS) ---
            st.divider()
            res_p = conectar().table("productos").select("ubicacion, tipo, ctd, ml").eq("proyecto_id", st.session_state.id_p_sel).execute()
            
            if res_p.data:
                df_matriz = pd.DataFrame(res_p.data)
                
                # Definimos el orden y nombres finales
                mapeo = {
                    'ubicacion': 'Ubicación',
                    'tipo': 'Tipo',
                    'ctd': 'Cantidad',
                    'ml': 'Metros Lineales (ml)'
                }
                
                # Creamos el dataframe unificado para evitar NameError
                df_unificado = df_matriz[list(mapeo.keys())].rename(columns=mapeo)
                
                # Mostramos la tabla unificada
                st.dataframe(df_unificado, hide_index=True, use_container_width=True)
                
                # Resumen de totales debajo de la tabla
                c1, c2 = st.columns(2)
                c1.info(f"**Total Piezas:** {int(df_unificado['Cantidad'].sum())}")
                c2.info(f"**Total Metraje:** {df_unificado['Metros Lineales (ml)'].sum():.2f} ml")

                if st.button("🗑️ Vaciar Matriz del Proyecto", type="primary"):
                    conectar().table("productos").delete().eq("proyecto_id", st.session_state.id_p_sel).execute()
                    st.rerun()
            else:
                st.info("La matriz está vacía.")
        else:
            st.info("⚠️ Selecciona un proyecto en la pestaña 'Listado y Búsqueda' para gestionar su matriz.")

    with tab4:
    if st.session_state.get('id_p_sel'):
        st.subheader("📊 Análisis de Cumplimiento por Hito")
        from base_datos import obtener_avance_por_hitos, obtener_productos_por_proyecto
        
        # Filtro rápido en métricas
        prods = obtener_productos_por_proyecto(st.session_state.id_p_sel)
        bus_m = st.text_input("Filtrar métricas por ubicación/tipo:", key="bus_met")
        if bus_m:
            prods = prods[prods['ubicacion'].str.contains(bus_m, case=False) | prods['tipo'].str.contains(bus_m, case=False)]
        
        avances = obtener_avance_por_hitos(st.session_state.id_p_sel, prods)
        
        # Mostrar métricas en columnas
        cols = st.columns(4)
        for i, (hito, porcentaje) in enumerate(avances.items()):
            cols[i % 4].metric(hito, f"{porcentaje}%")
            cols[i % 4].progress(porcentaje / 100)
    else:
        st.info("Selecciona un proyecto en 'Listado' para ver métricas.")
3. El ajuste Final en ejecucion.py (Para que el Gantt pinte)
Ahora que ya tenemos los porcentajes, el Gantt debe usarlos para dibujar las barras reales solo si el avance es mayor a 0.

Reemplaza la sección C de ejecucion.py por esta:

Python
            # --- C. DATA REAL (BASADA EN MÉTRICAS DE HITOS) ---
            from base_datos import obtener_avance_por_hitos
            # Obtenemos el avance real de cada hito
            avances_reales = obtener_avance_por_hitos(id_p)
            
            # Grupos de hitos que corresponden a cada etapa del Gantt
            GRUPOS_GANTT = {
                "Diseño": ["Diseñado"],
                "Fabricación": ["Fabricado"],
                "Traslado": ["Material en Obra", "Material en Ubicación"],
                "Instalación": ["Instalación de Estructura", "Instalación de Puertas o Frentes"],
                "Entrega": ["Revisión y Observaciones", "Entrega"]
            }

            for etapa_gantt, hitos_hijos in GRUPOS_GANTT.items():
                # Calculamos el promedio de avance de los hitos que componen la etapa
                suma_av = sum([avances_reales.get(h, 0) for h in hitos_hijos])
                promedio_etapa = suma_av / len(hitos_hijos)

                if promedio_etapa > 0:
                    # Dibujamos la barra real debajo de la planificada
                    # Usamos las fechas planificadas como base visual
                    data_final.append(dict(
                        Proyecto=p_nom, 
                        Etapa=etapa_gantt, 
                        Inicio=p_data.get(f'p_{etapa_gantt[:3].lower()}_i'),
                        # La longitud de la barra real depende del % de avance de esa etapa
                        Fin=p_data.get(f'p_{etapa_gantt[:3].lower()}_f'), 
                        Color=color_real, 
                        Tipo="2_Real",
                        Avance_Etapa=promedio_etapa # Para mostrar en el hover
                    ))
