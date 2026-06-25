import streamlit as st
import pandas as pd
from base_datos import *

def mostrar():
    st.markdown("### 📂 Control de Avances Operativos por Proyecto")
    st.write("Análisis del avance en base al número de tableros requeridos y procesados por frente de trabajo.")

    # 1. ENLACE DIRECTO CON EL EXCEL ALOJADO EN GOOGLE DRIVE (En vivo)
    # ID extraído del enlace oficial provisto para el archivo .xlsx
    FILE_ID = "1ATuNF0Js31QZCo3g3wDUfP3O2PzFjNjW"
    url_excel = f"https://docs.google.com/spreadsheets/d/{FILE_ID}/export?format=xlsx"

    try:
        # Leemos el archivo binario de Excel directamente de la nube especificando la pestaña 'Sheet1'
        df = pd.read_excel(url_excel, sheet_name="Sheet1")
    except Exception as e:
        # Respaldo si hay problemas de conectividad de red temporal
        try:
            df = pd.read_csv("Cortes holzher- OP Gildo 29052026.xlsx - Sheet1.csv")
        except:
            st.error(f"❌ Error de enlace: {e}. No se pudo conectar con Google Drive ni se encontró el archivo de respaldo local.")
            st.stop()
        # Respaldo si hay problemas de conectividad de red temporal
        try:
            df = pd.read_csv("Cortes holzher- OP Gildo 29052026.xlsx - Sheet1.csv")
        except:
            st.error("❌ No se pudo establecer conexión con Google Drive ni se encontró el archivo de respaldo.")
            st.stop()

    # Limpieza de registros y descarte de filas vacías estructurales de la plantilla
    if "Cant" in df.columns:
        df = df.dropna(subset=["Cant"])
        df["Cant"] = pd.to_numeric(df["Cant"], errors="coerce")
        df = df[df["Cant"] > 0]
    else:
        st.error("❌ La columna 'Cant' no se encuentra en el archivo. Verifique los encabezados.")
        st.stop()

    # 2. SELECCIÓN DE PROYECTO (Mapeo dinámico por OP o columna Proyecto)
    # Si la columna 'Proyecto' no está escrita, usamos 'OP' para identificar los frentes de trabajo de forma limpia
    if "Proyecto" in df.columns:
        columna_agrupadora = "Proyecto"
    elif "OP" in df.columns:
        columna_agrupadora = "OP"
        # Convertimos a string limpio sin decimales para la visualización del menú
        df["OP"] = df["OP"].astype(str).str.replace(".0", "", regex=False).str.strip()
    else:
        st.error("❌ El archivo no cuenta con una columna 'Proyecto' o 'OP' para indexar frentes.")
        st.stop()

    lista_proyectos = sorted(df[columna_agrupadora].dropna().unique())

    col_filtro, _ = st.columns([2, 2])
    with col_filtro:
        proyecto_seleccionado = st.selectbox(f"🔍 Seleccione el identificador ({columna_agrupadora}) a evaluar:", lista_proyectos)

    # Filtrado estricto del proyecto seleccionado por el usuario
    df_filtrado = df[df[columna_agrupadora] == proyecto_seleccionado].copy()

    # 3. CONSTRUCCIÓN DE LA MATRIZ DE TABLEROS
    if not df_filtrado.empty:
        # A. Normalización de Tipologías de Mueble
        if "Tipo" in df_filtrado.columns:
            df_filtrado["Mueble_Clase"] = df_filtrado["Tipo"].astype(str).str.strip().str.capitalize()
            df_filtrado.loc[~df_filtrado["Mueble_Clase"].isin(["Cocina", "Closet", "Baño"]), "Mueble_Clase"] = "Otros"
        else:
            df_filtrado["Mueble_Clase"] = "Otros"

        # B. Segmentación de Familias de Materiales (Lógica Corregida sin Marcas)
        def clasificar_material(material_nombre):
            # Convertimos a mayúsculas y limpiamos espacios para un escaneo infalible
            mat_str = str(material_nombre).upper().strip()
            
            # 1. Regla para Folio (Evaluación estricta por tipo de material)
            if "FOLIO" in mat_str:
                return "Folio"
            
            # 2. Regla para Tapa
            elif "TAPA" in mat_str:
                return "Tapa"
            
            # 3. Regla para Melamina Blanco (Ahora capturará correctamente 'Blanco - DUROLAC')
            elif "BLANCO" in mat_str:
                return "Melamina Blanco"
            
            # 4. Regla para Melamina de Color (Por descarte: cualquier otra combinación o marca)
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

        # Validación estructural rígida de las 4 columnas del reporte de ingeniería
        columnas_diseno = ["Melamina Blanco", "Melamina de Color", "Tapa", "Folio (Durolac)"]
        for col in columnas_diseno:
            if col not in matriz_consumo.columns:
                matriz_consumo[col] = 0.0
        matriz_consumo = matriz_consumo[columnas_diseno]

        # Estructura rígida de 4 filas requerida (Usa la variable sin tilde)
        filas_diseno = ["Cocina", "Closet", "Baño", "Otros"]
        matriz_consumo = matriz_consumo.reindex(filas_diseno, fill_value=0.0)

        # Inserción de fila de totales generales
        matriz_totales = matriz_consumo.copy()
        matriz_totales.loc["🔥 TOTAL REQUERIDO"] = matriz_totales.sum()

        # Formateo visual numérico para alta gerencia
        matriz_vista = matriz_totales.map(lambda x: f"{round(x, 2):,.2f} Unid" if x > 0 else "0.00 Unid")

        st.markdown("#### 🧱 Matriz de Consumo de Tableros por Tipología de Mueble")
        st.dataframe(matriz_vista, use_container_width=True)

        # 4. MAPEO DE UBICACIONES Y FRENTES ATENDIDOS
        st.markdown("#### 📍 Mapeo de Ubicaciones y Frentes Atendidos")
        iconos_muebles = {"Cocina": "🍳", "Closet": "🛏️", "Baño": "🚿", "Otros": "📦"}
        
        for clase in filas_diseno:
            df_mueble = df_filtrado[df_filtrado["Mueble_Clase"] == clase]
            ico = iconos_muebles.get(clase, "▪️")
            
            if not df_mueble.empty and "Ubicación" in df_mueble.columns:
                # Quitamos nulos y espacios en blanco de los pisos
                df_mueble["Ubicación"] = df_mueble["Ubicación"].astype(str).str.replace(".0", "", regex=False).str.strip()
                pisos = df_mueble["Ubicación"].unique()
                pisos_validos = [p for p in pisos if p != "" and p.lower() != "nan"]
                
                if pisos_validos:
                    string_pisos = ", ".join(sorted(pisos_validos))
                    st.info(f"**{ico} {clase}s Procesados** -> Ubicaciones consideradas: `{string_pisos}`")
                else:
                    st.write(f"{ico} {clase}s: Sin ubicaciones asignadas aún.")
            else:
                st.write(f"{ico} {clase}s: Sin registros de manufactura en este rango.")
    else:
        st.info("📂 No se detectaron requerimientos de cortes asignados al proyecto seleccionado.")
