import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from base_datos import conectar, obtener_feriados_lista, calcular_dias_utiles_taller

def mostrar():
    # Margen superior para separación ergonómica del menú principal
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    tab_matriz, tab_feriados = st.tabs(["🪚 Matriz de Carga de Producción", "📅 Calendario de Feriados"])

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

            # --- CONFIGURACIÓN DE CONTROLES TEMPORALES CON BUSCADOR DE PERÍODO ---
            st.write("<br>", unsafe_allow_html=True)
            c_titulo, c_periodo, c_fecha, c_vista = st.columns([3, 2.5, 2, 3.5])
            
            c_titulo.markdown("<h3 style='margin: 0px; padding-top: 0.3em;'>🪚 Producción Proyectada</h3>", unsafe_allow_html=True)
            
            hoy = date.today()
            meses_dict = {
                "Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5, "Junio": 6,
                "Julio": 7, "Agosto": 8, "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12
            }
            
            mes_sel = c_periodo.selectbox("📆 Período (Mes):", options=list(meses_dict.keys()), index=hoy.month - 1, label_visibility="collapsed")
            anio_sel = c_periodo.selectbox("📆 Período (Año):", options=[hoy.year - 1, hoy.year, hoy.year + 1], index=1, label_visibility="collapsed")
            
            fecha_periodo_base = date(anio_sel, meses_dict[mes_sel], 1)
            fecha_ref = c_fecha.date_input("Fecha Referencia:", value=fecha_periodo_base, format="DD/MM/YYYY", label_visibility="collapsed")
            vista = c_vista.radio("Vista:", ["📅 Semanal", "📅 Mensual", "📅 Trimestral"], horizontal=True, label_visibility="collapsed")
            st.markdown("<hr style='margin: 0.5rem 0px 1rem 0px;'>", unsafe_allow_html=True)

            # --- MOTOR DE GENERACIÓN DE COLUMNAS (LUNES A SÁBADO) ---
            if "Semanal" in vista:
                inicio_rango = fecha_ref - timedelta(days=fecha_ref.weekday())
                num_dias_busqueda = 7
            elif "Mensual" in vista:
                inicio_rango = date(fecha_ref.year, fecha_ref.month, 1)
                if fecha_ref.month == 12:
                    sig_mes = date(fecha_ref.year + 1, 1, 1)
                else:
                    sig_mes = date(fecha_ref.year, fecha_ref.month + 1, 1)
                num_dias_busqueda = (sig_mes - inicio_rango).days
            else:
                inicio_rango = date(fecha_ref.year, fecha_ref.month, 1)
                num_dias_busqueda = 90

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

            # Aplicamos el estilo condicional estrictamente a las columnas de los días
            df_matriz_estilada = df_matriz_interactiva.style.applymap(resaltar_sobrecarga, subset=columns_fecha)

            # Renderizado de la matriz interactiva unificada
            cambios_matriz_df = st.data_editor(
                df_matriz_estilada,
                column_config=config_columnas,
                hide_index=True,
                use_container_width=True,
                key="data_editor_produccion_horizontal_final"
            )

            # --- PROCESAMIENTO DE GUARDADO Y EFECTO CASCADA EN SUPABASE ---
            if st.button("💾 Guardar Cambios de Fechas y Tableros", type="primary"):
                try:
                    with st.spinner("Actualizando parámetros operativos y recalculando frentes..."):
                        # Filtrar la fila de totales (id=0) para procesar únicamente los proyectos reales
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
                            
                            # Cálculo del desfase de días para aplicar el efecto dominó en cascada
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
                            
                            # Sincronizar el Gantt real
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
    # PESTAÑA 2: CALENDARIO DE FERIADOS (TEXTO DD/MM/YYYY)
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
