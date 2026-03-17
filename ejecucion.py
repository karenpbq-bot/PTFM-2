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
                mapeo_cols = {
                    "Diseño": "av_diseno", 
                    "Fabricación": "av_fabricacion", 
                    "Traslado": "av_traslado", 
                    "Instalación": "av_instalacion", 
                    "Entrega": "av_entrega"
                }
                
                f_i_raw = row_av.get('fecha_inicio_real')
                f_f_raw = row_av.get('fecha_fin_real')

                if f_i_raw and f_f_raw:
                    for etapa_nom, col_bd in mapeo_cols.items():
                        porcentaje_etapa = row_av.get(col_bd, 0)
                        
                        if porcentaje_etapa > 0:
                            color_etapa = obtener_color_semaforo(porcentaje_etapa)
                            dt_i = pd.to_datetime(f_i_raw)
                            dt_f = pd.to_datetime(f_f_raw)

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
                df_fig = pd.DataFrame(data_final)
                df_fig['Inicio'] = pd.to_datetime(df_fig['Inicio'], errors='coerce')
                df_fig['Fin'] = pd.to_datetime(df_fig['Fin'], errors='coerce')
                df_fig = df_fig.dropna(subset=['Inicio', 'Fin'])

                mask_mismo_dia = (df_fig['Inicio'] == df_fig['Fin'])
                df_fig.loc[mask_mismo_dia, 'Fin'] = df_fig.loc[mask_mismo_dia, 'Fin'] + pd.Timedelta(hours=23)

                df_visible = df_fig[df_fig['Color'] != "rgba(0,0,0,0)"].copy()

                if not df_visible.empty:
                    df_visible['Etapa'] = pd.Categorical(
                        df_visible['Etapa'], 
                        categories=ORDEN_ETAPAS, 
                        ordered=True
                    )
                    
                    df_visible = df_visible.sort_values(['Proyecto', 'Etapa'], ascending=[True, True])

                    fig = px.timeline(
                        df_visible, 
                        x_start="Inicio", 
                        x_end="Fin", 
                        y="Etapa", 
                        color="Color", 
                        facet_col="Proyecto", 
                        facet_col_wrap=1, 
                        color_discrete_map="identity",
                        category_orders={"Etapa": ORDEN_ETAPAS}
                    )

                    fig.update_yaxes(autorange="reversed", showgrid=True)
                    
                    f_plan_ref = df_visible[df_visible['Tipo'] == "1_Planificado"]['Inicio']
                    f_min_x = f_plan_ref.min() if not f_plan_ref.empty else pd.Timestamp.now()
                    fig.update_xaxes(
                        range=[f_min_x - timedelta(days=2), f_min_x + timedelta(days=90)], 
                        showgrid=True,
                        dtick="M1", 
                        tickformat="%b %Y"
                    )

                    # --- CAMBIOS SOLICITADOS: ALTURA FIJA Y MENOS ESPACIO ---
                    fig.update_layout(
                        barmode='group', 
                        bargap=0.2, # Reducción de espacio entre barras (más juntas)
                        height=200 * len(proyectos_sel), # Altura aplanada fija por proyecto
                        margin=dict(l=10, r=10, t=50, b=10), 
                        showlegend=False
                    )

                    fig.update_traces(marker_line_width=0, opacity=0.9)

                    fig.add_vline(
                        x=pd.Timestamp.now().timestamp() * 1000, 
                        line_width=1.5, 
                        line_dash="dash", 
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
            
            with st.expander("🔍 Filtros de Auditoría Detallada", expanded=False):
                c1, c2 = st.columns(2)
                id_p_ini = dict_proy[proyectos_sel[0]]
                df_prods_ini = obtener_productos_por_proyecto(id_p_ini)
                
                opciones_u = sorted(df_prods_ini['ubicacion'].unique().tolist()) if not df_prods_ini.empty else []
                opciones_t = sorted(df_prods_ini['tipo'].unique().tolist()) if not df_prods_ini.empty else []
                
                f_ub = c1.multiselect("Filtrar por Ubicación:", options=opciones_u)
                f_ti = c2.multiselect("Filtrar por Tipo:", options=opciones_t)

            reporte_final = []
            for p_nom in proyectos_sel:
                id_p_loop = dict_proy[p_nom]
                df_prods_loop = obtener_productos_por_proyecto(id_p_loop)
                
                if f_ub: df_prods_loop = df_prods_loop[df_prods_loop['ubicacion'].isin(f_ub)]
                if f_ti: df_prods_loop = df_prods_loop[df_prods_loop['tipo'].isin(f_ti)]
                
                if df_prods_loop.empty: continue
                
                stats_hitos = obtener_avance_por_hitos(id_p_loop, df_productos_filtrados=df_prods_loop)
                
                GRUPOS_GANTT = {
                    "Diseño": ["Diseñado"], "Fabricación": ["Fabricado"],
                    "Traslado": ["Material en Obra", "Material en Ubicación"],
                    "Instalación": ["Instalación de Estructura", "Instalación de Puertas o Frentes"],
                    "Entrega": ["Revisión y Observaciones", "Entrega"]
                }
                
                fila = {"Proyecto": p_nom, "Muebles": len(df_prods_loop)}
                for etapa, lista_h in GRUPOS_GANTT.items():
                    val_etapa = sum([stats_hitos.get(h, 0) for h in lista_h]) / len(lista_h)
                    fila[f"{etapa} %"] = round(val_etapa, 1)
                reporte_final.append(fila)

            if reporte_final:
                df_matriz_final = pd.DataFrame(reporte_final)
                st.dataframe(df_matriz_final, use_container_width=True, hide_index=True)
                
                st.divider()
                col1, col2 = st.columns(2)
                
                csv_pct = df_matriz_final.to_csv(index=False).encode('utf-8')
                col1.download_button("📥 Exportar Resumen (%)", csv_pct, "avance_proyectos.csv", "text/csv")
                
                if col2.button("📊 Generar Auditoría 0/1 (Detallada)"):
                    codigos_sel = [p.split(" — ")[0].replace("[", "").replace("]", "") for p in proyectos_sel]
                    res_aud = supabase.table("productos_avance_valor").select("*").in_("codigo_proyecto", codigos_sel).execute()
                    if res_aud.data:
                        df_aud = pd.DataFrame(res_aud.data)
                        st.download_button("📥 Descargar Excel de Auditoría", df_aud.to_csv(index=False).encode('utf-8'), "auditoria_piezas.csv", "text/csv")
            else:
                st.info("No hay datos para mostrar con los filtros seleccionados.")
            st.divider()
            
            st.write("#### 🔍 Detalle por Hito Realizado")
            for p_nom in proyectos_sel:
                id_p_int = dict_proy[p_nom]
                st.markdown(f"**Proyecto: {p_nom}**")
                avances = obtener_avance_por_hitos(id_p_int)
                if avances:
                    m = st.columns(4)
                    for idx, (h, v) in enumerate(avances.items()):
                        with m[idx % 4]:
                            st.metric(h, f"{v}%")
                            st.progress(v / 100)
                st.divider()
