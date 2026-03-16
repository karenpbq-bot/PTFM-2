import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from base_datos import conectar, obtener_proyectos, obtener_gantt_real_data

# =========================================================
# SECCIÓN 1: CONFIGURACIÓN Y CONSTANTES
# =========================================================
ORDEN_ETAPAS = ["Diseño", "Fabricación", "Traslado", "Instalación", "Entrega"]

# Colores Ejecutados (Alta visibilidad para modo oscuro/claro)
COLORES_REALES = {
    "Diseño": "#1ABC9C",      
    "Fabricación": "#F39C12", 
    "Traslado": "#9B59B6",    
    "Instalación": "#2E86C1", 
    "Entrega": "#27AE60"      
}

def mostrar():
    st.header("📊 Cronograma Global de Ejecución")
    supabase = conectar()
    
    with st.sidebar:
        st.divider()
        st.subheader("Configuración de Visualización")
        solo_real = st.toggle("Ver solo ejecución real", value=False)
    
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
            res_p = supabase.table("proyectos").select("*").eq("id", id_p).execute()
            if not res_p.data: continue
            p_data = res_p.data[0]

            # --- ASEGURAR QUE LAS 5 ETAPAS EXISTAN SIEMPRE (ESQUELETO) ---
            # Creamos una fila "fantasma" sin duración para cada etapa si no hay datos
            for etapa_fija in ORDEN_ETAPAS:
                data_final.append(dict(
                    Proyecto=p_nom, Etapa=etapa_fija, 
                    Inicio=datetime.now().strftime('%Y-%m-%d'), 
                    Fin=datetime.now().strftime('%Y-%m-%d'), 
                    Color="rgba(0,0,0,0)", Tipo="Esqueleto" # Invisible
                ))
            
            # A. DATA PLANIFICADA (BARRAS GRISES DE ALTO CONTRASTE)
            if not solo_real:
                map_cols = [
                    ("Diseño", 'p_dis_i', 'p_dis_f', "#BDC3C7"), # Gris Perla
                    ("Fabricación", 'p_fab_i', 'p_fab_f', "#5D6D7E"), # Gris Azulado
                    ("Traslado", 'p_tra_i', 'p_tra_f', "#BDC3C7"),
                    ("Instalación", 'p_ins_i', 'p_ins_f', "#BDC3C7"),
                    ("Entrega", 'p_ent_i', 'p_ent_f', "#BDC3C7")
                ]
                for et, i_c, f_c, col in map_cols:
                    if p_data.get(i_c) and p_data.get(f_c):
                        data_final.append(dict(
                            Proyecto=p_nom, Etapa=et, Inicio=p_data[i_c], 
                            Fin=p_data[f_c], Color=col, Tipo="Planificado"
                        ))
            
            # B. DATA REAL (MAPEO DE HITOS)
            df_r = obtener_gantt_real_data(id_p)
            if not df_r.empty:
                for _, row in df_r.iterrows():
                    try:
                        str_f = str(row['fecha']).strip()
                        fecha_dt = datetime.strptime(str_f, '%d/%m/%Y') if "/" in str_f else datetime.strptime(str_f, '%Y-%m-%d')
                        
                        # Mapeo de hitos corregido para Diseño y otros
                        hito_l = row['hito'].lower()
                        if "disen" in hito_l: et_match = "Diseño"
                        elif any(x in hito_l for x in ["fabric", "corte", "canto", "armad"]): et_match = "Fabricación"
                        elif "tras" in hito_l or "obra" in hito_l: et_match = "Traslado"
                        elif "entreg" in hito_l or "revisi" in hito_l: et_match = "Entrega"
                        else: et_match = "Instalación"
                        
                        data_final.append(dict(
                            Proyecto=p_nom, Etapa=et_match, Inicio=fecha_dt.strftime('%Y-%m-%d'), 
                            Fin=(fecha_dt + timedelta(days=2)).strftime('%Y-%m-%d'), 
                            Color=COLORES_REALES.get(et_match, "#2E86C1"), Tipo="Real"
                        ))
                    except: continue

        df_fig = pd.DataFrame(data_final)
        
        # FORZAR LAS CATEGORÍAS (Esto hace que Diseño aparezca siempre)
        df_fig['Etapa'] = pd.Categorical(df_fig['Etapa'], categories=ORDEN_ETAPAS, ordered=True)
        df_fig = df_fig.sort_values(['Proyecto', 'Etapa', 'Tipo'], ascending=[True, False, True])
        
        fig = px.timeline(
            df_fig, x_start="Inicio", x_end="Fin", y="Etapa", color="Color",
            facet_col="Proyecto", facet_col_wrap=1,
            color_discrete_map="identity", category_orders={"Etapa": ORDEN_ETAPAS}
        )

        # AJUSTES DE VISIBILIDAD
        fig.update_yaxes(autorange="reversed", showgrid=True, gridcolor='rgba(128,128,128,0.2)')

        # RANGO DE 4 MESES (120 DÍAS)
        f_min = pd.to_datetime(df_fig[df_fig['Tipo'] != "Esqueleto"]['Inicio']).min()
        f_max_vista = f_min + timedelta(days=120)

        fig.update_xaxes(
            range=[f_min, f_max_vista],
            dtick="M1", 
            tickformat="%b %Y", 
            showgrid=True, 
            gridcolor='rgba(128,128,128,0.3)', 
            griddash='dot'
        )

        fig.update_layout(
            barmode='group',
            height=450 * len(proyectos_sel), 
            margin=dict(l=10, r=10, t=30, b=10),
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)', 
            plot_bgcolor='rgba(0,0,0,0)',
            bargap=0.2
        )

        # Bordes blancos para resaltar en Modo Oscuro
        fig.update_traces(marker_line_color="white", marker_line_width=1, opacity=0.9)

        # Línea de HOY en Rojo
        fig.add_vline(x=datetime.now().timestamp() * 1000, line_width=2, line_dash="dash", line_color="red")

        st.plotly_chart(fig, use_container_width=True)
        st.plotly_chart(fig, use_container_width=True)
