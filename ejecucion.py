import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from base_datos import conectar, obtener_proyectos, obtener_datos_gantt_procesados

# =========================================================
# 1. CONFIGURACIÓN Y LÓGICA DE COLOR MATIZADO
# =========================================================
ORDEN_ETAPAS = ["Diseño", "Fabricación", "Traslado", "Instalación", "Entrega"]

def obtener_color_estricto(avance):
    """Calcula el color matizado según el avance ponderado real."""
    if avance < 50:
        return f'rgb({int(160 + avance)}, 60, 60)' # Rojo matizado
    elif avance <= 75:
        return f'rgb({int(200 + (avance-50)*2)}, {int(180 + (avance-50)*2)}, 0)' # Amarillo
    else:
        return f'rgb(34, {int(100 + (avance-75)*4)}, 34)' # Verde matizado

def mostrar():
    st.header("📊 Tablero de Control: Planificado vs. Ejecutado")
    supabase = conectar()
    
    # --- A. FILTROS EN SIDEBAR ---
    with st.sidebar:
        st.divider()
        st.subheader("Opciones de Vista")
        ver_solo_real = st.toggle("Ocultar Planificación (Gris)", value=False)
    
    # --- B. BUSCADOR Y SELECCIÓN ---
    with st.container(border=True):
        bus = st.text_input("🔍 Localizador de Proyectos", placeholder="Código, Cliente o Nombre...")
        df_p = obtener_proyectos(bus)
        
        if df_p.empty:
            st.info("No se encontraron coincidencias."); return
            
        dict_proy = {r['proyecto_display']: r['id'] for _, r in df_p.iterrows()}
        
    proyectos_sel = st.multiselect("Proyectos a Auditar:", 
                                    options=list(dict_proy.keys()), 
                                    default=list(dict_proy.keys())[:1])

    if not proyectos_sel:
        st.info("💡 Seleccione proyectos para visualizar el cronograma comparativo."); return

    # --- C. CONSTRUCCIÓN DEL GRÁFICO (BLOQUES SEPARADOS) ---
    fig = go.Figure()
    ETAPAS_INV = ORDEN_ETAPAS[::-1] # Invertimos para que Diseño quede arriba

    for i, p_display in enumerate(proyectos_sel):
        id_p = dict_proy[p_display]
        
        # 1. Recuperar fechas del contrato (Planificado)
        res_p = supabase.table("proyectos").select("*").eq("id", id_p).execute()
        if not res_p.data: continue
        p_data = res_p.data[0]

        # 2. Recuperar avance real (Ejecutado)
        datos_reales = obtener_datos_gantt_procesados(id_p)
        dict_reales = {d['Etapa']: d for d in datos_reales}

        for y_idx, etapa in enumerate(ETAPAS_INV):
            # Posicionamiento absoluto: cada proyecto ocupa un bloque de 20 unidades en Y
            # Bloque Planificado: posiciones 11 a 15 | Bloque Ejecutado: posiciones 0 a 4
            base_y = i * 20

            # --- BARRA PLANIFICADA (ARRIBA - GRIS) ---
            if not ver_solo_real:
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
                        y=[base_y + y_idx + 10], # Posición en el bloque superior
                        orientation='h',
                        marker_color=c_plan,
                        name="Planificado",
                        hoverinfo="text",
                        text=f"PLAN: {etapa}",
                        width=0.7
                    ))

            # --- BARRA EJECUTADA (ABAJO - COLOR) ---
            if etapa in dict_reales:
                dr = dict_reales[etapa]
                av = round(dr['Avance'], 1)
                fig.add_trace(go.Bar(
                    base=[dr['Inicio'].strftime('%Y-%m-%d')],
                    x=[(dr['Fin'] - dr['Inicio']).days + 1],
                    y=[base_y + y_idx], # Posición en el bloque inferior
                    orientation='h',
                    marker_color=obtener_color_estricto(av),
                    text=f"<b>{av}%</b>", # Solo el porcentaje
                    textposition="inside",
                    textfont=dict(color="white", size=10),
                    name="Real",
                    hoverinfo="text",
                    hovertext=f"REAL: {etapa}<br>Avance: {av}%",
                    width=0.7
                ))

    # --- D. AJUSTES DE DISEÑO Y ESCALA TEMPORAL ---
    fig.update_layout(
        barmode='overlay', showlegend=False, plot_bgcolor="white",
        height=500 * len(proyectos_sel),
        xaxis=dict(
            type='date', tickformat='%b %Y', dtick="M1", # Escala Mensual
            gridcolor="#F0F0F0",
            minor=dict(dtick=1000*60*60*24*14, showgrid=True, gridcolor="#F8F8F8", griddash="dot") # Quincenas
        ),
        yaxis=dict(
            tickmode='array',
            tickvals=[(i * 20) + y for i in range(len(proyectos_sel)) for y in range(len(ETAPAS_INV))],
            ticktext=ETAPAS_INV * len(proyectos_sel),
            fixedrange=True
        ),
        margin=dict(l=220, r=50, t=50, b=50)
    )

    # Identificadores de Proyecto
    for i, p_display in enumerate(proyectos_sel):
        fig.add_annotation(
            x=-0.02, y=(i * 20) + 7, xref="paper", yref="y",
            text=f"<b>PROYECTO: {p_display.upper()}</b>",
            showarrow=False, xanchor="right", font=dict(size=14, color="#002147")
        )

    st.plotly_chart(fig, use_container_width=True)
