import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta, date
from base_datos import conectar, obtener_feriados_lista, calcular_dias_utiles_taller

def mostrar():
    # Margen superior para separación ergonómica del menú principal
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    tab_matriz, tab_analisis, tab_feriados = st.tabs([
        "📋 Matriz de Carga de Producción", 
        "📊 Análisis Multifrente", 
        "📅 Calendario de Feriados"
    ])

    supabase = conectar()
    hoy = date.today()
    feriados = obtener_feriados_lista()

    # =========================================================
    # CONSOLIDACIÓN MIGRADA A MODELO TRIDIMENSIONAL DINÁMICO
    # =========================================================
    try:
        # 1. Descargar los proyectos activos desde Supabase
        res_proyectos = supabase.table("proyectos").select("*").eq("estatus", "Activo").execute()
        if not res_proyectos.data:
            with tab_matriz:
                st.info("📂 Actualmente no existen proyectos con estatus 'Activo' registrados en el sistema.")
            return
        
        df_proy = pd.DataFrame(res_proyectos.data)
        
        # Mapeo y fallback seguro de Fechas Contractuales (Línea Base) vs Fechas de Ejecución Real
        df_proy["p_fab_i"] = pd.to_datetime(df_proy["p_fab_i"], errors='coerce').dt.date
        df_proy["p_fab_f"] = pd.to_datetime(df_proy["p_fab_f"], errors='coerce').dt.date
        
        # Si las columnas de ejecución están vacías en la BD, adoptamos las contractuales como inicio seguro
        df_proy["p_fab_i_ejecucion"] = pd.to_datetime(df_proy.get("p_fab_i_ejecucion"), errors='coerce').dt.date.fillna(df_proy["p_fab_i"])
        df_proy["p_fab_f_ejecucion"] = pd.to_datetime(df_proy.get("p_fab_f_ejecucion"), errors='coerce').dt.date.fillna(df_proy["p_fab_f"])
        df_proy["total_tableros"] = df_proy["total_tableros"].fillna(0).astype(int)

        lote_reporte = []

        for _, proy in df_proy.iterrows():
            id_p = int(proy['id'])
            
            # --- FRENTE 1: AVANCE EN OBRA (Metros Lineales basados en Estatus Muebles) ---
            res_prods = supabase.table("productos").select("id, ml").eq("proyecto_id", id_p).execute()
            df_items = pd.DataFrame(res_prods.data) if res_prods.data else pd.DataFrame(columns=['id', 'ml'])
            df_items['ml'] = df_items['ml'].fillna(0.0).astype(float)
            ml_total_proyecto = df_items['ml'].sum()

            ml_instalado = 0.0
            if not df_items.empty:
                ids_productos = df_items['id'].tolist()
                res_estatus = supabase.table("estatus_muebles").select("producto_id, culminado, entregado").in_("producto_id", ids_productos).execute()
                
                if res_estatus.data:
                    df_est = pd.DataFrame(res_estatus.data)
                    # Un mueble se considera instalado/listo si está culminado o entregado
                    df_est['listo'] = df_est['culminado'].fillna(False) | df_est['entregado'].fillna(False)
                    ids_listos = df_est[df_est['listo'] == True]['producto_id'].tolist()
                    ml_instalado = df_items[df_items['id'].isin(ids_listos)]['ml'].sum()

            ml_pendiente = max(0.0, ml_total_proyecto - ml_instalado)

            # --- FRENTE 2: CAPACIDAD DE PLANTA (Tableros basados en Fechas de Ejecución Ajustables) ---
            # Factor de conversión: cuántos tableros representa cada metro lineal diseñado en este lote
            factor_tablero_ml = proy['total_tableros'] / ml_total_proyecto if ml_total_proyecto > 0 else 0.0
            tableros_pendientes = ml_pendiente * factor_tablero_ml

            # Días útiles de taller calculados estrictamente sobre el rango móvil de ejecución (Lun-Sáb)
            fecha_inicio_calculo = max(hoy, proy['p_fab_i_ejecucion'])
            dias_restantes = calcular_dias_utiles_taller(fecha_inicio_calculo, proy['p_fab_f_ejecucion'], feriados)

            # Tasa de corte diaria recalculada automáticamente
            if dias_restantes > 0:
                tasa_diaria = tableros_pendientes / dias_restantes
            else:
                tasa_diaria = tableros_pendientes # Carga de urgencia si venció el rango de ejecución

            # Porcentaje de avance físico real basado en ML
            avance_real_ml = (ml_instalado / ml_total_proyecto * 100) if ml_total_proyecto > 0 else 0.0

            # --- FRENTE 3: AVANCE DE OPTIMIZACIÓN (Área Técnica / Diseño) ---
            tableros_optimizados = 0
            try:
                res_opt = supabase.table("tableros_requeridos").select("cantidad_tableros").eq("proyecto_id", id_p).execute()
                if res_opt.data:
                    tableros_optimizados = sum([int(t.get('cantidad_tableros', 0)) for t in res_opt.data])
            except:
                pass
            
            tableros_por_optimizar = max(0, proy['total_tableros'] - tableros_optimizados)

            lote_reporte.append({
                "id": id_p,
                "Código": proy['codigo'],
                "Proyecto": proy['proyecto_text'],
                "Cliente": proy['cliente'],
                "Línea Base Fin": proy['p_fab_f'], # Plazo Inamovible del Contrato
                "F. Inicio Ejecución": proy['p_fab_i_ejecucion'], # Ajustable en Planta
                "F. Fin Ejecución": proy['p_fab_f_ejecucion'], # Ajustable en Planta
                "ML Total": round(ml_total_proyecto, 1),
                "ML Pendiente": round(ml_pendiente, 1),
                "Avance (ML)": f"{avance_real_ml:.1f}%",
                "Tableros Totales": proy['total_tableros'],
                "Tableros Pendientes": round(tableros_pendientes, 1),
                "Días Útiles Restantes": dias_restantes,
                "Ritmo Diario (Tableros/Día)": round(tasa_diaria, 2),
                "Tableros Optimizados": tableros_optimizados,
                "Por Optimizar": tableros_por_optimizar
            })

        df_reporte = pd.DataFrame(lote_reporte) if lote_reporte else pd.DataFrame()

    except Exception as e:
        st.error(f"Error crítico en el cálculo dinámico multifrente: {e}")
        return

    # =========================================================
    # PESTAÑA 1: MATRIZ DE CARGA DE PRODUCCIÓN (EDITABLE)
    # =========================================================
    with tab_matriz:
        st.subheader("⚙️ Programación de Fechas de Ejecución y Ritmo de Planta")
        st.caption("Fije los plazos reales de ejecución de carpintería aquí. Las fechas contractuales originales de la Línea Base permanecerán seguras e inalteradas.")
        
        if not df_reporte.empty:
            # Grilla interactiva configurada para permitir la modificación exclusiva de las fechas de ejecución
            cambios_grid = st.data_editor(
                df_reporte[['id', 'Código', 'Proyecto', 'Línea Base Fin', 'F. Inicio Ejecución', 'F. Fin Ejecución', 'Tableros Pendientes', 'Días Útiles Restantes', 'Ritmo Diario (Tableros/Día)']],
                column_config={
                    "id": None,
                    "Código": st.column_config.TextColumn("Código", disabled=True),
                    "Proyecto": st.column_config.TextColumn("Proyecto", disabled=True),
                    "Línea Base Fin": st.column_config.DateColumn("Plazo Contrato", format="DD/MM/YYYY", disabled=True),
                    "F. Inicio Ejecución": st.column_config.DateColumn("F. Inicio Ejecución", format="DD/MM/YYYY", required=True),
                    "F. Fin Ejecución": st.column_config.DateColumn("F. Fin Ejecución", format="DD/MM/YYYY", required=True),
                    "Tableros Pendientes": st.column_config.NumberColumn("Tableros Pend.", format="%.1f", disabled=True),
                    "Días Útiles Restantes": st.column_config.NumberColumn("Días Utiles", format="%d", disabled=True),
                    "Ritmo Diario (Tableros/Día)": st.column_config.NumberColumn("Corte Requerido", format="%.2f", disabled=True)
                },
                hide_index=True,
                use_container_width=True,
                key="grid_ajuste_fechas_ejecucion_produccion"
            )
            
            # Sincronización e inyección en bloque a Supabase ante modificaciones
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("💾 Guardar Fechas de Ejecución Ajustadas", type="primary", use_container_width=True):
                cambios_detectados = 0
                for index, row in cambios_grid.iterrows():
                    id_proy_mod = int(row['id'])
                    match_original = df_reporte[df_reporte['id'] == id_proy_mod].iloc[0]
                    
                    f_i_iso = row['F. Inicio Ejecución'].isoformat() if isinstance(row['F. Inicio Ejecución'], (date, datetime)) else str(row['F. Inicio Ejecución'])
                    f_f_iso = row['F. Fin Ejecución'].isoformat() if isinstance(row['F. Fin Ejecución'], (date, datetime)) else str(row['F. Fin Ejecución'])
                    
                    if f_i_iso != match_original['F. Inicio Ejecución'].isoformat() or f_f_iso != match_original['F. Fin Ejecución'].isoformat():
                        supabase.table("proyectos").update({
                            "p_fab_i_ejecucion": f_i_iso,
                            "p_fab_f_ejecucion": f_f_iso
                        }).eq("id", id_proy_mod).execute()
                        cambios_detectados += 1
                
                if cambios_detectados > 0:
                    st.success(f"🎉 Fechas de ejecución guardadas con éxito para {cambios_detectados} proyecto(s).")
                    st.cache_data.clear()
                    st.rerun()
        else:
            st.info("📂 Los proyectos activos no cuentan con despiece de productos cargado.")

    # =========================================================
    # PESTAÑA 2: ANÁLISIS MULTIFRENTE Y GRÁFICO DE CARGA
    # =========================================================
    with tab_analisis:
        if not df_reporte.empty:
            st.subheader("📊 Reporte de Control Tridimensional Colectivo")
            
            # Despliegue unificado de los 3 frentes para análisis de la gerencia de operaciones
            st.dataframe(
                df_reporte[['Código', 'Proyecto', 'ML Total', 'ML Pendiente', 'Avance (ML)', 'Tableros Totales', 'Tableros Pendientes', 'Ritmo Diario (Tableros/Día)', 'Tableros Optimizados', 'Por Optimizar']],
                column_config={
                    "ML Total": st.column_config.NumberColumn("Metraje Lote (ml)", format="%.1f"),
                    "ML Pendiente": st.column_config.NumberColumn("Pend. Instalar (ml)", format="%.1f"),
                    "Ritmo Diario (Tableros/Día)": st.column_config.NumberColumn("Tableros/Día", format="%.2f"),
                    "Por Optimizar": st.column_config.NumberColumn("Por Diseñar (Tab)", format="%d")
                },
                hide_index=True,
                use_container_width=True
            )

            st.markdown("---")
            st.subheader("📈 Tasa de Corte Requerida por Jornada Útil Restante")
            
            # Reconstrucción simétrica del gráfico de barras interactivo de Plotly Express
            fig = px.bar(
                df_reporte,
                x="Proyecto",
                y="Ritmo Diario (Tableros/Día)",
                text="Ritmo Diario (Tableros/Día)",
                color="Proyecto",
                title="Número de Tableros a Cortar por Día Hábil de Ejecución Restante"
            )
            fig.update_traces(textposition='outside')
            st.plotly_chart(fig, use_container_width=True)
            
            # Gráfico de barras agrupado para análisis comparativo de saldos pendientes
            st.markdown("### 🔍 Comparativo de Saldos Pendientes por Frente Operativo")
            fig_frentes = px.bar(
                df_reporte,
                x="Proyecto",
                y=["ML Pendiente", "Tableros Pendientes", "Por Optimizar"],
                barmode="group",
                labels={"value": "Cantidad / Medida", "variable": "Frente de Análisis"},
                title="Estado de los Proyectos (Instalación de Muebles vs. Planta vs. Optimización de Ingeniería)"
            )
            st.plotly_chart(fig_frentes, use_container_width=True)
        else:
            st.info("No hay datos consolidados suficientes para mostrar los análisis gráficos.")

    # =========================================================
    # PESTAÑA 3: CALENDARIO DE FERIADOS
    # =========================================================
    with tab_feriados:
        st.markdown("### 📅 Registro de Días No Laborables de Taller")
        
        with st.form("form_feriados_p"):
            c1, c2 = st.columns([2, 4])
            f_sel = c1.date_input("Fecha Feriado:", value=hoy, format="DD/MM/YYYY")
            f_desc = c2.text_input("Descripción / Motivo:", placeholder="Ej. Aniversario de Arequipa")
            
            if st.form_submit_button("➕ Registrar Día Feriado"):
                try:
                    fecha_texto = f_sel.strftime('%d/%m/%Y')
                    supabase.table("feriados").insert({
                        "fecha": fecha_texto,
                        "descripcion": f_desc
                    }).execute()
                    st.success(f"✅ Feriado del {fecha_texto} registrado.")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error o fecha ya duplicada: {e}")

        st.divider()
        st.markdown("#### Feriados Activos en el Sistema")
        try:
            res_f = supabase.table("feriados").select("*").execute()
            if res_f.data:
                df_f_vista = pd.DataFrame(res_f.data)
                df_f_vista['date_obj'] = pd.to_datetime(df_f_vista['fecha'], format='%d/%m/%Y')
                df_f_vista = df_f_vista.sort_values('date_obj').rename(columns={'fecha': 'Fecha', 'descripcion': 'Descripción'})
                st.dataframe(df_f_vista[['Fecha', 'Descripción']], use_container_width=True, hide_index=True)
                
                if st.button("🧹 Vaciar Todos los Feriados", type="primary"):
                    supabase.table("feriados").delete().neq("id", 0).execute()
                    st.success("Calendario de feriados reiniciado.")
                    st.cache_data.clear()
                    st.rerun()
            else:
                st.info("No hay feriados registrados.")
        except Exception as e:
            st.error(f"Error al cargar feriados: {e}")
