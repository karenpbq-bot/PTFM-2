import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from base_datos import conectar, obtener_feriados_lista, calcular_dias_utiles_taller

def mostrar():
    # Margen superior para separación ergonómica del menú principal
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    tab_matriz, tab_grafico, tab_feriados = st.tabs(["🪚 Matriz de Carga de Producción", "📈 Gráfico de Carga", "📅 Calendario de Feriados"])

    # =========================================================
    # PESTAÑA 1: MATRIZ DE CARGA HORIZONTAL INTEGRADA (EDITABLE)
    # =========================================================
    with tab_matriz:
        try:
            supabase = conectar()
            res = supabase.table("proyectos").select("*").eq("estatus", "Activo").execute()
            
            if not res.data:
                st.info("📂 Actualmente no existen proyectos con estatus 'Activo' registrados en el sistema.")
                return

            df_proy = pd.DataFrame(res.data)
            
            # Conversión inicial segura a objetos date de Python
            df_proy["p_fab_i"] = pd.to_datetime(df_proy["p_fab_i"], errors='coerce').dt.date
            df_proy["p_fab_f"] = pd.to_datetime(df_proy["p_fab_f"], errors='coerce').dt.date
            df_proy["total_tableros"] = pd.to_numeric(df_proy["total_tableros"], errors='coerce').fillna(0).astype(int)

            # Cargar set de feriados registrados en formato texto DD/MM/YYYY
            feriados_set = obtener_feriados_lista()

            # --- CONFIGURACIÓN DE CONTROLES TEMPORALES COMPACTOS (UNA SOLA FILA HORIZONTAL) ---
            c_titulo, c_fecha, c_vista = st.columns([3.5, 3, 5.5])
            
            # Título compacto con margen cero para evitar espacio muerto superior
            c_titulo.markdown("<h3 style='margin: 0px; padding: 0px; line-height: 1.2;'>🪚 Producción Proyectada</h3>", unsafe_allow_html=True)
            
            # Selector de fecha y vista alineados a la altura del título (Etiquetas ocultas para ahorrar espacio)
            fecha_inicio_vista = c_fecha.date_input("Item Inicio:", value=date.today(), format="DD/MM/YYYY", label_visibility="collapsed")
            vista = c_vista.radio("🔍 Vista:", ["📅 Mensual (30 días)", "📅 Trimestral (90 días)"], horizontal=True, label_visibility="collapsed")
            
            st.markdown("<hr style='margin: 0.3rem 0px 0.8rem 0px;'>", unsafe_allow_html=True)

            # --- MOTOR DE GENERACIÓN DE COLUMNAS CONTINUAS (LUNES A SÁBADO) ---
            inicio_rango = fecha_inicio_vista
            num_dias_busqueda = 30 if "Mensual" in vista else 90

            lista_dias = []
            for x in range(num_dias_busqueda):
                d = inicio_rango + timedelta(days=x)
                if d.weekday() < 6: # Filtro estricto: Excluye Domingos (6)
                    lista_dias.append(d)

            columns_fecha = [d.strftime("%d/%m") for d in lista_dias]

            # --- CONSTRUCCIÓN DEL DATAEDITOR UNIFICADO ---
            filas_editor_base = []
            for _, fila in df_proy.iterrows():
                f_i = fila["p_fab_i"]
                f_f = fila["p_fab_f"]
                tot_tab = fila["total_tableros"]
                
                # Calcular días útiles reales (Lunes a Sábado) descartando feriados
                dias_utiles = 0
                if f_i and f_f and f_i <= f_f:
                    curr = f_i
                    while curr <= f_f:
                        if curr.weekday() < 6 and curr not in feriados_set:
                            dias_utiles += 1
                        curr += timedelta(days=1)

                tab_por_dia = tot_tab / dias_utiles if dias_utiles > 0 else 0.0

                registro = {
                    "id": fila["id"],
                    "Proyecto": fila["proyecto_text"],
                    "Fecha Inicio": f_i,
                    "Fecha Fin": f_f,
                    "Tableros Totales": tot_tab
                }
                
                # Inyección de las celdas calculadas para las columnas de días
                for d in lista_dias:
                    nombre_col = d.strftime("%d/%m")
                    if f_i and f_f and f_i <= d <= f_f and d.weekday() < 6 and d not in feriados_set:
                        registro[nombre_col] = round(tab_por_dia, 2)
                    else:
                        registro[nombre_col] = 0.0
                        
                filas_editor_base.append(registro)

            df_editor_base = pd.DataFrame(filas_editor_base)

            # Guardamos df_editor_base y lista_dias en el estado de sesión para compartirlos de forma segura con la pestaña del gráfico
            st.session_state["df_editor_base_cache"] = df_editor_base
            st.session_state["lista_dias_cache"] = lista_dias

            # Cálculo de la Fila de Totales Diarios en el Tope Superior
            totales_diarios = {col: round(df_editor_base[col].sum(), 2) for col in columns_fecha}
            fila_total = {
                "id": 0,
                "Proyecto": "🔥 TOTAL DIARIO",
                "Fecha Inicio": None,
                "Fecha Fin": None,
                "Tableros Totales": int(df_editor_base["Tableros Totales"].sum())
            }
            fila_total.update(totales_diarios)
            
            df_matriz_interactiva = pd.concat([pd.DataFrame([fila_total]), df_editor_base], ignore_index=True)

            # Configuración de permisos de edición por columna
            config_columnas = {
                "id": None,
                "Proyecto": st.column_config.TextColumn("Proyecto", disabled=True),
                "Fecha Inicio": st.column_config.DateColumn("Fecha Inicio", format="DD/MM/YYYY", required=True),
                "Fecha Fin": st.column_config.DateColumn("Fecha Fin", format="DD/MM/YYYY", required=True),
                "Tableros Totales": st.column_config.NumberColumn("Tabl. Tot.", min_value=1, step=1, required=True)
            }
            # Protegemos las columnas de los días (Solo Lectura)
            for col in columns_fecha:
                config_columnas[col] = st.column_config.NumberColumn(col, disabled=True, format="%.2f")

            # --- APLICACIÓN DE ALERTA VISUAL CONDICIONAL (>= 45 TABLEROS) ---
            def resaltar_sobrecarga(val):
                try:
                    if isinstance(val, (int, float)) and val >= 45.0:
                        return 'color: #D32F2F; font-weight: bold; background-color: #FFEBEE;'
                except:
                    pass
                return ''

            # Aplicamos el estilo condicional estrictamente a las columnas de los días utilizando .map() para Pandas 2.x
            df_matriz_estilada = df_matriz_interactiva.style.map(resaltar_sobrecarga, subset=columns_fecha)

            # Renderizado de la matriz interactiva unificada
            cambios_matriz_df = st.data_editor(
                df_matriz_estilada,
                column_config=config_columnas,
                hide_index=True,
                use_container_width=True,
                key="data_editor_produccion_horizontal_final"
            )

            # --- PROCESAMIENTO DE GUARDADO Y EFECTO CASCADA EN SUPABASE (CORREGIDO: Ubicación Nativa) ---
            if st.button("💾 Guardar Cambios de Fechas y Tableros", type="primary"):
                try:
                    with st.spinner("Actualizando parámetros operativos y recalculando frentes..."):
                        df_proyectos_editados = cambios_matriz_df[cambios_matriz_df['id'] > 0]
                        
                        for idx, row in df_proyectos_editados.iterrows():
                            id_proyecto = int(row['id'])
                            nuevo_ini_fab = row['Fecha Inicio']
                            nuevo_fin_fab = row['Fecha Fin']
                            nuevos_tableros = int(row['Tableros Totales'])
                            
                            if nuevo_ini_fab > nuevo_fin_fab:
                                st.error(f"❌ Error en proyecto {row['Proyecto']}: La fecha de inicio no puede ser posterior a la de fin.")
                                st.stop()
                            
                            datos_orig = df_proy[df_proy['id'] == id_proyecto].iloc[0]
                            old_ini_fab = datos_orig['p_fab_i']
                            
                            delta_dias = (nuevo_ini_fab - old_ini_fab).days if old_ini_fab else 0
                            
                            def desplazar_fecha(campo_fecha):
                                if datos_orig.get(campo_fecha):
                                    fecha_orig = pd.to_datetime(datos_orig[campo_fecha]).date()
                                    return (fecha_orig + timedelta(days=delta_dias)).isoformat()
                                return None

                            datos_actualizados = {
                                "p_fab_i": nuevo_ini_fab.isoformat(),
                                "p_fab_f": nuevo_fin_fab.isoformat(),
                                "total_tableros": nuevos_tableros,
                                "p_tra_i": desplazar_fecha('p_tra_i'),
                                "p_tra_f": desplazar_fecha('p_tra_f'),
                                "p_ins_i": desplazar_fecha('p_ins_i'),
                                "p_ins_f": desplazar_fecha('p_ins_f'),
                                "p_ent_i": desplazar_fecha('p_ent_i'),
                                "p_ent_f": desplazar_fecha('p_ent_f'),
                                "f_ini": nuevo_ini_fab.isoformat()
                            }
                            
                            supabase.table("proyectos").update(datos_actualizados).eq("id", id_proyecto).execute()
                            
                            from base_datos import sincronizar_avances_estructural
                            sincronizar_avances_estructural(datos_orig['codigo'])

                    st.success("✅ Parámetros de producción actualizados con éxito.")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar los datos en Supabase: {e}")

        except Exception as e:
            st.error(f"Error crítico en el renderizado de la matriz: {e}")

    # =========================================================
    # PESTAÑA 2: VISTA GRÁFICA DE LA CURVA DE FABRICACIÓN (MIGRADO A PLOTLY)
    # =========================================================
    with tab_grafico:
        try:
            df_editor_base_cache = st.session_state.get("df_editor_base_cache", None)

            if df_editor_base_cache is not None and not df_editor_base_cache.empty:
                st.markdown("<h4 style='margin: 0px; padding-bottom: 0.5rem;'>📈 Curva de Carga Diaria (Tableros Proyectados)</h4>", unsafe_allow_html=True)
                
                # Generación analítica independiente del rango temporal seleccionado
                inicio_rango_grafico = fecha_inicio_vista
                num_dias_grafico = 30 if "Mensual" in vista else 90

                lista_dias_grafico = []
                for x in range(num_dias_grafico):
                    d = inicio_rango_grafico + timedelta(days=x)
                    if d.weekday() < 6: # Excluye domingos de manera estricta
                        lista_dias_grafico.append(d)

                fechas_grafico = []
                totales_grafico = []
                
                for d in lista_dias_grafico:
                    nombre_col = d.strftime("%d/%m")
                    # Suma el volumen del día si existe en las columnas del dataframe operativo
                    total_dia = df_editor_base_cache[nombre_col].sum() if nombre_col in df_editor_base_cache.columns else 0.0
                    fechas_grafico.append(nombre_col)
                    totales_grafico.append(round(total_dia, 2))
                
                df_curva = pd.DataFrame({
                    "Día": fechas_grafico,
                    "Tableros a Cortar": totales_grafico
                })
                
                # --- NUEVA RENDERIZACIÓN CON PLOTLY PARA INYECTAR LAS ETIQUETAS DIARIAS ---
                fig_curva = px.line(
                    df_curva,
                    x="Día",
                    y="Tableros a Cortar",
                    text="Tableros a Cortar",  # Inyecta dinámicamente las etiquetas numéricas en cada punto
                    color_discrete_sequence=["#D32F2F"]
                )
                
                # Configuración estética de las etiquetas en los nodos de la curva
                fig_curva.update_traces(
                    textposition="top center", 
                    marker=dict(size=6, symbol="circle"), 
                    mode="lines+markers+text"
                )
                
                fig_curva.update_layout(
                    xaxis_title=None,
                    yaxis_title="Cantidad de Tableros",
                    margin=dict(l=10, r=10, t=15, b=10),
                    hovermode="x unified"
                )
                
                # Despliegue del gráfico Plotly adaptado al contenedor de Streamlit
                st.plotly_chart(fig_curva, use_container_width=True)
                
                c_inf1, c_inf2 = st.columns(2)
                with c_inf1:
                    st.info("💡 **Interpretación:** Los descensos que tocan el nivel 0 representan los domingos y feriados sin procesamiento de material.")
                with c_inf2:
                    if any(t >= 45.0 for t in totales_grafico):
                        st.warning("⚠️ **Alerta de Capacidad:** Se detectan picos que igualan o superan el umbral crítico de 45 tableros diarios. Se recomienda revisar la matriz para reprogramar fechas.")
                    else:
                        st.success("✅ **Flujo Optimizado:** La carga proyectada se mantiene balanceada dentro de las capacidades operativas.")
            else:
                st.info("📂 No hay datos de producción activos en este período para generar la gráfica.")
                
        except Exception as e:
            st.error(f"No se pudo renderizar la curva gráfica: {e}")

    # =========================================================
    # PESTAÑA 3: CALENDARIO DE FERIADOS (TEXTO DD/MM/YYYY)
    # =========================================================
    with tab_feriados:
        st.subheader("📅 Registro de Feriados Anuales")
        st.write("Declara los días festivos o cierres de taller en formato DD/MM/YYYY.")

        with st.form("form_nuevo_feriado", clear_on_submit=True):
            c_f1, c_f2 = st.columns(2)
            f_fecha = c_f1.date_input("Fecha No Laborable:", value=date.today(), format="DD/MM/YYYY")
            f_desc = c_f2.text_input("Descripción / Motivo:", placeholder="Ej: Fiestas Patrias")
            
            if st.form_submit_button("🚀 Registrar Feriado"):
                try:
                    fecha_texto = f_fecha.strftime('%d/%m/%Y')
                    conectar().table("feriados").insert({
                        "fecha": fecha_texto,
                        "descripcion": f_desc
                    }).execute()
                    st.success(f"✅ Feriado del {fecha_texto} registrado con éxito.")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error o fecha ya registrada: {e}")

        st.divider()
        st.markdown("#### Feriados Activos en el Sistema")
        try:
            res_f = conectar().table("feriados").select("*").execute()
            if res_f.data:
                df_f_vista = pd.DataFrame(res_f.data)
                
                # Ordenamiento cronológico seguro
                df_f_vista['date_obj'] = pd.to_datetime(df_f_vista['fecha'], format='%d/%m/%Y')
                df_f_vista = df_f_vista.sort_values('date_obj')
                
                df_f_vista = df_f_vista.rename(columns={'fecha': 'Fecha', 'descripcion': 'Descripción'})
                st.dataframe(df_f_vista[['Fecha', 'Descripción']], use_container_width=True, hide_index=True)
                
                if st.button("🧹 Vaciar Todos los Feriados", type="primary"):
                    conectar().table("feriados").delete().neq("id", 0).execute()
                    st.success("Calendario de feriados reiniciado.")
                    st.cache_data.clear()
                    st.rerun()
            else:
                st.info("No hay feriados registrados.")
        except Exception as e:
            st.error(f"Error al cargar feriados: {e}")
