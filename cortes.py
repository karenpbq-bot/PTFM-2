import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date

@st.cache_data(ttl=600)  # Caché de 10 minutos para optimizar la velocidad de carga
def cargar_datos_sheets():
    """Conecta con Google Sheets y limpia la estructura de filas del taller."""
    try:
        url = st.secrets["URL_GOOGLE_SHEETS"]
        # Leemos el archivo saltándonos las primeras filas de cabecera decorativa
        df = pd.read_csv(url, skiprows=2)
        
        # Renombramos columnas clave para asegurar compatibilidad matemática
        df.columns = df.columns.str.strip()
        df = df.rename(columns={
            "Fecha de \nCorte / Canteo": "Fecha_Corte",
            "Cantidad \n(Unid / ml)": "Cantidad",
            "Maquina": "Maquina"
        })
        
        # Limpieza estricta de filas vacías y conversión de tipos
        df = df.dropna(subset=["Fecha_Corte", "Maquina", "Cantidad"])
        df["Fecha_Corte"] = pd.to_datetime(df["Fecha_Corte"], errors='coerce').dt.date
        df["Cantidad"] = pd.to_numeric(df["Cantidad"], errors='coerce').fillna(0)
        df["Maquina"] = df["Maquina"].astype(str).str.strip().str.upper()
        
        return df.dropna(subset=["Fecha_Corte"])
    except Exception as e:
        st.error(f"Error al conectar con Google Drive: {e}")
        return pd.DataFrame()

def mostrar():
    st.markdown("<div style='margin-top: 0.5rem;'></div>", unsafe_allow_html=True)
    
    df_raw = cargar_datos_sheets()
    if df_raw.empty:
        st.info("📂 Esperando sincronización de datos válidos desde Google Drive...")
        return

    # --- CONFIGURACIÓN DE CONTROLES TEMPORALES RETROSPECTIVOS (UNA SOLA FILA) ---
    c_titulo, c_fecha, c_vista = st.columns([4, 3, 5])
    c_titulo.markdown("<h3 style='margin: 0px; padding: 0px; line-height: 1.2;'>📊 Rendimiento de Taller</h3>", unsafe_allow_html=True)
    
    fecha_anclaje = c_fecha.date_input("Fecha Fin:", value=date.today(), format="DD/MM/YYYY", label_visibility="collapsed")
    vista = c_vista.radio("🔍 Historial:", ["📅 Mensual (30 días atrás)", "📅 Trimestral (90 días atrás)"], horizontal=True, label_visibility="collapsed")
    st.markdown("<hr style='margin: 0.3rem 0px 0.8rem 0px;'>", unsafe_allow_html=True)

    # --- MOTOR RETROSPECTIVO (HACIA ATRÁS) ---
    dias_atras = 30 if "Mensual" in vista else 90
    fecha_inicio = fecha_anclaje - timedelta(days=dias_atras)
    
    # Construimos la lista completa de días en el rango para evitar saltos en las gráficas
    lista_dias = [fecha_inicio + timedelta(days=x) for x in range(dias_atras + 1)]
    
    # Filtrado del DataFrame general por el rango de fechas elegido
    df_filtrado = df_raw[(df_raw["Fecha_Corte"] >= fecha_inicio) & (df_raw["Fecha_Corte"] <= fecha_anclaje)]

    # Creamos sub-pestañas para no mezclar los procesos en la pantalla
    tab_corte, tab_canteo = st.tabs(["🪚 Procesamiento de Corte (S / E)", "🪵 Procesamiento de Canteo (C)"])

    # =========================================================
    # VISTA 1: CORTE (SÓLO SECCIONADORA S Y ESCUADRADORA E)
    # =========================================================
    with tab_corte:
        data_corte = []
        total_s, total_e = 0.0, 0.0
        
        for d in lista_dias:
            df_dia = df_filtrado[df_filtrado["Fecha_Corte"] == d]
            
            # Filtros estrictos para excluir la máquina C
            cortes_s = df_dia[df_dia["Maquina"] == "S"]["Cantidad"].sum()
            cortes_e = df_dia[df_dia["Maquina"] == "E"]["Cantidad"].sum()
            
            total_s += cortes_s
            total_e += cortes_e
            
            data_corte.append({
                "Día": d.strftime("%d/%m"),
                "Seccionadora S": round(cortes_s, 2),
                "Escuadradora E": round(cortes_e, 2)
            })

        df_curvas_corte = pd.DataFrame(data_corte).set_index("Día")

        st.markdown("<h4 style='margin: 0px; padding-bottom: 0.5rem;'>📈 Tableros Cortados por Día</h4>", unsafe_allow_html=True)
        st.line_chart(df_curvas_corte, use_container_width=True, color=["#D32F2F", "#1976D2"])

        # --- KPIs DE CORTE ---
        st.markdown("##### 📋 Resumen de Eficiencia de Corte")
        c_kpi1, c_kpi2 = st.columns(2)
        dias_reales = len(lista_dias)
        
        with c_kpi1:
            st.metric(label="🪚 Total Seccionadora S", value=f"{int(total_s)} Tableros", delta=f"{round(total_s/dias_reales, 1)} prom/día")
        with c_kpi2:
            st.metric(label="🪵 Total Escuadradora E", value=f"{int(total_e)} Tableros", delta=f"{round(total_e/dias_reales, 1)} prom/día", delta_color="inverse")

    # =========================================================
    # VISTA 2: CANTEADO (SÓLO CANTEADORA C)
    # =========================================================
    with tab_canteo:
        data_canteo = []
        total_c = 0.0
        
        for d in lista_dias:
            df_dia = df_filtrado[df_filtrado["Fecha_Corte"] == d]
            
            # Filtro estricto único para máquina C
            canteo_c = df_dia[df_dia["Maquina"] == "C"]["Cantidad"].sum()
            total_c += canteo_c
            
            data_canteo.append({
                "Día": d.strftime("%d/%m"),
                "Canteadora C": round(canteo_c, 2)
            })

        df_curva_canteo = pd.DataFrame(data_canteo).set_index("Día")

        st.markdown("<h4 style='margin: 0px; padding-bottom: 0.5rem;'>📈 Avanzado de Canteado Diario</h4>", unsafe_allow_html=True)
        # Color verde institucional para diferenciar el proceso de canteado del proceso de corte
        st.line_chart(df_curva_canteo, use_container_width=True, color=["#2E7D32"])

        # --- KPIs DE CANTEADO ---
        st.markdown("##### 📋 Resumen de Eficiencia de Canteo")
        c_kpi3 = st.columns(1)[0]
        
        with c_kpi3:
            st.metric(label="⚙️ Total Canteadora C", value=f"{round(total_c, 1)} Unid / ml", delta=f"{round(total_c/dias_reales, 1)} prom/día")
