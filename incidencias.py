import streamlit as st
import pandas as pd
import io
from datetime import date
from base_datos import conectar, obtener_proyectos, registrar_incidencia_detallada, obtener_incidencias_resumen

def mostrar():
    st.header("⚠️ Gestión de Requerimientos")
    
    # 3 Pestañas solicitadas
    tab_p, tab_m, tab_h = st.tabs(["🧩 Requerimiento de Piezas", "📦 Requerimiento de Material", "📜 Historial de Reportes"])

    df_p = obtener_proyectos("")
    dict_proyectos = {row['proyecto_text']: row['id'] for _, row in df_p.iterrows()}
    MOTIVOS = ["Faltante", "Cambio", "Otros"]

    # --- PESTAÑA 1: PIEZAS ---
    with tab_p:
        st.subheader("Configuración del Pedido de Piezas")
        col1, col2 = st.columns(2)
        proy_p = col1.selectbox("Proyecto:", list(dict_proyectos.keys()), key="proy_p")
        motivo_p = col2.selectbox("Motivo del Requerimiento:", MOTIVOS, key="mot_p")
        
        if 'tmp_piezas' not in st.session_state: st.session_state.tmp_piezas = []

        with st.expander("➕ Agregar Pieza a la Matriz", expanded=True):
            # Atributos técnicos solicitados
            c1, c2, c3 = st.columns([2,1,1])
            desc = c1.text_input("Descripción de la pieza")
            cant = c2.number_input("Cantidad", min_value=1, key="p_cant")
            ubi = c3.text_input("Ubicación", placeholder="Ej: B101")
            
            c4, c5, c6, c7 = st.columns(4)
            veta = c4.selectbox("Veta", ["SI", "NO"])
            nveta = c5.text_input("No Veta")
            material = c6.text_input("Material / Color")
            rot = c7.selectbox("Rotación", ["0°", "90°", "180°", "270°"])
            
            st.write("**Tapacantos**")
            t1, t2, t3, t4 = st.columns(4)
            tf = t1.text_input("Frontal (F)")
            tp = t2.text_input("Posterior (P)")
            td = t3.text_input("Derecho (D)")
            ti = t4.text_input("Izquierdo (I)")
            
            obs = st.text_area("Observaciones específicas de la pieza")
            
            if st.button("Añadir a Matriz"):
                st.session_state.tmp_piezas.append({
                    "descripcion": desc, "veta": veta, "no_veta": nveta, "cantidad": cant,
                    "ubicacion": ubi, "material": material, "tc_frontal": tf, "tc_posterior": tp,
                    "tc_derecho": td, "tc_izquierdo": ti, "rotacion": rot, "observaciones": obs
                })

        if st.session_state.tmp_piezas:
            st.write("### Matriz de Piezas Solicitadas")
            st.dataframe(pd.DataFrame(st.session_state.tmp_piezas), use_container_width=True)
            if st.button("🚀 Enviar Requerimiento de Piezas"):
                registrar_incidencia_detallada(dict_proyectos[proy_p], "Piezas", motivo_p, st.session_state.tmp_piezas, [], st.session_state.id_usuario)
                st.session_state.tmp_piezas = []
                st.success("Enviado con éxito"); st.rerun()

    # --- PESTAÑA 2: MATERIALES ---
    with tab_m:
        st.subheader("Configuración del Pedido de Materiales")
        col1m, col2m = st.columns(2)
        proy_m = col1m.selectbox("Proyecto:", list(dict_proyectos.keys()), key="proy_m")
        motivo_m = col2m.selectbox("Motivo del Requerimiento:", MOTIVOS, key="mot_m")
        
        if 'tmp_mats' not in st.session_state: st.session_state.tmp_mats = []

        with st.container(border=True):
            cm1, cm2 = st.columns([3,1])
            m_desc = cm1.text_input("Descripción (Accesorios, Pintura, Cerrajería...)")
            m_cant = cm2.number_input("Cant.", min_value=1, key="m_cant")
            m_obs = st.text_input("Observaciones de material")
            if st.button("➕ Agregar Material"):
                st.session_state.tmp_mats.append({"descripcion": m_desc, "cantidad": m_cant, "observaciones": m_obs})

        if st.session_state.tmp_mats:
            st.write("### Lista de Materiales")
            st.table(pd.DataFrame(st.session_state.tmp_mats))
            if st.button("🚀 Enviar Requerimiento de Materiales"):
                registrar_incidencia_detallada(dict_proyectos[proy_m], "Materiales", motivo_m, [], st.session_state.tmp_mats, st.session_state.id_usuario)
                st.session_state.tmp_mats = []
                st.success("Enviado con éxito"); st.rerun()

    # --- PESTAÑA 3: HISTORIAL ---
    with tab_h:
        historial = obtener_incidencias_resumen()
        if not historial.empty:
            for _, inc in historial.iterrows():
                with st.expander(f"REQ-{inc['id']} | {inc['proyecto_text']} | {inc['tipo_requerimiento']} ({inc['categoria']})"):
                    # Lógica de estados y exportación ya definida en la base anterior
                    st.write(f"Estado Actual: **{inc['estado']}**")
                    # Botón para descargar Excel (Pestañas automáticas según tipo)
                    # ... (Aquí va el código de io.BytesIO que genera las pestañas)
        else:
            st.info("No hay reportes registrados.")