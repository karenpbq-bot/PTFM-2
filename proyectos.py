import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from base_datos import crear_proyecto, obtener_proyectos, eliminar_proyecto, obtener_supervisores, conectar

def mostrar():
    st.title("📁 Gestión de Proyectos Nuevo")
    
    tab1, tab2, tab3 = st.tabs(["🆕 Registrar Proyecto Nuevo", "📋 Listado y Búsqueda", "📦 Matriz de Productos"])

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

            # 4. BOTÓN DE REGISTRO (Dentro del else para asegurar que existan las fechas)
            if st.button("🚀 REGISTRAR PROYECTO NUEVO"):
                if not codigo or not nombre:
                    st.warning("El Código y Nombre son obligatorios.")
                elif sum(pcts.values()) != 100:
                    st.error(f"La suma de porcentajes debe ser 100% (Actual: {sum(pcts.values())}%)")
                else:
                    datos_nube = {
                        "codigo": codigo,
                        "proyecto_text": nombre,
                        "cliente": cliente,
                        "partida": par,
                        "f_ini": str(f_ini),
                        "f_fin": str(f_fin),
                        "supervisor_id": dict_sups[sup_nom],
                        "estatus": "Activo",
                        "avance": 0,
                        "p_dis_i": str(cronograma_data[0]["Inicio"]), "p_dis_f": str(cronograma_data[0]["Fin"]),
                        "p_fab_i": str(cronograma_data[1]["Inicio"]), "p_fab_f": str(cronograma_data[1]["Fin"]),
                        "p_tra_i": str(cronograma_data[2]["Inicio"]), "p_tra_f": str(cronograma_data[2]["Fin"]),
                        "p_ins_i": str(cronograma_data[3]["Inicio"]), "p_ins_f": str(cronograma_data[3]["Fin"]),
                        "p_ent_i": str(cronograma_data[4]["Inicio"]), "p_ent_f": str(cronograma_data[4]["Fin"])
                    }
                    
                    try:
                        conectar().table("proyectos").insert(datos_nube).execute()
                        st.success(f"✅ Proyecto {codigo} registrado con cronograma automático.")
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
            # Recuperamos la info del proyecto desde el DataFrame df_p que cargaste en tab2
            info_p = df_p[df_p['id'] == st.session_state.id_p_sel].iloc[0]
            nombre_proyecto = info_p['proyecto_display']
            
            st.subheader(f"📦 Matriz de Productos: {nombre_proyecto}")
            
            # --- 1. SECCIÓN: CARGA MANUAL (PLEGABLE Y EN FILA ÚNICA) ---
            with st.expander("➕ Agregar Producto", expanded=False):
                with st.form("form_producto_manual", clear_on_submit=True):
                    # 4 campos uno al lado del otro
                    c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
                    u = c1.text_input("Ubicación", placeholder="Ej: 101")
                    t = c2.text_input("Tipo", placeholder="Ej: Closet")
                    c = c3.number_input("Cant.", min_value=1, step=1)
                    m = c4.number_input("ML", min_value=0.0, format="%.2f")
                    
                    if st.form_submit_button("Guardar Producto"):
                        if u and t:
                            try:
                                conectar().table("productos").insert({
                                    "proyecto_id": st.session_state.id_p_sel,
                                    "ubicacion": u, 
                                    "tipo": t, 
                                    "ctd": int(c), # <--- Aquí aseguramos la cantidad
                                    "ml": m
                                }).execute()
                                st.success("Producto añadido correctamente")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al guardar: {e}")
                        else:
                            st.warning("Ubicación y Tipo son obligatorios.")

            # --- 2. SECCIÓN: IMPORTAR LISTA DE PRODUCTOS (OPTIMIZADA) ---
            with st.expander("📥 Importar Lista de Productos (Excel/CSV)"):
                st.info("Columnas requeridas: UBICACION, TIPO, CTD, Medidas (ml)")
                f_up = st.file_uploader("Seleccionar archivo", type=["xlsx", "csv"], key="uploader_v2")
                
                if f_up and st.button("🚀 Iniciar Importación"):
                    try:
                        # Lectura del archivo
                        df_ex = pd.read_csv(f_up) if f_up.name.endswith('csv') else pd.read_excel(f_up)
                        
                        # Limpieza rápida: eliminamos filas donde la ubicación o tipo sean nulos
                        df_ex = df_ex.dropna(subset=['UBICACION', 'TIPO'])
                        
                        # CREACIÓN DEL LOTE (List Comprehension para velocidad)
                        lote_productos = [
                            {
                                "proyecto_id": int(st.session_state.id_p_sel),
                                "ubicacion": str(r['UBICACION']),
                                "tipo": str(r['TIPO']),
                                "ctd": int(r['CTD']),
                                "ml": float(r['Medidas (ml)'])
                            }
                            for _, r in df_ex.iterrows()
                        ]
                        
                        # INSERCIÓN MASIVA EN UN SOLO VIAJE
                        if lote_productos:
                            conectar().table("productos").insert(lote_productos).execute()
                            st.success(f"✅ ¡Éxito! Se han cargado {len(lote_productos)} productos al proyecto.")
                            st.balloons()
                            st.rerun()
                            
                    except Exception as e:
                        st.error(f"Error en la importación: {e}")

            # --- 3. VISUALIZACIÓN DE LA MATRIZ UNIFICADA ---
            st.divider()
            # Consultamos todos los campos de la tabla productos
            res_p = conectar().table("productos").select("ubicacion, tipo, ctd, ml").eq("proyecto_id", st.session_state.id_p_sel).execute()
            
            if res_p.data:
                # 1. Creamos el DataFrame con la data cruda
                df_matriz = pd.DataFrame(res_p.data)
                
                # 2. Definimos el orden y los nombres exactos de las 4 columnas
                # Asegúrate de que los nombres de la izquierda coincidan con tu base de datos
                mapeo_final = {
                    'ubicacion': 'Ubicación',
                    'tipo': 'Tipo',
                    'ctd': 'Cantidad',
                    'ml': 'Metros Lineales (ml)'
                }
                
                # 3. Filtramos y Reordenamos para asegurar que las 4 estén juntas
                columnas_disponibles = [c for c in mapeo_final.keys() if c in df_matriz.columns]
                df_unificado = df_matriz[columnas_disponibles].rename(columns=mapeo_final)
                
                # 4. MOSTRAMOS LA MATRIZ ÚNICA (Aquí verás las 4 columnas alineadas)
                st.dataframe(df_unificado, hide_index=True, use_container_width=True)
                
                # --- Resumen informativo al pie de la matriz ---
                c1, c2, c3 = st.columns(3)
                c1.write(f"**Total Ítems:** {len(df_unificado)}")
                if 'Cantidad' in df_unificado.columns:
                    c2.write(f"**Total Piezas:** {int(df_unificado['Cantidad'].sum())}")
                if 'Metros Lineales (ml)' in df_unificado.columns:
                    c3.write(f"**Total Metraje:** {df_unificado['Metros Lineales (ml)'].sum():.2f} ml")

                if st.button("🗑️ Vaciar Matriz del Proyecto", type="primary"):
                    conectar().table("productos").delete().eq("proyecto_id", st.session_state.id_p_sel).execute()
                    st.rerun()
            else:
                st.info("La matriz está vacía. Usa las opciones de arriba para cargar productos.")
