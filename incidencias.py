import streamlit as st
import pandas as pd
import io
from datetime import datetime
from base_datos import conectar, obtener_proyectos, registrar_incidencia_detallada, obtener_incidencias_resumen

def mostrar():
    st.header("⚠️ Gestión de Requerimientos")
    
    # --- NUEVO: BUSCADOR DE PROYECTO PARA ASOCIACIÓN ---
    with st.container(border=True):
        col_bus1, col_bus2 = st.columns([2, 1])
        bus_proy = col_bus1.text_input("🔍 Localizar Proyecto para el Requerimiento:", 
                                        placeholder="Escribe código o nombre...", key="bus_inc_proy")
        
        # Obtenemos proyectos filtrados
        df_proyectos_all = obtener_proyectos(bus_proy)
        
        if not df_proyectos_all.empty:
            dict_proyectos = {row['proyecto_display']: row['id'] for _, row in df_proyectos_all.iterrows()}
            proy_seleccionado_display = col_bus2.selectbox("Confirmar Proyecto:", 
                                                            list(dict_proyectos.keys()), key="sel_proy_inc")
            id_proyecto_actual = dict_proyectos[proy_seleccionado_display]
        else:
            st.warning("⚠️ No se encontró el proyecto. Escribe otro nombre.")
            return # Detiene la ejecución si no hay proyecto seleccionado

    # Memoria temporal
    if 'tmp_piezas' not in st.session_state: st.session_state.tmp_piezas = []
    if 'tmp_mats' not in st.session_state: st.session_state.tmp_mats = []

    tab_p, tab_m, tab_h = st.tabs(["🧩 Piezas", "📦 Materiales", "📜 Historial"])
    
    MOTIVOS = ["Faltante", "Cambio", "Pieza Dañada", "Otros"]

    # --- PESTAÑA 1: PIEZAS ---
    with tab_p:
        st.subheader("Configuración del Bloque de Piezas")
        c1, c2 = st.columns(2)
        
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
                # Cambiamos 'dict_proyectos[proy_p]' por 'id_proyecto_actual'
                registrar_incidencia_detallada(id_proyecto_actual, "Piezas", motivo_p, 
                                               st.session_state.tmp_piezas, [], st.session_state.get('id_usuario'))
                st.session_state.tmp_piezas = []
                st.success("Requerimiento enviado con éxito."); st.rerun()

    # --- PESTAÑA 2: MATERIALES ---
    with tab_m:
        st.subheader("Configuración del Bloque de Materiales")
        cm1, cm2 = st.columns(2)
        
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
                # Usamos id_proyecto_actual aquí también
                registrar_incidencia_detallada(id_proyecto_actual, "Materiales", motivo_m, 
                                               [], st.session_state.tmp_mats, st.session_state.get('id_usuario'))
                st.session_state.tmp_mats = []
                st.success("Enviado con éxito"); st.rerun()

  # --- PESTAÑA 3: HISTORIAL (SEMÁFORO + GESTIÓN COMPACTA) ---
    with tab_h:
        historial = obtener_incidencias_resumen()
        
        if not historial.empty:
            for _, inc in historial.iterrows():
                # 1. Recuperar valores actuales
                f_alm = inc.get('fecha_almacen', "")
                f_sol = inc.get('fecha_solicitante', "")
                f_teo = inc.get('fecha_teowin', "")
                id_i = inc['id']
                
                # 2. Lógica de Semáforos (Rojo/Verde)
                s1 = "🟩" if f_alm and str(f_alm).strip() != "" else "🟥"
                s2 = "🟩" if f_sol and str(f_sol).strip() != "" else "🟥"
                s3 = "🟩" if f_teo and str(f_teo).strip() != "" else "🟥"
                
                titulo_rotulo = f"REQ-{id_i} | {inc['proyecto_text']} | {inc['tipo_requerimiento']}  [{s1}{s2}{s3}]"

                with st.expander(titulo_rotulo):
                    # --- FILA DE GESTIÓN HORIZONTAL ---
                    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 2.5, 0.5])
                    
                    v_alm = c1.checkbox("📦 Almacén", value=(s1 == "🟩"), key=f"c_alm_{id_i}")
                    if f_alm: c1.caption(f"📅 {f_alm}")

                    v_sol = c2.checkbox("👤 Solicitante", value=(s2 == "🟩"), key=f"c_sol_{id_i}")
                    if f_sol: c2.caption(f"📅 {f_sol}")

                    v_teo = c3.checkbox("🖥️ Teowin", value=(s3 == "🟩"), key=f"c_teo_{id_i}")
                    if f_teo: c3.caption(f"📅 {f_teo}")
                    
                    v_not = c4.text_input("Nota", value=inc.get('obs_gestion', ""), 
                                         key=f"t_not_{id_i}", label_visibility="collapsed")

                    # BOTÓN DE GUARDADO
                    if c5.button("💾", key=f"b_sav_{id_i}"):
                        # Formato Día/Mes/Año solicitado
                        f_hoy = datetime.now().strftime("%d/%m/%Y %H:%M")
                        
                        # Si marcas el check y no hay fecha, ponemos hoy. Si desmarcas, limpiamos.
                        p_datos = {
                            "fecha_almacen": f_hoy if v_alm and not (f_alm and str(f_alm).strip()!="") else (f_alm if v_alm else ""),
                            "fecha_solicitante": f_hoy if v_sol and not (f_sol and str(f_sol).strip()!="") else (f_sol if v_sol else ""),
                            "fecha_teowin": f_hoy if v_teo and not (f_teo and str(f_teo).strip()!="") else (f_teo if v_teo else ""),
                            "obs_gestion": v_not
                        }
                        
                        from base_datos import actualizar_gestion_incidencia
                        actualizar_gestion_incidencia(id_i, p_datos)
                        st.rerun()

                    st.markdown("---")
                    st.write(f"**Motivo:** {inc['categoria']} | **Estado:** {inc['estado']}")
                    if inc.get('detalles'):
                        st.dataframe(pd.DataFrame(inc['detalles']), use_container_width=True)
            st.divider()
        else:
            st.info("No hay requerimientos registrados.")
