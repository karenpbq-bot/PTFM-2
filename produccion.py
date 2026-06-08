import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from base_datos import conectar

def mostrar():
    # 1. Ajuste de margen superior sutil para dar aire respecto al menú
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    try:
        # Recuperar los proyectos con estatus Activo directamente de Supabase
        supabase = conectar()
        res = supabase.table("proyectos").select("*").eq("estatus", "Activo").execute()
        
        if not res.data:
            st.info("📂 Actualmente no existen proyectos con estatus 'Activo' registrados en el sistema.")
            return

        df_proy = pd.DataFrame(res.data)
        
        # Conversión segura de tipos de datos de fechas y números
        df_proy["p_fab_i"] = pd.to_datetime(df_proy["p_fab_i"], errors='coerce').dt.date
        df_proy["p_fab_f"] = pd.to_datetime(df_proy["p_fab_f"], errors='coerce').dt.date
        df_proy["total_tableros"] = pd.to_numeric(df_proy["total_tableros"], errors='coerce').fillna(0).astype(int)

        # =========================================================
        # CABECERA COMPACTA EN UNA SOLA FILA HORIZONTAL
        # =========================================================
        c_titulo, c_fecha, c_vista = st.columns([3, 2, 4])
        
        # Título con tipografía más pequeña alineado a los controles
        c_titulo.markdown("<h3 style='margin: 0px; padding-top: 0.3em;'>🪚 Producción Proyectada</h3>", unsafe_allow_html=True)
        
        # Selector de fecha integrado
        fecha_ref = c_fecha.date_input("Fecha Referencia:", value=date.today(), format="DD/MM/YYYY", label_visibility="collapsed")
        
        # Selector de granularidad horizontal integrado
        vista = c_vista.radio("Vista:", ["📅 Semanal", "📅 Mensual", "📅 Trimestral"], horizontal=True, label_visibility="collapsed")
        
        st.markdown("<hr style='margin: 0.5rem 0px 1rem 0px;'>", unsafe_allow_html=True)

        # =========================================================
        # MOTOR DE GENERACIÓN DE COLUMNAS CALENDARIO
        # =========================================================
        if "Semanal" in vista:
            inicio_rango = fecha_ref - timedelta(days=fecha_ref.weekday())
            num_dias = 7
        elif "Mensual" in vista:
            inicio_rango = date(fecha_ref.year, fecha_ref.month, 1)
            if fecha_ref.month == 12:
                sig_mes = date(fecha_ref.year + 1, 1, 1)
            else:
                sig_mes = date(fecha_ref.year, fecha_ref.month + 1, 1)
            num_dias = (sig_mes - inicio_rango).days
        else:
            inicio_rango = date(fecha_ref.year, fecha_ref.month, 1)
            num_dias = 90

        lista_dias = [inicio_rango + timedelta(days=x) for x in range(num_dias)]

        # Construcción del vector de filas de proyectos activos
        filas_matriz = []
        for _, fila in df_proy.iterrows():
            f_i = fila["p_fab_i"]
            f_f = fila["p_fab_f"]
            tot_tab = fila["total_tableros"]
            
            if f_i and f_f and (f_f - f_i).days >= 0:
                dias_fab = (f_f - f_i).days + 1
                tab_por_dia = tot_tab / dias_fab
            else:
                dias_fab = 0
                tab_por_dia = 0.0

            registro = {
                "Proyecto": fila["proyecto_text"],
                "Total Tableros": tot_tab
            }
            
            for d in lista_dias:
                nombre_col = d.strftime("%d/%m")
                if f_i and f_f and f_i <= d <= f_f:
                    registro[nombre_col] = round(tab_por_dia, 2)
                else:
                    registro[nombre_col] = 0.0
                    
            filas_matriz.append(registro)

        df_proyectos_activos = pd.DataFrame(filas_matriz)

        # =========================================================
        # CONSOLIDACIÓN HORIZONTAL (FILA DE TOTALES ARRIBA)
        # =========================================================
        fila_total = {
            "Proyecto": "🔥 TOTAL DIARIO",
            "Total Tableros": df_proyectos_activos["Total Tableros"].sum()
        }
        
        for d in lista_dias:
            nombre_col = d.strftime("%d/%m")
            fila_total[nombre_col] = round(df_proyectos_activos[nombre_col].sum(), 2)
            
        # El total consolidado se inyecta estrictamente al tope de la visualización (Fila 1)
        df_matriz_final = pd.concat([pd.DataFrame([fila_total]), df_proyectos_activos], ignore_index=True)

        # Renderizado limpio y directo de la cuadrícula
        st.dataframe(df_matriz_final, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Error crítico al generar la matriz de producción proyectada: {e}")
