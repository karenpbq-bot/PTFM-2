import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from base_datos import (
    conectar, 
    obtener_proyectos, 
    obtener_gantt_real_data, 
    obtener_productos_por_proyecto, 
    obtener_avance_por_hitos
)

ORDEN_ETAPAS = ["Diseño", "Fabricación", "Traslado", "Instalación", "Entrega"]

def obtener_color_semaforo(avance):
    avance = max(0, min(100, avance))
    if avance < 50:
        val = int(100 + (avance * 2.5))
        return f'rgb({val}, 40, 40)'
    elif avance <= 75:
        val = int(160 + (avance - 50) * 3)
        return f'rgb({val}, {val}, 0)'
    else:
        val = int(120 + (avance - 75) * 5)
        return f'rgb(30, {val}, 30)'

def mostrar():
    st.header("📊 Tablero de Control: Planificado vs. Real")
    supabase = conectar()
    
    with st.sidebar:
        st.divider()
        st.subheader("Opciones de Vista")
        solo_real = st.toggle("Ocultar Planificación (Celeste)", value=False)
    
    with st.container(border=True):
        bus = st.text_input("🔍 Localizador de Proyectos", placeholder="Código, Cliente o Nombre...", key="bus_ejec")
        df_p = obtener_proyectos(bus)
        
        if df_p.empty:
            st.info("No se encontraron coincidencias."); return
            
        dict_proy = {f"{r['proyecto_text']} — {r['cliente']}": r['id'] for _, r in df_p.iterrows()}
        
    proyectos_sel = st.multiselect("Proyectos a Auditar:", 
                                    options=list(dict_proy.keys()), 
                                    default=list(dict_proy.keys())[:1])

    if proyectos_sel:
        # 1. DEFINICIÓN DE PESTAÑAS
        tab_gantt, tab_metricas = st.tabs(["📊 Cronograma Gantt", "📈 Métricas"])
        
        data_final = []
        
        # --- PROCESAMIENTO DE DATOS PARA GANTT ---
        for p_nom in proyectos_sel:
            id_p = dict_proy[p_nom]
            res_p = supabase.table("proyectos").select("*").eq("id", id_p).execute()
            if not res_p.data: continue
            p_data = res_p.data[0]
            
            # A. Esqueleto
            for etapa_fija in ORDEN_ETAPAS:
                data_final.append(dict(Proyecto=p_nom, Etapa=etapa_fija, Inicio=datetime.now(), Fin=datetime.now(), Color="rgba(0,0,0,0)", Tipo="3_Esqueleto"))

            # B. Data Planificada
            if not solo_real:
                map_cols = [("Diseño", 'p_dis_i', 'p_dis_f'), ("Fabricación", 'p_fab_i', 'p_fab_f'), ("Traslado", 'p_tra_i', 'p_tra_f'), ("Instalación", 'p_ins_i', 'p_ins_f'), ("Entrega", 'p_ent_i', 'p_ent_f')]
                for et, i_c, f_c in map_cols:
                    if p_data.get(i_c) and p_data.get(f_c):
                        data_final.append(dict(Proyecto=p_nom, Etapa=et, Inicio=p_data[i_c], Fin=p_data[f_c], Color="#87CEEB", Tipo="1_Planificado"))
            
            # --- C. DATA REAL (CONVERSIÓN DE FECHAS SEGURA) ---
            p_codigo_act = p_data.get('codigo')
            res_av = supabase.table("avances_etapas").select("*").eq("codigo", p_codigo_act).execute()
            
            if res_av.data:
                row_av = res_av.data[0]
                # Mapeo exacto de columnas de tu base de datos
                mapeo_cols = {
                    "Diseño": "av_diseno", 
                    "Fabricación": "av_fabricacion", 
                    "Traslado": "av_traslado", 
                    "Instalación": "av_instalacion", 
                    "Entrega": "av_entrega"
                }
                
                # Extraemos las fechas base del proyecto en esta tabla
                f_i_raw = row_av.get('fecha_inicio_real')
                f_f_raw = row_av.get('fecha_fin_real')

                if f_i_raw and f_f_raw:
                    for etapa_nom, col_bd in mapeo_cols.items():
                        porcentaje_etapa = row_av.get(col_bd, 0)
                        
                        if porcentaje_etapa > 0:
                            color_etapa = obtener_color_semaforo(porcentaje_etapa)
                            
                            # Convertimos a fecha real de Python
                            dt_i = pd.to_datetime(f_i_raw)
                            dt_f = pd.to_datetime(f_f_raw)

                            # PARCHE DE VISIBILIDAD: Si es el mismo día, sumamos 23 horas
                            if dt_i.date() == dt_f.date():
                                dt_f = dt_i + pd.Timedelta(hours=23)

                            data_final.append(dict(
                                Proyecto=p_nom, 
                                Etapa=etapa_nom, 
                                Inicio=dt_i, 
                                Fin=dt_f, 
                                Color=color_etapa, 
                                Tipo="2_Real"
                            ))

       # --- RENDERIZADO PESTAÑA GANTT ---
        with tab_gantt:
            if data_final:
                # 1. Crear DataFrame y asegurar tipos de tiempo
                df_fig = pd.DataFrame(data_final)
                df_fig['Inicio'] = pd.to_datetime(df_fig['Inicio'], errors='coerce')
                df_fig['Fin'] = pd.to_datetime(df_fig['Fin'], errors='coerce')
                
                # Limpiar filas con fechas inválidas
                df_fig = df_fig.dropna(subset=['Inicio', 'Fin'])

                # 2. VISIBILIDAD CRÍTICA < 24H: 
                # Si el hito se marcó el mismo día, Plotly no dibuja nada (ancho 0). 
                # Forzamos un ancho mínimo de 23 horas para que la barra de color sea visible.
                mask_mismo_dia = (df_fig['Inicio'] == df_fig['Fin'])
                df_fig.loc[mask_mismo_dia, 'Fin'] = df_fig.loc[mask_mismo_dia, 'Fin'] + pd.Timedelta(hours=23)

                # 3. FILTRADO DE SEGURIDAD: 
                # Solo mostramos barras que tengan color (Planificado y Real). 
                # El esqueleto solo sirve para reservar espacio si no hubiera nada.
                df_visible = df_fig[df_fig['Color'] != "rgba(0,0,0,0)"].copy()

                if not df_visible.empty:
                    # 4. ORDEN FORZADO: Aplicar categorías para que el eje Y respete el ORDEN_ETAPAS
                    df_visible['Etapa'] = pd.Categorical(
                        df_visible['Etapa'], 
                        categories=ORDEN_ETAPAS, 
                        ordered=True
                    )
                    
                    # Ordenar físicamente el dataframe
                    df_visible = df_visible.sort_values(['Proyecto', 'Etapa'], ascending=[True, True])

                    # 5. CREACIÓN DEL GRÁFICO
                    fig = px.timeline(
                        df_visible, 
                        x_start="Inicio", 
                        x_end="Fin", 
                        y="Etapa", 
                        color="Color", 
                        facet_col="Proyecto", 
                        facet_col_wrap=1, 
                        color_discrete_map="identity",
                        category_orders={"Etapa": ORDEN_ETAPAS} # Refuerzo de orden Diseño -> Entrega
                    )

                    # 6. CONFIGURACIÓN VISUAL (ALTA DENSIDAD: BARRAS DELGADAS Y COMPACTAS)
                    
                    # A. Ajuste de los Ejes
                    fig.update_yaxes(
                        autorange="reversed", 
                        showgrid=True, 
                        type='category',
                        categoryorder='array',
                        categoryarray=ORDEN_ETAPAS,
                        tickfont=dict(size=10), # Letra un poco más pequeña para ahorrar espacio
                        gridcolor="#F0F0F0"
                    )
                    
                    # B. Sincronización del Eje X (Escala de tiempo)
                    f_plan_ref = df_visible[df_visible['Tipo'] == "1_Planificado"]['Inicio']
                    f_min_x = f_plan_ref.min() if not f_plan_ref.empty else pd.Timestamp.now()
                    fig.update_xaxes(
                        range=[f_min_x - timedelta(days=2), f_min_x + timedelta(days=90)], 
                        showgrid=True,
                        dtick="M1", 
                        tickformat="%b %Y",
                        matches='x',
                        tickfont=dict(size=10),
                        gridcolor="#F0F0F0"
                    )

                    # C. Control de Posición y Grosor Compacto
                    fig.update_layout(
                        barmode='group',     
                        bargap=0.5,          # Mayor espacio entre Etapas (Diseño vs Fab) para que se vean delgadas
                        bargroupgap=0.0,     # Pegadas entre sí (Planificado arriba / Real abajo)
                        # REDUCIMOS ALTURA: Pasamos de 350 a 220px por proyecto para ver más a la vez
                        height=220 * len(proyectos_sel), 
                        margin=dict(l=10, r=10, t=30, b=10), 
                        showlegend=False,
                        plot_bgcolor='white'
                    )

                    # D. Forzamos Anchos Delgados
                    # Reducimos width a 0.35 para que las barras sean finas y elegantes
                    fig.update_traces(
                        width=0.35, 
                        marker_line_width=0, 
                        opacity=0.9
                    )

                    # Línea de "HOY" (Indicador rojo)
                    fig.add_vline(
                        x=pd.Timestamp.now().timestamp() * 1000, 
                        line_width=1, 
                        line_dash="dot", 
                        line_color="red"
                    )

                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No hay avances registrados para mostrar en el cronograma real.")
            else:
                st.warning("Seleccione al menos un proyecto para visualizar el Gantt.")

        # --- RENDERIZADO PESTAÑA MÉTRICAS ---
        with tab_metricas:
            st.subheader("📊 Centro de Métricas y Reportes")
            
            # 1. FILTROS DE AUDITORÍA (Estilo Seguimiento)
            with st.expander("🔍 Filtros por Producto", expanded=True):
                c1, c2 = st.columns(2)
                # Obtenemos todos los productos de los proyectos seleccionados para llenar los filtros
                ids_proy_busqueda = [dict_proy[p] for p in proyectos_sel]
                
                # Consolidamos opciones de filtros de todos los proyectos seleccionados
                lista_ubicaciones = []
                lista_tipos = []
                for id_p_bus in ids_proy_busqueda:
                    df_temp = obtener_productos_por_proyecto(id_p_bus)
                    if not df_temp.empty:
                        lista_ubicaciones.extend(df_temp['ubicacion'].unique().tolist())
                        lista_tipos.extend(df_temp['tipo'].unique().tolist())
                
                opciones_u = sorted(list(set(lista_ubicaciones)))
                opciones_t = sorted(list(set(lista_tipos)))
                
                f_ub = c1.multiselect("Filtrar por Ubicación:", options=opciones_u, key="f_ub_metricas")
                f_ti = c2.multiselect("Filtrar por Tipo:", options=opciones_t, key="f_ti_metricas")

            # Estructura de almacenamiento para exportación
            reporte_etapas = []
            reporte_hitos = []

            # =========================================================
            # SECCIÓN A: RESUMEN POR ETAPAS (ESTANDARIZADO)
            # =========================================================
            st.markdown("#### 🏗️ Avances por Etapa")
            
            # Encabezados de la "Tabla"
            h_cols = st.columns([2, 0.8, 1, 1, 1, 1, 1])
            titulos = ["Proyecto", "Cant.", "Diseño", "Fabricación", "Traslado", "Instalación", "Entrega"]
            for i, t in enumerate(titulos): h_cols[i].markdown(f"**{t}**")
            st.divider()

            for p_nom in proyectos_sel:
                id_p_loop = dict_proy[p_nom]
                df_prods_loop = obtener_productos_por_proyecto(id_p_loop)
                
                # Aplicar filtros
                if f_ub: df_prods_loop = df_prods_loop[df_prods_loop['ubicacion'].isin(f_ub)]
                if f_ti: df_prods_loop = df_prods_loop[df_prods_loop['tipo'].isin(f_ti)]
                
                if df_prods_loop.empty: continue
                
                stats_hitos = obtener_avance_por_hitos(id_p_loop, df_productos_filtrados=df_prods_loop)
                
                # Cálculo de Etapas
                GRUPOS_AVANCE = {
                    "Diseño": stats_hitos.get("Diseñado", 0),
                    "Fabricación": stats_hitos.get("Fabricado", 0),
                    "Traslado": round((stats_hitos.get("Material en Obra", 0) + stats_hitos.get("Material en Ubicación", 0)) / 2, 1),
                    "Instalación": round((stats_hitos.get("Instalación de Estructura", 0) + stats_hitos.get("Instalación de Puertas o Frentes", 0)) / 2, 1),
                    "Entrega": round((stats_hitos.get("Revisión y Observaciones", 0) + stats_hitos.get("Entrega", 0)) / 2, 1)
                }

                # Fila visual
                r = st.columns([2, 0.8, 1, 1, 1, 1, 1])
                r[0].write(f"**{p_nom}**")
                r[1].write(f"{len(df_prods_loop)}")
                
                for i, (etapa, valor) in enumerate(GRUPOS_AVANCE.items()):
                    with r[i+2]:
                        color_s = obtener_color_semaforo(valor)
                        st.markdown(f"<p style='margin:0; font-size:13px; font-weight:bold; color:{color_s};'>{valor}%</p>", unsafe_allow_html=True)
                        st.progress(valor / 100)
                
                # Guardar para reporte CSV Etapas
                fila_etapa = {"Proyecto": p_nom, "Muebles": len(df_prods_loop)}
                fila_etapa.update({f"{k} %": v for k, v in GRUPOS_AVANCE.items()})
                reporte_etapas.append(fila_etapa)
                
                # Guardar para reporte CSV Hitos
                fila_hitos = {"Proyecto": p_nom, "Muebles": len(df_prods_loop)}
                fila_hitos.update({f"{k} %": v for k, v in stats_hitos.items()})
                reporte_hitos.append(fila_hitos)

            # =========================================================
            # SECCIÓN B: DETALLE POR HITO (MISMA ESTÉTICA)
            # =========================================================
            st.divider()
            st.markdown("#### 🔍 Detalle por Hito Individual")
            
            # Encabezados para Hitos (8 hitos)
            # Usamos columnas más pequeñas para que quepan
            h_cols_h = st.columns([1.5] + [0.8]*8)
            h_cols_h[0].markdown("**Proyecto**")
            for i, h in enumerate(stats_hitos.keys()):
                # Usamos iniciales o nombres cortos para el encabezado
                h_cols_h[i+1].markdown(f"<p style='font-size:10px;'><b>{h}</b></p>", unsafe_allow_html=True)

            for p_nom in proyectos_sel:
                # Buscamos en el reporte ya calculado para no repetir procesos
                data_p = next((item for item in reporte_hitos if item["Proyecto"] == p_nom), None)
                if not data_p: continue
                
                rh = st.columns([1.5] + [0.8]*8)
                rh[0].write(f"<p style='font-size:12px;'>{p_nom}</p>", unsafe_allow_html=True)
                
                for i, hito_nom in enumerate(stats_hitos.keys()):
                    val_h = data_p.get(f"{hito_nom} %", 0)
                    with rh[i+1]:
                        c_h = obtener_color_semaforo(val_h)
                        st.markdown(f"<p style='margin:0; font-size:11px; color:{c_h};'>{val_h}%</p>", unsafe_allow_html=True)
                        st.progress(val_h / 100)

            # =========================================================
            # SECCIÓN C: EXPORTACIÓN
            # =========================================================
            st.divider()
            st.write("#### 📤 Exportar Resultados Filtrados")
            if reporte_etapas:
                c_exp1, c_exp2, c_exp3 = st.columns(3)
                
                # 1. Exportar Etapas
                df_exp_etapas = pd.DataFrame(reporte_etapas)
                c_exp1.download_button(
                    "📥 Resumen Etapas (CSV)", 
                    df_exp_etapas.to_csv(index=False).encode('utf-8'), 
                    "avance_etapas_filtrado.csv", "text/csv", use_container_width=True
                )
                
                # 2. Exportar Hitos
                df_exp_hitos = pd.DataFrame(reporte_hitos)
                c_exp2.download_button(
                    "📥 Detalle Hitos (CSV)", 
                    df_exp_hitos.to_csv(index=False).encode('utf-8'), 
                    "avance_hitos_filtrado.csv", "text/csv", use_container_width=True
                )
                
                # 3. Auditoría 0/1 (Mantiene funcionalidad original)
                if c_exp3.button("📊 Auditoría Piezas (0/1)", use_container_width=True):
                    codigos_sel = [p.split(" — ")[0].replace("[", "").replace("]", "") for p in proyectos_sel]
                    res_aud = supabase.table("productos_avance_valor").select("*").in_("codigo_proyecto", codigos_sel).execute()
                    if res_aud.data:
                        df_aud = pd.DataFrame(res_aud.data)
                        st.download_button("📥 Descargar Excel Auditoría", df_aud.to_csv(index=False).encode('utf-8'), "auditoria_detallada.csv", "text/csv")
            else:
                st.info("No hay datos para exportar con los filtros actuales.")
