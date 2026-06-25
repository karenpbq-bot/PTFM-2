import streamlit as st
import pandas as pd
from base_datos import * # Consistencia con la arquitectura del sistema

def mostrar():
    st.markdown("### 📂 Control de Avances Operativos por Proyecto")
    st.write("Análisis del avance en base al número de tableros requeridos y procesados por frente de trabajo.")

    # 1. CONEXIÓN Y CARGA DE DATOS DESDE EL SPREADSHEET
    try:
        # Intentamos leer la tabla consolidada desde tu conector habitual
        df = cargar_datos_desde_sheets()  
    except Exception as e:
        df = st.session_state.get("df_cortes_proyectos", pd.DataFrame())

    # Verificación de respaldo en caso de inicialización o archivo vacío
    if df.empty:
        st.info("🔄 Cargando base de datos de proyectos o configurando el conector...")
        try:
            # Intentar leer el CSV estructurado de respaldo para que la app nunca falle
            df = pd.read_csv("Cortes holzher- OP Gildo 29052026.xlsx - Sheet1.csv")
            if "Proyecto" not in df.columns:
                df["Proyecto"] = "Edificio Gildo"
        except:
            st.warning("⚠️ Conecte el módulo a la base de datos de Google Drive para visualizar datos en vivo.")
            st.stop()

    # Limpieza preventiva de filas vacías provenientes del Sheets
    df = df.dropna(subset=["Cant"])
    df = df[df["Cant"] > 0]

    # 2. FILTRO DE SELECCIÓN DE PROYECTO (Un proyecto a la vez)
    if "Proyecto" in df.columns:
        lista_proyectos = sorted(df["Proyecto"].dropna().astype(str).unique())
    else:
        df.columns = [col.strip().capitalize() for col in df.columns]
        if "Proyecto" in df.columns:
            lista_proyectos = sorted(df["Proyecto"].dropna().astype(str).unique())
        else:
            st.error("❌ No se encontró la columna 'Proyecto' en el archivo cargado. Verifique los encabezados.")
            st.stop()

    col_filtro, _ = st.columns([2, 2])
    with col_filtro:
        proyecto_seleccionado = st.selectbox("🔍 Seleccione el Proyecto a evaluar:", lista_proyectos)

    # Filtrado inmediato según la selección
    df_filtrado = df[df["Proyecto"] == proyecto_seleccionado].copy()

    # 3. CONSTRUCCIÓN DE LA MATRIZ DE TABLEROS
    if not df_filtrado.empty:
        # A. Clasificación de Muebles (Cocina, Closet, Baño, Otros)
        df_filtrado["Mueble_Clase"] = df_filtrado["Tipo"].astype(str).str.strip().str.capitalize()
        df_filtrado.loc[~df_filtrado["Mueble_Clase"].isin(["Closet", "Cocina", "Baño"]), "Mueble_Clase"] = "Otros"

        # B. Clasificación de Materiales (Melamina Blanco, Melamina de Color, Tapa, Folio)
        def clasificar_material(material_nombre):
            mat_str = str(material_nombre).upper().strip()
            if "DUROLAC" in mat_str or "FOLIO" in mat_str:
                return "Folio (Durolac)"
            elif "TAPA" in mat_str:
                return "Tapa"
            elif "BLANCO" in mat_str:
                return "Melamina Blanco"
            else:
                return "Melamina de Color"

        df_filtrado["Categoria_Material"] = df_filtrado["Material"].apply(clasificar_material)

        # C. Generación de la Tabla de Contingencia (Pivot Table)
        matriz_consumo = df_filtrado.pivot_table(
            index="Mueble_Clase",
            columns="Categoria_Material",
            values="Cant",
            aggfunc="sum"
        ).fillna(0.0)

        # Estructura rígida de 4 columnas requerida
        columnas_diseno = ["Melamina Blanco", "Melamina de Color", "Tapa", "Folio (Durolac)"]
        for col in columnas_diseno:
            if col not in matriz_consumo.columns:
                matriz_consumo[col] = 0.0
        matriz_consumo = matriz_consumo[columnas_diseno]

        # Estructura rígida de 4 filas requerida
        filas_diseno = ["Cocina", "Closet", "Baño", "Otros"]
        matriz_consumo = matriz_consumo.reindex(filas_diseno, fill_value=0.0)

        # Cálculo de la fila final de Totales Requeridos
        matriz_totales = matriz_consumo.copy()
        matriz_totales.loc["🔥 TOTAL REQUERIDO"] = matriz_totales.sum()

        # Formateo estricto de celdas para lectura profesional
        matriz_vista = matriz_totales.map(lambda x: f"{round(x, 2):,.2f} Unid" if x > 0 else "0.00 Unid")

        st.markdown("#### 🧱 Matriz de Consumo de Tableros por Tipología de Mueble")
        st.dataframe(matriz_vista, use_container_width=True)

        # 4. MAPEO DINÁMICO DE UBICACIONES (Pisos considerados)
        st.markdown("#### 📍 Mapeo de Ubicaciones y Frentes Atendidos")
        
        iconos_muebles = {"Cocina": "🍳", "Closet": "🛏️", "Baño": "🚿", "Otros": "📦"}
        
        for clase in filas_diseno:
            df_mueble = df_filtrado[df_filtrado["Mueble_Clase"] == clase]
            ico = iconos_muebles.get(clase, "▪️")
            
            if not df_mueble.empty and "Ubicación" in df_mueble.columns:
                pisos = df_mueble["Ubicación"].dropna().astype(str).str.strip().unique()
                pisos_validos = [p for p in pisos if p != "" and p.lower() != "nan"]
                
                if pisos_validos:
                    string_pisos = ", ".join(sorted(pisos_validos))
                    st.info(f"**{ico} {clase}s Procesados** -> Pisos considerados en este proyecto: `{string_pisos}`")
                else:
                    st.write(f"{ico} {clase}s: Sin ubicaciones específicas detalladas.")
            else:
                st.write(f"{ico} {clase}s: Sin registros de manufactura en este rango.")
    else:
        st.info("📂 No se detectaron requerimientos de cortes asignados al proyecto seleccionado.")
