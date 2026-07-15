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
        .stDataEditor { font-size: 13px; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<p class="title-modulo">📋 Planificación y Horizontes de Carga Operativa</p>', unsafe_allow_html=True)

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
    # 1. ORIGEN A: GOOGLE DRIVE (Frente Optimización)
    # =========================================================
    try:
        FILE_ID = "1ATuNF0Js31QZCo3g3wDUfP3O2PzFjNjW"
        url_excel = f"https://docs.google.com/spreadsheets/d/{FILE_ID}/export?format=xlsx"
        df_drive_optim = pd.read_excel(url_excel, sheet_name="Sheet1")
        df_drive_optim.columns = df_drive_optim.columns.str.strip()
    except:
        df_drive_optim = pd.DataFrame()

    # =========================================================
    # 2. ORIGEN B: SUPABASE Y CONSOLIDACIÓN DE DATOS (Producción e Instalación)
    # =========================================================
    try:
        # Descarga masiva para evitar loops en base de datos
        res_proy = supabase.table("proyectos").select("*").neq("estatus", "Cerrado").execute()
        if not res_proy.data:
            st.info("📂 No existen proyectos activos para proyectar cargas.")
            return
        
        df_p = pd.DataFrame(res_proy.data)
        
        # Saneamiento de fechas con cascada de respaldo (Ejecución -> Fabricación -> Global)
        for col in ["p_fab_i", "p_fab_f", "f_ini", "f_fin", "p_fab_i_ejecucion", "p_fab_f_ejecucion"]:
            if col in df_p.columns:
                df_p[col] = pd.to_datetime(df_p[col], errors='coerce').dt.date

        df_p["total_tableros"] = pd.to_numeric(df_p.get("total_tableros", 0), errors='coerce').fillna(0).astype(int)

        res_productos = supabase.table("productos").select("id, proyecto_id, ml, ctd").execute()
        df_prods = pd.DataFrame(res_productos.data) if res_productos.data else pd.DataFrame(columns=['id', 'proyecto_id', 'ml', 'ctd'])
        df_prods['ml'] = pd.to_numeric(df_prods['ml'], errors='coerce').fillna(0.0)
        df_prods['ctd'] = pd.to_numeric(df_prods['ctd'], errors='coerce').fillna(1).astype(int)

        res_estatus = supabase.table("estatus_muebles").select("producto_id, culminado, entregado").execute()
        df_est = pd.DataFrame(res_estatus.data) if res_estatus.data else pd.DataFrame(columns=['producto_id', 'culminado', 'entregado'])
        
        res_bit_taller = supabase.table("bitacoras_taller").select("id, proyecto").execute()
        df_bit_t = pd.DataFrame(res_bit_taller.data) if res_bit_taller.data else pd.DataFrame(columns=['id', 'proyecto'])
        
        res_bit_lineas = supabase.table("bitacoras_lineas").select("bitacora_id, cant_final_pl_pzs, cantidad").execute()
        df_bit_l = pd.DataFrame(res_bit_lineas.data) if res_bit_lineas.data else pd.DataFrame(columns=['bitacora_id', 'cant_final_pl_pzs', 'cantidad'])

        # Preparamos el rango del horizonte
        rango_fechas_3m = []
        curr = hoy
        while curr <= horizonte_3m:
            if curr.weekday() < 6 and curr not in feriados:
                rango_fechas_3m.append(curr)
            curr += timedelta(days=1)

        # Contenedores de las curvas
        curva_corte = {d: 0.0 for d in rango_fechas_3m}
        curva_optim = {d: 0.0 for d in rango_fechas_3m}
        curva_inst_muebles = {d: 0.0 for d in rango_fechas_3m}
        curva_inst_ml = {d: 0.0 for d in rango_fechas_3m}

        lote_resumen = []

        for _, proy in df_p.iterrows():
            id_p = int(proy['id'])
            cod_p = str(proy['codigo']).strip()
            nom_p = str(proy['proyecto_text']).strip()
            tableros_totales = proy['total_tableros']

            # Fechas reales de ejecución
            f_inicio = proy.get('p_fab_i_ejecucion') or proy.get('p_fab_i') or proy.get('f_ini') or hoy
            f_fin = proy.get('p_fab_f_ejecucion') or proy.get('p_fab_f') or proy.get('f_fin') or horizonte_3m

            # Despiece del proyecto
            df_p_prods = df_prods[df_prods['proyecto_id'] == id_p]
            ml_totales = df_p_prods['ml'].sum()
            muebles_totales = df_p_prods['ctd'].sum()

            # --- FRENTE: OPTIMIZACIÓN (Google Drive) ---
            tableros_optimizados = 0
            if not df_drive_optim.empty and "OP" in df_drive_optim.columns and "Cant" in df_drive_optim.columns:
                filtro_op = df_drive_optim[df_drive_optim["OP"].astype(str).str.contains(cod_p, case=False, na=False)]
                tableros_optimizados = pd.to_numeric(filtro_op["Cant"], errors="coerce").sum()
            
            av_optim = (tableros_optimizados / tableros_totales * 100) if tableros_totales > 0 else 0.0
            pend_optim = max(0.0, tableros_totales - tableros_optimizados)

            # --- FRENTE: PRODUCCIÓN / CORTE (Bitácoras) ---
            piezas_producidas = 0.0
            if not df_bit_t.empty and not df_bit_l.empty:
                ids_taller = df_bit_t[df_bit_t['proyecto'].str.strip().str.lower() == nom_p.lower()]['id'].tolist()
                df_l_filtrado = df_bit_l[df_bit_l['bitacora_id'].isin(ids_taller)]
                piezas_producidas = pd.to_numeric(df_l_filtrado['cant_final_pl_pzs'].fillna(df_l_filtrado['cantidad']), errors='coerce').sum()
            
            av_prod = (piezas_producidas / muebles_totales * 100) if muebles_totales > 0 else 0.0
            pend_prod_tableros = max(0.0, tableros_totales * (1.0 - (av_prod / 100.0)))

            # --- FRENTE: INSTALACIÓN (Estatus Muebles) ---
            ml_instalado = 0.0
            muebles_instalados = 0
            if not df_p_prods.empty and not df_est.empty:
                df_est_p = df_est[df_est['producto_id'].isin(df_p_prods['id'])]
                df_est_p['listo'] = df_est_p['culminado'].astype(bool) | df_est_p['entregado'].astype(bool)
                ids_listos = df_est_p[df_est_p['listo'] == True]['producto_id'].tolist()
                
                df_listos = df_p_prods[df_p_prods['id'].isin(ids_listos)]
                ml_instalado = df_listos['ml'].sum()
                muebles_instalados = df_listos['ctd'].sum()

            av_inst = (ml_instalado / ml_totales * 100) if ml_totales > 0 else 0.0
            pend_inst_ml = max(0.0, ml_totales - ml_instalado)
            pend_inst_muebles = max(0, muebles_totales - muebles_instalados)

            # --- DISTRIBUCIÓN EN CURVAS DIARIAS ---
            f_inicio_calc = max(hoy, f_inicio)
            dias_restantes = calcular_dias_utiles_taller(f_inicio_calc, f_fin, feriados)

            if dias_restantes > 0:
                c_opt = pend_optim / dias_restantes
                c_prod = pend_prod_tableros / dias_restantes
                c_inst_ml = pend_inst_ml / dias_restantes
                c_inst_m = pend_inst_muebles / dias_restantes

                for d in rango_fechas_3m:
                    if f_inicio_calc <= d <= f_fin:
                        curva_optim[d] += c_opt
                        curva_corte[d] += c_prod
                        curva_inst_ml[d] += c_inst_ml
                        curva_inst_muebles[d] += c_inst_m

            # Agregar a matriz base
            lote_resumen.append({
                "id": id_p,
                "Proyecto": f"[{cod_p}] {nom_p}",
                "F. Inicio": f_inicio,
                "F. Fin": f_fin,
                "ML Totales": round(ml_totales, 1),
                "Tableros Req.": tableros_totales,
                "% Optimiz.": av_optim,
                "% Producc.": av_prod,
                "% Instalac.": av_inst
            })

        df_resumen = pd.DataFrame(lote_resumen)

    except Exception as e:
        st.error(f"Falla en el procesamiento analítico: {e}")
        return

    # =========================================================
    # RENDERIZADO DE PESTAÑAS (MATRIZ Y GRÁFICOS)
    # =========================================================
    
    with tab1:
        st.subheader("⚙️ Control Interactivo de Saldos y Plazos")
        if not df_resumen.empty:
            cambios = st.data_editor(
                df_resumen,
                column_config={
                    "id": None,
                    "Proyecto": st.column_config.TextColumn("Proyecto", disabled=True),
                    "F. Inicio": st.column_config.DateColumn("Inicio Ejecución", format="DD/MM/YYYY", required=True),
                    "F. Fin": st.column_config.DateColumn("Fin Ejecución", format="DD/MM/YYYY", required=True),
                    "ML Totales": st.column_config.NumberColumn("ML Totales", disabled=True),
                    "Tableros Req.": st.column_config.NumberColumn("Tableros", disabled=True),
                    "% Optimiz.": st.column_config.ProgressColumn("Optimización", format="%.1f%%", min_value=0, max_value=100),
                    "% Producc.": st.column_config.ProgressColumn("Producción", format="%.1f%%", min_value=0, max_value=100),
                    "% Instalac.": st.column_config.ProgressColumn("Instalación", format="%.1f%%", min_value=0, max_value=100)
                },
                hide_index=True, use_container_width=True, key="grid_fechas_dinamicas"
            )

            if st.button("💾 Guardar Fechas de Ejecución Ajustadas", type="primary", use_container_width=True):
                modificados = 0
                for index, row in cambios.iterrows():
                    id_mod = int(row['id'])
                    orig = df_resumen[df_resumen['id'] == id_mod].iloc[0]
                    
                    fi_str = row['F. Inicio'].isoformat() if isinstance(row['F. Inicio'], (date, datetime)) else str(row['F. Inicio'])
                    ff_str = row['F. Fin'].isoformat() if isinstance(row['F. Fin'], (date, datetime)) else str(row['F. Fin'])
                    
                    fi_orig = orig['F. Inicio'].isoformat() if isinstance(orig['F. Inicio'], (date, datetime)) else str(orig['F. Inicio'])
                    ff_orig = orig['F. Fin'].isoformat() if isinstance(orig['F. Fin'], (date, datetime)) else str(orig['F. Fin'])
                    
                    if fi_str != fi_orig or ff_str != ff_orig:
                        supabase.table("proyectos").update({"p_fab_i_ejecucion": fi_str, "p_fab_f_ejecucion": ff_str}).eq("id", id_mod).execute()
                        modificados += 1
                if modificados > 0:
                    st.success("Plazos reprogramados correctamente en la base de datos."); st.cache_data.clear(); st.rerun()
        else:
            st.info("No hay información de proyectos para proyectar.")

    with tab2:
        st.subheader("🪚 Presión Logística: Tableros a Producir por Día")
        if rango_fechas_3m:
            df_plot_corte = pd.DataFrame({"Fecha": [d.strftime("%d/%m") for d in curva_corte.keys()], "Tableros": list(curva_corte.values())})
            fig2 = px.line(df_plot_corte, x="Fecha", y="Tableros", title="Sumatoria Diaria de Carga en Seccionadora/Escuadradora", markers=True)
            fig2.update_traces(line_color="#1E3A8A", mode="lines+markers")
            fig2.update_layout(yaxis_title="Cantidad de Tableros")
            st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        st.subheader("📐 Tasa de Diseño y Declaración de Cortes")
        if rango_fechas_3m:
            df_plot_optim = pd.DataFrame({"Fecha": [d.strftime("%d/%m") for d in curva_optim.keys()], "Tableros": list(curva_optim.values())})
            fig3 = px.line(df_plot_optim, x="Fecha", y="Tableros", title="Curva de Demanda para el Equipo de Ingeniería", markers=True)
            fig3.update_traces(line_color="#E67E22", mode="lines+markers")
            fig3.update_layout(yaxis_title="Tableros a Optimizar")
            st.plotly_chart(fig3, use_container_width=True)

    with tab4:
        st.subheader("📦 Horizonte de Capacidad en Obra")
        if rango_fechas_3m:
            fechas_str = [d.strftime("%d/%m") for d in rango_fechas_3m]
            fig4 = go.Figure()
            
            fig4.add_trace(go.Scatter(
                x=fechas_str, y=list(curva_inst_muebles.values()),
                name="Muebles (und/Día)", mode="lines+markers", line=dict(color="#2ECC71")
            ))
            fig4.add_trace(go.Scatter(
                x=fechas_str, y=list(curva_inst_ml.values()),
                name="Metraje (ml/Día)", mode="lines+markers", line=dict(color="#9B59B6"),
                yaxis="y2"
            ))

            fig4.update_layout(
                title="Ritmo de Despliegue de Muebles y Metros Lineales Requerido",
                xaxis_title="Fechas Hábiles Taller (Horizonte 90 Días)",
                yaxis=dict(title="Muebles a Instalar", titlefont=dict(color="#2ECC71"), tickfont=dict(color="#2ECC71")),
                yaxis2=dict(title="Metros Lineales (ML)", titlefont=dict(color="#9B59B6"), tickfont=dict(color="#9B59B6"), overlaying="y", side="right"),
                legend=dict(x=0.01, y=0.99)
            )
            st.plotly_chart(fig4, use_container_width=True)
