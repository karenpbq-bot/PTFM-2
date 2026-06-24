import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta, date

@st.cache_data(ttl=300)  # Caché de seguridad de 5 minutos
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
        
        df = pd.read_csv(url_dinamica)
        df = df.dropna(how='all')
        
        # Limpieza de nombres de columnas
        df.columns = df.columns.str.replace(r'[\r\n]+', ' ', regex=True).str.replace(r'\s+', ' ', regex=True).str.strip()
        
        if "Fecha de Corte / Canteo" not in df.columns:
            for i, fila in df.iterrows():
                valores_fila = fila.astype(str).str.replace(r'[\r\n]+', ' ', regex=True).str.strip().values
                if "Fecha de Corte / Canteo" in valores_fila or "Maquina" in valores_fila:
                    df.columns = valores_fila
                    df = df.iloc[i+1:].reset_index(drop=True)
                    break

        df.columns = df.columns.str.replace(r'[\r\n]+', ' ', regex=True).str.replace(r'\s+', ' ', regex=True).str.strip()
        
        df = df.rename(columns={
            "Fecha de Corte / Canteo": "Fecha_Corte",
            "Cantidad (Unid / ml)": "Cantidad",
            "Maquina": "Maquina"
        })
        
        if "Fecha_Corte" not in df.columns or "Maquina" not in df.columns or "Cantidad" not in df.columns:
            return pd.DataFrame()
            
        df = df.dropna(subset=["Fecha_Corte", "Maquina"])
        df["Maquina"] = df["Maquina"].astype(str).str.strip().str.upper()
        df["Cantidad"] = pd.to_numeric(df["Cantidad"], errors='coerce').fillna(0)
        
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
    
    # --- FILA DE CONTROLES SUPERIORES ---
    c_titulo, c_fecha, c_vista, c_sync = st.columns([3.5, 2.5, 4.5, 1.5])
    
    c_titulo.markdown("<h3 style='margin: 0px; padding: 0px; line-height: 1.2;'>📊 Rendimiento</h3>", unsafe_allow_html=True)
    
    fecha_anclaje = c_fecha.date_input("Fecha Fin:", value=date.today(), format="DD/MM/YYYY", label_visibility="collapsed")
    vista = c_vista.radio("🔍 Rango:", ["📅 Mensual (30 días)", "📅 Trimestral (90 días)"], horizontal=True, label_visibility="collapsed")
    
    # BOTÓN DE ACTUALIZACIÓN FORZADA
    if c_sync.button("🔄 Actualizar", use_container_width=True, type="primary", help="Limpia la caché y descarga los datos nuevos de Google Sheets inmediatamente."):
        st.cache_data.clear()
        st.success("¡Datos actualizados desde Google Drive!")
        st.rerun()
        
    st.markdown("<hr style='margin: 0.3rem 0px 0.8rem 0px;'>", unsafe_allow_html=True)
    
    df_raw = cargar_datos_sheets()
    if df_raw.empty:
        st.info("📂 Esperando sincronización de registros estructurados desde Google Drive...")
        return

    # --- MOTOR TEMPORAL RETROSPECTIVO ---
    dias_atras = 30 if "Mensual" in vista else 90
    fecha_inicio = fecha_anclaje - timedelta(days=dias_atras)
    rango_dias = [fecha_inicio + timedelta(days=x) for x in range(dias_atras + 1)]
    
    df_filtrado = df_raw[(df_raw["Fecha_Corte"] >= fecha_inicio) & (df_raw["Fecha_Corte"] <= fecha_anclaje)]

    tab_corte, tab_canteo = st.tabs(["🪚 Procesamiento de Corte (S / E)", "🪵 Procesamiento de Canteo (C)"])

    # =========================================================
    # VISTA 1: CORTE (MÁQUINAS S Y E) - 4 RECTAS: TABLEROS Y RETAZOS
    # =========================================================
    with tab_corte:
        data_corte = []
        total_s, total_e = 0.0, 0.0
        
        # Primero nos aseguramos de normalizar la columna Material a strings limpios
        if not df_filtrado.empty and "Material" in df_filtrado.columns:
            df_filtrado["Material"] = df_filtrado["Material"].astype(str).str.strip()

        for d in rango_dias:
            df_dia = df_filtrado[df_filtrado["Fecha_Corte"] == d]
            
            # Filtrado por Máquina S (Seccionadora)
            df_s = df_dia[df_dia["Maquina"] == "S"]
            tab_s = df_s[df_s["Material"] == "Tablero"]["Cantidad"].sum()
            ret_s = df_s[df_s["Material"] == "Retazo"]["Cantidad"].sum()
            
            # Filtrado por Máquina E (Escuadradora)
            df_e = df_dia[df_dia["Maquina"] == "E"]
            tab_e = df_e[df_e["Material"] == "Tablero"]["Cantidad"].sum()
            ret_e = df_e[df_e["Material"] == "Retazo"]["Cantidad"].sum()
            
            # Mantener la suma total para los KPIs inferiores del resumen
            total_s += (tab_s + ret_s)
            total_e += (tab_e + ret_e)
            
            # Inyección independiente para conformar las 4 rectas continuas (Solo si el valor aporta carga)
            nombre_col = d.strftime("%d/%m")
            if tab_s > 0:
                data_corte.append({"Día": nombre_col, "Cantidad": round(tab_s, 2), "Línea Operativa": "🪚 Tableros Seccionadora S"})
            if ret_s > 0:
                data_corte.append({"Día": nombre_col, "Cantidad": round(ret_s, 2), "Línea Operativa": "♻️ Retazos Seccionadora S"})
            if tab_e > 0:
                data_corte.append({"Día": nombre_col, "Cantidad": round(tab_e, 2), "Línea Operativa": "🪚 Tableros Escuadradora E"})
            if ret_e > 0:
                data_corte.append({"Día": nombre_col, "Cantidad": round(ret_e, 2), "Línea Operativa": "♻️ Retazos Escuadradora E"})

        if data_corte:
            df_plotly_corte = pd.DataFrame(data_corte)
            
            # Construcción gráfica multifactorial mapeada por la serie Línea Operativa
            fig_corte = px.line(
                df_plotly_corte, 
                x="Día", 
                y="Cantidad", 
                color="Línea Operativa",
                text="Cantidad",
                color_discrete_map={
                    "🪚 Tableros Seccionadora S": "#D32F2F",  # Rojo oscuro
                    "♻️ Retazos Seccionadora S": "#EF9A9A",   # Rojo claro
                    "🪚 Tableros Escuadradora E": "#1976D2",  # Azul oscuro
                    "♻️ Retazos Escuadradora E": "#90CAF9"   # Azul claro
                }
            )
            
            fig_corte.update_traces(
                textposition="top center", 
                marker=dict(size=5, symbol="circle"), 
                mode="lines+markers+text"
            )
            
            fig_corte.update_layout(
                xaxis_title=None, 
                yaxis_title="Cantidad de Tableros / Unidades",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=10, r=10, t=15, b=10), 
                hovermode="x unified"
            )
            st.plotly_chart(fig_corte, use_container_width=True)
        else:
            st.info("📂 No se detectaron registros de tableros o retazos en este rango.")

        st.markdown("##### 📋 Resumen del Período")
        c_kpi1, c_kpi2 = st.columns(2)
        dias_activos = len(df_filtrado["Fecha_Corte"].unique()) if not df_filtrado.empty else 1
        
        with c_kpi1:
            st.metric(label="🪚 Total Seccionadora S", value=f"{int(total_s)} Tableros", delta=f"{round(total_s/dias_activos, 1)} prom/día activo")
        with c_kpi2:
            st.metric(label="🪵 Total Escuadradora E", value=f"{int(total_e)} Tableros", delta=f"{round(total_e/dias_activos, 1)} prom/día activo")

    # =========================================================
    # VISTA 2: CANTEADO (MÁQUINA C)
    # =========================================================
    with tab_canteo:
        data_canteo = []
        total_c = 0.0
        
        for d in rango_dias:
            df_dia = df_filtrado[df_filtrado["Fecha_Corte"] == d]
            canteo_c = df_dia[df_dia["Maquina"] == "C"]["Cantidad"].sum()
            total_c += canteo_c
            
            if canteo_c > 0:
                data_canteo.append({"Día": d.strftime("%d/%m"), "Cantidad": round(canteo_c, 2)})

        if data_canteo:
            df_plotly_canteo = pd.DataFrame(data_canteo)
            fig_canteo = px.line(
                df_plotly_canteo, x="Día", y="Cantidad", text="Cantidad", color_discrete_sequence=["#2E7D32"]
            )
            fig_canteo.update_traces(textposition="top center", marker=dict(size=6), mode="lines+markers+text")
            fig_canteo.update_layout(xaxis_title=None, yaxis_title="Metros Lineales (ml)", margin=dict(l=10, r=10, t=10, b=10), hovermode="x unified")
            st.plotly_chart(fig_canteo, use_container_width=True)
        else:
            st.info("📂 No se detectaron registros de canteado (C) en este rango.")

        st.markdown("##### 📋 Resumen del Período")
        c_kpi3 = st.columns(1)[0]
        with c_kpi3:
            st.metric(label="⚙️ Total Canteadora C", value=f"{round(total_c, 1)} Unid / ml", delta=f"{round(total_c/dias_activos, 1)} prom/día activo")
