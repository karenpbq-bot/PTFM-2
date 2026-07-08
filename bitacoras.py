import streamlit as st
import pandas as pd
from datetime import datetime, date
import io
from base_datos import conectar

def mostrar(supervisor_id=None):
    st.markdown("""
        <style>
        .report-title { font-size: 24px; font-weight: bold; color: #1E3A8A; margin-bottom: 0.5rem; }
        .block-header { background-color: #F3F4F6; padding: 6px; font-weight: bold; border-left: 5px solid #1E3A8A; margin-top: 1rem; margin-bottom: 0.5rem; }
        .stDataEditor { font-size: 11px; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<p class="report-title">📋 Bitácoras de Trazabilidad de Producción</p>', unsafe_allow_html=True)
    
    supabase = conectar()
    
    # Manejo de estados de navegación en la sesión de Streamlit
    if 'id_bitacora_activa' not in st.session_state:
        st.session_state.id_bitacora_activa = None
    if 'ver_formulario_alta' not in st.session_state:
        st.session_state.ver_formulario_alta = False

    # Botón para regresar al historial si hay un documento abierto
    if st.session_state.id_bitacora_activa:
        if st.button("⬅️ Volver al Historial de Bitácoras"):
            st.session_state.id_bitacora_activa = None
            st.rerun()

    # =========================================================================
    # VISTA 1: HISTORIAL Y APERTURA DE BITÁCORAS
    # =========================================================================
    if not st.session_state.id_bitacora_activa:
        st.subheader("🗂️ Historial de Hojas Abiertas en Taller")
        
        # Filtro de búsqueda rápida
        busq = st.text_input("🔍 Filtrar por Nº Orden, Proyecto, Cliente o Mueble:", placeholder="Ej: 262200017...")
        
        # Carga rápida de cabeceras existentes
        res_t = supabase.table("bitacoras_taller").select("*").order("fecha", desc=True).execute()
        df_t = pd.DataFrame(res_t.data) if res_t.data else pd.DataFrame()
        
        if busq and not df_t.empty:
            df_t = df_t[
                df_t['n_orden'].astype(str).str.contains(busq, case=False) |
                df_t['proyecto'].astype(str).str.contains(busq, case=False) |
                df_t['cliente'].astype(str).str.contains(busq, case=False) |
                df_t['tipo_mueble'].astype(str).str.contains(busq, case=False)
            ]
            
        if not df_t.empty:
            df_vis = df_t.copy().rename(columns={
                'id': 'ID', 'fecha': 'Fecha', 'n_orden': 'Nº Orden', 'tipo_mueble': 'Tipo Mueble',
                'cliente': 'Cliente', 'proyecto': 'Proyecto', 'estado': 'Estado'
            })
            st.dataframe(df_vis[['ID', 'Fecha', 'Nº Orden', 'Tipo Mueble', 'Cliente', 'Proyecto', 'Estado']], hide_index=True, use_container_width=True)
            
            id_sel = st.number_input("Digite el ID de la Bitácora que desea abrir/completar:", min_value=1, step=1)
            if st.button("🔓 Abrir Formato en Pantalla", type="secondary", use_container_width=True):
                if id_sel in df_t['id'].tolist():
                    st.session_state.id_bitacora_activa = int(id_sel)
                    st.rerun()
                else:
                    st.error("El ID seleccionado no existe en el registro.")
        else:
            st.info("No se encontraron bitácoras registradas.")
            
        st.divider()
        
        # Botón para desplegar la creación de una nueva bitácora vacía
        if not st.session_state.ver_formulario_alta:
            if st.button("➕ Crear Nueva Bitácora de Producción"):
                st.session_state.ver_formulario_alta = True
                st.rerun()
                
        if st.session_state.ver_formulario_alta:
            st.markdown("### 📝 Nueva Bitácora (Se puede iniciar con campos vacíos)")
            with st.form("alta_bitacora_form"):
                f_doc = st.date_input("Fecha:", value=date.today())
                n_ord = st.text_input("Nº Orden:")
                t_mue = st.text_input("Tipo de Mueble:")
                mot = st.text_input("Motivo:")
                cli = st.text_input("Cliente:")
                proy = st.text_input("Proyecto:")
                sol_por = st.text_input("Solicitado por:")
                sup_prod = st.text_input("Sup. de Producción:", value="DOMÉNICO MORÓN")
                
                c_izq, c_der = st.columns(2)
                btn_crear = c_izq.form_submit_button("🚀 Inicializar Hoja", type="primary")
                btn_can = c_der.form_submit_button("Cancelar")
                
                if btn_crear:
                    res_ins = supabase.table("bitacoras_taller").insert({
                        "fecha": f_doc.isoformat(), "n_orden": n_ord, "tipo_mueble": t_mue,
                        "motivo": mot, "cliente": cli, "proyecto": proy,
                        "solicitado_por": sol_por, "sup_production": sup_prod, "estado": "En Proceso"
                    }).execute()
                    
                    if res_ins.data:
                        b_id = res_ins.data[0]['id']
                        
                        # Pre-cargar filas en blanco iniciales reglamentarias para cada proceso
                        lineas_iniciales = []
                        for _ in range(3):
                            lineas_iniciales.append({"bitacora_id": b_id, "proceso_bloque": "SECCIONADORA", "cantidad": 0.0})
                            lineas_iniciales.append({"bitacora_id": b_id, "proceso_bloque": "ESCUADRADORA", "cantidad": 0.0})
                            lineas_iniciales.append({"bitacora_id": b_id, "proceso_bloque": "CANTEO", "cantidad": 0.0})
                            
                        supabase.table("bitacoras_lineas").insert(lineas_iniciales).execute()
                        st.session_state.id_bitacora_activa = b_id
                        st.session_state.ver_formulario_alta = False
                        st.rerun()
                        
                if btn_can:
                    st.session_state.ver_formulario_alta = False
                    st.rerun()

    # =========================================================================
    # VISTA 2: RÉPLICA DEL FORMATO EN PANTALLA (EDICIÓN PAULATINA)
    # =========================================================================
    else:
        id_act = st.session_state.id_bitacora_activa
        
        # Cargar cabecera
        cab = supabase.table("bitacoras_taller").select("*").eq("id", id_act).execute().data[0]
        
        # Mostrar metadatos de control superiores estilo papel
        with st.container(border=True):
            st.markdown(f"**BITÁCORA DE PRODUCCIÓN Nº {cab['id']}**")
            col1, col2, col3 = st.columns(3)
            col1.write(f"**Fecha:** {cab['fecha']}")
            col1.write(f"**Tipo Mueble:** {cab['tipo_mueble'] or '-'}")
            col1.write(f"**Solicitado por:** {cab['solicitado_por'] or '-'}")
            
            col2.write(f"**Nº Orden:** {cab['n_orden'] or '-'}")
            col2.write(f"**Motivo:** {cab['motivo'] or '-'}")
            col2.write(f"**Sup. Producción:** {cab['sup_production'] or '-'}")
            
            col3.write(f"**Cliente:** {cab['cliente'] or '-'}")
            col3.write(f"**Proyecto:** {cab['proyecto'] or '-'}")
            est_doc = col3.selectbox("Estado del documento:", ["En Proceso", "Concluido"], index=0 if cab['estado']=='En Proceso' else 1)
            if est_doc != cab['estado']:
                supabase.table("bitacoras_taller").update({"estado": est_doc}).eq("id", id_act).execute()

        # Cargar todas las líneas de detalle de esta bitácora
        res_l = supabase.table("bitacoras_lineas").select("*").eq("bitacora_id", id_act).order("id").execute()
        df_l = pd.DataFrame(res_l.data) if res_l.data else pd.DataFrame()
        
        # Separación por bloques funcionales
        df_secc = df_l[df_l['proceso_bloque'] == 'SECCIONADORA'].copy() if not df_l.empty else pd.DataFrame()
        df_escu = df_l[df_l['proceso_bloque'] == 'ESCUADRADORA'].copy() if not df_l.empty else pd.DataFrame()
        df_cant = df_l[df_l['proceso_bloque'] == 'CANTEO'].copy() if not df_l.empty else pd.DataFrame()

        # ---------------------------------------------------------------------
        # BLOQUE 1: CORTE SECCIONADORA
        # ---------------------------------------------------------------------
        st.markdown('<div class="block-header">🪚 CORTE SECCIONADORA</div>', unsafe_allow_html=True)
        if st.button("➕ Añadir Fila a Seccionadora"):
            supabase.table("bitacoras_lineas").insert({"bitacora_id": id_act, "proceso_bloque": "SECCIONADORA", "cantidad": 0.0}).execute()
            st.rerun()
            
        res_secc_ed = st.data_editor(
            df_secc[['id', 'cantidad', 'descripcion', 'fecha_inicio', 'hora_inicio', 'cant_final_pl_pzs', 'hora_termino', 'fecha_termino', 'obs_incidencias', 'nombre_firma_operario']],
            column_config={
                "id": None,
                "cantidad": st.column_config.NumberColumn("CANT.", format="%.2f"),
                "descripcion": st.column_config.TextColumn("DESCRIPCION"),
                "fecha_inicio": st.column_config.TextColumn("FECHA INICIO"),
                "hora_inicio": st.column_config.TextColumn("HORA INICIO"),
                "cant_final_pl_pzs": st.column_config.TextColumn("CANT. FINAL PL."),
                "hora_termino": st.column_config.TextColumn("HORA TERMINO"),
                "fecha_termino": st.column_config.TextColumn("FECHA TERMINO"),
                "obs_incidencias": st.column_config.TextColumn("OBS/INCIDENCIAS"),
                "nombre_firma_operario": st.column_config.TextColumn("OPERARIO CORTE")
            },
            hide_index=True, use_container_width=True, key=f"ed_secc_{id_act}"
        )

        # ---------------------------------------------------------------------
        # BLOQUE 2: CORTE ESCUADRADORA
        # ---------------------------------------------------------------------
        st.markdown('<div class="block-header">📐 CORTE ESCUADRADORA</div>', unsafe_allow_html=True)
        if st.button("➕ Añadir Fila a Escuadradora"):
            supabase.table("bitacoras_lineas").insert({"bitacora_id": id_act, "proceso_bloque": "ESCUADRADORA", "cantidad": 0.0}).execute()
            st.rerun()
            
        res_escu_ed = st.data_editor(
            df_escu[['id', 'cantidad', 'descripcion', 'fecha_inicio', 'hora_inicio', 'cant_final_pl_pzs', 'hora_termino', 'fecha_termino', 'obs_incidencias', 'nombre_firma_operario']],
            column_config={
                "id": None,
                "cantidad": st.column_config.NumberColumn("CANT.", format="%.2f"),
                "descripcion": st.column_config.TextColumn("DESCRIPCION"),
                "fecha_inicio": st.column_config.TextColumn("FECHA INICIO"),
                "hora_inicio": st.column_config.TextColumn("HORA INICIO"),
                "cant_final_pl_pzs": st.column_config.TextColumn("CANT. PIEZAS"),
                "hora_termino": st.column_config.TextColumn("HORA TERMINO"),
                "fecha_termino": st.column_config.TextColumn("FECHA TERMINO"),
                "obs_incidencias": st.column_config.TextColumn("OBS/INCIDENCIAS"),
                "nombre_firma_operario": st.column_config.TextColumn("OPERARIO CORTE")
            },
            hide_index=True, use_container_width=True, key=f"ed_escu_{id_act}"
        )

        # ---------------------------------------------------------------------
        # BLOQUE 3: CANTEO
        # ---------------------------------------------------------------------
        st.markdown('<div class="block-header">⚙️ CANTEO</div>', unsafe_allow_html=True)
        if st.button("➕ Añadir Fila a Canteo"):
            supabase.table("bitacoras_lineas").insert({"bitacora_id": id_act, "proceso_bloque": "CANTEO", "cantidad": 0.0}).execute()
            st.rerun()
            
        res_cant_ed = st.data_editor(
            df_cant[['id', 'cantidad', 'descripcion', 'tipo_canto', 'fecha_inicio', 'hora_inicio', 'cant_final_pl_pzs', 'fecha_termino', 'obs_incidencias', 'nombre_firma_operario']],
            column_config={
                "id": None,
                "cantidad": st.column_config.NumberColumn("CANT.", format="%.2f"),
                "descripcion": st.column_config.TextColumn("DESCRIPCION"),
                "tipo_canto": st.column_config.TextColumn("TIPO DE CANTO"),
                "fecha_inicio": st.column_config.TextColumn("FECHA INICIO"),
                "hora_inicio": st.column_config.TextColumn("HORA INICIAL"),
                "cant_final_pl_pzs": st.column_config.TextColumn("CANTO USADO"),
                "fecha_termino": st.column_config.TextColumn("FECHA FINAL"),
                "obs_incidencias": st.column_config.TextColumn("OBS/INCIDENCIAS"),
                "nombre_firma_operario": st.column_config.TextColumn("OPERARIO CORTE")
            },
            hide_index=True, use_container_width=True, key=f"ed_cant_{id_act}"
        )

        # ---------------------------------------------------------------------
        # CONTROL CENTRAL DE PROCESAMIENTO Y GUARDADO
        # ---------------------------------------------------------------------
        st.divider()
        c_b1, c_b2 = st.columns(2)
        
        # Botón 1: Guardar cambios parciales / progresivos
        if c_b1.button("💾 GUARDAR AVANCE EN LA APP", type="primary", use_container_width=True):
            try:
                # Consolidar los tres bloques editados en una sola lista para el guardado masivo
                lotes_actualizar = (
                    res_secc_ed.to_dict(orient='records') +
                    res_escu_ed.to_dict(orient='records') +
                    res_cant_ed.to_dict(orient='records')
                )
                
                for r_upd in lotes_actualizar:
                    id_f = int(r_upd['id'])
                    payload = {
                        "cantidad": float(r_upd['cantidad']) if r_upd['cantidad'] else 0.0,
                        "descripcion": str(r_upd['descripcion']).strip() if r_upd['descripcion'] else None,
                        "tipo_canto": str(r_upd.get('tipo_canto', '')).strip() if r_upd.get('tipo_canto') else None,
                        "fecha_inicio": str(r_upd['fecha_inicio']).strip() if r_upd['fecha_inicio'] else None,
                        "hora_inicio": str(r_upd['hora_inicio']).strip() if r_upd['hora_inicio'] else None,
                        "cant_final_pl_pzs": str(r_upd['cant_final_pl_pzs']).strip() if r_upd['cant_final_pl_pzs'] else None,
                        "hora_termino": str(r_upd.get('hora_termino', '')).strip() if r_upd.get('hora_termino') else None,
                        "fecha_termino": str(r_upd['fecha_termino']).strip() if r_upd['fecha_termino'] else None,
                        "obs_incidencias": str(r_upd['obs_incidencias']).strip() if r_upd['obs_incidencias'] else None,
                        "nombre_firma_operario": str(r_upd['nombre_firma_operario']).strip() if r_upd['nombre_firma_operario'] else None
                    }
                    supabase.table("bitacoras_lineas").update(payload).eq("id", id_f).execute()
                    
                st.success("🎉 Datos de trazabilidad guardados exitosamente."); st.cache_data.clear(); st.rerun()
            except Exception as e:
                st.error(f"Falla al guardar avance: {e}")

        # Botón 2: Generar planilla lista para impresión
        # Reconstrucción horizontal limpia unificada del reporte
        df_print_all = pd.DataFrame()
        listado_completo = []
        
        for r_p in res_secc_ed.to_dict(orient='records'):
            r_p['PROCESO'] = 'CORTE SECCIONADORA'; listado_completo.append(r_p)
        for r_p in res_escu_ed.to_dict(orient='records'):
            r_p['PROCESO'] = 'CORTE ESCUADRADORA'; listado_completo.append(r_p)
        for r_p in res_cant_ed.to_dict(orient='records'):
            r_p['PROCESO'] = 'CANTEO'; listado_completo.append(r_p)
            
        if listado_completo:
            df_print_all = pd.DataFrame(listado_completo)
            df_print_all.insert(0, "Proyecto", cab['proyecto'])
            df_print_all.insert(0, "Nº Orden", cab['n_orden'])
            df_print_all = df_print_all.drop(columns=['id'])
            
        out_bit = io.BytesIO()
        with pd.ExcelWriter(out_bit, engine='openpyxl') as writer:
            if not df_print_all.empty:
                df_print_all.to_excel(writer, index=False, sheet_name="Trazabilidad")
                
        c_b2.download_button(
            "🖨️ EXPORTAR FORMATO LIMPIO PARA IMPRESIÓN",
            data=out_bit.getvalue(),
            file_name=f"Bitacora_Trazabilidad_{cab['id']}.xlsx",
            use_container_width=True
        )
