import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from base_datos import (
    conectar, 
    obtener_proyectos, 
    obtener_gantt_real_data, 
    obtener_productos_por_proyecto, # <-- FALTA ESTA
    obtener_avance_por_hitos        # <-- ASEGURATE QUE ESTÉ ESTA TAMBIÉN
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
            
            # C. Data Real (Lectura Horizontal)
            p_codigo_act = p_data.get('codigo')
            res_av = supabase.table("avances_etapas").select("*").eq("codigo", p_codigo_act).execute()
            
            if res_av.data:
                row_av = res_av.data[0]
                mapeo_cols = {"Diseño": "av_diseno", "Fabricación": "av_fabricacion", "Traslado": "av_traslado", "Instalación": "av_instalacion", "Entrega": "av_entrega"}
                
                for etapa_nom, col_bd in mapeo_cols.items():
                    porcentaje_etapa = row_av.get(col_bd, 0)
                    if porcentaje_etapa > 0:
                        color_etapa = obtener_color_semaforo(porcentaje_etapa)
                        f_ini_r = row_av.get('fecha_inicio_real') or p_data.get(f'p_{etapa_nom[:3].lower()}_i')
                        f_fin_r = row_av.get('fecha_fin_real') or p_data.get(f'p_{etapa_nom[:3].lower()}_f')

                        data_final.append(dict(Proyecto=p_nom, Etapa=etapa_nom, Inicio=f_ini_r, Fin=f_fin_r, Color=color_etapa, Tipo="2_Real"))

        # --- RENDERIZADO PESTAÑA GANTT ---
        with tab_gantt:
            if data_final:
                df_fig = pd.DataFrame(data_final)
                df_fig['Inicio'] = pd.to_datetime(df_fig['Inicio'], errors='coerce')
                df_fig['Fin'] = pd.to_datetime(df_fig['Fin'], errors='coerce')
                df_fig = df_fig.dropna(subset=['Inicio', 'Fin'])
                df_fig['Etapa'] = pd.Categorical(df_fig['Etapa'], categories=ORDEN_ETAPAS, ordered=True)
                df_fig = df_fig.sort_values(['Proyecto', 'Etapa', 'Tipo'], ascending=[True, True, True])
                
                fig = px.timeline(df_fig, x_start="Inicio", x_end="Fin", y="Etapa", color="Color", facet_col="Proyecto", facet_col_wrap=1, color_discrete_map="identity", category_orders={"Etapa": ORDEN_ETAPAS})
                
                f_plan_ref = df_fig[df_fig['Tipo'] == "1_Planificado"]['Inicio']
                f_min_x = f_plan_ref.min() if not f_plan_ref.empty else pd.Timestamp.now()
                fig.update_xaxes(range=[f_min_x - timedelta(days=2), f_min_x + timedelta(days=120)], dtick="M1", tickformat="%b %Y", showgrid=True)
                fig.update_yaxes(autorange="reversed", showgrid=True)
                fig.update_layout(barmode='group', bargap=0.5, height=250 * len(proyectos_sel), margin=dict(l=10, r=10, t=50, b=10), showlegend=False)
                fig.update_traces(marker_line_width=0, opacity=0.9)
                fig.add_vline(x=pd.Timestamp.now().timestamp() * 1000, line_width=1.5, line_dash="dash", line_color="red")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("No hay datos suficientes para generar el Gantt.")

        # --- RENDERIZADO PESTAÑA MÉTRICAS ---
        with tab_metricas:
            st.subheader("📊 Centro de Métricas y Reportes")
            
            # --- SECCIÓN A: FILTRO DINÁMICO ---
            with st.expander("🔍 Filtros de Auditoría Detallada", expanded=False):
                c1, c2 = st.columns(2)
                # Obtenemos productos del primer proyecto seleccionado para llenar los filtros
                id_p_ref = dict_proy[proyectos_sel[0]]
                df_prods_ref = obtener_productos_por_proyecto(id_p_ref)
                
                filtro_ub = c1.multiselect("Filtrar por Ubicación:", options=df_prods_ref['ubicacion'].unique() if not df_prods_ref.empty else [])
                filtro_ti = c2.multiselect("Filtrar por Tipo:", options=df_prods_ref['tipo'].unique() if not df_prods_ref.empty else [])

            # --- SECCIÓN B: REPORTE MATRICIAL DINÁMICO ---
            reporte_data = []
            for p_nom in proyectos_sel:
                id_p = dict_proy[p_nom]
                df_prods = obtener_productos_por_proyecto(id_p)
                
                # Aplicar filtros si existen
                if filtro_ub: df_prods = df_prods[df_prods['ubicacion'].isin(filtro_ub)]
                if filtro_ti: df_prods = df_prods[df_prods['tipo'].isin(filtro_ti)]
                
                if df_prods.empty: continue
                
                # Calculamos avance filtrado usando la función de base_datos
                avances_hitos = obtener_avance_por_hitos(id_p, df_productos_filtrados=df_prods)
                
                # Mapeo a las 5 etapas
                GRUPOS = {
                    "Diseño": ["Diseñado"],
                    "Fabricación": ["Fabricado"],
                    "Traslado": ["Material en Obra", "Material en Ubicación"],
                    "Instalación": ["Instalación de Estructura", "Instalación de Puertas o Frentes"],
                    "Entrega": ["Revisión y Observaciones", "Entrega"]
                }
                
                fila = {"Proyecto": p_nom, "Productos": len(df_prods)}
                for etapa, hitos in GRUPOS.items():
                    porc_etapa = sum([avances_hitos.get(h, 0) for h in hitos]) / len(hitos)
                    fila[f"{etapa} %"] = round(porc_etapa, 1)
                
                reporte_data.append(fila)

            if reporte_data:
                df_matriz = pd.DataFrame(reporte_data)
                st.dataframe(df_matriz, use_container_width=True, hide_index=True)
                
                # Botones de exportación... (tu código anterior)
                
                # --- SECCIÓN C: BOTONES DE EXPORTACIÓN ---
                st.write("---")
                col1, col2 = st.columns(2)
                
                # Reporte 1: Porcentajes
                csv_pct = df_matriz.to_csv(index=False).encode('utf-8')
                col1.download_button("📥 Exportar Reporte de Avances (%)", csv_pct, "reporte_avances_pct.csv", "text/csv")
                
                # Reporte 2: Detalle por Producto y Hito (Auditoría total)
                if st.button("📊 Generar Reporte Detallado por Producto"):
                    res_auditoria = supabase.table("productos_avance_valor").select("*").in_("codigo_proyecto", [p.split(" — ")[0] for p in proyectos_sel]).execute()
                    if res_auditoria.data:
                        df_aud = pd.DataFrame(res_auditoria.data)
                        st.download_button("📥 Descargar Auditoría (Logrados 0/1)", df_aud.to_csv(index=False).encode('utf-8'), "auditoria_muebles.csv", "text/csv")
            else:
                st.info("Ajuste los filtros para ver datos.")

            st.divider()
            
            # 2. DETALLE INDIVIDUAL (Bucle para ver el detalle de los proyectos seleccionados)
            st.write("#### 🔍 Detalle por Hito Realizado")
            from base_datos import obtener_avance_por_hitos
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
