import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from base_datos import crear_proyecto, obtener_proyectos, eliminar_proyecto, obtener_supervisores, conectar

def mostrar():
    st.title("📁 Gestión de Proyectos Nuevo")
    
    tab1, tab2 = st.tabs(["🆕 Registrar Proyecto Nuevo", "📋 Listado y Búsqueda"])

    with tab1:
        st.subheader("Configuración y Cronograma Planificado")
        
        # 1. DATOS BÁSICOS
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            codigo = c1.text_input("Código (DNI)", placeholder="Ej: PTF-001")
            nombre = c2.text_input("Nombre del Proyecto")
            cliente = c3.text_input("Cliente")
            
            par = c1.text_input("Partida")
            df_sups = obtener_supervisores()
            dict_sups = {r['nombre_real']: r['id'] for _, r in df_sups.iterrows()}
            sup_nom = c2.selectbox("Responsable:", options=list(dict_sups.keys()))
            
            f_ini = c1.date_input("Fecha Inicio Global", value=date.today())
            f_fin = c2.date_input("Fecha Término Global", value=date.today() + timedelta(days=30))

        # 2. PONDERACIÓN DE ETAPAS
        st.write("### ⚖️ Distribución de Tiempo (%)")
        etapas = ["Diseño", "Fabricación", "Traslado", "Instalación", "Entrega"]
        pcts = {}
        cols_pct = st.columns(5)
        # Valores por defecto sugeridos para sumar 100
        defaults = [15, 40, 10, 25, 10]
        
        for i, et in enumerate(etapas):
            pcts[et] = cols_pct[i].number_input(f"{et} %", 0, 100, defaults[i])

        # 3. LÓGICA DE CÁLCULO Y PREVISUALIZACIÓN
        st.divider()
        dias_totales = (f_fin - f_ini).days
        
        if dias_totales <= 0:
            st.error("La fecha de término debe ser posterior a la de inicio.")
        else:
            # Calculamos el cronograma temporal para mostrarlo
            cronograma_calculado = []
            fecha_aux = f_ini
            
            for et in etapas:
                dias_etapa = round(dias_totales * (pcts[et] / 100))
                f_f = fecha_aux + timedelta(days=max(0, dias_etapa - 1))
                cronograma_calculado.append({
                    "Etapa": et,
                    "Inicio": fecha_aux.strftime("%d/%m/%Y"),
                    "Fin": f_f.strftime("%d/%m/%Y"),
                    "dias": dias_etapa,
                    "raw_i": str(fecha_aux),
                    "raw_f": str(f_f)
                })
                fecha_aux = f_f + timedelta(days=1)

            st.write("#### 🔍 Previsualización del Cronograma")
            st.table(pd.DataFrame(cronograma_calculado)[["Etapa", "Inicio", "Fin", "dias"]])

            # 4. BOTÓN DE REGISTRO
            if st.button("🚀 REGISTRAR PROYECTO NUEVO"):
                if not codigo or not nombre:
                    st.warning("El Código y Nombre son obligatorios.")
                elif sum(pcts.values()) != 100:
                    st.error(f"La suma de porcentajes debe ser 100% (Actual: {sum(pcts.values())}%)")
                else:
                    # Preparamos el diccionario para Supabase incluyendo las fechas calculadas
                    datos_nube = {
                        "codigo": codigo,
                        "proyecto_text": nombre,
                        "cliente": cliente,
                        "partida": par,
                        "f_ini": str(f_ini),
                        "f_fin": str(f_fin),
                        "supervisor_id": dict_sups[sup_nom],
                        "estatus": "Activo",
                        "avance": 0,
                        # Mapeo de fechas calculadas a las columnas de la DB
                        "p_dis_i": cronograma_calculado[0]["raw_i"], "p_dis_f": cronograma_calculado[0]["raw_f"],
                        "p_fab_i": cronograma_calculado[1]["raw_i"], "p_fab_f": cronograma_calculado[1]["raw_f"],
                        "p_tra_i": cronograma_calculado[2]["raw_i"], "p_tra_f": cronograma_calculado[2]["raw_f"],
                        "p_ins_i": cronograma_calculado[3]["raw_i"], "p_ins_f": cronograma_calculado[3]["raw_f"],
                        "p_ent_i": cronograma_calculado[4]["raw_i"], "p_ent_f": cronograma_calculado[4]["raw_f"]
                    }
                    
                    try:
                        conectar().table("proyectos").insert(datos_nube).execute()
                        st.success(f"✅ Proyecto {codigo} registrado con cronograma automático.")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Error al guardar en nube: {e}")

    with tab2:
        st.subheader("Listado Maestro")
        bus = st.text_input("🔍 Buscar...", placeholder="Escribe código, nombre o cliente")
        df_p = obtener_proyectos(bus)
        if not df_p.empty:
            st.dataframe(df_p[['codigo', 'proyecto_text', 'cliente', 'partida', 'avance']], hide_index=True)
