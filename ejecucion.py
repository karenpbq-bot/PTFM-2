import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from base_datos import conectar, obtener_proyectos, obtener_gantt_real_data

# =========================================================
# SECCIÓN 1: CONFIGURACIÓN Y CONSTANTES (FUNCIONALIDAD ORIGINAL)
# Mantiene el orden estricto de etapas para evitar la inversión del gráfico.
# =========================================================
ORDEN_ETAPAS = ["Diseño", "Fabricación", "Traslado", "Instalación", "Entrega"]

COLORES_REALES = {
    "Diseño": "#1ABC9C",      # Turquesa
    "Fabricación": "#F39C12", # Naranja
    "Traslado": "#9B59B6",    # Morado
    "Instalación": "#2E86C1", # Azul
    "Entrega": "#27AE60"      # Verde
}

def mostrar():
    st.header("📊 Cronograma Global de Ejecución")
    supabase = conectar()
    
    # --- 1. CONFIGURACIÓN DE VISTA EN SIDEBAR ---
    with st.sidebar:
        st.divider()
        st.subheader("Configuración de Visualización")
        solo_real = st.toggle("Ver solo ejecución real", value=False, 
                              help="Oculta las barras grises de planificación contractual")
    
    # --- 2. SELECCIÓN DE PROYECTOS ---
    with st.container(border=True):
        bus = st.text_input("🔍 Buscar por Proyecto o Cliente...", placeholder="Ej: Casa")
        df_p = obtener_proyectos(bus)
        
        if df_p.empty:
            st.info("No se encontraron proyectos activos."); return
            
        dict_proy = {f"{r['proyecto_text']} — {r['cliente']}": r['id'] for _, r in df_p.iterrows()}
        
    proyectos_sel = st.multiselect("Visualizar Proyectos:", 
                                    options=list(dict_proy.keys()), 
                                    default=list(dict_proy.keys())[:1])

    if proyectos_sel:
        data_final = []
        
        for p_nom in proyectos_sel:
            id_p = dict_proy[p_nom]
            
            # --- CONSULTA NUBE: Recupera datos del proyecto (Sin errores de conexión) ---
            res_p = supabase.table("proyectos").select("*").eq("id", id_p).execute()
            if not res_p.data: continue
            p_data = res_p.data[0]
            
            # A. DATA PLANIFICADA (Lógica Original Contractual)
            if not solo_real:
                map_cols = [
                    ("Diseño", 'p_dis_i', 'p_dis_f', "#EBEDEF"),
                    ("Fabricación", 'p_fab_i', 'p_fab_f', "#7F8C8D"),
                    ("Traslado", 'p_tra_i', 'p_tra_f', "#EBEDEF"),
                    ("Instalación", 'p_ins_i', 'p_ins_f', "#EBEDEF"),
                    ("Entrega", 'p_ent_i', 'p_ent_f', "#EBEDEF")
                ]
                for et, i_c, f_c, col in map_cols:
                    if p_data.get(i_c) and p_data.get(f_c):
                        data_final.append(dict(
                            Proyecto=p_nom, Etapa=et, Inicio=p_data[i_c], 
                            Fin=p_data[f_c], Color=col, Tipo="Planificado"
                        ))
            
            # B. DATA REAL (Lógica de Seguimiento de Nube)
            df_r = obtener_gantt_real_data(id_p)
            if not df_r.empty:
                for _, row in df_r.iterrows():
                    try:
                        str_f = str(row['fecha']).strip()
                        fecha_dt = datetime.strptime(str_f, '%d/%m/%Y') if "/" in str_f else datetime.strptime(str_f, '%Y-%m-%d')
                        
                        inicio_real = fecha_dt.strftime('%Y-%m-%d')
                        fin_real = (fecha_dt + timedelta(days=1)).strftime('%Y-%m-%d')
                        
                        # Mapeo inteligente de hitos a etapas del Gantt
                        et_match = next((et for et in ORDEN_ETAPAS if et[:4].lower() in row['hito'].lower()), "Instalación")
                        
                        data_final.append(dict(
                            Proyecto=p_nom, Etapa=et_match, Inicio=inicio_real, 
                            Fin=fin_real, Color=COLORES_REALES.get(et_match, "#2E86C1"), Tipo="Real"
                        ))
                    except: continue

        if not data_final:
            st.warning("No hay datos para mostrar con los filtros seleccionados."); return

        # =========================================================
        # SECCIÓN 3: GENERACIÓN DEL GRÁFICO (RESTAURACIÓN DE ORDEN)
        # Aquí se incluye la lógica que evita la inversión de etapas.
        # =========================================================
        df_fig = pd.DataFrame(data_final)
        
        # DEFINICIÓN DE CATEGORÍA ORDENADA (Evita inversión de eje Y)
        df_fig['Etapa'] = pd.Categorical(df_fig['Etapa'], categories=ORDEN_ETAPAS, ordered=True)
        
        # ORDENAMIENTO FÍSICO DEL DATAFRAME
        df_fig = df_fig.sort_values(['Proyecto', 'Etapa'], ascending=[True, False])
        
        fig = px.timeline(
            df_fig, x_start="Inicio", x_end="Fin", y="Etapa", color="Color",
            facet_col="Proyecto", facet_col_wrap=1,
            color_discrete_map="identity", category_orders={"Etapa": ORDEN_ETAPAS}
        )

        # AJUSTES DE DISEÑO ORIGINALES
        fig.update_yaxes(
            categoryorder="array",
            categoryarray=ORDEN_ETAPAS,
            autorange="reversed", # FORZA DISEÑO ARRIBA
            showgrid=True
        )

        fig.update_layout(
            barmode='overlay', # Mantiene la superposición Planificado vs Real
            height=200 * len(proyectos_sel), 
            margin=dict(l=10, r=10, t=30, b=10),
            showlegend=False,
            bargap=0.1
        )

        # Cuadrícula semanal y línea roja de fecha actual
        fig.update_xaxes(dtick="W1", tickformat="%d/%b", showgrid=True, gridcolor='LightGray', griddash='dot')
        fig.add_vline(x=datetime.now().timestamp() * 1000, line_width=2, line_dash="dash", line_color="red")

        st.plotly_chart(fig, use_container_width=True)
