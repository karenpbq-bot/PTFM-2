import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from base_datos import crear_proyecto, obtener_proyectos, eliminar_proyecto_completo, obtener_supervisores, conectar

def mostrar():
    # Estilos CSS profesionales para mejorar la visualización de la interfaz
    st.markdown("""
        <style>
        .report-title { font-size: 28px; font-weight: bold; color: #1E3A8A; margin-bottom: 0.5rem; }
        [data-testid="stMetricValue"] { font-size: 20px !important; font-weight: bold !important; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<p class="report-title">📁 Centro de Control y Gestión de Proyectos</p>', unsafe_allow_html=True)
    
    # REINGENIERÍA: Listado es la primera pestaña en visualizarse
    tab_listado, tab_registro, tab_matriz = st.tabs(["📋 Listado, Búsqueda y Edición", "🆕 Registrar Proyecto Nuevo", "📦 Matriz de Productos"])

    # Carga inicial de supervisores para mapeo de nombres de responsables
    df_sups = obtener_supervisores()
    dict_sups = {r['nombre_real']: r['id'] for _, r in df_sups.iterrows()}
    dict_sups_inv = {r['id']: r['nombre_real'] for _, r in df_sups.iterrows()}

    lista_estados = ["En Cotización", "En ejecución", "Cerrado"]

    # =========================================================
    # PESTAÑA 1: LISTADO, BÚSQUEDA Y EDICIÓN (MATRIZ DE PROYECTOS)
    # =========================================================
    with tab_listado:
        st.subheader("📊 Matriz de Proyectos")
        
        # REINGENIERÍA DE INTERFAZ: Buscador y Filtro de Estado a la misma altura
        c_bus1, c_bus2 = st.columns([4, 4])
        
        with c_bus1:
            bus = st.text_input("🔍 Buscar proyecto...", placeholder="Escribe código, nombre del proyecto o cliente...", label_visibility="visible")
        
        with c_bus2:
            estado_filtro = st.selectbox("🚦 Filtrar por Estado:", ["-- Todos los Estados --"] + lista_estados, index=0)
        
        # 1. Obtención inicial de datos mediante el buscador por texto
        df_p = obtener_proyectos(bus)
        
        if not df_p.empty:
            # Asegurar de forma segura la existencia de la columna de estado
            if 'estado' not in df_p.columns:
                df_p['estado'] = 'En Cotización'
            
            # 2. Aplicación del filtro por estado si se seleccionó uno específico
            if estado_filtro != "-- Todos los Estados --":
                df_p = df_p[df_p['estado'] == estado_filtro].copy()

        # Renderizar la matriz solo si quedan registros tras el filtrado compuesto
        if not df_p.empty:
            # Mapear el ID del supervisor al nombre real para visualización en la matriz
            df_p['responsable'] = df_p['supervisor_id'].map(dict_sups_inv).fillna("Sin Asignar")
            
            # Preparar el DataFrame para el editor interactivo
            df_editor = df_p.copy()
            df_editor['responsable'] = df_editor['responsable'].astype(str)

            # RENDERIZADO DE LA MATRIZ CON EDICIÓN EXCLUSIVA DE ESTADO
            cambios_tabla = st.data_editor(
                df_editor[['id', 'codigo', 'proyecto_text', 'partida', 'responsable', 'total_tableros', 'estado', 'avance']],
                column_config={
                    "id": None, # Oculta el ID interno
                    "codigo": st.column_config.TextColumn("Código", disabled=True),
                    "proyecto_text": st.column_config.TextColumn("Proyecto", disabled=True),
                    "partida": st.column_config.TextColumn("Partida", disabled=True),
                    "responsable": st.column_config.TextColumn("Responsable", disabled=True),
                    "total_tableros": st.column_config.NumberColumn("Nro Tableros", format="%d", disabled=True),
                    "avance": st.column_config.ProgressColumn("Avance Real", format="%.2f%%", min_value=0, max_value=100, disabled=True),
                    # El Estado es totalmente mutable directamente en la celda
                    "estado": st.column_config.SelectboxColumn("Estado", options=lista_estados, required=True, disabled=False)
                },
                hide_index=True,
                use_container_width=True,
                key="matriz_proyectos_editable_directo"
            )

            # PROCESAMIENTO AUTOMÁTICO DE CAMBIOS DE ESTADO DESDE LA MATRIZ
            if not cambios_tabla.equals(df_editor[['id', 'codigo', 'proyecto_text', 'partida', 'responsable', 'total_tableros', 'estado', 'avance']]):
                for index, row in cambios_tabla.iterrows():
                    id_fila = int(row['id'])
                    estado_nuevo = str(row['estado'])
                    estado_antiguo = str(df_p[df_p['id'] == id_fila].iloc[0]['estado'] if 'estado' in df_p.columns else "En Cotización")
                    
                    if estado_nuevo != estado_antiguo:
                        try:
                            conectar().table("proyectos").update({"estado": estado_nuevo}).eq("id", id_fila).execute()
                            st.success(f"✅ Estado actualizado a '{estado_nuevo}' directamente en la Matriz.")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar el estado: {e}")

            st.divider()
            
            # --- PANEL DE ACCIÓN SUB-SIGUIENTE: EDICIÓN DE PARÁMETROS GENERALES ---
            opciones_proy = df_p['proyecto_display'].tolist()
            seleccionado = st.selectbox("🎯 Seleccione un proyecto para editar sus datos generales o eliminarlo:", ["-- Seleccionar para Gestionar --"] + opciones_proy)

            if seleccionado != "-- Seleccionar para Gestionar --":
                fila_proy = df_p[df_p['proyecto_display'] == seleccionado].iloc[0]
                id_sel = int(fila_proy['id'])
                st.session_state.id_p_sel = id_sel 

                # Formulario reactivo con todos los datos editables del proyecto (A excepción del estado)
                with st.form("form_edicion_integral_proyecto"):
                    st.markdown(f"### 🛠️ Sección de Edición: **{fila_proy['proyecto_text']}**")
                    st.caption("Nota: El estado se edita directamente haciendo doble clic sobre la celda en la 'Matriz de Proyectos' de arriba.")
                    
                    c_ed1, c_ed2 = st.columns(2)
                    edit_nombre = c_ed1.text_input("Nombre del Proyecto (Obligatorio):", value=str(fila_proy['proyecto_text']))
                    edit_cliente = c_ed2.text_input("Cliente / Razón Social (Obligatorio):", value=str(fila_proy['cliente'] if fila_proy['cliente'] else ""))
                    edit_partida = c_ed1.text_input("Partida Presupuestal (Obligatorio):", value=str(fila_proy['partida'] if fila_proy['partida'] else ""))
                    
                    edit_codigo = c_ed2.text_input("Código de Proyecto / DNI:", value=str(fila_proy['codigo'] if fila_proy['codigo'] else ""))
                    
                    nom_resp_actual = dict_sups_inv.get(fila_proy['supervisor_id'], list(dict_sups.keys())[0]) if fila_proy['supervisor_id'] else list(dict_sups.keys())[0]
                    edit_resp = c_ed1.selectbox("Responsable del Proyecto:", options=list(dict_sups.keys()), index=list(dict_sups.keys()).index(nom_resp_actual))
                    
                    edit_tableros = c_ed2.number_input("Número de Tableros de Melamina:", min_value=0, value=int(fila_proy['total_tableros'] if fila_proy['total_tableros'] else 0))
                    
                    f_ini_act = fila_proy['f_ini'] if pd.notna(fila_proy['f_ini']) else date.today()
                    f_fin_act = fila_proy['f_fin'] if pd.notna(fila_proy['f_fin']) else date.today() + timedelta(days=30)
                    edit_f_ini = c_ed1.date_input("Fecha Inicio Global:", value=f_ini_act, format="DD/MM/YYYY")
                    edit_f_fin = c_ed2.date_input("Fecha Término Global:", value=f_fin_act, format="DD/MM/YYYY")

                    st.markdown("<br>", unsafe_allow_html=True)
                    c_btn_save, _ = st.columns([2, 6])
                    
                    if c_btn_save.form_submit_button("💾 Guardar Datos Generales", type="primary", use_container_width=True):
                        if not edit_nombre or not edit_cliente or not edit_partida:
                            st.error("❌ Los campos Nombre, Cliente y Partida son estrictamente obligatorios.")
                        else:
                            try:
                                payload_update = {
                                    "proyecto_text": edit_nombre,
                                    "cliente": edit_cliente,
                                    "partida": edit_partida,
                                    "codigo": edit_codigo.strip() if edit_codigo else f"PROY-{id_sel}",
                                    "supervisor_id": dict_sups[edit_resp],
                                    "total_tableros": int(edit_tableros),
                                    "f_ini": edit_f_ini.isoformat(),
                                    "f_fin": edit_f_fin.isoformat()
                                }
                                conectar().table("proyectos").update(payload_update).eq("id", id_sel).execute()
                                st.success("✅ Datos generales del proyecto actualizados correctamente.")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al actualizar la base de datos: {e}")

                # --- ZONA DE ELIMINACIÓN INTEGRADA ---
                with st.expander("🚫 Zona de Peligro: Eliminar Proyecto"):
                    st.warning(f"⚠️ Al presionar el botón inferior se eliminará permanentemente el proyecto '{fila_proy['proyecto_text']}' y todas sus piezas de forma irreversible.")
                    confirmar_borrado = st.checkbox(f"Confirmo que deseo purgar el proyecto {fila_proy['proyecto_text']} del servidor de la empresa")
                    
                    if st.button("🔥 Eliminar Proyecto Completo", type="primary", disabled=not confirmar_borrado, use_container_width=True):
                        if eliminar_proyecto_completo(id_sel):
                            st.success("💥 Proyecto eliminado de la base de datos central.")
                            st.session_state.id_p_sel = None
                            st.cache_data.clear()
                            st.rerun()
        else:
            st.info("📂 No existen proyectos activos o en este estado que coincidan con los filtros de búsqueda.")

    # =========================================================
    # PESTAÑA 2: REGISTRAR PROYECTO NUEVO (CAMPOS MÍNIMOS OBLIGATORIOS)
    # =========================================================
    with tab_registro:
        st.subheader("🆕 Alta de Proyecto Nuevo")
        st.write("Complete la información comercial base requerida para aperturar el expediente operativo.")

        with st.form("form_registro_minimo_proyecto", clear_on_submit=True):
            with st.container(border=True):
                st.markdown("#### 🔹 Datos de Carácter Obligatorio")
                reg_nombre = st.text_input("Nombre del Proyecto:", placeholder="Ej: Fabricación de Muebles de Cocina - Edificio Los Sauces")
                reg_cliente = st.text_input("Cliente / Razón Social o Propietario:", placeholder="Ej: Inmobiliaria San Jerónimo S.A.C.")
                reg_partida = st.text_input("Partida Presupuestal / Nro de Contrato:", placeholder="Ej: PART-2026-99A")
            
            st.info("💡 Los campos técnicos como Código, Responsable, Tableros y Fechas Globales se inicializarán automáticamente en blanco. Podrá completarlos en la sección inferior de la primera pestaña; el Estado se configurará inicialmente como 'En Cotización'.")

            if st.form_submit_button("🚀 INICIALIZAR PROYECTO EN EL SISTEMA", type="primary", use_container_width=True):
                if not reg_nombre or not reg_cliente or not reg_partida:
                    st.warning("⚠️ Para aperturar el proyecto debe indicar obligatoriamente el Nombre, Cliente y la Partida.")
                else:
                    try:
                        payload_nuevo = {
                            "proyecto_text": reg_nombre.strip(),
                            "cliente": reg_cliente.strip(),
                            "partida": reg_partida.strip(),
                            "codigo": f"TEMP-{datetime.now().strftime('%M%S')}", 
                            "estado": "En Cotización", 
                            "total_tableros": 0,
                            "avance": 0.0,
                            "f_ini": date.today().isoformat(),
                            "f_fin": (date.today() + timedelta(days=30)).isoformat()
                        }
                        
                        conectar().table("proyectos").insert(payload_nuevo).execute()
                        st.success(f"🎉 ¡Proyecto '{reg_nombre}' creado con éxito! Vaya a la primera pestaña para completar sus datos generales.")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error de estas de consistencia en Supabase: {e}")

    # =========================================================
    # PESTAÑA 3: MATRIZ DE PRODUCTOS (DESPIECE VINCULADO)
    # =========================================================
    with tab_matriz:
        if st.session_state.get('id_p_sel'):
            res_info = conectar().table("proyectos").select("*").eq("id", st.session_state.id_p_sel).execute()
            if res_info.data:
                info_p = res_info.data[0]
                st.subheader(f"📦 Despiece de Productos Vinculado: {info_p['proyecto_text']} ({info_p['codigo']})")

                # Formulario para agregar producto manual
                with st.expander("➕ Agregar Producto Manualmente", expanded=False):
                    with st.form("form_producto_manual_reing", clear_on_submit=True):
                        c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
                        u = c1.text_input("Ubicación / Ambiente:")
                        t = c2.text_input("Tipo de Mueble:")
                        c = c3.number_input("Cantidad:", min_value=1, value=1, step=1)
                        m = c4.number_input("Metros Lineales (ML):", min_value=0.0, format="%.2f")
                        
                        if st.form_submit_button("Guardar Producto"):
                            if u and t:
                                try:
                                    res_c = conectar().table("productos").select("id", count="exact").eq("proyecto_id", st.session_state.id_p_sel).execute()
                                    nuevo_n = (res_c.count if res_c.count else 0) + 1
                                    etiqueta = f"{info_p['codigo']}-{str(nuevo_n).zfill(4)}"

                                    datos_producto = {
                                        "proyecto_id": int(st.session_state.id_p_sel),
                                        "codigo_etiqueta": etiqueta,
                                        "ubicacion": str(u).strip(),
                                        "tipo": str(t).strip(),
                                        "ctd": int(c),
                                        "ml": float(m)
                                    }
                                    conectar().table("productos").insert(datos_producto).execute()
                                    st.success(f"✅ Pieza registrada con etiqueta: {etiqueta}")
                                    st.cache_data.clear()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error al guardar pieza: {e}")

                # Visualización de la matriz de despiece vinculada
                st.divider()
                res_p = conectar().table("productos").select("codigo_etiqueta, ubicacion, tipo, ctd, ml").eq("proyecto_id", st.session_state.id_p_sel).order("codigo_etiqueta").execute()
                
                if res_p.data:
                    df_matriz_prod = pd.DataFrame(res_p.data)
                    df_unificado = df_matriz_prod.rename(columns={
                        'codigo_etiqueta': 'Código ID',
                        'ubicacion': 'Ubicación',
                        'tipo': 'Tipo Mueble',
                        'ctd': 'Cantidad',
                        'ml': 'ML'
                    })
                    st.dataframe(df_unificado, hide_index=True, use_container_width=True)
                    
                    cx1, cx2 = st.columns(2)
                    cx1.info(f"**Total Piezas en Lote:** {int(df_unificado['Cantidad'].sum())} Unidades")
                    cx2.info(f"**Metraje Total Asignado:** {df_unificado['ML'].sum():.2f} ml")
                else:
                    st.info("📂 Este proyecto no cuenta con despieces de carpintería registrados aún.")
        else:
            st.info("⚠️ Seleccione un proyecto en la matriz de la pestaña **'Listado, Búsqueda y Edición'** para ver su desglose de piezas.")
