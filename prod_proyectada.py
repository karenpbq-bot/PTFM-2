import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
from base_datos import conectar, obtener_feriados_lista, calcular_dias_utiles_taller

def mostrar():
    st.markdown("""
        <style>
        .title-modulo { font-size: 26px; font-weight: bold; color: #1E3A8A; margin-bottom: 1rem; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<p class="title-modulo">📋 Planificación y Horizontes de Carga de Producción</p>', unsafe_allow_html=True)

    supabase = conectar()
    hoy = date.today()
    horizonte_3m = hoy + timedelta(days=90)
    feriados = obtener_feriados_lista()

    # =========================================================
    # EXTRACCIÓN Y PROCESAMIENTO CENTRAL DE DATOS (MULTIFRENTE)
    # =========================================================
    try:
        # Descargar proyectos que no estén cerrados
        res_proy = supabase.table("proyectos").select("*").neq("estatus", "Cerrado").execute()
        if not res_proy.data:
            st.info("📂 No existen proyectos activos en ejecución actualmente.")
            return
        
        df_p = pd.DataFrame(res_proy.data)
        
        # Saneamiento seguro de variables de fechas de ejecución y totales
        df_p["p_fab_i_ejecucion"] = pd.to_datetime(df_p.get("p_fab_i_ejecucion"), errors='coerce').dt.date.fillna(pd.to_datetime(df_p["p_fab_i"]).dt.date)
        df_p["p_fab_f_ejecucion"] = pd.to_datetime(df_p.get("p_fab_f_ejecucion"), errors='coerce').dt.date.fillna(pd.to_datetime(df_p["p_fab_f"]).dt.date)
        df_p["total_tableros"] = df_p["total_tableros"].fillna(0).astype(int)

        res_total_productos = supabase.table("productos").select("id, proyecto_id, ml, ctd").execute()
        df_all_prods = pd.DataFrame(res_total_productos.data) if res_total_productos.data else pd.DataFrame(columns=['id', 'proyecto_id', 'ml', 'ctd'])
        df_all_prods['ml'] = df_all_prods['ml'].fillna(0.0).astype(float)
        df_all_prods['ctd'] = df_all_prods['ctd'].fillna(1).astype(int)

        lote_resumen = []
        
        # Crear un rango continuo de días para las curvas de los próximos 3 meses
        rango_fechas_3m = []
        curr = hoy
        while curr <= horizonte_3m:
            if curr.weekday() < 6 and curr not in feriados:
                rango_fechas_3m.append(curr)
            curr += timedelta(days=1)

        # Diccionarios de acumulación diaria para las curvas horizontales
        carga_diaria_corte = {d: 0.0 for d in rango_fechas_3m}
        carga_diaria_optim = {d: 0.0 for d in rango_fechas_3m}
        carga_diaria_inst_m = {d: 0.0 for d in rango_fechas_3m}
        carga_diaria_inst_ml = {d: 0.0 for d in rango_fechas_3m}

        for _, proy in df_p.iterrows():
            id_p = int(proy['id'])
            df_prods_p = df_all_prods[df_all_prods['proyecto_id'] == id_p]
            
            if df_prods_p.empty:
                continue

            ids_prods_list = df_prods_p['id'].tolist()
            ml_total_p = df_prods_p['ml'].sum()
            muebles_totales_p = df_prods_p['ctd'].sum()

            # --- AVANCE DE OPTIMIZACIÓN (ÁREA TÉCNICA) ---
            tableros_optimizados = 0
            res_opt = supabase.table("tableros_requeridos").select("cantidad_tableros").eq("proyecto_id", id_p).execute()
            if res_opt.data:
                tableros_optimizados = sum([int(t.get('cantidad_tableros', 0)) for t in res_opt.data])
            
            avance_optim = (tableros_optimizados / proy['total_tableros'] * 100) if proy['total_tableros'] > 0 else 0.0
            tableros_pendientes = max(0, proy['total_tableros'] - tableros_optimizados)

            # --- AVANCE DE PRODUCCIÓN (BITÁCORAS DE PLACA / CORTE) ---
            piezas_producidas = 0
            res_bit = supabase.table("bitacoras_lineas").select("cant_final_pl_pzs").eq("bitacora_id", id_p).execute()
            if res_bit.data:
                for b in res_bit.data:
                    try: piezas_producidas += int(float(b.get('cant_final_pl_pzs', 0) or 0))
                    except: pass
            
            avance_prod = (piezas_producidas / muebles_totales_p * 100) if muebles_totales_p > 0 else 0.0
            tableros_pendientes_corte = max(0.0, proy['total_tableros'] * (1.0 - (avance_prod / 100.0)))

            # --- AVANCE DE INSTALACIÓN (ESTATUS MUEBLES EN OBRA) ---
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

            avance_inst = (ml_instalado / ml_total_proyecto * 100) if ml_total_p > 0 else 0.0
            ml_pendiente = max(0.0, ml_total_p - ml_instalado)
            muebles_pendientes = max(0, muebles_totales_p - muebles_instalados)

            # --- DISTRIBUCIÓN EN LA LÍNEA DE TIEMPO DEL HORIZONTE DE EJECUCIÓN ---
            f_i_ejec = max(hoy, proy['p_fab_i_ejecucion'])
            f_f_ejec = proy['p_fab_f_ejecucion']
            dias_utiles_restantes = calcular_dias_utiles_taller(f_i_ejec, f_f_ejec, feriados)

            if dias_utiles_restantes > 0:
                cuota_corte = tableros_pendientes_corte / dias_utiles_restantes
                cuota_optim = tableros_pendientes / dias_utiles_restantes
                cuota_muebles = muebles_pendientes / dias_utiles_restantes
                cuota_ml = ml_pendiente / dias_utiles_restantes

                for d in rango_fechas_3m:
                    if f_i_ejec <= d <= f_f_ejec:
                        carga_diaria_corte[d] += cuota_corte
                        carga_diaria_optim[d] += cuota_optim
                        carga_diaria_inst_m[d] += cuota_muebles
                        carga_diaria_inst_ml[d] += cuota_ml

            lote_resumen.append({
                "Código": proy['codigo'],
                "Proyecto": proy['proyecto_text'],
                "ML Totales": round(ml_total_p, 1),
                "Tableros Demandados": proy['total_tableros'],
                "% Avance Optimización": f"{avance_optim:.1f}%",
                "% Avance Producción": f"{avance_prod:.1f}%",
                "% Avance Instalación": f"{avance_inst:.1f}%"
            })

        df_resumen_tab1 = pd.DataFrame(lote_resumen) if lote_resumen else pd.DataFrame()

    except Exception as e:
        st.error(f"Error técnico en el procesamiento multifrente: {e}")
        return

    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Estado de Avance por Frentes", 
        "🪚 Curva de Producción (Tableros)", 
        "📐 Curva de Optimización (Diseño)", 
        "📦 Curva de Instalación (Obra)"
    ])

    # =========================================================
    # PESTAÑA 1: MATRIZ RESUMEN DE PROYECTOS
    # =========================================================
    with tab1:
        st.subheader("📊 Cuadro de Mandos de Avance Integral")
        if not df_resumen_tab1.empty:
            st.dataframe(df_resumen_tab1, hide_index=True, use_container_width=True)
        else:
            st.info("No hay proyectos con despieces configurados en este momento.")

    # =========================================================
    # PESTAÑA 2: GRÁFICO HORIZONTE DE CORTE (TABLEROS)
    # =========================================================
    with tab2:
        st.subheader("📈 Carga Diaria de Corte Acumulada (Horizonte 3 Meses)")
        if rango_fechas_3m:
            df_corte_timeline = pd.DataFrame({
                "Fecha": [d.strftime("%d/%m") for d in carga_diaria_corte.keys()],
                "Tableros por Día": list(carga_diaria_corte.values())
            })
            fig2 = px.line(df_corte_timeline, x="Fecha", y="Tableros por Día", title="Sumatoria de Tableros Requeridos por Día Hábil en Taller", markers=True)
            fig2.update_traces(line_color="#1E3A8A", mode="lines+markers")
            st.plotly_chart(fig2, use_container_width=True)

    # =========================================================
    # PESTAÑA 3: GRÁFICO HORIZONTE DE OPTIMIZACIÓN (DISEÑO)
    # =========================================================
    with tab3:
        st.subheader("📐 Planificación Diaria de Ingeniería de Detalle")
        if rango_fechas_3m:
            df_optim_timeline = pd.DataFrame({
                "Fecha": [d.strftime("%d/%m") for d in carga_diaria_optim.keys()],
                "Tableros a Optimizar": list(carga_diaria_optim.values())
            })
            fig3 = px.line(df_optim_timeline, x="Fecha", y="Tableros a Optimizar", title="Meta de Tableros a Diseñar/Optimizar Diariamente", markers=True)
            fig3.update_traces(line_color="#E67E22", mode="lines+markers")
            st.plotly_chart(fig3, use_container_width=True)

    # =========================================================
    # PESTAÑA 4: GRÁFICO HORIZONTE DE INSTALACIÓN EN OBRA
    # =========================================================
    with tab4:
        st.subheader("📦 Exigencia Logística de Colocación en Obra")
        if rango_fechas_3m:
            fechas_label = [d.strftime("%d/%m") for d in rango_fechas_3m]
            
            # Construcción de gráfico con doble eje Y usando graph_objects
            fig4 = go.Figure()
            
            # Curva 1: Muebles/Piezas por Día
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

            # Diseño de la interfaz de doble eje simétrico
            fig4.update_layout(
                title="Metas Diarias de Instalación Basadas en Saldo Pendiente",
                xaxis_title="Línea de Tiempo Hábil",
                yaxis=dict(title="Muebles (Unidades / Día)", titlefont=dict(color="#2ECC71"), tickfont=dict(color="#2ECC71")),
                yaxis2=dict(title="Metraje Lineal (ml / Día)", titlefont=dict(color="#9B59B6"), tickfont=dict(color="#9B59B6"), overlaying="y", side="right"),
                legend=dict(x=0.01, y=0.99)
            )
            st.plotly_chart(fig4, use_container_width=True)
