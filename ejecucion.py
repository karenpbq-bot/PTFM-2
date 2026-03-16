import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from base_datos import conectar, obtener_proyectos, obtener_gantt_real_data

# =========================================================
# 1. CONFIGURACIÓN Y CONSTANTES (ESQUELETO INAMOVIBLE)
# =========================================================
ORDEN_ETAPAS = ["Diseño", "Fabricación", "Traslado", "Instalación", "Entrega"]

def obtener_color_semaforo(avance):
    """Calcula el color matizado según el % de avance del proyecto."""
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
        bus = st.text_input("🔍 Localizador de Proyectos", placeholder="Código, Cliente o Nombre...")
        df_p = obtener_proyectos(bus)
        
        if df_p.empty:
            st.info("No se encontraron coincidencias."); return
            
        dict_proy = {f"{r['proyecto_text']} — {r['cliente']}": r['id'] for _, r in df_p.iterrows()}
        
    proyectos_sel = st.multiselect("Proyectos a Auditar:", 
                                    options=list(dict_proy.keys()), 
                                    default=list(dict_proy.keys())[:1])

    if proyectos_sel:
        data_final = []
        
        for p_nom in proyectos_sel:
            id_p = dict_proy[p_nom]
            # Traemos todos los campos de la tabla proyectos
            res_p = supabase.table("proyectos").select("*").eq("id", id_p).execute()
            if not res_p.data: continue
            p_data = res_p.data[0]
            
            avance_p = p_data.get('avance', 0)
            color_real = obtener_color_semaforo(avance_p)

            # --- A. FORZAR ESQUELETO DE 5 ETAPAS ---
            for etapa_fija in ORDEN_ETAPAS:
                data_final.append(dict(
                    Proyecto=p_nom, Etapa=etapa_fija, 
                    Inicio=datetime.now(), Fin=datetime.now(), 
                    Color="rgba(0,0,0,0)", Tipo="3_Esqueleto"
                ))

            # --- B. DATA PLANIFICADA (BARRAS CELESTES - BLOQUE SUPERIOR) ---
            if not solo_real:
                c_plan = "#87CEEB" # Celeste SkyBlue
                map_cols = [
                    ("Diseño", 'p_dis_i', 'p_dis_f'),
                    ("Fabricación", 'p_fab_i', 'p_fab_f'),
                    ("Traslado", 'p_tra_i', 'p_tra_f'),
                    ("Instalación", 'p_ins_i', 'p_ins_f'),
                    ("Entrega", 'p_ent_i', 'p_ent_f')
                ]
                for et, i_c, f_c in map_cols:
                    if p_data.get(i_c) and p_data.get(f_c):
                        data_final.append(dict(
                            Proyecto=p_nom, Etapa=et, Inicio=p_data[i_c], 
                            Fin=p_data[f_c], Color=c_plan, Tipo="1_Planificado"
                        ))
            
            # --- C. DATA REAL (EJECUTADO - BLOQUE INFERIOR) ---
            df_r = obtener_gantt_real_data(id_p)
            if not df_r.empty:
                for _, row in df_r.iterrows():
                    try:
                        str_f = str(row['fecha']).strip()
                        fecha_dt = datetime.strptime(str_f, '%d/%m/%Y') if "/" in str_f else datetime.strptime(str_f, '%Y-%m-%d')
                        
                        hito_l = row['hito'].lower()
                        if "disen" in hito_l: et_m = "Diseño"
                        elif any(x in hito_l for x in ["fabric", "corte", "armad"]): et_m = "Fabricación"
                        elif "tras" in hito_l or "obra" in hito_l: et_m = "Traslado"
                        elif "entreg" in hito_l: et_m = "Entrega"
                        else: et_m = "Instalación"
                        
                        data_final.append(dict(
                            Proyecto=p_nom, Etapa=et_m, Inicio=fecha_dt.strftime('%Y-%m-%d'), 
                            Fin=(fecha_dt + timedelta(days=2)).strftime('%Y-%m-%d'), 
                            Color=color_real, Tipo="2_Real"
                        ))
                    except: continue

        # --- D. GENERACIÓN DEL GRÁFICO (RESTAURACIÓN) ---
        if not data_final:
            st.warning("No hay datos para mostrar."); return

        df_fig = pd.DataFrame(data_final)
        df_fig['Etapa'] = pd.Categorical(df_fig['Etapa'], categories=ORDEN_ETAPAS, ordered=True)
        # Ordenamos por Tipo (1_Planificado < 2_Real) asegura que el celeste esté arriba
        df_fig = df_fig.sort_values(['Proyecto', 'Etapa', 'Tipo'], ascending=[True, False, True])
        
        fig = px.timeline(
            df_fig, x_start="Inicio", x_end="Fin", y="Etapa", color="Color",
            facet_col="Proyecto", facet_col_wrap=1,
            color_discrete_map="identity", category_orders={"Etapa": ORDEN_ETAPAS}
        )

        fig.update_yaxes(autorange="reversed", showgrid=True, gridcolor='rgba(128,128,128,0.2)')

        # Ajuste de escala a 4 meses (120 días)
        f_val = pd.to_datetime(df_fig[df_fig['Tipo'] != "3_Esqueleto"]['Inicio'])
        f_min = f_val.min() if not f_val.empty else datetime.now()
        
        fig.update_xaxes(
            range=[f_min - timedelta(days=5), f_min + timedelta(days=120)],
            dtick="M1", tickformat="%b %Y", showgrid=True, gridcolor='rgba(128,128,128,0.3)', griddash='dot'
        )

        fig.update_layout(
            barmode='group', # ESTO SEPARA LAS BARRAS: Planificado arriba, Real abajo
            height=450 * len(proyectos_sel), 
            margin=dict(l=10, r=10, t=50, b=10),
            showlegend=False
        )

        fig.update_traces(marker_line_color="white", marker_line_width=1, opacity=0.9)
        fig.add_vline(x=datetime.now().timestamp() * 1000, line_width=2, line_dash="dash", line_color="red")

        st.plotly_chart(fig, use_container_width=True)
