import streamlit as st
import pandas as pd
from datetime import datetime, date

@st.cache_data(ttl=60)  # Reducido a 1 minuto para pruebas ágiles en tiempo real
def cargar_datos_sheets():
    """Conecta con Google Sheets, remueve filas decorativas vacías y normaliza cabeceras."""
    try:
        url_base = "https://docs.google.com/spreadsheets/d/1mscx8TPy-JzafQfW2s7Cz7S0uYgClriW/export?format=csv"
        
        meses_nombres = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 
            5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto", 
            9: "Setiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }
        
        mes_actual = datetime.now().month
        nombre_pestaña = meses_nombres[mes_actual]
        url_dinamica = f"{url_base}&sheet={nombre_pestaña}"
        
        # Leemos el CSV completo desde el inicio para no perder la fila de cabecera real
        df = pd.read_csv(url_dinamica)
        
        # Eliminamos filas completamente vacías que genera Google Sheets en la parte superior
        df = df.dropna(how='all')
        
        # Limpieza profunda de los nombres de columnas: quitamos saltos de línea (\n), retornos (\r) y espacios extras
        df.columns = df.columns.str.replace(r'[\r\n]+', ' ', regex=True).str.replace(r'\s+', ' ', regex=True).str.strip()
        
        # Si la primera fila contiene los nombres reales por un desfase de lectura, la promovemos
        if "Fecha de Corte / Canteo" not in df.columns:
            # Buscamos la fila que contenga el identificador de columnas
            for i, fila in df.iterrows():
                valores_fila = fila.astype(str).str.replace(r'[\r\n]+', ' ', regex=True).str.strip().values
                if "Fecha de Corte / Canteo" in valores_fila or "Maquina" in valores_fila:
                    df.columns = valores_fila
                    df = df.iloc[i+1:].reset_index(drop=True)
                    break

        # Re-normalizamos los nombres de las columnas tras cualquier ajuste de fila
        df.columns = df.columns.str.replace(r'[\r\n]+', ' ', regex=True).str.replace(r'\s+', ' ', regex=True).str.strip()
        
        # Mapeo unificado estricto
        df = df.rename(columns={
            "Fecha de Corte / Canteo": "Fecha_Corte",
            "Cantidad (Unid / ml)": "Cantidad",
            "Maquina": "Maquina"
        })
        
        # Filtrado de seguridad: Requerimos obligatoriamente estas tres columnas
        if "Fecha_Corte" not in df.columns or "Maquina" not in df.columns or "Cantidad" not in df.columns:
            st.error("⚠️ Estructura incompatible. Columnas detectadas: " + str(list(df.columns)))
            return pd.DataFrame()
            
        # Limpieza de filas secundarias inactivas
        df = df.dropna(subset=["Fecha_Corte", "Maquina"])
        
        df["Maquina"] = df["Maquina"].astype(str).str.strip().str.upper()
        df["Cantidad"] = pd.to_numeric(df["Cantidad"], errors='coerce').fillna(0)
        
        # Procesamiento tolerante de fechas fila por fila
        def procesar_fecha(val):
            if pd.isna(val):
                return None
            s = str(val).strip().replace('?', '')
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d'):
                try:
                    return pd.to_datetime(s, format=fmt).date()
                except:
                    continue
            try:
                return pd.to_datetime(s, errors='coerce').date()
            except:
                return None

        df["Fecha_Corte"] = df["Fecha_Corte"].apply(procesar_fecha)
        return df.dropna(subset=["Fecha_Corte"])
        
    except Exception as e:
        st.error(f"Error analítico en el procesamiento del taller: {e}")
        return pd.DataFrame()

def mostrar():
    st.markdown("<div style='margin-top: 0.5rem;'></div>", unsafe_allow_html=True)
    
    df_raw = cargar_datos_sheets()
    if df_raw.empty:
        st.info("📂 Esperando sincronización de registros estructurados desde Google Drive...")
        return

    st.markdown("<h3 style='margin: 0px; padding: 0px;'>📊 Rendimiento de Taller</h3>", unsafe_allow_html=True)
    st.markdown("<hr style='margin: 0.3rem 0px 0.8rem 0px;'>", unsafe_allow_html=True)

    # Agrupamos las fechas reales únicas existentes para el gráfico
    fechas_reales = sorted(df_raw["Fecha_Corte"].unique())
    if not fechas_reales:
        st.info("No se encontraron registros de fechas procesables para este mes.")
        return

    tab_corte, tab_canteo = st.tabs(["🪚 Procesamiento de Corte (S / E)", "🪵 Procesamiento de Canteo (C)"])

    # =========================================================
    # VISTA 1: CORTE (MÁQUINAS S Y E)
    # =========================================================
    with tab_corte:
        data_corte = []
        total_s, total_e = 0.0, 0.0
        
        for d in fechas_reales:
            df_dia = df_raw[df_raw["Fecha_Corte"] == d]
            
            cortes_s = df_dia[df_dia["Maquina"] == "S"]["Cantidad"].sum()
            cortes_e = df_dia[df_dia["Maquina"] == "E"]["Cantidad"].sum()
            
            total_s += cortes_s
            total_e += cortes_e
            
            data_corte.append({
                "Día": d.strftime("%d/%m"),
                "Seccionadora S": round(cortes_s, 2),
                "Escuadradora E": round(cortes_e, 2)
            })

        df_grafico_corte = pd.DataFrame(data_corte).set_index("Día")

        st.markdown("<h4 style='margin: 0px; padding-bottom: 0.5rem;'>📈 Tableros Cortados por Día</h4>", unsafe_allow_html=True)
        st.line_chart(df_grafico_corte, use_container_width=True, color=["#D32F2F", "#1976D2"])

        st.markdown("##### 📋 Resumen Acumulado del Mes")
        c_kpi1, c_kpi2 = st.columns(2)
        dias_activos = len(fechas_reales)
        
        with c_kpi1:
            st.metric(label="🪚 Total Seccionadora S", value=f"{int(total_s)} Tableros", delta=f"{round(total_s/dias_activos, 1)} prom/día")
        with c_kpi2:
            st.metric(label="🪵 Total Escuadradora E", value=f"{int(total_e)} Tableros", delta=f"{round(total_e/dias_activos, 1)} prom/día")

    # =========================================================
    # VISTA 2: CANTEADO (MÁQUINA C)
    # =========================================================
    with tab_canteo:
        data_canteo = []
        total_c = 0.0
        
        for d in fechas_reales:
            df_dia = df_raw[df_raw["Fecha_Corte"] == d]
            canteo_c = df_dia[df_dia["Maquina"] == "C"]["Cantidad"].sum()
            total_c += canteo_c
            
            data_canteo.append({
                "Día": d.strftime("%d/%m"),
                "Canteadora C": round(canteo_c, 2)
            })

        df_grafico_canteo = pd.DataFrame(data_canteo).set_index("Día")

        st.markdown("<h4 style='margin: 0px; padding-bottom: 0.5rem;'>📈 Avanzado de Canteado Diario</h4>", unsafe_allow_html=True)
        st.line_chart(df_grafico_canteo, use_container_width=True, color=["#2E7D32"])

        st.markdown("##### 📋 Resumen Acumulado del Mes")
        c_kpi3 = st.columns(1)[0]
        with c_kpi3:
            st.metric(label="⚙️ Total Canteadora C", value=f"{round(total_c, 1)} Unid / ml", delta=f"{round(total_c/dias_activos, 1)} prom/día")
