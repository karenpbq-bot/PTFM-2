import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from base_datos import conectar, obtener_proyectos, obtener_gantt_real_data

def mostrar():
    st.header("📊 Cronograma Global de Ejecución")
    
    # 1. CONFIGURACIÓN DE VISTA EN SIDEBAR
    with st.sidebar:
        st.divider()
        st.subheader("Configuración de Visualización")
        solo_real = st.toggle("Ver solo ejecución real", value=False, help="Oculta las barras grises de planificación contractual")
    
    # 2. SELECCIÓN DE PROYECTOS
    with st.container(border=True):
        bus = st.text_input("🔍 Buscar por Proyecto o Cliente...", placeholder="Ej: Casa")
        df_p = obtener_proyectos(bus)
        dict_proy = {f"{r['proyecto_text']} — {r['cliente']}": r['id'] for _, r in df_p.iterrows()}
        
    if not dict_proy:
        st.info("No se encontraron proyectos activos."); return

    proyectos_sel = st.multiselect("Visualizar Proyectos:", 
                                    options=list(dict_proy.keys()), 
                                    default=list(dict_proy.keys())[:1])

    if proyectos_sel:
        data_final = []
        ORDEN_ETAPAS = ["Diseño", "Fabricación", "Traslado", "Instalación", "Entrega"]
        
        COLORES_REALES = {
            "Diseño": "#1ABC9C", "Fabricación": "#F39C12", 
            "Traslado": "#9B59B6", "Instalación": "#2E86C1", "Entrega": "#27AE60"
        }
        
        for p_nom in proyectos_sel:
            id_p = dict_proy[p_nom]
            p_data = pd.read_sql_query("SELECT * FROM proyectos WHERE id=?", conectar(), params=(id_p,)).iloc[0]
            
            # A. DATA PLANIFICADA (Solo si el switch está apagado)
            if not solo_real:
                map_cols = [
                    ("Diseño", 'p_dis_i', 'p_dis_f', "#EBEDEF"),
                    ("Fabricación", 'p_fab_i', 'p_fab_f', "#7F8C8D"),
                    ("Traslado", 'p_tra_i', 'p_tra_f', "#EBEDEF"),
                    ("Instalación", 'p_ins_i', 'p_ins_f', "#EBEDEF"),
                    ("Entrega", 'p_ent_i', 'p_ent_f', "#EBEDEF")
                ]
                for et, i_c, f_c, col in map_cols:
                    if p_data[i_c] and p_data[f_c]:
                        data_final.append(dict(Proyecto=p_nom, Etapa=et, Inicio=p_data[i_c], Fin=p_data[f_c], Color=col, Tipo="Planificado"))
            
            # B. DATA REAL
            df_r = obtener_gantt_real_data(id_p)
            if not df_r.empty:
                for _, row in df_r.iterrows():
                    fin_real = row['Fin']
                    if row['Inicio'] == row['Fin']:
                        fin_real = (datetime.strptime(row['Fin'], '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
                    
                    color_etapa = COLORES_REALES.get(row['Etapa'], "#2E86C1")
                    data_final.append(dict(Proyecto=p_nom, Etapa=row['Etapa'], Inicio=row['Inicio'], Fin=fin_real, Color=color_etapa, Tipo="Real"))

        if not data_final:
            st.warning("No hay datos para mostrar con los filtros seleccionados."); return

        # ORDENAMIENTO FÍSICO PARA EVITAR EL GANTT INVERTIDO
        df_fig = pd.DataFrame(data_final)
        df_fig['Etapa'] = pd.Categorical(df_fig['Etapa'], categories=ORDEN_ETAPAS, ordered=True)
        # Ordenamos descendente para que al aplicar 'reversed' en el eje Y, Diseño quede arriba
        df_fig = df_fig.sort_values(['Proyecto', 'Etapa'], ascending=[True, False])
        
        # 3. GENERACIÓN DEL GRÁFICO
        fig = px.timeline(
            df_fig, 
            x_start="Inicio", 
            x_end="Fin", 
            y="Etapa", 
            color="Color",
            facet_col="Proyecto", 
            facet_col_wrap=1,
            color_discrete_map="identity",
            category_orders={"Etapa": ORDEN_ETAPAS}
        )

        # 4. AJUSTES FINALES DE DISEÑO
        fig.update_yaxes(
            categoryorder="array",
            categoryarray=ORDEN_ETAPAS,
            autorange="reversed", # DISEÑO ARRIBA
            showgrid=True
        )

        fig.update_layout(
            barmode='group' if not solo_real else 'overlay',
            height=160 * len(proyectos_sel), 
            margin=dict(l=10, r=10, t=30, b=10),
            showlegend=False,
            bargap=0.1,
            font=dict(size=10)
        )

        fig.update_xaxes(dtick="W1", tickformat="%d/%b", showgrid=True, gridcolor='LightGray', griddash='dot')
        fig.add_vline(x=datetime.now().timestamp() * 1000, line_width=2, line_dash="dash", line_color="red")

        st.plotly_chart(fig, use_container_width=True)
        
        # Leyenda de Colores
        st.markdown("<p style='font-size: 11px; color: gray;'>🔴 Hoy | ⚪ Gris: Plan | 🎨 Colores: Real</p>", unsafe_allow_html=True)