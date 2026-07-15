import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
from base_datos import conectar, obtener_feriados_lista, calcular_dias_utiles_taller

def mostrar():
    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Estado de Avance por Frentes", 
        "🪚 Curva de Producción (Tableros)", 
        "📐 Curva de Optimización (Diseño)", 
        "📦 Curva de Instalación (Obra)"
    ])

    supabase = conectar()
    hoy = date.today()
    horizonte_3m = hoy + timedelta(days=90)
    feriados = obtener_feriados_lista()

    # =========================================================
    # 1. CONEXIÓN EXTERNA CON GOOGLE DRIVE (FRENTE OPTIMIZACIÓN)
    # =========================================================
    try:
        FILE_ID = "1ATuNF0Js31QZCo3g3wDUfP3O2PzFjNjW"
        url_excel = f"https://docs.google.com/spreadsheets/d/{FILE_ID}/export?format=xlsx"
        df_drive_optim = pd.read_excel(url_excel, sheet_name="Sheet1")
        df_drive_optim.columns = df_drive_optim.columns.str.strip()
    except:
        try:
            df_drive_optim = pd.read_csv("Cortes holzher- OP Gildo 29052026.xlsx - Sheet1.csv")
            df_drive_optim.columns = df_drive_optim.columns.str.strip()
        except:
            df_drive_optim = pd.DataFrame()

    # =========================================================
    # 2. EXTRACCIÓN DE DATOS DESDE SUPABASE Y CONSOLIDACIÓN
    # =========================================================
    try:
        res_proy = supabase.table("proyectos").select("*").neq("estatus", "Cerrado").execute()
        if not res_proy.data:
            st.info("📂 No existen proyectos activos en ejecución actualmente.")
            return
        
        df_p = pd.DataFrame(res_proy.data)
        
        # Saneamiento de fechas Contractuales vs Ejecución
        df_p["p_fab_i"] = pd.to_datetime(df_p["p_fab_i"], errors='coerce').dt.date
        df_p["p_fab_f"] = pd.to_datetime(df_p["p_fab_f"], errors='coerce').dt.date
        df_p["p_fab_i_ejecucion"] = pd.to_datetime(df_p.get("p_fab_i_ejecucion"), errors='coerce').dt.date.fillna(df_p["p_fab_i"])
        df_p["p_fab_f_ejecucion"] = pd.to_datetime(df_p.get("p_fab_f_ejecucion"), errors='coerce').dt.date.fillna(df_p["p_fab_f"])
        df_p["total_tableros"] = df_p["total_tableros"].fillna(0).astype(int)

        res_productos = supabase.table("productos").select("id, proyecto_id, ml, ctd").execute()
        df_all_prods = pd.DataFrame(res_productos.data) if res_productos.data else pd.DataFrame(columns=['id', 'proyecto_id', 'ml', 'ctd'])
        df_all_prods['ml'] = df_all_prods['ml'].fillna(0.0).astype(float)
        df_all_prods['ctd'] = df_all_prods['ctd'].fillna(1).astype(int)

        # Generar rango continuo de días útiles taller para las curvas
        rango_fechas_3m = []
        curr = hoy
        while curr <= horizonte_3m:
            if curr.weekday() < 6 and curr not in feriados:
                rango_fechas_3m.append(curr)
            curr += timedelta(days=1)

        # Diccionarios de acumulación temporal diaria
        carga_diaria_corte = {d: 0.0 for d in rango_fechas_3m}
        carga_diaria_optim = {d: 0.0 for d in rango_fechas_3m}
        carga_diaria_inst_m = {d: 0.0 for d in rango_fechas_3m}
        carga_diaria_inst_ml = {d: 0.0 for d in rango_fechas_3m}

        lote_resumen = []

        for _, proy in df_p.iterrows():
            id_p = int(proy['id'])
            cod_p = str(proy['codigo']).strip()
            df_prods_p = df_all_prods[df_all_prods['proyecto_id'] == id_p]
            
            if df_prods_p.empty:
                continue

            ids_prods_list = df_prods_p['id'].tolist()
            ml_total_p = df_prods_p['ml'].sum()
            muebles_totales_p = df_prods_p['ctd'].sum()

            # --- FRENTE A: % AVANCE OPTIMIZACIÓN (DESDE GOOGLE DRIVE) ---
            tableros_optimizados = 0
            if not df_drive_optim.empty and "OP" in df_drive_optim.columns and "Cant" in df_drive_optim.columns:
                # Filtrar en Drive por el código de OP del proyecto
                df_op_drive = df_drive_optim[df_drive_optim["OP"].astype(str).str.contains(cod_p, case=False, na=False)]
                tableros_optimizados = pd.to_numeric(df_op_drive["Cant"], errors="coerce").sum()
            
            tableros_totales_p = proy['total_tableros']
            avance_optim = (tableros_optimizados / tableros_totales_p * 100) if tableros_totales_p > 0 else 0.0
            tableros_pendientes_optim = max(0.0, tableros_totales_p - tableros_optimizados)

            # --- FRENTE B: % AVANCE PRODUCCIÓN (CORTADO EN BITÁCORAS) ---
            piezas_producidas = 0
            res_bit = supabase.table("bitacoras_lineas").select("cantidad").eq("bitacora_id", id_p).execute()
            if res_bit.data:
                piezas_producidas = sum([float(b.get('cantidad', 0) or 0) for b in res_bit.data])
            
            avance_prod = (piezas_producidas / muebles_totales_p * 100) if muebles_totales_p > 0 else 0.0
            tableros_pendientes_corte = max(0.0, tableros_totales_p * (1.0 - (avance_prod / 100.0)))

            # --- FRENTE C: % AVANCE INSTALACIÓN (CAMPO OBRA) ---
            ml_instalado = 0.0
            muebles_instalados = 0
            res_est = supabase.table("estatus_muebles").select("producto_id, culminado, entregado").in_("producto_id", ids_prods_list).execute()
            
            if res_est.data:
                df_est = pd.DataFrame(res_est.data)
                df_est['listo'] = df_est['culminado'].fillna(False) | df_est['entregado'].fillna(False)
                ids_listos = df_est[df_est['listo'] == True]['producto_id'].tolist()
                
                df_listos_p = df_prods_p[df_prods_p['id'].isin(ids_listos)]
                ml_instalado = df_listos_p['ml'].sum()
                muebles_instalados = df_listos_p['ctd'].sum()

            avance_inst = (ml_instalado / ml_total_p * 100) if ml_total_p > 0 else 0.0
            ml_pendiente = max(0.0, ml_total_p - ml_instalado)
            muebles_pendientes = max(0, muebles_totales_p - muebles_instalados)

            # --- DISTRIBUCIÓN LOGÍSTICA TEMPORAL EN LAS CURVAS ---
            f_i_ejec = max(hoy, proy['p_fab_i_ejecucion'])
            f_f_ejec = proy['p_fab_f_ejecucion']
            dias_utiles_restantes = calcular_dias_utiles_taller(f_i_ejec, f_f_ejec, feriados)

            if dias_utiles_restantes > 0:
                cuota_corte = tableros_pendientes_corte / dias_utiles_restantes
                cuota_optim = tableros_pendientes_optim / dias_utiles_restantes
                cuota_muebles = muebles_pendientes / dias_utiles_restantes
                cuota_ml = ml_pendiente / dias_utiles_restantes

                for d in rango_fechas_3m:
                    if f_i_ejec <= d <= f_f_ejec:
                        carga_diaria_corte[d] += cuota_corte
                        carga_diaria_optim[d] += cuota_optim
                        carga_diaria_inst_m[d] += cuota_muebles
                        carga_diaria_inst_ml[d] += cuota_ml

            lote_resumen.append({
                "id": id_p,
                "Código": proy['codigo'],
                "Proyecto": proy['proyecto_text'],
                "F. Inicio Ejecución": proy['p_fab_i_ejecucion'],
                "F. Fin Ejecución": proy['p_fab_f_ejecucion'],
                "ML Totales": round(ml_total_p, 1),
                "Tableros Demandados": tableros_totales_p,
                "% Avance Optimización": f"{avance_optim:.1f}%",
                "% Avance Producción": f"{avance_prod:.1f}%",
                "% Avance Instalación": f"{avance_inst:.1f}%"
            })

        df_resumen = pd.DataFrame(lote_resumen) if lote_resumen else pd.DataFrame()

    except Exception as e:
        st.error(f"Error en consolidación multifrente: {e}")
        return

    # =========================================================
    # RENDIMIENTO PESTAÑA 1: GESTIÓN DE PROYECTOS Y FECHAS
    # =========================================================
    with tab1:
        st.subheader("📊 Cuadro de Mandos de Avance Integral")
        if not df_resumen.empty:
            cambios_fechas = st.data_editor(
                df_resumen[['id', 'Código', 'Proyecto', 'ML Totales', 'Tableros Demandados', 'F. Inicio Ejecución', 'F. Fin Ejecución', '% Avance Optimización', '% Avance Producción', '% Avance Instalación']],
                column_config={
                    "id": None,
                    "F. Inicio Ejecución": st.column_config.DateColumn("F. Inicio Ejecución", format="DD/MM/YYYY", required=True),
                    "F. Fin Ejecución": st.column_config.DateColumn("F. Fin Ejecución", format="DD/MM/YYYY", required=True),
                    "ML Totales": st.column_config.NumberColumn("ML Totales", disabled=True),
                    "Tableros Demandados": st.column_config.NumberColumn("Tableros", disabled=True)
                },
                hide_index=True, use_container_width=True, key="grid_reprogramacion_fechas_capacidad"
            )
            
            if st.button("💾 Guardar Fechas de Ejecución Ajustadas", type="primary", use_container_width=True):
                cambios_efectuados = 0
                for index, row in cambios_fechas.iterrows():
                    id_proy_mod = int(row['id'])
                    match_orig = df_resumen[df_resumen['id'] == id_proy_mod].iloc[0]
                    
                    f_i_str = row['F. Inicio Ejecución'].isoformat() if isinstance(row['F. Inicio Ejecución'], (date, datetime)) else str(row['F. Inicio Ejecución'])
                    f_f_str = row['F. Fin Ejecución'].isoformat() if isinstance(row['F. Fin Ejecución'], (date, datetime)) else str(row['F. Fin Ejecución'])
                    
                    if f_i_str != match_orig['F. Inicio Ejecución'].isoformat() or f_f_str != match_orig['F. Fin Ejecución'].isoformat():
                        supabase.table("proyectos").update({"p_fab_i_ejecucion": f_i_str, "p_fab_f_ejecucion": f_f_str}).eq("id", id_proy_mod).execute()
                        cambios_efectuados += 1
                if cambios_efectuados > 0:
                    st.success(f"🎉 Rango de ejecución actualizado."); st.cache_data.clear(); st.rerun()
        else:
            st.info("No hay proyectos activos con desglose.")

    # =========================================================
    # PESTAÑA 2: HORIZONTE DE CAPACIDAD DE CORTE (TABLEROS)
    # =========================================================
    with tab2:
        st.subheader("📈 Tasa de Corte de Tableros Requerida por Día Hábil")
        if rango_fechas_3m:
            df_corte_timeline = pd.DataFrame({
                "Fecha": [d.strftime("%d/%m") for d in carga_diaria_corte.keys()],
                "Tableros por Día": list(carga_diaria_corte.values())
            })
            fig2 = px.line(df_corte_timeline, x="Fecha", y="Tableros por Día", title="Planificación Temporal de Carga Diaria de Corte de Placas", markers=True)
            fig2.update_traces(line_color="#1E3A8A", mode="lines+markers")
            st.plotly_chart(fig2, use_container_width=True)

    # =========================================================
    # PESTAÑA 3: HORIZONTE DE OPTIMIZACIÓN (DISEÑO)
    # =========================================================
    with tab3:
        st.subheader("📐 Tasa de Optimización / Ingeniería por Día Hábil")
        if rango_fechas_3m:
            df_optim_timeline = pd.DataFrame({
                "Fecha": [d.strftime("%d/%m") for d in carga_diaria_optim.keys()],
                "Tableros a Optimizar": list(carga_diaria_optim.values())
            })
            fig3 = px.line(df_optim_timeline, x="Fecha", y="Tableros a Optimizar", title="Meta Diaria de Tableros a Diseñar y Declarar para Corte", markers=True)
            fig3.update_traces(line_color="#E67E22", mode="lines+markers")
            st.plotly_chart(fig3, use_container_width=True)

    # =========================================================
    # PESTAÑA 4: HORIZONTE DE INSTALACIÓN EN OBRA
    # =========================================================
    with tab4:
        st.subheader("📦 Exigencia de Colocación en Obra (Doble Curva)")
        if rango_fechas_3m:
            fechas_label = [d.strftime("%d/%m") for d in rango_fechas_3m]
            
            fig4 = go.Figure()
            # Curva 1: Muebles por Día
            fig4.add_trace(go.Scatter(
                x=fechas_label, y=list(carga_diaria_inst_m.values()),
                name="Muebles por Instalar (und/Día)", mode="lines+markers", line=dict(color="#2ECC71")
            ))
            # Curva 2: Metros Lineales por Día
            fig4.add_trace(go.Scatter(
                x=fechas_label, y=list(carga_diaria_inst_ml.values()),
                name="Metraje por Instalar (ml/Día)", mode="lines+markers", line=dict(color="#9B59B6"),
                yaxis="y2"
            ))

            fig4.update_layout(
                title="Curva Temporal de Ritmo de Instalación Requerido",
                xaxis_title="Línea de Tiempo Hábil (Próximos 3 Meses)",
                yaxis=dict(title="Muebles (Unidades / Día)", titlefont=dict(color="#2ECC71"), tickfont=dict(color="#2ECC71")),
                yaxis2=dict(title="Metraje Lineal (ml / Día)", titlefont=dict(color="#9B59B6"), tickfont=dict(color="#9B59B6"), overlaying="y", side="right"),
                legend=dict(x=0.01, y=0.99)
            )
            st.plotly_chart(fig4, use_container_width=True)
