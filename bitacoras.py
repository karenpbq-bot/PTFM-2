import streamlit as st
import pandas as pd
from datetime import datetime, date
import io
from base_datos import conectar

# Verificación de ReportLab para la exportación a PDF nativo
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
except ImportError:
    st.error("Por favor ejecute 'pip install reportlab' en la terminal para habilitar la exportación a PDF.")

def mostrar(supervisor_id=None):
    st.markdown("""
        <style>
        .section-header { background-color: #E5E7EB; padding: 5px 10px; font-weight: bold; color: #1F2937; border-left: 5px solid #1E3A8A; margin-top: 12px; margin-bottom: 4px; font-size: 13px; }
        .stDataEditor { font-size: 11px; }
        div[data-testid="stForm"] { padding: 10px; }
        </style>
    """, unsafe_allow_html=True)

    supabase = conectar()
    
    if 'id_bitacora_activa' not in st.session_state:
        st.session_state.id_bitacora_activa = None

    # 1. EXTRACCIÓN MAESTRA EN TIEMPO REAL DESDE LAS TABLAS CONFIGURABLES
    try:
        lista_ops = [r['nombre'] for r in supabase.table("cfg_operarios").select("nombre").order("nombre").execute().data]
        lista_descs = [r['detalle'] for r in supabase.table("cfg_descripciones").select("detalle").order("detalle").execute().data]
        lista_cantos = [r['tipo'] for r in supabase.table("cfg_cantos").select("tipo").order("tipo").execute().data]
    except Exception as e:
        st.error(f"Error al cargar tablas de configuración base: {e}")
        lista_ops, lista_descs, lista_cantos = [], [], []

    # Fallbacks de seguridad para evitar quiebres en componentes visuales si están vacías
    if not lista_ops: lista_ops = ["Sin Asignar"]
    if not lista_descs: lista_descs = ["General"]
    if not lista_cantos: lista_cantos = ["Delgado 0.4mm"]

    # =========================================================================
    # VISTA DE EDICIÓN DE UN REGISTRO ACTIVO
    # =========================================================================
    if st.session_state.id_bitacora_activa:
        id_act = st.session_state.id_bitacora_activa
        
        if st.button("⬅️ Volver al Listado de Bitácoras"):
            st.session_state.id_bitacora_activa = None
            st.rerun()
            
        cab = supabase.table("bitacoras_taller").select("*").eq("id", id_act).execute().data[0]
        
        st.markdown('<div class="section-header">📄 SECCIÓN 1: DATOS GENERALES DEL FORMATO</div>', unsafe_allow_html=True)
        with st.container(border=True):
            c1, c2 = st.columns(2)
            try:
                fecha_dt = datetime.strptime(cab['fecha'], "%Y-%m-%d").date()
            except:
                fecha_dt = date.today()
                
            u_fecha = c1.date_input("FECHA (DD/MM/AAAA):", value=fecha_dt, format="DD/MM/YYYY")
            u_n_orden = c2.text_input("Nº ORDEN:", value=cab['n_orden'] or "")
            u_tipo_mueble = c1.text_input("TIPO DE MUEBLE:", value=cab['tipo_mueble'] or "")
            u_motivo = c2.text_input("MOTIVO (Texto libre):", value=cab['motivo'] or "")
            u_cliente = c1.text_input("CLIENTE:", value=cab['cliente'] or "")
            u_proyecto = c2.text_input("PROYECTO:", value=cab['proyecto'] or "")
            u_sol_por = c1.text_input("SOLICITADO POR:", value=cab['solicitado_por'] or "")
            u_sup_prod = c2.text_input("SUP. DE PRODUCCION:", value=cab['sup_production'] or "")
            u_estado = st.selectbox("ESTADO DE LA BITÁCORA:", ["Pendiente", "En Proceso", "Cerrada"], index=["Pendiente", "En Proceso", "Cerrada"].index(cab['estado']))

        res_l = supabase.table("bitacoras_lineas").select("*").eq("bitacora_id", id_act).order("id").execute()
        df_l = pd.DataFrame(res_l.data) if res_l.data else pd.DataFrame()
        
        def filtrar_bloque(df, bloque_nom):
            if df.empty: return pd.DataFrame()
            sub_df = df[df['proceso_bloque'] == bloque_nom].copy()
            for col_f in ['fecha_inicio', 'fecha_termino']:
                if col_f in sub_df.columns:
                    sub_df[col_f] = sub_df[col_f].apply(lambda x: f"{x[5:7]}/{x[8:10]}" if (x and len(str(x)) >= 10 and str(x)[4] == '-') else x)
            return sub_df

        df_secc = filtrar_bloque(df_l, 'SECCIONADORA')
        df_escu = filtrar_bloque(df_l, 'ESCUADRADORA')
        df_cant = filtrar_bloque(df_l, 'CANTEO')

        def generar_bloque_interfaz(titulo, bloque_id, df_bloque, col_cant_nom):
            st.markdown(f'<div class="section-header">{titulo}</div>', unsafe_allow_html=True)
            
            op_actual1, op_actual2 = "", ""
            if not df_bloque.empty:
                if 'nombre_firma_operario' in df_bloque.columns:
                    op_actual1 = df_bloque['nombre_firma_operario'].iloc[0] or ""
                if 'nombre_firma_operario2' in df_bloque.columns:
                    op_actual2 = df_bloque['nombre_firma_operario2'].iloc[0] or ""
                
            cx1, cx2, cx3 = st.columns([2, 2, 2])
            btn_ins = cx1.button(f"➕ Registro a {titulo.split(': ')[1]}", key=f"btn_ins_{bloque_id}")
            
            idx_op1 = lista_ops.index(op_actual1) if op_actual1 in lista_ops else 0
            idx_op2 = lista_ops.index(op_actual2) if op_actual2 in lista_ops else 0
            
            op_val1 = cx2.selectbox("👨‍🔧 RESPONSABLE 1:", options=lista_ops, index=idx_op1, key=f"op_val1_{bloque_id}")
            op_val2 = cx3.selectbox("👥 RESPONSABLE 2:", options=lista_ops, index=idx_op2, key=f"op_val2_{bloque_id}")
            
            if btn_ins:
                supabase.table("bitacoras_lineas").insert({
                    "bitacora_id": id_act, "proceso_bloque": bloque_id, "cantidad": 0.0, 
                    "nombre_firma_operario": op_val1, "nombre_firma_operario2": op_val2
                }).execute()
                st.rerun()
            
            columnas_visibles = ['id', 'cantidad', 'descripcion', 'fecha_inicio', 'hora_inicio', 'cant_final_pl_pzs', 'hora_termino', 'fecha_termino', 'obs_incidencias']
            
            config_columnas = {
                "id": None,
                "cantidad": st.column_config.NumberColumn("CANT.", format="%.2f"),
                "descripcion": st.column_config.SelectboxColumn("DESCRIPCION", options=lista_descs, required=True),
                "fecha_inicio": st.column_config.TextColumn("F. INICIO (DD/MM)"),
                "hora_inicio": st.column_config.TextColumn("H. INICIO"),
                "cant_final_pl_pzs": st.column_config.TextColumn(col_cant_nom),
                "hora_termino": st.column_config.TextColumn("H. TERMINO"),
                "fecha_termino": st.column_config.TextColumn("F. TERMINO (DD/MM)"),
                "obs_incidencias": st.column_config.TextColumn("OBS/INCIDENCIAS")
            }
            
            if bloque_id == 'CANTEO':
                columnas_visibles = ['id', 'cantidad', 'descripcion', 'tipo_canto', 'fecha_inicio', 'hora_inicio', 'cant_final_pl_pzs', 'fecha_termino', 'obs_incidencias']
                config_columnas = {
                    "id": None,
                    "cantidad": st.column_config.NumberColumn("CANT.", format="%.2f"),
                    "descripcion": st.column_config.SelectboxColumn("DESCRIPCION", options=lista_descs, required=True),
                    "tipo_canto": st.column_config.SelectboxColumn("TIPO DE CANTO", options=lista_cantos, required=True),
                    "fecha_inicio": st.column_config.TextColumn("F. INICIO (DD/MM)"),
                    "hora_inicio": st.column_config.TextColumn("H. INICIAL"),
                    "cant_final_pl_pzs": st.column_config.TextColumn("CANTO USADO"),
                    "fecha_termino": st.column_config.TextColumn("F. FINAL (DD/MM)"),
                    "obs_incidencias": st.column_config.TextColumn("OBS/INCIDENCIAS")
                }

            if not df_bloque.empty:
                for col_obligatoria in columnas_visibles:
                    if col_obligatoria not in df_bloque.columns: df_bloque[col_obligatoria] = ""
                df_limpio = df_bloque[columnas_visibles].copy()
            else:
                df_limpio = pd.DataFrame(columns=columnas_visibles)

            for col_c in df_limpio.columns:
                if col_c == "cantidad":
                    df_limpio[col_c] = pd.to_numeric(df_limpio[col_c]).fillna(0.0)
                elif col_c != "id":
                    df_limpio[col_c] = df_limpio[col_c].fillna("").astype(str).str.strip()

            res_ed = st.data_editor(
                df_limpio, column_config=config_columnas, hide_index=True, use_container_width=True, key=f"editor_grid_{bloque_id}_{id_act}"
            )
            return res_ed, op_val1, op_val2

        ed_secc, op_secc1, op_secc2 = generar_bloque_interfaz("🪚 SECCIÓN 2: CORTE SECCIONADORA", "SECCIONADORA", df_secc, "CANT. FINAL PL.")
        ed_escu, op_escu1, op_escu2 = generar_bloque_interfaz("📐 SECCIÓN 3: CORTE ESCUADRADORA", "ESCUADRADORA", df_escu, "CANT. PIEZAS")
        ed_cant, op_cant1, op_cant2 = generar_bloque_interfaz("⚙️ SECCIÓN 4: CANTEO", "CANTEO", df_cant, "CANTO USADO")

        # SECCIÓN 5: LOGÍSTICA Y ARMADO
        st.markdown('<div class="section-header">🚚 SECCIÓN 5: ARMADO Y DESPACHO</div>', unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("**1. ENRUTAMIENTO DE PIEZAS (CONTROL DE DESTINO)**")
            c_arm, c_des = st.columns(2)
            with c_arm:
                st.markdown("<font color='#4B5563'><b>📦 ZONA DE ARMADO (Taller)</b></font>", unsafe_allow_html=True)
                f_arm_val = cab.get('log_armado_fecha')
                f_arm_dt = datetime.strptime(f_arm_val, "%Y-%m-%d").date() if f_arm_val else None
                u_log_armado_fecha = st.date_input("FECHA RECEPCIÓN (ARMADO):", value=f_arm_dt, format="DD/MM/YYYY", key="f_arm_log")
                u_log_armado_cant = st.text_input("Nº PALLETS / PIEZAS (ARMADO):", value=cab.get('log_armado_cant') or "")
                u_log_armado_vob = st.text_input("VºBº SUP. PRODUCCIÓN:", value=cab.get('log_armado_vob') or "")
            with c_des:
                st.markdown("<font color='#4B5563'><b>📦 ZONA DE DESPACHO (Obra)</b></font>", unsafe_allow_html=True)
                f_des_val = cab.get('log_despacho_fecha')
                f_des_dt = datetime.strptime(f_des_val, "%Y-%m-%d").date() if f_des_val else None
                u_log_despacho_fecha = st.date_input("FECHA RECEPCIÓN (DESPACHO):", value=f_des_dt, format="DD/MM/YYYY", key="f_des_log")
                u_log_despacho_cant = st.text_input("Nº PALLETS / PIEZAS (DESPACHO):", value=cab.get('log_despacho_cant') or "")
                u_log_despacho_vob = st.text_input("VºBº ALMACÉN / DESPACHO:", value=cab.get('log_despacho_vob') or "")

            st.divider()
            st.markdown("**2. DATOS DE SALIDA A OBRA**")
            col_s1, col_s2, col_s3 = st.columns(3)
            f_sal_val = cab.get('log_salida_fecha')
            f_sal_dt = datetime.strptime(f_sal_val, "%Y-%m-%d").date() if f_sal_val else None
            u_log_salida_fecha = col_s1.date_input("FECHA SALIDA A OBRA:", value=f_sal_dt, format="DD/MM/YYYY", key="f_sal_log")
            u_log_salida_conductor = col_s2.text_input("CONDUCTOR / CHOFER:", value=cab.get('log_salida_conductor') or "")
            u_log_salida_vob = col_s3.text_input("VºBº ALMACÉN (SALIDA):", value=cab.get('log_salida_vob') or "")

            st.divider()
            st.markdown("**3. OBSERVACIONES / INCIDENCIAS DE LOGÍSTICA**")
            u_log_observaciones = st.text_area("Registre novedades del flete:", value=cab.get('log_observaciones') or "", height=80, label_visibility="collapsed")

        st.divider()
        c_save, c_pdf = st.columns(2)
        
        if c_save.button("💾 GUARDAR AVANCES Y CAMBIOS", type="primary", use_container_width=True):
            try:
                supabase.table("bitacoras_taller").update({
                    "fecha": u_fecha.isoformat(), "n_orden": u_n_orden, "tipo_mueble": u_tipo_mueble,
                    "motivo": u_motivo, "cliente": u_cliente, "proyecto": u_proyecto,
                    "solicitado_por": u_sol_por, "sup_production": u_sup_prod, "estado": u_estado,
                    "log_armado_fecha": u_log_armado_fecha.isoformat() if u_log_armado_fecha else None,
                    "log_armado_cant": u_log_armado_cant, "log_armado_vob": u_log_armado_vob,
                    "log_despacho_fecha": u_log_despacho_fecha.isoformat() if u_log_despacho_fecha else None,
                    "log_despacho_cant": u_log_despacho_cant, "log_despacho_vob": u_log_despacho_vob,
                    "log_salida_fecha": u_log_salida_fecha.isoformat() if u_log_salida_fecha else None,
                    "log_salida_conductor": u_log_salida_conductor, "log_salida_vob": u_log_salida_vob,
                    "log_observaciones": u_log_observaciones
                }).eq("id", id_act).execute()
                
                def procesar_lote_guardado(df_editor, bloque_id, op1, op2):
                    for _, r in df_editor.iterrows():
                        def normalizar_fecha_iso(valor_celda):
                            if not valor_celda or pd.isna(valor_celda): return None
                            texto = str(valor_celda).strip()
                            if len(texto) == 5 and "/" in texto: return f"2026-{texto[3:5]}-{texto[0:2]}"
                            return texto
                        
                        payload = {
                            "cantidad": float(r['cantidad']) if r['cantidad'] else 0.0,
                            "descripcion": str(r['descripcion']).strip() if r['descripcion'] else None,
                            "tipo_canto": str(r['tipo_canto']).strip() if 'tipo_canto' in r and r['tipo_canto'] else None,
                            "fecha_inicio": normalizar_fecha_iso(r['fecha_inicio']),
                            "hora_inicio": str(r['hora_inicio']).strip() if r['hora_inicio'] else None,
                            "cant_final_pl_pzs": str(r['cant_final_pl_pzs']).strip() if r['cant_final_pl_pzs'] else None,
                            "hora_termino": str(r['hora_termino']).strip() if 'hora_termino' in r and r['hora_termino'] else None,
                            "fecha_termino": normalizar_fecha_iso(r['fecha_termino']),
                            "obs_incidencias": str(r['obs_incidencias']).strip() if r['obs_incidencias'] else None,
                            "nombre_firma_operario": op1, "nombre_firma_operario2": op2
                        }
                        supabase.table("bitacoras_lineas").update(payload).eq("id", int(r['id'])).execute()

                procesar_lote_guardado(ed_secc, "SECCIONADORA", op_secc1, op_secc2)
                procesar_lote_guardado(ed_escu, "ESCUADRADORA", op_escu1, op_escu2)
                procesar_lote_guardado(ed_cant, "CANTEO", op_cant1, op_cant2)
                
                st.success("🎉 Trazabilidad guardada con éxito."); st.rerun()
            except Exception as e:
                st.error(f"Falla de sincronización: {e}")

    # =========================================================================
    # ENTORNO INICIAL: HISTORIAL, ALTA Y MANTENIMIENTO MAESTRO (3 PESTAÑAS)
    # =========================================================================
    else:
        tab_listado, tab_alta_nueva, tab_config = st.tabs(["🗂️ Listado de Bitácoras", "➕ Nueva Bitácora", "⚙️ Configuración de Datos"])
        
        with tab_listado:
            filtro = st.text_input("🔍 Filtro rápido de búsqueda:", placeholder="Escriba el número de OP, cliente...")
            try:
                res_t = supabase.table("bitacoras_taller").select("*").execute()
                df_t = pd.DataFrame(res_t.data) if res_t.data else pd.DataFrame()
            except:
                df_t = pd.DataFrame()
                
            if filtro and not df_t.empty:
                df_t = df_t[df_t['n_orden'].astype(str).str.contains(filtro, case=False) | df_t['cliente'].astype(str).str.contains(filtro, case=False)]
                
            if not df_t.empty:
                df_t = df_t.sort_values(by="fecha", ascending=False)
                df_estados = st.data_editor(
                    df_t[['id', 'fecha', 'n_orden', 'proyecto', 'cliente', 'tipo_mueble', 'estado']],
                    column_config={
                        "id": st.column_config.TextColumn("ID", disabled=True),
                        "fecha": st.column_config.TextColumn("FECHA", disabled=True),
                        "estado": st.column_config.SelectboxColumn("ESTADO", options=["Pendiente", "En Proceso", "Cerrada"], required=True)
                    },
                    hide_index=True, use_container_width=True, key="grid_estados_inicial"
                )
                
                if st.button("💾 Actualizar"):
                    for _, r_e in df_estados.iterrows():
                        supabase.table("bitacoras_taller").update({"estado": r_e['estado']}).eq("id", int(r_e['id'])).execute()
                    st.success("Estados guardados."); st.rerun()
                    
                st.divider()
                id_abrir = st.number_input("ID de Bitácora a editar:", min_value=1, step=1)
                if st.button("🔓 Abrir Formato Simétrico en Pantalla", type="primary"):
                    st.session_state.id_bitacora_activa = int(id_abrir)
                    st.rerun()

        with tab_alta_nueva:
            with st.form("form_alta_inicial"):
                f_n = st.date_input("FECHA:", value=date.today(), format="DD/MM/YYYY")
                o_n = st.text_input("Nº ORDEN:")
                m_n = st.text_input("TIPO DE MUEBLE:")
                mt_n = st.text_input("MOTIVO:")
                cl_n = st.text_input("CLIENTE:")
                pr_n = st.text_input("PROYECTO:")
                sl_n = st.text_input("SOLICITADO POR:")
                sp_n = st.text_input("SUP. DE PRODUCCION:", value="DOMÉNICO MORÓN")
                
                if st.form_submit_button("🚀 Inicializar Bitácora", type="primary"):
                    res_ins = supabase.table("bitacoras_taller").insert({
                        "fecha": f_n.isoformat(), "n_orden": o_n, "tipo_mueble": m_n,
                        "motivo": mt_n, "cliente": cl_n, "proyecto": pr_n,
                        "solicitado_por": sl_n, "sup_production": sp_n, "estado": "Pendiente"
                    }).execute()
                    
                    if res_ins.data:
                        b_id = res_ins.data[0]['id']
                        lineas_iniciales = []
                        for _ in range(2):
                            lineas_iniciales.append({"bitacora_id": b_id, "proceso_bloque": "SECCIONADORA", "cantidad": 0.0})
                            lineas_iniciales.append({"bitacora_id": b_id, "proceso_bloque": "ESCUADRADORA", "cantidad": 0.0})
                            lineas_iniciales.append({"bitacora_id": b_id, "proceso_bloque": "CANTEO", "cantidad": 0.0})
                        supabase.table("bitacoras_lineas").insert(lineas_iniciales).execute()
                        st.session_state.id_bitacora_activa = b_id
                        st.rerun()

        # =========================================================================
        # 🛠️ PESTAÑA 3 CORREGIDA Y OPERATIVA: MANTENIMIENTO FÍSICO DE TABLAS MAESTRAS
        # =========================================================================
        with tab_config:
            st.markdown("### 🛠️ Panel de Alimentación Directa para Tablas de Configuración")
            st.caption("Los datos ingresados aquí aparecerán inmediatamente como opciones seleccionables dentro de los bloques de producción.")
            
            c_cfg1, c_cfg2, c_cfg3 = st.columns(3)
            
            # Bloque A: Operarios (Alimenta cfg_operarios)
            with c_cfg1:
                st.markdown('<div style="background-color:#F3F4F6; padding:8px; border-radius:4px; font-weight:bold; text-align:center;">👤 SECCIÓN: OPERARIOS</div>', unsafe_allow_html=True)
                with st.form("form_add_operario", clear_on_submit=True):
                    nuevo_op = st.text_input("Nombre completo:", placeholder="Ej: JUAN PÉREZ")
                    enviar_op = st.form_submit_button("➕ Agregar Operario", use_container_width=True)
                    if enviar_op and nuevo_op.strip():
                        try:
                            supabase.table("cfg_operarios").insert({"nombre": nuevo_op.strip().upper()}).execute()
                            st.toast("Operario agregado con éxito", icon="✅")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Error al insertar operario: {ex}")
                
                # Visualización de registros actuales en base de datos
                try:
                    df_ops_view = pd.DataFrame(supabase.table("cfg_operarios").select("nombre").order("nombre").execute().data)
                    if not df_ops_view.empty:
                        st.dataframe(df_ops_view, hide_index=True, use_container_width=True)
                except:
                    st.info("Sin registros.")

            # Bloque B: Descripciones / Materiales (Alimenta cfg_descripciones)
            with c_cfg2:
                st.markdown('<div style="background-color:#F3F4F6; padding:8px; border-radius:4px; font-weight:bold; text-align:center;">📄 SECCIÓN: MATERIALES</div>', unsafe_allow_html=True)
                with st.form("form_add_desc", clear_on_submit=True):
                    nueva_desc = st.text_input("Detalle del material:", placeholder="Ej: Melamina 18mm Crudo")
                    enviar_desc = st.form_submit_button("➕ Agregar Material", use_container_width=True)
                    if enviar_desc and nueva_desc.strip():
                        try:
                            supabase.table("cfg_descripciones").insert({"detalle": nueva_desc.strip()}).execute()
                            st.toast("Material agregado con éxito", icon="✅")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Error al insertar material: {ex}")
                
                try:
                    df_desc_view = pd.DataFrame(supabase.table("cfg_descripciones").select("detalle").order("detalle").execute().data)
                    if not df_desc_view.empty:
                        st.dataframe(df_desc_view, hide_index=True, use_container_width=True)
                except:
                    st.info("Sin registros.")

            # Bloque C: Tipos de Canto (Alimenta cfg_cantos)
            with c_cfg3:
                st.markdown('<div style="background-color:#F3F4F6; padding:8px; border-radius:4px; font-weight:bold; text-align:center;">⚙️ SECCIÓN: CANTOS</div>', unsafe_allow_html=True)
                with st.form("form_add_canto", clear_on_submit=True):
                    nuevo_canto = st.text_input("Tipo de canto:", placeholder="Ej: Delgado 0.4mm")
                    enviar_canto = st.form_submit_button("➕ Agregar Canto", use_container_width=True)
                    if enviar_canto and nuevo_canto.strip():
                        try:
                            supabase.table("cfg_cantos").insert({"tipo": nuevo_canto.strip()}).execute()
                            st.toast("Canto agregado con éxito", icon="✅")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Error al insertar canto: {ex}")
                
                try:
                    df_canto_view = pd.DataFrame(supabase.table("cfg_cantos").select("tipo").order("tipo").execute().data)
                    if not df_canto_view.empty:
                        st.dataframe(df_canto_view, hide_index=True, use_container_width=True)
                except:
                    st.info("Sin registros.")
