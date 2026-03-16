import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from base_datos import conectar, obtener_proyectos, obtener_datos_gantt_procesados

def obtener_color_estricto(avance):
    """Semáforo gerencial matizado."""
    if avance < 50:
        # Rojo: Intensidad según gravedad
        return f'rgb({int(180 + avance)}, 60, 60)'
    elif avance <= 75:
        # Amarillo: Ocre a brillante
        return f'rgb({int(200 + (avance-50)*2)}, {int(180 + (avance-50)*2)}, 0)'
    else:
        # Verde: Lima a Bosque
        return f'rgb(40, {int(120 + (avance-75)*4)}, 40)'

def mostrar():
    st.title("📈 Tablero de Control de Proyectos (Gantt)")
    
    # --- 1. FILTROS ESTRATÉGICOS ---
    with st.sidebar:
        st.subheader("🔍 Localizador de Proyectos")
        bus_keyword = st.text_input("Buscador (Código, Cliente, Nombre)")
        df_p = obtener_proyectos(bus_keyword)
        
        if df_p.empty:
            st.warning("No se encontraron proyectos."); return

        proyectos_selec = st.multiselect("Seleccione Proyectos para Comparar", df_p['proyecto_display'].tolist())
        
        st.divider()
        modo_vista = st.radio("Modo de Vista", ["Comparativo (Plan vs Real)", "Solo Avance Real (Ejecutado)"])

    if not proyectos_selec:
        st.info("Para comenzar, seleccione uno o más proyectos del buscador lateral."); return

    # --- 2. CONFIGURACIÓN VISUAL ---
    # Orden cronológico de arriba hacia abajo
    ETAPAS = ["Diseño", "Fabricación", "Traslado", "Instalación", "Entrega"]
    ETAPAS_REVERSA = ETAPAS[::-1] # Para el eje Y de Plotly
    
    fig = go.Figure()
    supabase = conectar()

    for i, p_display in enumerate(proyectos_selec):
        p_row = df_p[df_p['proyecto_display'] == p_display].iloc[0]
        id_p = p_row['id']
        
        # Traer fechas planificadas de la tabla proyectos
        res_p = supabase.table("proyectos").select("*").eq("id", id_p).execute()
        if not res_p.data: continue
        p_data = res_p.data[0]

        # Traer avance real procesado desde base_datos (Hitos ponderados)
        datos_reales = obtener_datos_gantt_procesados(id_p)
        dict_reales = {d['Etapa']: d for d in datos_reales}

        for y_idx, etapa in enumerate(ETAPAS_REVERSA):
            # Calculamos una posición única en el eje Y para cada barra de cada proyecto
            # Esto evita que los proyectos se encimen
            pos_y = (i * (len(ETAPAS) * 3)) + (y_idx * 2)

            # --- A. BARRA PLANIFICADA (BASE GRIS) ---
            map_fechas = {
                "Diseño": ("p_dis_i", "p_dis_f"), "Fabricación": ("p_fab_i", "p_fab_f"),
                "Traslado": ("p_tra_i", "p_tra_f"), "Instalación": ("p_ins_i", "p_ins_f"),
                "Entrega": ("p_ent_i", "p_ent_f")
            }
            
            f_i, f_f = map_fechas[etapa]
            if p_data.get(f_i) and p_data.get(f_f) and modo_vista == "Comparativo (Plan vs Real)":
                color_plan = "#4F4F4F" if etapa == "Fabricación" else "#D3D3D3"
                fig.add_trace(go.Bar(
                    base=[p_data[f_i]],
                    x=[(pd.to_datetime(p_data[f_f]) - pd.to_datetime(p_data[f_i])).days],
                    y=[pos_y + 0.4],
                    orientation='h',
                    marker_color=color_plan,
                    name="Planificado",
                    hoverinfo="skip", # Menos ruido, solo visual
                    width=0.4
                ))

            # --- B. BARRA EJECUTADA (AVANCE REAL) ---
            if etapa in dict_reales:
                dr = dict_reales[etapa]
                avance = round(dr['Avance'], 1)
                color_real = obtener_color_estricto(avance)
                
                fig.add_trace(go.Bar(
                    base=[dr['Inicio'].strftime('%Y-%m-%d')],
                    x=[(dr['Fin'] - dr['Inicio']).days + 1],
                    y=[pos_y - 0.4] if modo_vista == "Comparativo (Plan vs Real)" else [pos_y],
                    orientation='h',
                    marker_color=color_real,
                    text=f"{avance}%", # SOLO EL % SOLICITADO
                    textposition="inside",
                    insidetextanchor="middle",
                    textfont=dict(color="white", size=11),
                    name="Real",
                    hoverinfo="text",
                    hovertext=f"Proyecto: {p_display}<br>Etapa: {etapa}<br>Inicio: {dr['Inicio'].date()}<br>Fin: {dr['Fin'].date()}",
                    width=0.6 if modo_vista == "Comparativo (Plan vs Real)" else 1.2
                ))

    # --- 3. ESTILIZACIÓN DEL GRÁFICO (REGLAS GERENCIALES) ---
    fig.update_layout(
        barmode='overlay',
        showlegend=False,
        plot_bgcolor="white",
        height=200 + (len(proyectos_selec) * 400),
        xaxis=dict(
            type='date',
            tickformat='%d %b', # Formato limpio: 15 Mar
            dtick="M1", # Divisiones mensuales
            gridcolor="#EEEEEE",
            minor=dict(dtick=1000*60*60*24*14, showgrid=True, gridcolor="#F5F5F5", griddash="dot") # Quincenas
        ),
        yaxis=dict(
            tickmode='array',
            tickvals=[(i * (len(ETAPAS) * 3)) + (y * 2) for i in range(len(proyectos_selec)) for y in range(len(ETAPAS))],
            ticktext=ETAPAS_REVERSA * len(proyectos_selec),
            fixedrange=True
        ),
        margin=dict(l=200, r=50, t=50, b=50)
    )

    # Títulos de Proyecto en el lateral izquierdo
    for i, p_display in enumerate(proyectos_selec):
        fig.add_annotation(
            x=-0.01, y=(i * (len(ETAPAS) * 3)) + (len(ETAPAS) - 1),
            xref="paper", yref="y",
            text=f"<b>PROYECTO: {p_display.upper()}</b>",
            showarrow=False, xanchor="right", font=dict(size=14, color="#002147")
        )

    st.plotly_chart(fig, use_container_width=True)
