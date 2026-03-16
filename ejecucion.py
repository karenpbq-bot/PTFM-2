import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from base_datos import conectar, obtener_proyectos, obtener_datos_gantt_procesados

def obtener_color_gerencial(avance):
    """Semáforo matizado: Rojo (<50), Amarillo (50-75), Verde (>75)."""
    if avance < 50:
        return f'rgb({int(160 + avance)}, 60, 60)'
    elif avance <= 75:
        return f'rgb({int(210 + (avance-50)*1.5)}, {int(190 + (avance-50)*1.5)}, 0)'
    else:
        return f'rgb(34, {int(110 + (avance-75)*4)}, 34)'

def mostrar():
    st.title("📊 Tablero de Control: Planificado vs. Ejecutado")
    
    # --- 1. FILTROS Y BÚSQUEDA ---
    with st.sidebar:
        st.subheader("🔍 Localizador de Proyectos")
        bus = st.text_input("Buscador Universal", placeholder="Código, Cliente, Nombre...")
        df_p = obtener_proyectos(bus)
        
        if df_p.empty:
            st.warning("No se encontraron coincidencias."); return

        proyectos_selec = st.multiselect("Proyectos a Auditar:", df_p['proyecto_display'].tolist())

    if not proyectos_selec:
        st.info("💡 Seleccione proyectos en el buscador para visualizar el cronograma."); return

    # --- 2. CONFIGURACIÓN DEL GRÁFICO ---
    ETAPAS = ["Diseño", "Fabricación", "Traslado", "Instalación", "Entrega"]
    # Invertimos para que Diseño aparezca al principio (arriba)
    ETAPAS_INV = ETAPAS[::-1] 
    
    fig = go.Figure()
    supabase = conectar()

    for i, p_display in enumerate(proyectos_selec):
        p_row = df_p[df_p['proyecto_display'] == p_display].iloc[0]
        id_p = p_row['id']
        
        # Datos del Proyecto (Planificado)
        res_p = supabase.table("proyectos").select("*").eq("id", id_p).execute()
        if not res_p.data: continue
        p_data = res_p.data[0]

        # Datos de Seguimiento (Ejecutado)
        datos_reales = obtener_datos_gantt_procesados(id_p)
        dict_reales = {d['Etapa']: d for d in datos_reales}

        # --- A. BLOQUE PLANIFICADO (Superior) ---
        for y_idx, etapa in enumerate(ETAPAS_INV):
            # Posición en el eje Y: Desplazada hacia arriba para el bloque Planificado
            pos_y_plan = (i * 15) + (y_idx + 6) 
            
            f_map = {
                "Diseño": ("p_dis_i", "p_dis_f"), "Fabricación": ("p_fab_i", "p_fab_f"),
                "Traslado": ("p_tra_i", "p_tra_f"), "Instalación": ("p_ins_i", "p_ins_f"),
                "Entrega": ("p_ent_i", "p_ent_f")
            }
            fi, ff = f_map[etapa]
            
            if p_data.get(fi) and p_data.get(ff):
                c_plan = "#4F4F4F" if etapa == "Fabricación" else "#D3D3D3"
                fig.add_trace(go.Bar(
                    base=[p_data[fi]],
                    x=[(pd.to_datetime(p_data[ff]) - pd.to_datetime(p_data[fi])).days],
                    y=[pos_y_plan],
                    orientation='h',
                    marker_color=c_plan,
                    name=f"PLAN: {etapa}",
                    hoverinfo="text",
                    hovertext=f"PLANIFICADO: {etapa}<br>{p_data[fi]} al {p_data[ff]}",
                    width=0.8
                ))

        # --- B. BLOQUE EJECUTADO (Inferior, justo debajo del anterior) ---
        for y_idx, etapa in enumerate(ETAPAS_INV):
            # Posición en el eje Y: Justo debajo de las barras grises
            pos_y_real = (i * 15) + (y_idx)

            if etapa in dict_reales:
                dr = dict_reales[etapa]
                av = round(dr['Avance'], 1)
                fig.add_trace(go.Bar(
                    base=[dr['Inicio'].strftime('%Y-%m-%d')],
                    x=[(dr['Fin'] - dr['Inicio']).days + 1],
                    y=[pos_y_real],
                    orientation='h',
                    marker_color=obtener_color_gerencial(av),
                    text=f"<b>{av}%</b>",
                    textposition="inside",
                    textfont=dict(color="white", size=11),
                    name=f"REAL: {etapa}",
                    hoverinfo="text",
                    hovertext=f"EJECUTADO REAL: {etapa}<br>Avance: {av}%<br>{dr['Inicio'].date()} al {dr['Fin'].date()}",
                    width=0.8
                ))

    # --- 3. DISEÑO DE ESCALA Y EJES ---
    fig.update_layout(
        barmode='overlay',
        showlegend=False,
        plot_bgcolor="white",
        height=400 * len(proyectos_selec),
        xaxis=dict(
            type='date',
            tickformat='%b %Y', # Escala Mensual (Ej: Mar 2026)
            dtick="M1",
            gridcolor="#F0F0F0",
            minor=dict(dtick=1000*60*60*24*14, showgrid=True, gridcolor="#F9F9F9", griddash="dot") # Quincenas
        ),
        yaxis=dict(
            tickmode='array',
            tickvals=[(i * 15) + y for i in range(len(proyectos_selec)) for y in range(11)],
            ticktext=(ETAPAS_INV + ["--- EJECUTADO ---"] + ETAPAS_INV + ["--- PLANIFICADO ---"]) * len(proyectos_selec),
            fixedrange=True
        ),
        margin=dict(l=220, r=50, t=80, b=50)
    )

    # Separadores visuales de Proyectos
    for i, p_display in enumerate(proyectos_selec):
        fig.add_annotation(
            x=-0.05, y=(i * 15) + 5,
            xref="paper", yref="y",
            text=f"<b>PROYECTO: {p_display.upper()}</b>",
            showarrow=False, xanchor="right", font=dict(size=14, color="#002147")
        )

    st.plotly_chart(fig, use_container_width=True)
