import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from base_datos import conectar, obtener_proyectos, obtener_datos_gantt_procesados

def calcular_color_semaforo(avance):
    """Devuelve el color matizado según el avance (Rojo-Amarillo-Verde)."""
    if avance < 50:
        # Rojo: De oscuro (poco avance) a más claro
        intensidad = int(100 + (avance * 2)) 
        return f'rgb({intensidad}, 0, 0)'
    elif avance <= 75:
        # Amarillo: De ocre a brillante
        val = int((avance - 50) * 10)
        return f'rgb({200+val}, {200+val}, 0)'
    else:
        # Verde: De lima a bosque (oscuro al llegar al 100)
        intensidad = int(255 - ((avance - 75) * 4))
        return f'rgb(0, {intensidad}, 0)'

def mostrar():
    st.title("📊 Gantt Comparativo: Planificado vs. Ejecutado")
    
    # --- 1. BUSCADOR Y SELECCIÓN ---
    with st.sidebar:
        st.subheader("Filtros de Visualización")
        bus_keyword = st.text_input("🔍 Buscar Proyecto (Código, Cliente, Nombre)")
        df_p = obtener_proyectos(bus_keyword)
        
        if df_p.empty:
            st.warning("No hay proyectos que coincidan.")
            return

        proyectos_nombres = df_p['proyecto_display'].tolist()
        seleccionados = st.multiselect("Proyectos a comparar:", proyectos_nombres)

    if not seleccionados:
        st.info("Seleccione uno o más proyectos en la barra lateral para visualizar el Gantt.")
        return

    # --- 2. PROCESAMIENTO DE DATOS PARA EL GRÁFICO ---
    df_gantt_final = []
    ETAPAS_ORDEN = ["Diseño", "Fabricación", "Traslado", "Instalación", "Entrega"]
    
    supabase = conectar()

    for p_display in seleccionados:
        # Obtener ID y datos del proyecto
        p_row = df_p[df_p['proyecto_display'] == p_display].iloc[0]
        id_p = p_row['id']
        res_p = supabase.table("proyectos").select("*").eq("id", id_p).execute()
        p_data = res_p.data[0]

        # A. Datos Planificados (Gris Claro / Gris Oscuro)
        map_plan = [
            ("Diseño", "p_dis_i", "p_dis_f", "#D3D3D3"), # Gris Claro
            ("Fabricación", "p_fab_i", "p_fab_f", "#4F4F4F"), # Gris Oscuro
            ("Traslado", "p_tra_i", "p_tra_f", "#D3D3D3"),
            ("Instalación", "p_ins_i", "p_ins_f", "#D3D3D3"),
            ("Entrega", "p_ent_i", "p_ent_f", "#D3D3D3")
        ]

        for et, ini_c, fin_c, color in map_plan:
            if p_data.get(ini_c) and p_data.get(fin_c):
                df_gantt_final.append({
                    "Proyecto": p_display,
                    "Etapa": et,
                    "Inicio": p_data[ini_c],
                    "Fin": p_data[fin_c],
                    "Color": color,
                    "Tipo": "1. Planificado",
                    "Avance": 100,
                    "Label": f"{et} (Plan)"
                })

        # B. Datos Ejecutados (Basados en Hitos Reales)
        datos_reales = obtener_datos_gantt_procesados(id_p)
        for dr in datos_reales:
            color_sem = calcular_color_semaforo(dr['Avance'])
            df_gantt_final.append({
                "Proyecto": p_display,
                "Etapa": dr['Etapa'],
                "Inicio": dr['Inicio'].strftime('%Y-%m-%d'),
                "Fin": dr['Fin'].strftime('%Y-%m-%d'),
                "Color": color_sem,
                "Tipo": "2. Ejecutado",
                "Avance": round(dr['Avance'], 1),
                "Label": f"{dr['Etapa']} (Real: {round(dr['Avance'], 1)}%)"
            })

    if not df_gantt_final:
        st.warning("No hay fechas suficientes para generar el gráfico.")
        return

    # --- 3. CONSTRUCCIÓN DEL GRÁFICO ---
    df_plot = pd.DataFrame(df_gantt_final)
    
    # Forzar orden de etapas y proyectos para que no se mezclen
    df_plot['Etapa'] = pd.Categorical(df_plot['Etapa'], categories=ETAPAS_ORDEN, ordered=True)
    df_plot = df_plot.sort_values(by=["Proyecto", "Etapa", "Tipo"])

    fig = px.timeline(
        df_plot, 
        x_start="Inicio", 
        x_end="Fin", 
        y="Etapa", 
        color="Color",
        facet_row="Proyecto",
        color_discrete_map="identity",
        hover_data={"Avance": True, "Inicio": True, "Fin": True, "Color": False, "Tipo": False},
        category_orders={"Etapa": ETAPAS_ORDEN}
    )

    # Ajustes de diseño solicitados
    fig.update_yaxes(autorange="reversed") 
    fig.update_layout(
        height=300 * len(seleccionados),
        showlegend=False,
        title_text="Cronograma Comparativo por Proyecto",
        margin=dict(t=50, l=10, r=10, b=50)
    )

    # Líneas punteadas para quincenas/meses
    fig.update_xaxes(
        dtick="M1", # Marca principal cada mes
        minor=dict(dtick=1000*60*60*24*14, showgrid=True, gridcolor="LightGrey", gridwidth=1, griddash="dot"), # Quincenas
        showgrid=True, gridcolor="Silver", gridwidth=1, griddash="dash"
    )

    # Ajuste de las etiquetas de facet_row para que sean legibles
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))

    st.plotly_chart(fig, use_container_width=True)
