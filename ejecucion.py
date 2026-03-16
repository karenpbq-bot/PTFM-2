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

       # --- D. GENERACIÓN DEL GRÁFICO (CORRECCIÓN DE ORDEN) ---
        if not data_final:
            st.warning("No hay datos para mostrar."); return

        df_fig = pd.DataFrame(data_final)
        
        # 1. Definimos el orden categórico
        df_fig['Etapa'] = pd.Categorical(df_fig['Etapa'], categories=ORDEN_ETAPAS, ordered=True)
        
        # 2. ORDEN CLAVE: Para que Diseño sea el primero ARRIBA en el gráfico, 
        # Plotly necesita que sea el ÚLTIMO en el DataFrame si no usamos reversed,
        # o el PRIMERO si ordenamos de forma ascendente y quitamos reversed.
        df_fig = df_fig.sort_values(['Proyecto', 'Etapa', 'Tipo'], ascending=[True, False, True])
        
        fig = px.timeline(
            df_fig, x_start="Inicio", x_end="Fin", y="Etapa", color="Color",
            facet_col="Proyecto", facet_col_wrap=1,
            color_discrete_map="identity",
            category_orders={"Etapa": ORDEN_ETAPAS[::-1]} # <--- Invertimos la categoría aquí
        )

        # 3. CONFIGURACIÓN DE EJES (Sin autorange reversed para evitar conflictos)
        fig.update_yaxes(
            autorange=True,      # <--- Cambiado de "reversed" a True
            showgrid=True, 
            gridcolor='rgba(128,128,128,0.1)',
            fixedrange=True
        )

        # 4. COMPACTACIÓN Y DISEÑO
        fig.update_layout(
            barmode='group',
            bargap=0.4,           
            bargroupgap=0.1,      
            height=200 + (150 * len(proyectos_sel)), # Altura dinámica más eficiente
            margin=dict(l=10, r=10, t=40, b=10),
            showlegend=False
        )

        fig.update_traces(marker_line_width=0, opacity=0.85)

        # Línea de tiempo "Hoy"
        fig.add_vline(x=datetime.now().timestamp() * 1000, line_width=1.5, line_dash="solid", line_color="red")

        st.plotly_chart(fig, use_container_width=True)
