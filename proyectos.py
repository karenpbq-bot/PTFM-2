import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from base_datos import crear_proyecto, obtener_proyectos, eliminar_proyecto, obtener_supervisores, conectar

def mostrar():
    st.title("📁 Gestión de Proyectos Nuevo")
    
    tab1, tab2 = st.tabs(["🆕 Registrar Proyecto Nuevo", "📋 Listado y Búsqueda"])

    with tab1:
        st.subheader("Configuración y Cronograma Planificado")
        
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

        st.write("### ⚖️ Distribución de Tiempo por Etapa (%)")
        etapas_nombres = ["Diseño", "Fabricación", "Traslado", "Instalación", "Entrega"]
        defaults = [15, 40, 10, 25, 10]
        pcts = {}
        cols_pct = st.columns(5)
        
        for i, et in enumerate(etapas_nombres):
            pcts[et] = cols_pct[i].number_input(f"{et} %", 0, 100, defaults[i])

        # --- LÓGICA DE CÁLCULO DE CRONOGRAMA ---
        st.divider()
        dias_totales = (f_fin - f_ini).days
        
        if dias_totales <= 0:
            st.error("La fecha de término debe ser posterior a la de inicio.")
        else:
            cronograma_data = []
            fecha_aux = f_ini
            
            for et in etapas_nombres:
                dias_etapa = round(dias_totales * (pcts[et] / 100))
                # Evitamos que una etapa tenga menos de 1 día si el proyecto es corto
                f_f = fecha_aux + timedelta(days=max(0, dias_etapa - 1))
                cronograma_data.append({
                    "Etapa": et,
                    "Inicio": fecha_aux,
                    "Fin": f_f,
                    "Días": dias_etapa
                })
                fecha_aux = f_f + timedelta(days=1)

            # Previsualización compacta
            df_previs = pd.DataFrame(cronograma_data)
            df_previs["Inicio"] = df_previs["Inicio"].apply(lambda x: x.strftime("%d/%m/%Y"))
            df_previs["Fin"] = df_previs["Fin"].apply(lambda x: x.strftime("%d/%m/%Y"))
            st.write("#### 🔍 Previsualización del Cronograma Planificado")
            st.table(df_previs[["Etapa", "Inicio", "Fin", "Días"]])

            if st.button("🚀 REGISTRAR PROYECTO NUEVO"):
                if not codigo or not nombre:
                    st.warning("Completa Código y Nombre.")
                elif sum(pcts.values()) != 100:
                    st.error(f"La suma debe ser 100% (Actual: {sum(pcts.values())}%)")
                else:
                    # Mapeo exacto a las columnas de tu DB
                    datos_nube = {
                        "codigo": codigo, "proyecto_text": nombre, "cliente": cliente,
                        "partida": par, "f_ini": str(f_ini), "f_fin": str(f_fin),
                        "supervisor_id": dict_sups[sup_nom], "estatus": "Activo", "avance": 0,
                        "p_dis_i": str(cronograma_data[0]["Inicio"]), "p_dis_f": str(cronograma_data[0]["Fin"]),
                        "p_fab_i": str(cronograma_data[1]["Inicio"]), "p_fab_f": str(cronograma_data[1]["Fin"]),
                        "p_tra_i": str(cronograma_data[2]["Inicio"]), "p_tra_f": str(cronograma_data[2]["Fin"]),
                        "p_ins_i": str(cronograma_data[3]["Inicio"]), "p_ins_f": str(cronograma_data[3]["Fin"]),
                        "p_ent_i": str(cronograma_data[4]["Inicio"]), "p_ent_f": str(cronograma_data[4]["Fin"])
                    }
                    
                    try:
                        conectar().table("proyectos").insert(datos_nube).execute()
                        st.success(f"✅ Proyecto {codigo} creado con éxito.")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Error de base de datos: {e}")

    with tab2:
        st.subheader("Listado Maestro")
        bus = st.text_input("🔍 Filtro Universal", placeholder="Código, nombre o cliente")
        df_p = obtener_proyectos(bus)
        if not df_p.empty:
            st.dataframe(df_p[['codigo', 'proyecto_text', 'cliente', 'avance']], hide_index=True)
