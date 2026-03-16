import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from base_datos import conectar, obtener_proyectos, obtener_datos_gantt_procesados

# --- 1. LÓGICA DE COLOR GERENCIAL (RECUPERADA) ---
def obtener_color_estricto(avance):
    """Semáforo matizado: Rojo (<50), Amarillo (50-75), Verde (>75)."""
    if avance < 50:
        return f'rgb({int(150 + avance)}, 50, 50)' # Rojo
    elif avance <= 75:
        return f'rgb({int(200 + (avance-50)*2)}, {int(180 + (avance-50)*2)}, 0)' # Amarillo
    else:
        return f'rgb(34, {int(100 + (avance-75)*4)}, 34)' # Verde

def mostrar():
    st.title("📊 Seguimiento de Contratos (Gantt Plan vs Real)")
    
    # --- 2. FILTROS DE SELECCIÓN ---
    with st.sidebar:
        st.subheader("🔍 Localizador de Proyectos")
        bus_keyword = st.text_input("Buscador Universal", placeholder="Código, Cliente, Nombre...")
        df_p = obtener_proyectos(bus_keyword)
        
        if df_p.empty:
            st.warning("No se encontraron coincidencias."); return

        proyectos_selec = st.multiselect("Proyectos a visualizar:", df_p['proyecto_display'].tolist())
        
    if not proyectos_selec:
        st.info("💡 Seleccione proyectos en el buscador lateral para ver el cronograma."); return

    # --- 3. CONFIGURACIÓN DE LA MATRIZ GANTT ---
    ETAPAS = ["Diseño", "Fabricación", "Traslado", "Instalación", "Entrega"]
    ETAPAS_REVERSA = ETAPAS[::-1] # Inversión para que Diseño quede arriba
    
    fig = go.Figure()
    supabase = conectar()

    for i, p_display in enumerate(proyectos_selec):
        p_row = df_p[df_p['proyecto_display'] == p_display].iloc[0]
        id_p = p_row['id']
        
        # Datos Planificados (Tabla Proyectos)
        res_p = supabase.table("proyectos").select("*").eq("id", id_p).execute()
        if not res_p.data: continue
        p_data = res_p.data[0]

        # Datos Ejecutados (Cálculo de Hitos Ponderados en base_datos.py)
        datos_reales = obtener_datos_gantt_procesados(id_p)
        dict_reales = {d['Etapa']: d for d in datos_reales}

        for y_idx, etapa in enumerate(ETAPAS_REVERSA):
            # Posicionamiento absoluto para forzar los dos carriles (Arriba Plan / Abajo Real)
            pos_y = (i * (len(ETAPAS) * 3)) + (y_idx * 2)

            # --- BARRA PLANIFICADA (ARRIBA - GRIS) ---
            map_fechas = {
                "Diseño": ("p_dis_i", "p_dis_f"), "Fabricación": ("p_fab_i", "p_fab_f"),
                "Traslado": ("p_tra_i", "p_tra_f"), "Instalación": ("p_ins_i", "p_ins_f"),
                "Entrega": ("p_ent_i", "p_ent_f")
            }
            f_i, f_f = map_fechas[etapa]
            
            if p_data.get(f_i) and p_data.get(f_f):
                col_plan = "#4F4F4F" if etapa == "Fabricación" else "#D3D3D3"
                fig.add_trace(go.Bar(
                    base=[p_data[f_i]],
                    x=[(pd.to_datetime(p_data[f_f]) - pd.to_datetime(p_data[f_i])).days],
                    y=[pos_y + 0.4],
                    orientation='h',
                    marker_color=col_plan,
                    name="Planificado",
                    hoverinfo="text",
                    text=f"PLAN: {etapa}",
                    width=0.4
                ))

            # --- BARRA EJECUTADA (ABAJO - COLOR) ---
            if etapa in dict_reales:
                dr = dict_reales[etapa]
                avance = round(dr['Avance'], 1)
                color_real = obtener_color_estricto(avance)
                
                fig.add_trace(go.Bar(
                    base=[dr['Inicio'].strftime('%Y-%m-%d')],
                    x=[(dr['Fin'] - dr['Inicio']).days + 1],
                    y=[pos_y - 0.4],
                    orientation='h',
                    marker_color=color_real,
                    text=f"{avance}%", 
                    textposition="inside",
                    textfont=dict(color="white", size=10),
                    name="Real",
                    hoverinfo="text",
                    hovertext=f"REAL: {etapa}<br>Avance: {avance}%",
                    width=0.6
                ))

    # --- 4. FORMATO FINAL DEL GRÁFICO (REGLAS DE VISUALIZACIÓN) ---
    fig.update_layout(
        barmode='overlay',
        showlegend=False,
        plot_bgcolor="white",
        height=300 + (len(proyectos_selec) * 400),
        xaxis=dict(
            type='date',
            tickformat='%b %Y', # Escala mensual
            dtick="M1",
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

    # Nombres de proyecto en el eje Y
    for i, p_display in enumerate(proyectos_selec):
        fig.add_annotation(
            x=-0.02, y=(i * (len(ETAPAS) * 3)) + (len(ETAPAS) - 1),
            xref="paper", yref="y",
            text=f"<b>PROYECTO: {p_display.upper()}</b>",
            showarrow=False, xanchor="right", font=dict(size=14, color="#002147")
        )

    st.plotly_chart(fig, use_container_width=True)
