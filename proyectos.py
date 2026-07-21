import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import io  # <-- INTEGRADO: Requerido para procesar flujos de archivos Excel/CSV en memoria
from base_datos import crear_proyecto, obtener_proyectos, eliminar_proyecto_completo, obtener_supervisores, conectar

def mostrar():
    # Estilos CSS profesionales para la consistencia visual de la plataforma
    st.markdown("""
        <style>
        .report-title { font-size: 28px; font-weight: bold; color: #1E3A8A; margin-bottom: 0.5rem; }
        [data-testid="stMetricValue"] { font-size: 20px !important; font-weight: bold !important; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<p class="report-title">📁 Centro de Control y Gestión de Proyectos</p>', unsafe_allow_html=True)
    
    # REINGENIERÍA: La Matriz de proyectos es la pestaña principal por defecto
    tab_listado, tab_registro, tab_matriz = st.tabs(["📋 Matriz de Proyectos", "🆕 Registrar Proyecto Nuevo", "📦 Matriz de Productos"])

    # Carga inicial de supervisores para el mapeo relacional de IDs a Nombres reales
    df_sups = obtener_supervisores()
    dict_sups = {r['nombre_real']: r['id'] for _, r in df_sups.iterrows()}
    dict_sups_inv = {r['id']: r['nombre_real'] for _, r in df_sups.iterrows()}

    lista_estados = ["En Cotización", "En ejecución", "Cerrado"]
    
    # SOLUCIÓN: Incorporamos "-" como opción válida de responsable en el drop-down por si no tiene asignado ninguno
    lista_responsables_opciones = ["-"] + list(dict_sups.keys())

    # =========================================================
    # PESTAÑA 1: MATRIZ DE PROYECTOS (EDICIÓN INTEGRAL DIRECTA)
    # =========================================================
    with tab_listado:
        st.subheader("📊 Control y Edición Directa de Proyectos")
        
        # Filtros de segmentación perfectamente alineados a la misma altura horizontal
        c_bus1, c_bus2 = st.columns([4, 4])
        with c_bus1:
            bus = st.text_input("🔍 Buscar proyecto...", placeholder="Filtre por código, nombre del proyecto o cliente...", label_visibility="visible")
        with c_bus2:
            estado_filtro = st.selectbox("🚦 Filtrar por Estado:", ["-- Todos los Estados --"] + lista_estados, index=0)
        
        # Obtención de datos desde la base de datos
        df_p = obtener_proyectos(bus)
        
        if not df_p.empty:
            # ALINEACIÓN SUPABASE: Mapear la columna real 'estatus' a la variable de interfaz 'estado'
            if 'estatus' in df_p.columns:
                df_p['estado'] = df_p['estatus'].fillna('En Cotización').astype(str)
            elif 'estado' not in df_p.columns:
                df_p['estado'] = 'En Cotización'
                
            # Aplicar filtro cruzado por estado seleccionado
            if estado_filtro != "-- Todos los Estados --":
                df_p = df_p[df_p['estado'] == estado_filtro].copy()

        if not df_p.empty:
            # Mapear supervisor de ID numérico a Nombre de texto para la grilla
            df_p['responsable'] = df_p['supervisor_id'].map(dict_sups_inv).fillna("-")
            
            # REINGENIERÍA DE BLINDAJE CRÍTICO: Reemplazo absoluto de nulos por los valores predefinidos ("-" y 0)
            df_editor = pd.DataFrame()
            df_editor['id'] = df_p['id']
            df_editor['codigo'] = df_p['codigo'].fillna("-").astype(str)
            df_editor['proyecto_text'] = df_p['proyecto_text'].fillna("-").astype(str)
            df_editor['cliente'] = df_p['cliente'].fillna("-").astype(str)
            df_editor['partida'] = df_p['partida'].fillna("-").astype(str)
            df_editor['responsable'] = df_p['responsable'].astype(str)
            df_editor['total_tableros'] = df_p['total_tableros'].fillna(0).astype(int)
            df_editor['estado'] = df_p['estado'].fillna("En Cotización").astype(str)
            
            # Formateo visual numérico estable para el avance
            df_editor['avance_vista'] = df_p['avance'].fillna(0.0).astype(float).map("{:.2f}%".format)
            
            # Fallback seguro para fechas globales en la matriz
            df_editor['f_ini'] = pd.to_datetime(df_p['f_ini'], errors='coerce').dt.date.fillna(date.today())
            df_editor['f_fin'] = pd.to_datetime(df_p['f_fin'], errors='coerce').dt.date.fillna(date.today() + timedelta(days=30))

            st.caption("💡 Tip operativo: Modifique cualquier dato haciendo doble clic sobre la celda de la matriz.")

            # RENDERIZADO DE LA MATRIZ INTEGRAL EDITABLE
            cambios_tabla = st.data_editor(
                df_editor[['id', 'codigo', 'proyecto_text', 'cliente', 'partida', 'responsable', 'total_tableros', 'estado', 'f_ini', 'f_fin', 'avance_vista']],
                column_config={
                    "id": None, 
                    "codigo": st.column_config.TextColumn("Código", disabled=True),
                    "proyecto_text": st.column_config.TextColumn("Proyecto", disabled=False, required=True),
                    "cliente": st.column_config.TextColumn("Cliente", disabled=False, required=True),
                    "partida": st.column_config.TextColumn("Partida", disabled=False, required=True),
                    "responsable": st.column_config.SelectboxColumn("Responsable", options=lista_responsables_opciones, disabled=False, required=True),
                    "total_tableros": st.column_config.NumberColumn("Nro Tableros", format="%d", min_value=0, disabled=False),
                    "estado": st.column_config.SelectboxColumn("Estado", options=lista_estados, required=True, disabled=False),
                    "f_ini": st.column_config.DateColumn("F. Inicio Global", format="DD/MM/YYYY", required=True, disabled=False),
                    "f_fin": st.column_config.DateColumn("F. Término Global", format="DD/MM/YYYY", required=True, disabled=False),
                    "avance_vista": st.column_config.TextColumn("Avance Real", disabled=True)
                },
                hide_index=True,
                use_container_width=True,
                key="matriz_proyectos_colectiva_total"
            )

            # PROCESAMIENTO Y ACTUALIZACIÓN EN BLOQUE
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("💾 Guardar Cambios Realizados en la Matriz", type="primary", use_container_width=True):
                if not cambios_tabla.equals(df_editor[['id', 'codigo', 'proyecto_text', 'cliente', 'partida', 'responsable', 'total_tableros', 'estado', 'f_ini', 'f_fin', 'avance_vista']]):
                    cambios_detectados = 0
                    
                    for index, row in cambios_tabla.iterrows():
                        id_fila = int(row['id'])
                        original_row = df_p[df_p['id'] == id_fila].iloc[0]
                        
                        p_text = str(row['proyecto_text']).strip()
                        p_client = str(row['cliente']).strip()
                        p_partida = str(row['partida']).strip()
                        p_resp_id = dict_sups.get(row['responsable'], None)
                        p_tableros = int(row['total_tableros'])
                        p_estado = str(row['estado'])
                        
                        p_f_ini = row['f_ini'].isoformat() if isinstance(row['f_ini'], (date, datetime)) else str(row['f_ini'])
                        p_f_fin = row['f_fin'].isoformat() if isinstance(row['f_fin'], (date, datetime)) else str(row['f_fin'])

                        # Comparación de auditoría relacional
                        orig_estatus = str(original_row['estatus'] if 'estatus' in original_row and original_row['estatus'] else "En Cotización").strip()

                        if (p_text != str(original_row['proyecto_text']).strip() or 
                            p_client != str(original_row['cliente']).strip() or 
                            p_partida != str(original_row['partida']).strip() or 
                            p_resp_id != original_row['supervisor_id'] or 
                            p_tableros != int(original_row['total_tableros'] if original_row['total_tableros'] else 0) or 
                            p_estado != orig_estatus or 
                            p_f_ini != (original_row['f_ini'].isoformat() if isinstance(original_row['f_ini'], (date, datetime)) else str(original_row['f_ini'])) or 
                            p_f_fin != (original_row['f_fin'].isoformat() if isinstance(original_row['f_fin'], (date, datetime)) else str(original_row['f_fin']))):
                            
                            if not p_text or p_text == "-" or not p_client or p_client == "-" or not p_partida or p_partida == "-":
                                st.error(f"❌ Los campos obligatorios no pueden quedar vacíos en el Código: {row['codigo']}")
                                continue
                                
                            try:
                                # ALINEACIÓN SUPABASE: Inyección directa en la columna física 'estatus'
                                payload_update = {
                                    "proyecto_text": p_text, "cliente": p_client, "partida": p_partida,
                                    "supervisor_id": p_resp_id, "total_tableros": p_tableros, "estatus": p_estado,
                                    "f_ini": p_f_ini, "f_fin": p_f_fin
                                }
                                conectar().table("proyectos").update(payload_update).eq("id", id_fila).execute()
                                cambios_detectados += 1
                            except Exception as e:
                                st.error(f"Error al actualizar Supabase para el proyecto {row['codigo']}: {e}")
                    
                    if cambios_detectados > 0:
                        st.success(f"🎉 Sincronización exitosa. Se actualizaron {cambios_detectados} proyecto(s) en la base de datos.")
                        st.cache_data.clear()
                        st.rerun()
                else:
                    st.info("ℹ️ No se detectaron modificaciones pendientes de procesar en las celdas.")

            # --- PANEL DE ACCIÓN INTEGRADO PARA ENLAZAR EL DESPIECE ---
            st.divider()
            opciones_proy = df_p['proyecto_display'].tolist()
            seleccionado = st.selectbox("🎯 Seleccione un proyecto de la matriz para enlazar su Despiece de Productos o removerlo:", ["-- Seleccionar Proyecto Activo --"] + opciones_proy)

            if seleccionado != "-- Seleccionar Proyecto Activo --":
                fila_proy = df_p[df_p['id'] == df_p[df_p['proyecto_display'] == seleccionado]['id'].values[0]].iloc[0]
                id_sel = int(fila_proy['id'])
                st.session_state.id_p_sel = id_sel 
                st.info(f"✨ Proyecto **{fila_proy['proyecto_text']}** enlazado correctamente. Puede dirigirse a la tercera pestaña para gestionar sus piezas.")

                with st.expander("🚫 Zona de Peligro: Eliminar Proyecto Seleccionado"):
                    st.warning(f"⚠️ Al presionar el botón inferior se eliminará permanentemente el proyecto '{fila_proy['proyecto_text']}' y todas sus piezas vinculadas de forma irreversible.")
                    confirmar_borrado = st.checkbox(f"Confirmo que deseo purgar el proyecto {fila_proy['proyecto_text']} del sistema central")
                    
                    if st.button("🔥 Eliminar Proyecto Completo", type="primary", disabled=not confirmar_borrado, use_container_width=True):
                        if eliminar_proyecto_completo(id_sel):
                            st.success("💥 Proyecto y dependencias eliminadas del sistema con éxito.")
                            st.session_state.id_p_sel = None
                            st.cache_data.clear()
                            st.rerun()
        else:
            st.info("📂 No existen proyectos registrados que coincidan con los criterios de los filtros seleccionados.")

    # =========================================================
    # PESTAÑA 2: REGISTRAR PROYECTO NUEVO
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
            
            st.info("💡 Los campos técnicos como Código, Responsable, Tableros y Fechas Globales se inicializarán automáticamente vacíos.")

            if st.form_submit_button("🚀 INICIALIZAR PROYECTO EN EL SISTEMA", type="primary", use_container_width=True):
                if not reg_nombre or not reg_cliente or not reg_partida:
                    st.warning("⚠️ Para aperturar el proyecto debe indicar obligatoriamente el Nombre, Cliente y la Partida.")
                else:
                    try:
                        # ALINEACIÓN SUPABASE: Corrección de la columna física a 'estatus'
                        payload_nuevo = {
                            "proyecto_text": reg_nombre.strip(), "cliente": reg_cliente.strip(), "partida": reg_partida.strip(),
                            "codigo": f"TEMP-{datetime.now().strftime('%M%S')}", "estatus": "En Cotización", "total_tableros": 0, "avance": 0.0,
                            "f_ini": date.today().isoformat(), "f_fin": (date.today() + timedelta(days=30)).isoformat()
                        }
                        conectar().table("proyectos").insert(payload_nuevo).execute()
                        st.success(f"🎉 ¡Proyecto '{reg_nombre}' creado con éxito! Regrese a la primera pestaña para completar sus datos.")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error de consistencia en Supabase: {e}")

    # =========================================================
    # PESTAÑA 3: MATRIZ DE PRODUCTOS (DESPIECE VINCULADO / IMPORTACIÓN MASIVA)
    # =========================================================
    with tab_matriz:
        if st.session_state.get('id_p_sel'):
            from base_datos import conectar, sincronizar_avances_estructural
            
            res_info = conectar().table("proyectos").select("*").eq("id", st.session_state.id_p_sel).execute()
            if res_info.data:
                info_p = res_info.data[0]
                st.subheader(f"📦 Despiece de Productos Vinculado: {info_p['proyecto_text']} ({info_p['codigo']})")

                # --- SUBSISTEMA DE IMPORTACIÓN MASIVA DESDE PLANILLA DE CARPINTERÍA ---
                with st.expander("📥 Importar Despiece desde Archivo Externo (Excel / CSV)", expanded=False):
                    st.write("Cargue la planilla excel de despiece para este lote. Columnas requeridas: **Ubicación**, **Tipo Mueble**, **ML**.")
                    archivo_despiece = st.file_uploader("Seleccione el archivo de despiece de melamina:", type=["xlsx", "csv"], key="uploader_despiece_masivo")
                    
                    if archivo_despiece and st.button("🚀 PROCESAR E IMPORTAR PLANILLA AL SISTEMA", type="primary", use_container_width=True):
                        with st.spinner("Procesando y sincronizando con la base de datos matriz..."):
                            try:
                                # 1. Lectura y limpieza de formato
                                if archivo_despiece.name.endswith(".csv"):
                                    df_imp = pd.read_csv(archivo_despiece)
                                else:
                                    df_imp = pd.read_excel(archivo_despiece)
                                
                                df_imp.columns = df_imp.columns.astype(str).str.strip()
                                
                                # Diccionario flexible para normalizar las columnas base
                                mapeo_columnas = {
                                    'Ubicación': 'ubicacion', 'Ubicacion': 'ubicacion', 'ubicacion': 'ubicacion', 'UBICACIÓN': 'ubicacion',
                                    'Tipo Mueble': 'tipo', 'Tipo': 'tipo', 'Tipo de Mueble': 'tipo', 'tipo': 'tipo', 'TIPO': 'tipo',
                                    'ML': 'ml', 'Metros Lineales': 'ml', 'ml': 'ml', 'metros lineales': 'ml',
                                    'Cantidad': 'ctd', 'cantidad': 'ctd', 'CANTIDAD': 'ctd', 'ctd': 'ctd'
                                }
                                df_imp = df_imp.rename(columns=mapeo_columnas)
                                
                                # 2. Validación de columnas mandatorias
                                columnas_necesarias = ['ubicacion', 'tipo', 'ml']
                                columnas_faltantes = [col for col in columnas_necesarias if col not in df_imp.columns]
                                
                                if columnas_faltantes:
                                    st.error(f"❌ Estructura incorrecta. Faltan las columnas: **{', '.join(columnas_faltantes)}**.")
                                else:
                                    df_imp = df_imp.dropna(subset=['ubicacion', 'tipo'])
                                    
                                    if df_imp.empty:
                                        st.warning("⚠️ El archivo Excel no contiene registros válidos.")
                                    else:
                                        res_c = conectar().table("productos").select("id", count="exact").eq("proyecto_id", st.session_state.id_p_sel).execute()
                                        conteo_inicial = res_c.count if res_c.count else 0
                                        
                                        lote_productos = []
                                        df_imp['codigo_etiqueta'] = "" # Columna de apoyo para el mapeo
                                        
                                        # 3. Preparación de la carga de Productos (Sanitizando tipos de datos a int y float puros)
                                        for idx, row in df_imp.iterrows():
                                            conteo_inicial += 1
                                            etiqueta_generada = f"{info_p['codigo']}-{str(conteo_inicial).zfill(4)}"
                                            df_imp.at[idx, 'codigo_etiqueta'] = etiqueta_generada
                                            
                                            cantidad_pieza = int(row['ctd']) if 'ctd' in df_imp.columns and pd.notna(row['ctd']) else 1
                                            metros_lineales = float(pd.to_numeric(row['ml'], errors='coerce'))
                                            if pd.isna(metros_lineales): metros_lineales = 0.0

                                            lote_productos.append({
                                                "proyecto_id": int(st.session_state.id_p_sel),
                                                "codigo_etiqueta": etiqueta_generada,
                                                "ubicacion": str(row['ubicacion']).strip(),
                                                "tipo": str(row['tipo']).strip(),
                                                "ctd": cantidad_pieza,
                                                "ml": metros_lineales
                                            })
                                        
                                        if lote_productos:
                                            # === INSERCIÓN EN CASCADA (NÚCLEO DEL SISTEMA) ===
                                            # PASO A: Insertamos y recuperamos los IDs autogenerados por Supabase
                                            res_insert = conectar().table("productos").insert(lote_productos).execute()
                                            
                                            if res_insert.data:
                                                inserted_products = res_insert.data
                                                
                                                lote_estatus = []
                                                lote_fechas = []
                                                lote_pav = []
                                                
                                                hitos_pesos = {
                                                    "Diseñado": 15, "Fabricado": 40, "Material en Obra": 5,
                                                    "Material en Ubicación": 5, "Instalación de Estructura": 15,
                                                    "Instalación de Puertas o Frentes": 10, "Revisión y Observaciones": 5, "Entrega": 5
                                                }
                                                
                                                # Construcción en memoria de los registros analíticos hijos
                                                for prod in inserted_products:
                                                    p_id = int(prod['id'])
                                                    cod_etiq = prod['codigo_etiqueta']
                                                    
                                                    lote_estatus.append({"producto_id": p_id, "en_proceso": False, "culminado": False, "entregado": False})
                                                    lote_fechas.append({"producto_id": p_id})
                                                    
                                                    row_ex = df_imp[df_imp['codigo_etiqueta'] == cod_etiq].iloc[0]
                                                    
                                                    for hito, peso in hitos_pesos.items():
                                                        # ¡Magia Analítica!: Si la columna del hito existe en el Excel y tiene dato (ej. Diseñado), se da por logrado.
                                                        logrado = 1 if hito in row_ex.index and pd.notna(row_ex[hito]) else 0
                                                            
                                                        lote_pav.append({
                                                            "codigo_proyecto": info_p['codigo'],
                                                            "producto_id": p_id,
                                                            "hito": hito,
                                                            "logrado": logrado,
                                                            "valor_porcentual": peso
                                                        })
                                                
                                                # PASO B: Inicializamos Estatus y Fechas
                                                if lote_estatus: conectar().table("estatus_muebles").insert(lote_estatus).execute()
                                                if lote_fechas: conectar().table("fechas_hitos_muebles").insert(lote_fechas).execute()
                                                
                                                # PASO C: Cargamos los valores porcentuales (En bloques para cuidar la RAM)
                                                tam_lote = 1000
                                                for i in range(0, len(lote_pav), tam_lote):
                                                    conectar().table("productos_avance_valor").insert(lote_pav[i:i+tam_lote]).execute()
                                                    
                                                # PASO D: Motor Estructural (Actualizamos avances_etapas del proyecto)
                                                sincronizar_avances_estructural(info_p['codigo'])
                                                
                                                st.success(f"🎉 ¡Éxito Total! Se registraron {len(inserted_products)} productos y sus matrices analíticas vinculadas. Revise el módulo de Producción Proyectada.")
                                                st.cache_data.clear()
                                                st.rerun()
                                            else:
                                                st.error("❌ Ocurrió un error: La base de datos no devolvió los IDs insertados.")
                            except Exception as e:
                                st.error(f"❌ Falla de sistema al procesar el enlace masivo: {e}")

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

                                    # Se crea el producto unitario sanitizado
                                    datos_producto = {
                                        "proyecto_id": int(st.session_state.id_p_sel), "codigo_etiqueta": etiqueta,
                                        "ubicacion": str(u).strip(), "tipo": str(t).strip(), "ctd": int(c), "ml": float(m)
                                    }
                                    res_man = conectar().table("productos").insert(datos_producto).execute()
                                    
                                    # INICIALIZACIÓN UNITARIA OBLIGATORIA
                                    if res_man.data:
                                        p_id = int(res_man.data[0]['id'])
                                        conectar().table("estatus_muebles").insert({"producto_id": p_id, "en_proceso": False, "culminado": False, "entregado": False}).execute()
                                        conectar().table("fechas_hitos_muebles").insert({"producto_id": p_id}).execute()
                                        
                                        lote_pav_m = []
                                        for hito, peso in {"Diseñado": 15, "Fabricado": 40, "Material en Obra": 5, "Material en Ubicación": 5, "Instalación de Estructura": 15, "Instalación de Puertas o Frentes": 10, "Revisión y Observaciones": 5, "Entrega": 5}.items():
                                            lote_pav_m.append({"codigo_proyecto": info_p['codigo'], "producto_id": p_id, "hito": hito, "logrado": 0, "valor_porcentual": peso})
                                        
                                        conectar().table("productos_avance_valor").insert(lote_pav_m).execute()
                                        from base_datos import sincronizar_avances_estructural
                                        sincronizar_avances_estructural(info_p['codigo'])
                                        
                                    st.success(f"✅ Pieza registrada e inicializada correctamente con etiqueta: {etiqueta}")
                                    st.cache_data.clear()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error técnico al guardar pieza manual: {e}")

                # =========================================================================
                # VISUALIZACIÓN Y EDICIÓN INTERACTIVA DE LA MATRIZ DE DESPIECE
                # =========================================================================
                st.divider()
                st.subheader("✏️ Edición y Gestión del Despiece Registrado")
                
                # Obtenemos los productos incluyendo su ID para poder editarlos/borrarlos
                res_p = conectar().table("productos").select("id, codigo_etiqueta, ubicacion, tipo, ctd, ml").eq("proyecto_id", st.session_state.id_p_sel).order("codigo_etiqueta").execute()
                
                if res_p.data:
                    df_matriz_prod = pd.DataFrame(res_p.data)
                    
                    # Insertamos una columna de control para marcar filas a eliminar
                    df_matriz_prod.insert(0, "Eliminar", False)
                    
                    st.caption("💡 Puede editar la Ubicación, Tipo, Cantidad y ML directamente en las celdas. Para borrar una pieza, marque la casilla de la izquierda.")
                    
                    # Desplegamos la grilla editable
                    edit_grid = st.data_editor(
                        df_matriz_prod,
                        column_config={
                            "Eliminar": st.column_config.CheckboxColumn("🗑️ Borrar", default=False),
                            "id": None, # Ocultamos el ID interno
                            "codigo_etiqueta": st.column_config.TextColumn("Código Etiqueta", disabled=True),
                            "ubicacion": st.column_config.TextColumn("Ubicación / Ambiente", required=True),
                            "tipo": st.column_config.TextColumn("Tipo Mueble", required=True),
                            "ctd": st.column_config.NumberColumn("Cantidad", min_value=1, step=1, required=True),
                            "ml": st.column_config.NumberColumn("Metros Lineales (ML)", min_value=0.0, format="%.2f", required=True)
                        },
                        hide_index=True, 
                        use_container_width=True, 
                        key=f"grid_edicion_prods_{st.session_state.id_p_sel}"
                    )
                    
                    # Resumen visual rápido
                    cx1, cx2 = st.columns(2)
                    cx1.info(f"**Total Piezas Actuales:** {int(df_matriz_prod['ctd'].sum())} Unidades")
                    cx2.info(f"**Metraje Total Actual:** {df_matriz_prod['ml'].sum():.2f} ml")

                    # BOTÓN DE GUARDADO Y ELIMINACIÓN MASIVA
                    if st.button("💾 Guardar Cambios y/o Eliminar Piezas", type="primary", use_container_width=True):
                        
                        # 1. Identificar filas marcadas para eliminar
                        filas_a_borrar = edit_grid[edit_grid["Eliminar"] == True]
                        ids_a_borrar = filas_a_borrar["id"].tolist()
                        
                        # 2. Identificar filas que se mantienen (para revisar si fueron editadas)
                        filas_a_mantener = edit_grid[edit_grid["Eliminar"] == False]
                        
                        cambios_hechos = 0
                        borrados_hechos = 0
                        
                        with st.spinner("Procesando modificaciones en la base de datos..."):
                            try:
                                # --- FASE A: ELIMINACIÓN EN CASCADA ---
                                if ids_a_borrar:
                                    # Se eliminan los registros analíticos hijos primero para mantener la integridad relacional
                                    conectar().table("productos_avance_valor").delete().in_("producto_id", ids_a_borrar).execute()
                                    conectar().table("estatus_muebles").delete().in_("producto_id", ids_a_borrar).execute()
                                    conectar().table("fechas_hitos_muebles").delete().in_("producto_id", ids_a_borrar).execute()
                                    conectar().table("seguimiento").delete().in_("producto_id", ids_a_borrar).execute()
                                    
                                    # Se elimina la pieza padre
                                    conectar().table("productos").delete().in_("id", ids_a_borrar).execute()
                                    borrados_hechos += len(ids_a_borrar)
                                
                                # --- FASE B: ACTUALIZACIÓN DE PIEZAS EDITADAS ---
                                for _, row in filas_a_mantener.iterrows():
                                    p_id = int(row["id"])
                                    orig_row = df_matriz_prod[df_matriz_prod["id"] == p_id].iloc[0]
                                    
                                    if (str(row["ubicacion"]).strip() != str(orig_row["ubicacion"]).strip() or
                                        str(row["tipo"]).strip() != str(orig_row["tipo"]).strip() or
                                        int(row["ctd"]) != int(orig_row["ctd"]) or
                                        float(row["ml"]) != float(orig_row["ml"])):
                                        
                                        payload_up = {
                                            "ubicacion": str(row["ubicacion"]).strip(),
                                            "tipo": str(row["tipo"]).strip(),
                                            "ctd": int(row["ctd"]),
                                            "ml": float(row["ml"])
                                        }
                                        conectar().table("productos").update(payload_up).eq("id", p_id).execute()
                                        cambios_hechos += 1
                                
                                # --- FASE C: RECALCULAR AVANCE DEL PROYECTO ---
                                if borrados_hechos > 0 or cambios_hechos > 0:
                                    from base_datos import sincronizar_avances_estructural
                                    sincronizar_avances_estructural(info_p['codigo'])
                                    
                                    st.success(f"✅ Operación completada: {cambios_hechos} piezas modificadas, {borrados_hechos} piezas eliminadas.")
                                    st.cache_data.clear()
                                    st.rerun()
                                else:
                                    st.info("ℹ️ No se detectaron modificaciones en las celdas para guardar.")
                            
                            except Exception as e:
                                st.error(f"❌ Ocurrió un error crítico durante la edición: {e}")
                else:
                    st.info("📂 Este proyecto no cuenta con despieces de carpintería registrados aún.")
        else:
            st.info("⚠️ Seleccione un proyecto en la pestaña **'📋 Matriz de Proyectos'** para habilitar y visualizar su desglose de piezas.")
