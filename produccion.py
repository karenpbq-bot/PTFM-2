import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from base_datos import conectar

def mostrar():
    st.title("🪚 Producción Proyectada de Tableros")
    st.write("Este módulo consolida la demanda diaria de materia prima cruzando el cronograma de fabricación de todos los proyectos activos.")

    try:
        # 1. Recuperar los proyectos con estatus Activo directamente de Supabase
        supabase = conectar()
        res = supabase.table("proyectos").select("*").eq("estatus", "Activo").execute()
        
        if not res.data:
            st.info("📂 Actualmente no existen proyectos con estatus 'Activo' registrados en el sistema.")
            return

        df_proy = pd.DataFrame(res.data)
        
        # 2. Conversión segura de tipos de datos de fechas y números
        df_proy["p_fab_i"] = pd.to_datetime(df_proy["p_fab_i"], errors='coerce').dt.date
        df_proy["p_fab_f"] = pd.to_datetime(df_proy["p_fab_f"], errors='coerce').dt.date
        df_proy["total_tableros"] = pd.to_numeric(df_proy["total_tableros"], errors='coerce').fillna(0).astype(int)

        # 3. Selectores de control de la cuadrícula temporal
        st.markdown("---")
        c1, c2 = st.columns([2, 3])
        
        fecha_ref = c1.date_input("Seleccionar Fecha de Referencia:", value=date.today(), format="DD/MM/YYYY")
        vista = c2.radio("Granularidad del Calendario:", ["📅 Vista Semanal", "📅 Vista Mensual", "📅 Vista Trimestral"], horizontal=True)

        # 4. Establecer las fechas límites de las columnas según la vista elegida
        if vista == "📅 Vista Semanal":
            # Sincronizamos para arrancar siempre desde el lunes de la semana seleccionada
            inicio_rango = fecha_ref - timedelta(days=fecha_ref.weekday())
            num_dias = 7
        elif vista == "📅 Vista Mensual":
            # Arranca desde el primer día del mes de la fecha de referencia
            inicio_rango = date(fecha_ref.year, fecha_ref.month, 1)
            if fecha_ref.month == 12:
                sig_mes = date(fecha_ref.year + 1, 1, 1)
            else:
                sig_mes = date(fecha_ref.year, fecha_ref.month + 1, 1)
            num_dias = (sig_mes - inicio_rango).days
        else:
            # Vista Trimestral: 90 días a partir del primer día del mes actual
            inicio_rango = date(fecha_ref.year, fecha_ref.month, 1)
            num_dias = 90

        # Lista ordenada de días que conformarán las columnas dinámicas de la matriz
        lista_dias = [inicio_rango + timedelta(days=x) for x in range(num_dias)]

        # 5. Construcción del vector de filas de la matriz
        filas_matriz = []
        
        for _, fila in df_proy.iterrows():
            f_i = fila["p_fab_i"]
            f_f = fila["p_fab_f"]
            tot_tab = fila["total_tableros"]
            
            # Validación matemática de plazos configurados
            if f_i and f_f and (f_f - f_i).days >= 0:
                dias_fab = (f_f - f_i).days + 1
                tab_por_dia = tot_tab / dias_fab
            else:
                dias_fab = 0
                tab_por_dia = 0.0

            # Estructura descriptiva inicial de las columnas fijas
            registro = {
                "Código": fila["codigo"],
                "Proyecto": fila["proyecto_text"],
                "Cliente": fila["cliente"] if fila["cliente"] else "N/A",
                "Total Tableros": tot_tab,
                "Tableros / Día": round(tab_por_dia, 2)
            }
            
            # Distribución de la demanda diaria en las celdas temporales
            for d in lista_dias:
                nombre_col = d.strftime("%d/%m")  # Formato corto DD/MM para visualización óptima
                if f_i and f_f and f_i <= d <= f_f:
                    registro[nombre_col] = round(tab_por_dia, 2)
                else:
                    registro[nombre_col] = 0.0
                    
            filas_matriz.append(registro)

        # Convertimos la estructura armada en un DataFrame listo para visualización
        df_matriz_final = pd.DataFrame(filas_matriz)

        # 6. Agregar fila de Resumen "TOTAL DIARIO" al final de la matriz
        fila_total = {
            "Código": "🔥 TOTAL DIARIO",
            "Proyecto": "Consolidado Taller",
            "Cliente": "",
            "Total Tableros": df_matriz_final["Total Tableros"].sum(),
            "Tableros / Día": round(df_matriz_final["Tableros / Día"].sum(), 2)
        }
        
        for d in lista_dias:
            nombre_col = d.strftime("%d/%m")
            fila_total[nombre_col] = round(df_matriz_final[nombre_col].sum(), 2)
            
        df_matriz_final = pd.concat([df_matriz_final, pd.DataFrame([fila_total])], ignore_index=True)

        # 7. Renderizado profesional con scroll horizontal nativo
        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("📋 Calendario de Asignación y Demanda de Cortes")
        st.write("Las columnas representan los días de la jornada. Los valores representan la cantidad de tableros completos a procesar por proyecto.")
        
        # st.dataframe permite scroll fluido y fijación visual del índice sin colapsar el navegador
        st.dataframe(df_matriz_final, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Error crítico al generar la matriz de producción proyectada: {e}")
