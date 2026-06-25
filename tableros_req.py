import streamlit as st
import pandas as pd
from base_datos import *

def mostrar():
    st.markdown("### 📂 Control de Avances Operativos por Proyecto")
    st.write("Análisis del avance en base al número de tableros requeridos y procesados por frente de trabajo.")

    # 1. ENLACE DIRECTO CON EL EXCEL ALOJADO EN GOOGLE DRIVE (En vivo)
    FILE_ID = "1ATuNF0Js31QZCo3g3wDUfP3O2PzFjNjW"
    url_excel = f"https://docs.google.com/spreadsheets/d/{FILE_ID}/export?format=xlsx"

    try:
        df = pd.read_excel(url_excel, sheet_name="Sheet1")
    except Exception as e:
        try:
            df = pd.read_csv("Cortes holzher- OP Gildo 29052026.xlsx - Sheet1.csv")
        except:
            st.error(f"❌ Error de enlace: {e}. No se pudo conectar con Google Drive ni se encontró el archivo de respaldo local.")
            st.stop()

    # Limpieza de registros y descarte de filas vacías
    if "Cant" in df.columns:
        df = df.dropna(subset=["Cant"])
        df["Cant"] = pd.to_numeric(df["Cant"], errors="coerce")
        df = df[df["Cant"] > 0]
    else:
        st.error("❌ La columna 'Cant' no se encuentra en el archivo. Verifique los encabezados.")
        st.stop()

    # 2. SELECCIÓN DE PROYECTO
    if "Proyecto" in df.columns:
        columna_agrupadora = "Proyecto"
    elif "OP" in df.columns:
        columna_agrupadora = "OP"
        df["OP"] = df["OP"].astype(str).str.replace(".0", "", regex=False).str.strip()
    else:
        st.error("❌ El archivo no cuenta con una columna 'Proyecto' o 'OP' para indexar frentes.")
        st.stop()

    lista_proyectos = sorted(df[columna_agrupadora].dropna().unique())

    col_filtro, _ = st.columns([2, 2])
    with col_filtro:
        proyecto_seleccionado = st.selectbox(f"🔍 Seleccione el identificador ({columna_agrupadora}) a evaluar:", lista_proyectos)

    df_filtrado = df[df[columna_agrupadora] == proyecto_seleccionado].copy()

    # 3. CONSTRUCCIÓN DE LA MATRIZ DE TABLEROS
    if not df_filtrado.empty:
        # A. Normalización de Tipologías de Mueble (Lógica de Mapeo Flexible)
        if "Tipo" in df_filtrado.columns:
            tipo_upper = df_filtrado["Tipo"].astype(str).str.strip()
            df_filtrado["Mueble_Clase"] = "Otros"
            
            df_filtrado.loc[tipo_upper.str.contains("CLOSET|W Y CLOSET|VESTIDOR", case=False, na=False), "Mueble_Clase"] = "Closet"
            df_filtrado.loc[tipo_upper.str.contains("COCINA", case=False, na=False), "Mueble_Clase"] = "Cocina"
            df_filtrado.loc[tipo_upper.str.contains("BAÑO", case=False, na=False), "Mueble_Clase"] = "Baño"
            df_filtrado.loc[tipo_upper.str.contains("LAVANDERIA|LAVANDERÍA", case=False, na=False), "Mueble_Clase"] = "Lavanderia"
        else:
            df_filtrado["Mueble_Clase"] = "Otros"

        # B. Segmentación de Familias de Materiales (Lógica Corregida sin Marcas)
        def clasificar_material(material_nombre):
            mat_str = str(material_nombre).upper().strip()
            
            if "FOLIO" in mat_str:
                return "Folio"
            elif "TAPA" in mat_str:
                return "Tapa"
            elif "BLANCO" in mat_str:
                return "Melamina Blanco"
            else:
                return "Melamina de Color"

        if "Material" in df_filtrado.columns:
            df_filtrado["Categoria_Material"] = df_filtrado["Material"].apply(clasificar_material)
        else:
            df_filtrado["Categoria_Material"] = "Melamina Blanco"

        # C. Generación de la Pivot Table Operativa
        matriz_consumo = df_filtrado.pivot_table(
            index="Mueble_Clase",
            columns="Categoria_Material",
            values="Cant",
            aggfunc="sum"
        ).fillna(0.0)

        # Validación estructural rígida de las 4 columnas del reporte
        columnas_diseno = ["Melamina Blanco", "Melamina de Color", "Tapa", "Folio"]
        for col in columnas_diseno:
            if col not in matriz_consumo.columns:
                matriz_consumo[col] = 0.0
        matriz_consumo = matriz_consumo[columnas_diseno]

        # Validación estructural rígida de las 5 filas del reporte de ingeniería
        filas_diseno = ["Cocina", "Closet", "Baño", "Lavanderia", "Otros"]
        matriz_consumo = matriz_consumo.reindex(filas_diseno, fill_value=0.0)

        # Inserción de la fila de totales generales (UNA SOLA VEZ)
        matriz_totales = matriz_consumo.copy()
        matriz_totales.loc["🔥 TOTAL REQUERIDO"] = matriz_totales.sum()

        # Formateo visual numérico profesional
        matriz_vista = matriz_totales.map(lambda x: f"{round(x, 2):,.2f} Unid" if x > 0 else "0.00 Unid")

        st.markdown("#### 🧱 Matriz de Consumo de Tableros por Tipología de Mueble")
        st.dataframe(matriz_vista, use_container_width=True)

        # 4. MAPEO DE UBICACIONES Y FRENTES ATENDIDOS
        st.markdown("#### 📍 Mapeo de Ubicaciones y Frentes Atendidos")
        iconos_muebles = {"Cocina": "🍳", "Closet": "🛏️", "Baño": "🚿", "Lavanderia": "🧺", "Otros": "📦"}
        
        for clase in filas_diseno:
            df_mueble = df_filtrado[df_filtrado["Mueble_Clase"] == clase]
            ico = iconos_muebles.get(clase, "▪️")
            
            if not df_mueble.empty and "Ubicación" in df_mueble.columns:
                pisos = df_mueble["Ubicación"].dropna().unique()
                
                # Filtro de descarte seguro para omitir nulos, vacíos y ruidos numéricos de Excel
                pisos_validos = []
                for p in pisos:
                    p_str = str(p).replace(".0", "").strip()
                    if p_str != "" and p_str.lower() != "nan" and p_str.lower() != "<na>":
                        pisos_validos.append(p_str)
                
                if pisos_validos:
                    string_pisos = ", ".join(sorted(pisos_validos))
                    st.info(f"**{ico} {clase}s Procesados** -> Ubicaciones consideradas: `{string_pisos}`")
                else:
                    st.write(f"{ico} {clase}s: Sin ubicaciones asignadas aún.")
            else:
                st.write(f"{ico} {clase}s: Sin registros de manufactura en este rango.")
    else:
        st.info("📂 No se detectaron requerimientos de cortes asignados al proyecto seleccionado.")
