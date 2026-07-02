import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from base_datos import crear_proyecto, obtener_proyectos, eliminar_proyecto_completo, obtener_supervisores, conectar

def mostrar():
    # Estilos CSS profesionales para la consistencia visual del sistema modular
    st.markdown("""
        <style>
        .report-title { font-size: 28px; font-weight: bold; color: #1E3A8A; margin-bottom: 0.5rem; }
        [data-testid="stMetricValue"] { font-size: 20px !important; font-weight: bold !important; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<p class="report-title">📁 Centro de Control y Gestión de Proyectos</p>', unsafe_allow_html=True)
    
    # Estructura modular de 3 pestañas principales (Listado es la vista por defecto)
    tab_listado, tab_registro, tab_matriz = st.tabs(["📋 Matriz de Proyectos", "🆕 Registrar Proyecto Nuevo", "📦 Matriz de Productos"])

    # Carga inicial de supervisores para mapeo de responsables
    df_sups = obtener_supervisores()
    dict_sups = {r['nombre_real']: r['id'] for _, r in df_sups.iterrows()}
    dict_sups_inv = {r['id']: r['nombre_real'] for _, r in df_sups.iterrows()}

    lista_estados = ["En Cotización", "En ejecución", "Cerrado"]

    # =========================================================
    # PESTAÑA 1: LISTADO MAESTRO (EDICIÓN INTEGRAL DESDE LA MATRIZ)
    # =========================================================
    with tab_listado:
        st.subheader("📊 Control y Edición Directa de Proyectos")
        
        # Filtros de segmentación alineados horizontalmente a la misma altura
        c_bus1, c_bus2 = st.columns([4, 4])
        with c_bus1:
            bus = st.text_input("🔍 Buscar proyecto...", placeholder="Filtre por código, nombre del proyecto o cliente...", label_visibility="visible")
        with c_bus2:
            estado_filtro = st.selectbox("🚦 Filtrar por Estado:", ["-- Todos los Estados --"] + lista_estados, index=0)
        
        # Obtención de registros desde la capa de persistencia (base_datos.py)
        df_p = obtener_proyectos(bus)
        
        if not df_p.empty:
            # Consistencia para asegurar la columna de estado por reingeniería
            if 'estado' not in df_p.columns:
                df_p['estado'] = 'En Cotización'
                
            # Aplicación del filtro por estado si no está en la opción global
            if estado_filtro != "-- Todos los Estados --":
                df_p = df_p[df_p['estado'] == estado_filtro].copy()

        if not df_p.empty:
            # Mapear el ID del supervisor al nombre real para visualización en la cuadrícula
            df_p['responsable'] = df_p['supervisor_id'].map(dict_sups_inv).fillna("Sin Asignar")
            
            # Preparar el DataFrame para el editor interactivo
            df_editor = df_p.copy()
            df_editor['responsable'] = df_editor['responsable'].astype(str)
            
            # Normalización y casteo estricto de la columna de avance para evitar fallos de renderizado
            df_editor['avance'] = df_editor['avance'].fillna(0.0).astype(float) / 100.0
            df_editor['avance'] = df_editor['avance'].clip(0.0, 1.0)
            
            # Asegurar casteo seguro de fechas globales para el componente DateColumn
            df_editor['f_ini'] = pd.to_datetime(df_editor['f_ini'], errors='coerce').dt.date
            df_editor['f_fin'] = pd.to_datetime(df_editor['f_fin'], errors='coerce').dt.date

            st.caption("💡 Tip operativo: Modifique cualquier celda (Texto, Estado o Fechas) haciendo doble clic directamente sobre la matriz.")

            # RENDERIZADO DE LA MATRIZ TOTALMENTE EDITABLE
            cambios_tabla = st.data_editor(
                df_editor[['id', 'codigo', 'proyecto_text', 'cliente', 'partida', 'responsable', 'total_tableros', 'estado', 'f_ini', 'f_fin', 'avance']],
                column_config={
                    "id": None, # Ocultar el ID del sistema
                    "codigo": st.column_config.TextColumn("Código", disabled=True),
                    "proyecto_text": st.column_config.TextColumn("Proyecto", disabled=False, required=True),
                    "cliente": st.column_config.TextColumn("Cliente", disabled=False, required=True),
                    "partida": st.column_config.TextColumn("Partida", disabled=False, required=True),
                    "responsable": st.column_config.SelectboxColumn("Responsable", options=list(dict_sups.keys()), disabled=False, required=True),
                    "total_tableros": st.column_config.NumberColumn("Nro Tableros", format="%d", min_value=0, disabled=False),
                    "estado": st.column_config.SelectboxColumn("Estado", options=lista_estados, required=True, disabled=False),
                    # Configuración de fechas con calendario desplegable integrado
                    "f_ini": st.column_config.DateColumn("F. Inicio Global", format="DD/MM/YYYY", required=True, disabled=False),
                    "f_fin": st.column_config.DateColumn("F. Término Global", format="DD/MM/YYYY", required=True, disabled=False),
                    "avance": st.column_config.ProgressColumn("Avance Real", min_value=0.0, max_value=1.0, format="%.2f", disabled=True)
                },
                hide_index=True,
                use_container_width=True,
                key="matriz_proyectos_colectiva_total"
            )

            # PROCESAMIENTO Y APLICACIÓN DE CAMBIOS EN BLOQUE
            c_save_col, c_del_col = st.columns([3, 5])
            
            if c_save_col.button("💾 Guardar Cambios Realizados en la Matriz", type="primary", use_container_width=True):
                # Validar si hubo alteraciones comparando contra el estado inicial en memoria
                if not cambios_tabla.equals(df_editor[['id', 'codigo', 'proyecto_text', 'cliente', 'partida', 'responsable', 'total_tableros', 'estado', 'f_ini', 'f_fin', 'avance']]):
                    cambios_detectados = 0
                    for index, row in cambios_tabla.iterrows():
                        id_fila = int(row['id'])
                        
                        # Obtener la fila original antes de las modificaciones del usuario
                        original_row = df_p[df_p['id'] == id_fila].iloc[0]
                        
                        # Extraer variables con fallback seguro de tipos
                        p_text = str(row['proyecto_text']).strip()
                        p_client = str(row['cliente']).strip()
                        p_partida = str(row['partida']).strip()
                        p_resp_id = dict_sups.get(row['responsable'], original_row['supervisor_id'])
                        p_tableros = int(row['total_tableros'])
                        p_estado = str(row['estado'])
                        
                        # Procesamiento seguro de fechas mutadas
                        p_f_ini = row['f_ini'].isoformat() if isinstance(row['f_ini'], (date, datetime)) else str(row['f_ini'])
                        p_f_fin = row['f_fin'].isoformat() if isinstance(row['f_fin'], (date, datetime)) else str(row['f_fin'])

                        # Evaluar si esta fila en particular sufrió cambios estructurales
                        if (p_text != str(original_row['proyecto_text']) or 
                            p_client != str(original_row['cliente']) or 
                            p_partida != str(original_row['partida']) or 
                            p_resp_id != original_row['supervisor_id'] or 
                            p_tableros != int(original_row['total_tableros'] if original_row['total_tableros'] else 0) or 
                            p_estado != str(original_row['estado'] if 'estado' in original_row else "En Cotización") or 
                            p_f_ini != str(original_row['f_ini']) or 
                            p_f_fin != str(original_row['f_fin'])):
                            
                            if not p_text or not p_client or not p_partida:
                                st.error(f"❌ Error en fila con Código {row['codigo']}: Los campos Proyecto, Cliente y Partida no pueden quedar vacíos.")
                                continue
                                
                            try:
                                payload_update = {
                                    "proyecto_text": p_text,
                                    "cliente": p_client,
                                    "partida": p_partida,
                                    "supervisor_id": p_resp_id,
                                    "total_tableros": p_tableros,
                                    "estado": p_estado,
                                    "f_ini": p_f_ini,
                                    "f_fin": p_f_fin
                                }
                                conectar().table("proyectos").update(payload_update).eq("id", id_fila).execute()
                                cambios_detectados += 1
                            except Exception as e:
                                st.error(f"Error al guardar datos del proyecto {row['codigo']}: {e}")
                    
                    if cambios_detectados > 0:
                        st.success(f"🎉 Se sincronizaron con éxito {cambios_detectados} proyecto(s) en el servidor de la empresa.")
                        st.cache_data.clear()
                        st.rerun()
                else:
                    st.info("ℹ️ No se detectó ninguna modificación en las celdas de la matriz para procesar.")

            # --- SELECTOR INTEGRADO EXCLUSIVO PARA ASIGNAR EL PROYECTO ACTIVO EN SESIÓN O ELIMINACIÓN ---
            st.divider()
            opciones_proy = df_p['proyecto_display'].tolist()
            seleccionado = st.selectbox("🎯 Seleccione un proyecto de la matriz para enlazar su Despiece de Productos o removerlo:", ["-- Seleccionar Proyecto Activo --"] + opciones_proy)

            if seleccionado != "-- Seleccionar Proyecto Activo --":
                fila_proy = df_p[df_p['id'] == df_p[df_p['proyecto_display'] == seleccionado]['id'].values[0]].iloc[0]
                id_sel = int(fila_proy['id'])
                st.session_state.id_p_sel = id_sel 
                st.info(f"✨ Proyecto **{fila_proy['proyecto_text']}** seleccionado para gestión de despieces. Puede dirigirse a la tercera pestaña.")

                with st.expander("🚫 Zona de Peligro: Eliminar Proyecto Seleccionado"):
                    st.warning(f"⚠️ Al presionar el botón inferior se eliminará permanentemente el proyecto '{fila_proy['proyecto_text']}' y todas sus piezas asociadas de forma irreversible en Supabase.")
                    confirmar_borrado = st.checkbox(f"Confirmo que deseo purgar el proyecto {fila_proy['proyecto_text']} del servidor central")
                    
                    if st.button("🔥 Eliminar Proyecto Completo", type="primary", disabled=not confirmar_borrado, use_container_width=True):
                        if eliminar_proyecto_completo(id_sel):
                            st.success("💥 Proyecto eliminado de la base de datos central de la organización.")
                            st.session_state.id_p_sel = None
                            st.cache_data.clear()
                            st.rerun()
        else:
            st.info("📂 No existen proyectos registrados que coincidan con los criterios de los filtros seleccionados.")

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
                        st.success(f"🎉 ¡Proyecto '{reg_nombre}' creado con éxito! Vaya a la primera pestaña para completar sus datos generales directamente en la matriz.")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error de consistencia en Supabase: {e}")

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
            st.info("⚠️ Seleccione un proyecto en la pestaña **'📋 Matriz de Proyectos'** para habilitar y visualizar su desglose de piezas.")
