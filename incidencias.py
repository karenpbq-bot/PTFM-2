import streamlit as st
import pandas as pd
import io
from datetime import datetime
from base_datos import conectar, obtener_proyectos, registrar_incidencia_detallada, obtener_incidencias_resumen, marcar_atencion_incidencia, guardar_obs_gestion, obtener_datos_reporte_incidencias

def mostrar():
    st.header("⚠️ Gestión de Requerimientos")
    
    # Memoria temporal para consolidar antes de enviar
    if 'tmp_piezas' not in st.session_state: st.session_state.tmp_piezas = []
    if 'tmp_mats' not in st.session_state: st.session_state.tmp_mats = []

    tab_p, tab_m, tab_h = st.tabs(["🧩 Requerimiento de Piezas", "📦 Requerimiento de Material", "📜 Historial de Requerimientos"])

    df_p = obtener_proyectos("")
    dict_proyectos = {row['proyecto_text']: row['id'] for _, row in df_p.iterrows()}
    MOTIVOS = ["Faltante", "Cambio", "Pieza Dañada", "Otros"]

    # --- PESTAÑA 1: PIEZAS ---
    with tab_p:
        st.subheader("Configuración del Bloque de Piezas")
        c1, c2 = st.columns(2)
        proy_p = c1.selectbox("Proyecto:", list(dict_proyectos.keys()), key="proy_p_sel")
        motivo_p = c2.selectbox("Motivo:", MOTIVOS, key="mot_p_sel")
        
        # ... (dentro de la Pestaña 1: Piezas)
        with st.expander("➕ Agregar Pieza a la Matriz", expanded=True):
            col_a, col_b, col_c = st.columns([2,1,1])
            desc = col_a.text_input("Descripción de la pieza", key="in_p_desc")
            cant = col_b.number_input("Cantidad", min_value=1, key="in_p_cant")
            ubi = col_c.text_input("Ubicación", key="in_p_ubi")
            
            col_d, col_e, col_f, col_g = st.columns(4)
            # ETIQUETAS CORREGIDAS SEGÚN TU SOLICITUD
            veta = col_d.number_input("Veta (Dimención)", min_value=0, key="in_p_veta")
            nveta = col_e.number_input("No Veta (Dimención)", min_value=0, key="in_p_nveta")
            mat = col_f.text_input("Material / Color", key="in_p_mat")
            rot = col_g.selectbox("Rotación", [0, 1], help="0: No / 1: Si", key="in_p_rot")
            
           # --- AJUSTE DE TAPACANTOS (Definición de columnas para evitar NameError) ---
            st.write("**Tapacantos (mm)**")
            t1, t2, t3, t4 = st.columns(4) # <--- ESTO FALTABA
            
            tf = t1.text_input("Frontal (F)", key="p_tf_in")
            tp = t2.text_input("Posterior (P)", key="p_tp_in")
            td = t3.text_input("Derecho (D)", key="p_td_in")
            ti = t4.text_input("Izquierdo (I)", key="p_ti_in")
            
            # BLOQUE DE OBSERVACIONES (Recuperado y con Key única)
            obs = st.text_area("Observaciones específicas de la pieza", key="p_obs_in")
            
            if st.button("➕ Añadir a Matriz", key="btn_add_p"):
                # Aseguramos que se guarden todos los campos técnicos y dimensiones
                st.session_state.tmp_piezas.append({
                    "descripcion": desc, 
                    "veta": veta, 
                    "no_veta": nveta, 
                    "cantidad": cant,
                    "ubicacion": ubi, 
                    "material": mat, 
                    "tc_frontal": tf, 
                    "tc_posterior": tp,
                    "tc_derecho": td, 
                    "tc_izquierdo": ti, 
                    "rotacion": rot, 
                    "observaciones": obs
                })
                st.rerun()
        if st.session_state.tmp_piezas:
            st.write("### 📋 Bloque de Piezas Consolidado")
            st.dataframe(pd.DataFrame(st.session_state.tmp_piezas), use_container_width=True)
            if st.button("🚀 ENVIAR REQUERIMIENTO (PIEZAS)", type="primary"):
                registrar_incidencia_detallada(dict_proyectos[proy_p], "Piezas", motivo_p, st.session_state.tmp_piezas, [], st.session_state.get('id_usuario'))
                st.session_state.tmp_piezas = []
                st.success("Requerimiento enviado con éxito."); st.rerun()

    # --- PESTAÑA 2: MATERIALES ---
    with tab_m:
        st.subheader("Configuración del Bloque de Materiales")
        cm1, cm2 = st.columns(2)
        proy_m = cm1.selectbox("Proyecto:", list(dict_proyectos.keys()), key="proy_m_sel")
        motivo_m = cm2.selectbox("Motivo:", MOTIVOS, key="mot_m_sel")

        with st.container(border=True):
            ma, mb, mc = st.columns([2,1,1])
            m_desc = ma.text_input("Descripción Material", key="in_m_desc")
            m_cant = mb.number_input("Cant.", min_value=1, key="in_m_cant")
            m_obs = mc.text_input("Observaciones", key="in_m_obs")
            
            if st.button("➕ Añadir Material"):
                st.session_state.tmp_mats.append({"descripcion": m_desc, "cantidad": m_cant, "observaciones": m_obs})
                st.rerun()

        if st.session_state.tmp_mats:
            st.table(pd.DataFrame(st.session_state.tmp_mats))
            if st.button("🚀 ENVIAR CONSOLIDADO DE MATERIALES"):
                registrar_incidencia_detallada(dict_proyectos[proy_m], "Materiales", motivo_m, [], st.session_state.tmp_mats, st.session_state.get('id_usuario'))
                st.session_state.tmp_mats = []
                st.success("Enviado con éxito"); st.rerun()

    # --- PESTAÑA 3: HISTORIAL (REEMPLAZO TOTAL) ---
    with tab_h:
        st.subheader("📋 Seguimiento de Requerimientos")
        
        # 1. BOTÓN DE EXPORTACIÓN (Con todos los detalles)
        df_export = obtener_datos_reporte_incidencias() # Esta función debe traer los 'detalles'
        if not df_export.empty:
            st.download_button("📥 Descargar Reporte Completo (Excel/CSV)", 
                             df_export.to_csv(index=False).encode('utf-8'), 
                             "reporte_requerimientos.csv", "text/csv")
        
        st.divider()

        # 2. LISTADO SIMPLIFICADO CON CHECKS
        historial = obtener_incidencias_resumen()
        if not historial.empty:
            for _, inc in historial.iterrows():
                with st.expander(f"REQ-{inc['id']} | {inc['proyecto_text']} | {inc['tipo_requerimiento']}"):
                    st.write(f"**Motivo:** {inc['categoria']} | **Estado:** {inc['estado']}")
                    
                    # Matriz de Seguimiento (Checks y Fechas)
                    c1, c2, c3 = st.columns(3)
                    
                    with c1:
                        v_alm = st.checkbox("Almacén", value=inc.get('check_almacen', False), key=f"ch_alm_{inc['id']}")
                        if v_alm != inc.get('check_almacen', False):
                            actualizar_check_incidencia(inc['id'], 'check_almacen', 'fecha_almacen', v_alm)
                            st.rerun()
                        if inc.get('fecha_almacen'): st.caption(f"📅 {inc['fecha_almacen']}")

                    with c2:
                        v_rec = st.checkbox("Recepción", value=inc.get('check_recepcion', False), key=f"ch_rec_{inc['id']}")
                        if v_rec != inc.get('check_recepcion', False):
                            actualizar_check_incidencia(inc['id'], 'check_recepcion', 'fecha_recepcion', v_rec)
                            st.rerun()
                        if inc.get('fecha_recepcion'): st.caption(f"📅 {inc['fecha_recepcion']}")

                    with c3:
                        v_teo = st.checkbox("Teowin", value=inc.get('check_teowin', False), key=f"ch_teo_{inc['id']}")
                        if v_teo != inc.get('check_teowin', False):
                            actualizar_check_incidencia(inc['id'], 'check_teowin', 'fecha_teowin', v_teo)
                            st.rerun()
                        if inc.get('fecha_teowin'): st.caption(f"📅 {inc['fecha_teowin']}")

                    # Observaciones
                    obs_g = st.text_input("Observaciones de gestión:", value=inc.get('obs_gestion', ""), key=f"obs_{inc['id']}")
                    if st.button("Guardar Nota", key=f"btn_obs_{inc['id']}"):
                        guardar_obs_gestion(inc['id'], obs_g)
                        st.success("Nota guardada")
