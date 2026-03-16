import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from base_datos import conectar, obtener_proyectos, obtener_datos_gantt_procesados

# --- 1. LÓGICA DE COLOR MATIZADO (PRECISIÓN GERENCIAL) ---
def obtener_color_estricto(avance):
    """Semáforo gerencial: Rojo (<50), Amarillo (50-75), Verde (>75)."""
    if avance < 50:
        return f'rgb({int(160 + avance)}, 60, 60)'
    elif avance <= 75:
        return f'rgb({int(200 + (avance-50)*2)}, {int(180 + (avance-50)*2)}, 0)'
    else:
        return f'rgb(34, {int(100 + (avance-75)*4)}, 34)'

def mostrar():
    st.title("📊 Control Contractual: Planificado vs. Ejecutado")
    
    # --- 2. FILTROS ESTRATÉGICOS ---
    with st.sidebar:
        st.subheader("🔍 Localizador de Proyectos")
        bus = st.text_input("Buscador (Código, Cliente, Nombre)")
        df_p = obtener_proyectos(bus)
        
        if df_p.empty:
            st.warning("No hay coincidencias."); return

        proyectos_selec = st.multiselect("Comparar Proyectos:", df_p['proyecto_display'].tolist())
        
        st.divider()
        st.caption("Visualización: Mes a Mes | Quincenas Punteadas")

    if not proyectos_selec:
        st.info("💡 Seleccione proyectos para visualizar el cumplimiento de contratos."); return

    # --- 3. ARQUITECTURA DEL GANTT (BLOQUES INDEPENDIENTES) ---
    ETAPAS = ["Diseño", "Fabricación", "Traslado", "Instalación", "Entrega"]
    ETAPAS_INV = ETAPAS[::-1] # Diseño arriba
    
    fig = go.Figure()
    supabase = conectar()

    for i, p_display in enumerate(proyectos_selec):
        p_row = df_p[df_p['proyecto_display'] == p_display].iloc[0]
        id_p = p_row['id']
        
        # A. Datos Planificados (Compromiso)
        res_p = supabase.table("proyectos").select("*").eq("id", id_p).execute()
        p_data = res_p.data[0] if res_p.data else {}

        # B. Datos Ejecutados (Realidad Ponderada)
        datos_reales = obtener_datos_gantt_procesados(id_p)
        dict_reales = {d['Etapa']: d for d in datos_reales}

        # --- DIBUJO POR BLOQUES (NO ENTRELAZADOS) ---
        # Posicionamiento absoluto: 20 unidades de alto por proyecto
        for y_idx, etapa in enumerate(ETAPAS_INV):
            
            # 🏢 BLOQUE PLANIFICADO (Superior del bloque)
            pos_y_plan = (i * 20) + (y_idx + 12) 
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
                    name=f"Plan: {etapa}",
                    hoverinfo="text",
                    hovertext=f"PLAN: {etapa}<br>{p_data[fi]} al {p_data[ff]}",
                    width=0.8
                ))

            # 🛠️ BLOQUE EJECUTADO (Inferior del bloque)
            pos_y_real = (i * 20) + y_idx
            if etapa in dict_reales:
                dr = dict_reales[etapa]
                av = round(dr['Avance'], 1)
                fig.add_trace(go.Bar(
                    base=[dr['Inicio'].strftime('%Y-%m-%d')],
                    x=[(dr['Fin'] - dr['Inicio']).days + 1],
                    y=[pos_y_real],
                    orientation='h',
                    marker_color=obtener_color_estricto(av),
                    text=f"<b>{av}%</b>",
                    textposition="inside",
                    textfont=dict(color="white", size=11),
                    hoverinfo="text",
                    hovertext=f"REAL: {etapa}<br>Avance: {av}%<br>{dr['Inicio'].date()} al {dr['Fin'].date()}",
                    width=0.8
                ))

    # --- 4. FORMATO Y ESCALA (MES A MES) ---
    fig.update_layout(
        barmode='overlay', showlegend=False, plot_bgcolor="white",
        height=500 * len(proyectos_selec),
        xaxis=dict(
            type='date', tickformat='%b %Y', dtick="M1",
            gridcolor="#F0F0F0",
            minor=dict(dtick=1000*60*60*24*14, showgrid=True, gridcolor="#F8F8F8", griddash="dot")
        ),
        yaxis=dict(
            tickmode='array',
            tickvals=[(i * 20) + y for i in range(len(proyectos_selec)) for y in range(len(ETAPAS_INV))],
            ticktext=ETAPAS_INV * len(proyectos_selec),
            fixedrange=True
        ),
        margin=dict(l=250, r=50, t=80, b=50)
    )

    # Títulos de Proyecto
    for i, p_display in enumerate(proyectos_selec):
        fig.add_annotation(
            x=-0.05, y=(i * 20) + 8, xref="paper", yref="y",
            text=f"<b>PROYECTO: {p_display.upper()}</b>",
            showarrow=False, xanchor="right", font=dict(size=14, color="#002147")
        )
        fig.add_annotation(x=0, y=(i * 20) + 16.5, xref="paper", yref="y", text="<b>📋 PLANIFICADO</b>", showarrow=False, font=dict(color="#4F4F4F"), xanchor="left")
        fig.add_annotation(x=0, y=(i * 20) + 5.5, xref="paper", yref="y", text="<b>🚀 EJECUTADO</b>", showarrow=False, font=dict(color="green"), xanchor="left")

    st.plotly_chart(fig, use_container_width=True)
