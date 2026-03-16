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
            st.markdown("### 🎯 Gestión de Matriz por Selección")
            
            # Creamos una lista para que elijas el proyecto que acabas de buscar
            opciones_proy = df_p['proyecto_display'].tolist()
            seleccionado = st.selectbox("Selecciona un proyecto para gestionar sus productos:", ["-- Seleccionar --"] + opciones_proy)

            if seleccionado != "-- Seleccionar --":
                # Extraemos el ID del proyecto seleccionado
                id_sel = df_p[df_p['proyecto_display'] == seleccionado]['id'].values[0]
                st.session_state.id_p_sel = id_sel
                
                st.success(f"✅ Proyecto '{seleccionado}' seleccionado.")
                st.info("Ahora puedes ir a la pestaña **'📦 Matriz de Productos'** para cargar el Excel o agregar ítems manualmente.")
    
    with tab3: # Nueva pestaña
    if st.session_state.id_p_sel:
        st.subheader("📥 Carga y Gestión de Matriz")
        
        col_manual, col_import = st.columns(2)
        
        with col_import:
            with st.expander("Subir archivo Excel (Metrados)"):
                f_up = st.file_uploader("Seleccione el archivo .xlsx", type=["xlsx", "csv"])
                if f_up and st.button("Procesar Matriz"):
                    # Lógica para leer el archivo de Eliza
                    df_ex = pd.read_csv(f_up) if f_up.name.endswith('csv') else pd.read_excel(f_up)
                    # Limpieza: Si la primera fila es nula, saltar (skiprows)
                    for _, r in df_ex.iterrows():
                        # Función que debemos asegurar en base_datos.py
                        agregar_producto_manual(st.session_state.id_p_sel, r['UBICACION'], r['TIPO'], r['CTD'], r['Medidas (ml)'])
                    st.success("Matriz cargada correctamente.")
                    st.rerun()
        
        # Aquí iría la visualización de la tabla con botones 💾 y 🗑️
    else:
        st.info("Por favor, selecciona un proyecto en la pestaña 'Listado' para ver su matriz.")

    
                st.info("Ahora puedes ir a la pestaña **'📦 Matriz de Productos'** para cargar el Excel o agregar ítems manualmente.")go', 'proyecto_text', 'cliente', 'partida', 'avance']], hide_index=True)
