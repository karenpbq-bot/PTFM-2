import streamlit as st
import pandas as pd
from datetime import datetime, date
import io
from base_datos import conectar

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
except ImportError:
    st.error("Por favor ejecute 'pip install reportlab' en la terminal para habilitar la exportación a PDF.")

def mostrar(supervisor_id=None):
    # AJUSTE DE INTERFAZ EN PANTALLA (100% ALINEADO)
    st.markdown("""
        <style>
        .block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; }
        
        .section-header { 
            background-color: #E5E7EB; 
            padding: 4px 8px; 
            font-weight: bold; 
            color: #1F2937; 
            border-left: 5px solid #1E3A8A; 
            margin-top: 6px; 
            margin-bottom: 2px; 
            font-size: 13px; 
        }
        
        div[data-testid="stDataEditor"] {
            font-size: 12.5px !important;
            font-family: monospace !important;
            margin-bottom: 2px !important;
            padding: 0px !important;
            width: 100% !important;
        }
        
        /* Forzar simetría y altura incrementada un 40% en las 6 filas en pantalla */
        div[data-testid="stDataEditor"] div[role="rowgroup"] div[role="row"] {
            min-height: 34px !important;
            height: 34px !important;
            display: flex;
            align-items: center;
        }
        
        div[data-testid="stForm"] { padding: 4px 6px !important; }
        div[data-testid="stVerticalBlock"] > div { padding-bottom: 2px !important; padding-top: 2px !important; }
        </style>
    """, unsafe_allow_html=True)

    supabase = conectar()
    
    if 'id_bitacora_activa' not in st.session_state:
        st.session_state.id_bitacora_activa = None

    # --- NUEVO: CARGA DE LISTAS DESPLEGABLES (PROYECTOS, RESPONSABLES, MOTIVOS) ---
    try:
        # Trae proyectos que estén en Cotización o Ejecución
        res_proy = supabase.table("proyectos").select("proyecto_text").in_("estatus", ["En Cotización", "En ejecución"]).order("proyecto_text").execute()
        lista_proy = [""] + [p['proyecto_text'] for p in res_proy.data] if res_proy.data else [""]
    except:
        lista_proy = [""]
        
    try:
        # Trae usuarios que sean Gerentes o de Diseño
        res_usu = supabase.table("usuarios").select("nombre_completo").in_("rol", ["Gerente", "Diseño"]).order("nombre_completo").execute()
        lista_usu = [""] + [u['nombre_completo'] for u in res_usu.data] if res_usu.data else [""]
    except:
        lista_usu = [""]
        
    try:
        # Trae la lista de la nueva tabla de motivos
        res_mot = supabase.table("cfg_motivos").select("motivo").order("motivo").execute()
        lista_mot = [""] + [m['motivo'] for m in res_mot.data] if res_mot.data else [""]
    except:
        lista_mot = [""]

    # Función para evitar errores si en el pasado se guardó un nombre que ya no está en la lista
    def safe_idx(lista, val):
        if not val: return 0
        if val in lista: return lista.index(val)
        lista.append(val)
        return len(lista) - 1
    # -----------------------------------------------------------------------------

    # =========================================================================
    # VISTA DE EDICIÓN / APERTURA SIMÉTRICA
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
            u_motivo = c2.selectbox("MOTIVO:", options=lista_mot, index=safe_idx(lista_mot, cab['motivo']))
            u_cliente = c1.text_input("CLIENTE:", value=cab['cliente'] or "")
            u_proyecto = c2.selectbox("PROYECTO:", options=lista_proy, index=safe_idx(lista_proy, cab['proyecto']))
            u_sol_por = c1.selectbox("SOLICITADO POR:", options=lista_usu, index=safe_idx(lista_usu, cab['solicitado_por']))
            u_sup_prod = c2.text_input("SUP. PROD.:", value=cab['sup_production'] or "")
            u_estado = st.selectbox("ESTADO DE LA BITÁCORA:", ["Pendiente", "En Proceso", "Cerrada"], index=["Pendiente", "En Proceso", "Cerrada"].index(cab['estado']))

        res_l = supabase.table("bitacoras_lineas").select("*").eq("bitacora_id", id_act).order("id").execute()
        df_l = pd.DataFrame(res_l.data) if res_l.data else pd.DataFrame()

        lista_ops = [""] + [op['nombre'] for op in supabase.table("cfg_operarios").select("nombre").order("nombre").execute().data]
        lista_mats = [""] + [mat['detalle'] for mat in supabase.table("cfg_descripciones").select("detalle").order("detalle").execute().data]
        lista_cantos = [""] + [can['tipo'] for can in supabase.table("cfg_cantos").select("tipo").order("tipo").execute().data]
        # CARGA DEL NUEVO MAESTRO DINÁMICO DE SUPABASE (TABLERO / RETAZO)
        lista_tipos_piezas = [""] + [opt['opcion'] for opt in supabase.table("cfg_tipo_pieza_corte").select("opcion").order("opcion").execute().data]

        def filtrar_bloque(df, bloque_nom):
            if df.empty: return pd.DataFrame()
            sub_df = df[df['proceso_bloque'] == bloque_nom].copy()
            for col_f in ['fecha_inicio', 'fecha_termino']:
                if col_f in sub_df.columns:
                    sub_df[col_f] = sub_df[col_f].apply(lambda x: f"{x[5:7]}/{x[8:10]}" if (x and len(str(x)) >= 10 and str(x)[4] == '-') else x)
            return sub_df

        def garantizar_filas_por_seccion(df_bloque, bloque_id, cantidad_fija):
            columnas_base = ['id', 'cantidad', 'descripcion', 'tipo_canto', 'tipo_tablero_retazo', 'fecha_inicio', 'hora_inicio', 'hora_termino', 'fecha_termino', 'cant_final_pl_pzs', 'obs_incidencias']
            if df_bloque.empty:
                df_bloque = pd.DataFrame(columns=columnas_base)
            
            for col in columnas_base:
                if col not in df_bloque.columns:
                    df_bloque[col] = None
            
            actuales = len(df_bloque)
            if actuales < cantidad_fija:
                filas_faltantes = cantidad_fija - actuales
                nuevas_filas = []
                for _ in range(filas_faltantes):
                    nuevas_filas.append({
                        "id": "", "bitacora_id": id_act, "proceso_bloque": bloque_id,
                        "cantidad": None, "descripcion": "", "tipo_canto": "", "tipo_tablero_retazo": "",
                        "fecha_inicio": "", "hora_inicio": "", "hora_termino": "",
                        "fecha_termino": "", "cant_final_pl_pzs": "", "obs_incidencias": ""
                    })
                df_bloque = pd.concat([df_bloque, pd.DataFrame(nuevas_filas)], ignore_index=True)
            
            df_bloque['id'] = df_bloque['id'].fillna("")
            df_bloque['descripcion'] = df_bloque['descripcion'].fillna("")
            df_bloque['tipo_canto'] = df_bloque['tipo_canto'].fillna("")
            df_bloque['tipo_tablero_retazo'] = df_bloque['tipo_tablero_retazo'].fillna("")
            
            for idx, row in df_bloque.iterrows():
                if row['id'] == "":
                    df_bloque.at[idx, 'cantidad'] = None
                    df_bloque.at[idx, 'cant_final_pl_pzs'] = ""
            return df_bloque.head(cantidad_fija)

        # ASIGNACIÓN ESTRICTA: 6 filas para Seccionadora, 5 para Escuadradora y 9 para Canteo
        df_secc = garantizar_filas_por_seccion(filtrar_bloque(df_l, 'SECCIONADORA'), 'SECCIONADORA', 6)
        df_escu = garantizar_filas_por_seccion(filtrar_bloque(df_l, 'ESCUADRADORA'), 'ESCUADRADORA', 5)
        df_cant = garantizar_filas_por_seccion(filtrar_bloque(df_l, 'CANTEO'), 'CANTEO', 9)

        def generar_bloque_interfaz(titulo, bloque_id, df_bloque, col_salida_label):
            st.markdown(f'<div class="section-header">{titulo}</div>', unsafe_allow_html=True)
            op_actual1, op_actual2 = "", ""
            df_con_datos = df_bloque[df_bloque['id'] != ""]
            if not df_con_datos.empty:
                op_actual1 = df_con_datos['nombre_firma_operario'].iloc[0] or ""
                op_actual2 = df_con_datos['nombre_firma_operario2'].iloc[0] or ""
                
            cx1, cx2, cx3 = st.columns([2, 2, 2])
            # Clave única garantizada con bloque_id e id_act
            btn_ins = cx1.button(f"➕ Registro a {titulo.split(': ')[-1]}", key=f"btn_ins_{bloque_id}_{id_act}")
            
            idx_op1 = lista_ops.index(op_actual1) if op_actual1 in lista_ops else 0
            idx_op2 = lista_ops.index(op_actual2) if op_actual2 in lista_ops else 0
            
            op_val1 = cx2.selectbox("👨‍🔧 RESPONSABLE 1:", options=lista_ops, index=idx_op1, key=f"op_val1_{bloque_id}_{id_act}")
            op_val2 = cx3.selectbox("👥 RESPONSABLE 2:", options=lista_ops, index=idx_op2, key=f"op_val2_{bloque_id}_{id_act}")
            
            if btn_ins:
                supabase.table("bitacoras_lineas").insert({
                    "bitacora_id": id_act, "proceso_bloque": bloque_id, "cantidad": 0.0, 
                    "descripcion": "", "nombre_firma_operario": op_val1, "nombre_firma_operario2": op_val2
                }).execute()
                st.rerun()
            
            if bloque_id == 'CANTEO':
                columnas_visibles = ['id', 'cantidad', 'descripcion', 'tipo_canto', 'fecha_inicio', 'hora_inicio', 'hora_termino', 'fecha_termino', 'cant_final_pl_pzs', 'obs_incidencias']
                config_columnas = {
                    "id": None,
                    # Ancho incrementado a 80px (30% más) para '#', y descripción ajustada
                    "cantidad": st.column_config.NumberColumn("#", format="%.2f", width=80),
                    "descripcion": st.column_config.SelectboxColumn("DESCRIPCIÓN", options=lista_mats, required=False, width=275),
                    "tipo_canto": st.column_config.SelectboxColumn("TIPO", options=lista_cantos, required=False, width="medium"),
                    "fecha_inicio": st.column_config.TextColumn("F.I.", width="small"),
                    "hora_inicio": st.column_config.TextColumn("H.I.", width="small"),
                    "hora_termino": st.column_config.TextColumn("H.T.", width="small"),
                    "fecha_termino": st.column_config.TextColumn("F.T.", width="small"),
                    "cant_final_pl_pzs": st.column_config.TextColumn(col_salida_label, width="medium"),
                    "obs_incidencias": st.column_config.TextColumn("OBS", width="small")
                }
            else:
                columnas_visibles = ['id', 'cantidad', 'descripcion', 'tipo_tablero_retazo', 'fecha_inicio', 'hora_inicio', 'hora_termino', 'fecha_termino', 'cant_final_pl_pzs', 'obs_incidencias']
                config_columnas = {
                    "id": None,
                    # Ancho incrementado a 80px (30% más) para '#', y descripción ajustada
                    "cantidad": st.column_config.NumberColumn("#", format="%.2f", width=80),
                    "descripcion": st.column_config.SelectboxColumn("DESCRIPCIÓN", options=lista_mats, required=False, width=275),
                    "tipo_tablero_retazo": st.column_config.SelectboxColumn("TIPO", options=lista_tipos_piezas, required=False, width="medium"),
                    "fecha_inicio": st.column_config.TextColumn("F.I.", width="small"),
                    "hora_inicio": st.column_config.TextColumn("H.I.", width="small"),
                    "hora_termino": st.column_config.TextColumn("H.T.", width="small"),
                    "fecha_termino": st.column_config.TextColumn("F.T.", width="small"),
                    "cant_final_pl_pzs": st.column_config.TextColumn(col_salida_label, width="medium"),
                    "obs_incidencias": st.column_config.TextColumn("OBS", width="small")
                }

            df_limpio = df_bloque[columnas_visibles].copy()
            res_ed = st.data_editor(
                df_limpio, column_config=config_columnas, hide_index=True, use_container_width=True, key=f"grid_{bloque_id}_{id_act}"
            )
            return res_ed, op_val1, op_val2
            
            if bloque_id == 'CANTEO':
                columnas_visibles = ['id', 'cantidad', 'descripcion', 'tipo_canto', 'fecha_inicio', 'hora_inicio', 'hora_termino', 'fecha_termino', 'cant_final_pl_pzs', 'obs_incidencias']
                config_columnas = {
                    "id": None,
                    "cantidad": st.column_config.NumberColumn("#", format="%.2f", width=80),
                    # Descripción reducida para ceder espacio a TIPO y Salida
                    "descripcion": st.column_config.SelectboxColumn("DESCRIPCIÓN", options=lista_mats, required=False, width=240),
                    # TIPO y ML CANTO expandidos explícitamente a 140px
                    "tipo_canto": st.column_config.SelectboxColumn("TIPO", options=lista_cantos, required=False, width=140),
                    "fecha_inicio": st.column_config.TextColumn("F.I.", width="small"),
                    "hora_inicio": st.column_config.TextColumn("H.I.", width="small"),
                    "hora_termino": st.column_config.TextColumn("H.T.", width="small"),
                    "fecha_termino": st.column_config.TextColumn("F.T.", width="small"),
                    "cant_final_pl_pzs": st.column_config.TextColumn(col_salida_label, width=140),
                    "obs_incidencias": st.column_config.TextColumn("OBS", width="small")
                }
            else:
                columnas_visibles = ['id', 'cantidad', 'descripcion', 'tipo_tablero_retazo', 'fecha_inicio', 'hora_inicio', 'hora_termino', 'fecha_termino', 'cant_final_pl_pzs', 'obs_incidencias']
                config_columnas = {
                    "id": None,
                    "cantidad": st.column_config.NumberColumn("#", format="%.2f", width=80),
                    # Descripción reducida para ceder espacio a TIPO y Salida
                    "descripcion": st.column_config.SelectboxColumn("DESCRIPCIÓN", options=lista_mats, required=False, width=240),
                    # TIPO y N° PL/PZAS expandidos explícitamente a 140px
                    "tipo_tablero_retazo": st.column_config.SelectboxColumn("TIPO", options=lista_tipos_piezas, required=False, width=140),
                    "fecha_inicio": st.column_config.TextColumn("F.I.", width="small"),
                    "hora_inicio": st.column_config.TextColumn("H.I.", width="small"),
                    "hora_termino": st.column_config.TextColumn("H.T.", width="small"),
                    "fecha_termino": st.column_config.TextColumn("F.T.", width="small"),
                    "cant_final_pl_pzs": st.column_config.TextColumn(col_salida_label, width=140),
                    "obs_incidencias": st.column_config.TextColumn("OBS", width="small")
                }
            df_limpio = df_bloque[columnas_visibles].copy()
            res_ed = st.data_editor(
                df_limpio, column_config=config_columnas, hide_index=True, use_container_width=True, key=f"grid_{bloque_id}_{id_act}"
            )
            return res_ed, op_val1, op_val2

        ed_secc, op_secc1, op_secc2 = generar_bloque_interfaz("🪚 SECCIÓN 2: CORTE SECCIONADORA", "SECCIONADORA", df_secc, "N° PL.")
        ed_escu, op_escu1, op_escu2 = generar_bloque_interfaz("📐 SECCIÓN 3: CORTE ESCUADRADORA", "ESCUADRADORA", df_escu, "N° PZAS")
        ed_cant, op_cant1, op_cant2 = generar_bloque_interfaz("⚙️ SECCIÓN 4: CANTEO", "CANTEO", df_cant, "ML CANTO")

        # Se elimina el título de la sección 5 para ahorrar espacio vertical
        with st.container(border=True):
            c_arm, c_des = st.columns(2)
            with c_arm:
                st.markdown("<b>📦 ZONA DE ARMADO (Taller)</b>", unsafe_allow_html=True)
                f_arm_val = cab.get('log_armado_fecha')
                f_arm_dt = datetime.strptime(f_arm_val, "%Y-%m-%d").date() if f_arm_val else None
                u_log_armado_fecha = st.date_input("FECHA RECEPCIÓN (ARMADO):", value=f_arm_dt, format="DD/MM/YYYY", key="f_arm_log")
                u_log_armado_cant = st.text_input("Nº PALLETS / PIEZAS (ARMADO):", value=cab.get('log_armado_cant') or "")
                u_log_armado_vob = st.text_input("VºBº SUP. PRODUCCIÓN:", value=cab.get('log_armado_vob') or "")
            with c_des:
                st.markdown("<b>📦 ZONA DE DESPACHO (Directo a Obra)</b>", unsafe_allow_html=True)
                f_des_val = cab.get('log_despacho_fecha')
                f_des_dt = datetime.strptime(f_des_val, "%Y-%m-%d").date() if f_des_val else None
                u_log_despacho_fecha = st.date_input("FECHA RECEPCIÓN (DESPACHO):", value=f_des_dt, format="DD/MM/YYYY", key="f_des_log")
                u_log_despacho_cant = st.text_input("Nº PALLETS / PIEZAS (DESPACHO):", value=cab.get('log_despacho_cant') or "")
                u_log_despacho_vob = st.text_input("VºBº ALMACÉN / DESPACHO:", value=cab.get('log_despacho_vob') or "")

            col_s1, col_s2, col_s3 = st.columns(3)
            f_sal_val = cab.get('log_salida_fecha')
            f_sal_dt = datetime.strptime(f_sal_val, "%Y-%m-%d").date() if f_sal_val else None
            u_log_salida_fecha = col_s1.date_input("FECHA SALIDA A OBRA:", value=f_sal_dt, format="DD/MM/YYYY", key="f_sal_log")
            u_log_salida_conductor = col_s2.text_input("CONDUCTOR / CHOFER:", value=cab.get('log_salida_conductor') or "")
            u_log_salida_vob = col_s3.text_input("VºBº ALMACÉN (SALIDA):", value=cab.get('log_salida_vob') or "")
            u_log_observaciones = st.text_area("Observaciones de Logística:", value=cab.get('log_observaciones') or "", height=20)

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
                        if not r['descripcion'] or pd.isna(r['descripcion']) or str(r['descripcion']).strip() == "":
                            continue
                        def normalizar_fecha_iso(val):
                            if not val or pd.isna(val): return None
                            t = str(val).strip()
                            return f"2026-{t[3:5]}-{t[0:2]}" if (len(t) == 5 and "/" in t) else t
                        
                        payload = {
                            "bitacora_id": id_act, "proceso_bloque": bloque_id,
                            "cantidad": float(r['cantidad']) if r['cantidad'] else 0.0,
                            "descripcion": str(r['descripcion']).strip(),
                            "tipo_canto": str(r['tipo_canto']).strip() if 'tipo_canto' in r and r['tipo_canto'] else None,
                            "tipo_tablero_retazo": str(r['tipo_tablero_retazo']).strip() if 'tipo_tablero_retazo' in r and r['tipo_tablero_retazo'] else None,
                            "fecha_inicio": normalizar_fecha_iso(r['F.I.'] if 'F.I.' in r else r.get('fecha_inicio')),
                            "hora_inicio": str(r['H.I.'] if 'H.I.' in r else r.get('hora_inicio')).strip(),
                            "cant_final_pl_pzs": str(r['cant_final_pl_pzs']).strip() if 'cant_final_pl_pzs' in r else None,
                            "hora_termino": str(r['H.T.'] if 'H.T.' in r else r.get('hora_termino')).strip(),
                            "fecha_termino": normalizar_fecha_iso(r['F.T.'] if 'F.T.' in r else r.get('fecha_termino')),
                            "obs_incidencias": str(r['OBS'] if 'OBS' in r else r.get('obs_incidencias')).strip(),
                            "nombre_firma_operario": op1, "nombre_firma_operario2": op2
                        }
                        if pd.notna(r['id']) and r['id'] != "":
                            supabase.table("bitacoras_lineas").update(payload).eq("id", int(r['id'])).execute()
                        else:
                            supabase.table("bitacoras_lineas").insert(payload).execute()

                procesar_lote_guardado(ed_secc, "SECCIONADORA", op_secc1, op_secc2)
                procesar_lote_guardado(ed_escu, "ESCUADRADORA", op_escu1, op_escu2)
                procesar_lote_guardado(ed_cant, "CANTEO", op_cant1, op_cant2)
                st.success("🎉 Trazabilidad y ordenación guardados."); st.rerun()
            except Exception as e:
                st.error(f"Falla de sincronización: {e}")
        
       # =========================================================================
        # RECONSTRUCCIÓN CRÍTICA DE REPORTLAB - FOLIO ÚNICO Y ANCHOS CALIBRADOS
        # =========================================================================
        try:
            buffer_pdf = io.BytesIO()
            doc_pdf = SimpleDocTemplate(buffer_pdf, pagesize=A4, rightMargin=10, leftMargin=10, topMargin=10, bottomMargin=10)
            story = []
            
            # VALORES AMPLIADOS UN 10% ADICIONAL (Letra 10.5pt y filas más altas con pad_v = 3.0)
            f_sz, f_ld, pad_v = 10.5, 13.0, 3.0
            style_normal = ParagraphStyle('Norm', fontName='Helvetica', fontSize=f_sz, leading=f_ld)
            style_bold = ParagraphStyle('Bld', fontName='Helvetica-Bold', fontSize=f_sz, leading=f_ld)
            style_title = ParagraphStyle('Tit', fontName='Helvetica-Bold', fontSize=12, leading=14, alignment=1)
            style_seccion_titulo = ParagraphStyle('SecTit', fontName='Helvetica-Bold', fontSize=15.5, leading=18.0, alignment=1)
            
            story.append(Paragraph("<b>BITÁCORA DE PRODUCCIÓN</b>", style_title))
            story.append(Spacer(1, 2))
            
            data_s1 = [
                [Paragraph("<b>FECHA:</b>", style_normal), Paragraph(u_fecha.strftime("%d/%m/%Y"), style_normal), Paragraph("<b>Nº ORDEN:</b>", style_normal), Paragraph(u_n_orden, style_normal)],
                [Paragraph("<b>TIPO DE MUEBLE:</b>", style_normal), Paragraph(u_tipo_mueble, style_normal), Paragraph("<b>MOTIVO:</b>", style_normal), Paragraph(u_motivo, style_normal)],
                [Paragraph("<b>CLIENTE:</b>", style_normal), Paragraph(u_cliente, style_normal), Paragraph("<b>PROYECTO:</b>", style_normal), Paragraph(u_proyecto, style_normal)],
                [Paragraph("<b>SOLICITADO POR:</b>", style_normal), Paragraph(u_sol_por, style_normal), Paragraph("<b>SUP. DE PROD:</b>", style_normal), Paragraph(u_sup_prod, style_normal)]
            ]
            t_s1 = Table(data_s1, colWidths=[110, 186, 110, 186])
            t_s1.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (0,3), colors.lightgrey), 
                ('BACKGROUND', (2,0), (2,3), colors.lightgrey), 
                ('GRID', (0,0), (-1,-1), 0.5, colors.black), 
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('TOPPADDING', (0,0), (-1,-1), pad_v + 1),
                ('BOTTOMPADDING', (0,0), (-1,-1), pad_v + 1)
            ]))
            story.append(t_s1)
            story.append(Spacer(1, 2))
            
            def inyectar_tabla_pdf(titulo, cabeceras, df_ed, op1, op2, ancho_cols):
                op_text = f"{op1} / {op2}".strip(" / ")
                story.append(Paragraph(f"<b>{titulo}</b>", style_seccion_titulo))
                rows_pdf = [[Paragraph(f"<b>{h}</b>", style_bold) for h in cabeceras]]
                
                for _, r in df_ed.iterrows():
                    fila = []
                    es_vacia = (str(r.get('id','')) == "")
                    for col_id in df_ed.columns:
                        if col_id != 'id':
                            val_t = "" if es_vacia else str(r[col_id])
                            if val_t.lower() == "nan" or val_t == "None" or val_t == "0.0": 
                                val_t = ""
                            
                            p_celda = Paragraph("&nbsp;" if val_t == "" else val_t, style_normal)
                            fila.append(p_celda)
                    rows_pdf.append(fila)
                
                rows_pdf.append([Paragraph(f"<b>RESPONSABLE (S):</b> {op_text}", style_normal), "", "", "", "", "", "", Paragraph("<b>V°B° SUP PROD:</b>", style_normal), ""])
                    
                t_block = Table(rows_pdf, colWidths=ancho_cols)
                t_block.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.lightgrey), 
                    ('GRID', (0,0), (-1,-2), 0.5, colors.black),
                    ('BOX', (0,-1), (-1,-1), 0.5, colors.black),
                    ('LINEBEFORE', (7,-1), (7,-1), 0.5, colors.black),
                    ('SPAN', (0,-1), (6,-1)),
                    ('SPAN', (7,-1), (8,-1)),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), 
                    ('TOPPADDING', (0,0), (-1,-2), pad_v), 
                    ('BOTTOMPADDING', (0,0), (-1,-2), pad_v),
                    ('TOPPADDING', (0,-1), (-1,-1), pad_v + 4), 
                    ('BOTTOMPADDING', (0,-1), (-1,-1), pad_v + 4)
                ]))
                story.append(t_block)
                story.append(Spacer(1, 2))

            # ANCHOS CALIBRADOS: TIPO (+15% = 63 pt), Salida (+15% = 69 pt), Descripción reducida a 197 pt
            # Suma total exacta mantenida: 38 + 197 + 63 + 35 + 35 + 35 + 35 + 69 + 85 = 592 pt
            anchos_tabla_corte = [38, 197, 63, 35, 35, 35, 35, 69, 85]
            
            inyectar_tabla_pdf("CORTE SECCIONADORA", ["#", "DESCRIPCIÓN", "TIPO", "F.I.", "H.I.", "H.T.", "F.T.", "N° PL.", "OBS"], ed_secc, op_secc1, op_secc2, anchos_tabla_corte)
            inyectar_tabla_pdf("CORTE ESCUADRADORA", ["#", "DESCRIPCIÓN", "TIPO", "F.I.", "H.I.", "H.T.", "F.T.", "N° PZAS", "OBS"], ed_escu, op_escu1, op_escu2, anchos_tabla_corte)            
            
            # CANTEO CON ANCHOS CALIBRADOS
            op_cant_text = f"{op_cant1} / {op_cant2}".strip(" / ")
            story.append(Paragraph("<b>CANTEO</b>", style_seccion_titulo))
            rows_canteo = [[Paragraph(f"<b>{h}</b>", style_bold) for h in ["#", "DESCRIPCIÓN", "TIPO", "F.I.", "H.I.", "H.T.", "F.T.", "ML CANTO", "OBS"]]]
            
            columnas_canteo_mapeo = ['cantidad', 'descripcion', 'tipo_canto', 'fecha_inicio', 'hora_inicio', 'hora_termino', 'fecha_termino', 'cant_final_pl_pzs', 'obs_incidencias']
            for _, r in ed_cant.iterrows():
                fila_c = []
                es_vacia = (str(r.get('id','')) == "")
                for col_id in columnas_canteo_mapeo:
                    val_t = "" if es_vacia else str(r[col_id])
                    if val_t.lower() == "nan" or val_t == "None" or val_t == "0.0": 
                        val_t = ""
                    
                    p_celda = Paragraph("&nbsp;" if val_t == "" else val_t, style_normal)
                    fila_c.append(p_celda)
                rows_canteo.append(fila_c)
                
            rows_canteo.append([Paragraph(f"<b>RESPONSABLE (S):</b> {op_cant_text}", style_normal), "", "", "", "", "", "", Paragraph("<b>V°B° SUP PROD:</b>", style_normal), ""])
            
            t_cant = Table(rows_canteo, colWidths=anchos_tabla_corte)
            t_cant.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                ('GRID', (0,0), (-1,-2), 0.5, colors.black),
                ('BOX', (0,-1), (-1,-1), 0.5, colors.black),
                ('LINEBEFORE', (7,-1), (7,-1), 0.5, colors.black),
                ('SPAN', (0,-1), (6,-1)),
                ('SPAN', (7,-1), (8,-1)),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('TOPPADDING', (0,0), (-1,-2), pad_v),
                ('BOTTOMPADDING', (0,0), (-1,-2), pad_v),
                ('TOPPADDING', (0,-1), (-1,-1), pad_v + 4),
                ('BOTTOMPADDING', (0,-1), (-1,-1), pad_v + 4)
            ]))
            story.append(t_cant)
            story.append(Spacer(1, 2))

            f_arm_p = u_log_armado_fecha.strftime("%d/%m/%Y") if u_log_armado_fecha else ""
            f_des_p = u_log_despacho_fecha.strftime("%d/%m/%Y") if u_log_despacho_fecha else ""
            f_sal_p = u_log_salida_fecha.strftime("%d/%m/%Y") if u_log_salida_fecha else ""

            data_tres_columnas = [
                [
                    Paragraph("<b>ZONA DE ARMADO</b>", style_bold), 
                    Paragraph("<b>ZONA DE DESPACHO</b>", style_bold), 
                    Paragraph("<b>ZONA DE SALIDA</b>", style_bold)
                ],
                [
                    Paragraph(f"FECHA: {f_arm_p}", style_normal), 
                    Paragraph(f"FECHA: {f_des_p}", style_normal), 
                    Paragraph(f"SALIDA A OBRA: {f_sal_p}", style_normal)
                ],
                [
                    Paragraph(f"Nº PALLETS: {u_log_armado_cant}", style_normal), 
                    Paragraph(f"Nº PALLETS: {u_log_despacho_cant}", style_normal), 
                    Paragraph(f"CONDUCTOR: {u_log_salida_conductor}", style_normal)
                ],
                [
                    Paragraph(f"VºBº SUP. PROD: {u_log_armado_vob}", style_normal), 
                    Paragraph(f"V°B° ALMACÉN: {u_log_despacho_vob}", style_normal), 
                    Paragraph(f"V°B° ALMACÉN: {u_log_salida_vob}", style_normal)
                ]
            ]
            
            t_log_tres = Table(data_tres_columnas, colWidths=[197, 197, 198])
            t_log_tres.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey), 
                ('GRID', (0,0), (-1,-1), 0.5, colors.black), 
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), 
                # Padding estándar para las filas superiores de la sección 5
                ('TOPPADDING', (0,0), (-1,-2), pad_v), 
                ('BOTTOMPADDING', (0,0), (-1,-2), pad_v),
                # Última fila (V°B° / Firmas) con altura incrementada un 15% para mayor espacio
                ('TOPPADDING', (0,-1), (-1,-1), pad_v + 5.5), 
                ('BOTTOMPADDING', (0,-1), (-1,-1), pad_v + 5.5)
            ]))
            story.append(t_log_tres)
            
            doc_pdf.build(story)
            c_pdf.download_button("🖨️ EXPORTAR EN UN SOLO FOLIO (PDF)", data=buffer_pdf.getvalue(), file_name=f"Format_B_{u_n_orden}.pdf", mime="application/pdf", use_container_width=True)
        except Exception as e_pdf:
            c_pdf.error(f"Aviso de compactación: {e_pdf}")
            
    # =========================================================================
    # ENTORNO INICIAL (PESTAÑAS HISTORIAL, ALTA Y CONFIGURACIÓN MAESTROS)
    # =========================================================================
    else:
        tab_listado, tab_alta_nueva, tab_config, tab_importacion_historica = st.tabs(["🗂️ Listado de Bitácoras", "➕ Nueva Bitácora", "⚙️ Configuración de Catálogos", "📥 Importación Histórica"])
        
        with tab_listado:
            filtro = st.text_input("🔍 Filtro rápido de búsqueda:", placeholder="Escriba la OP o cliente...")
            try:
                res_t = supabase.table("bitacoras_taller").select("*").execute()
                df_t = pd.DataFrame(res_t.data) if res_t.data else pd.DataFrame()
            except:
                df_t = pd.DataFrame()
                
            if filtro and not df_t.empty:
                df_t = df_t[df_t['n_orden'].astype(str).str.contains(filtro, case=False) | df_t['cliente'].astype(str).str.contains(filtro, case=False)]
                
            if not df_t.empty:
                df_t = df_t.sort_values(by="fecha", ascending=False)
                
                # INYECCIÓN DE COLUMNAS DE SELECCIÓN Y BORRADO
                df_t.insert(0, "EDITAR", False)
                df_t.insert(1, "ELIMINAR", False)
                
                st.caption("💡 Para borrar bitácoras creadas por error, marque las casillas de la columna 🗑️ y presione el botón rojo al final.")
                df_estados = st.data_editor(
                    df_t[['EDITAR', 'ELIMINAR', 'id', 'fecha', 'n_orden', 'proyecto', 'cliente', 'tipo_mueble', 'estado']],
                    column_config={
                        "EDITAR": st.column_config.CheckboxColumn("✏️ Abrir", help="Marque para abrir el formato inmediatamente", default=False),
                        "ELIMINAR": st.column_config.CheckboxColumn("🗑️ Borrar", default=False),
                        "id": st.column_config.TextColumn("ID", disabled=True),
                        "fecha": st.column_config.TextColumn("FECHA", disabled=True),
                        "estado": st.column_config.SelectboxColumn("ESTADO", options=["Pendiente", "En Proceso", "Cerrada"], required=True)
                    },
                    hide_index=True, use_container_width=True, key="grid_estados_inicial"
                )
                
                # CONTROLADOR DE TRIGER INMEDIATO
                filas_editadas = df_estados[df_estados["EDITAR"] == True]
                if not filas_editadas.empty:
                    id_seleccionado = int(filas_editadas.iloc[0]["id"])
                    st.session_state.id_bitacora_activa = id_seleccionado
                    st.rerun()
                
                c_act, c_del = st.columns(2)
                if c_act.button("💾 Actualizar Estados Modificados", type="primary", use_container_width=True):
                    for _, r_e in df_estados.iterrows():
                        supabase.table("bitacoras_taller").update({"estado": r_e['estado']}).eq("id", int(r_e['id'])).execute()
                    st.success("Estados guardados."); st.rerun()
                    
                # MOTOR DE ELIMINACIÓN EN CASCADA ROBUSTO Y PERSISTENTE
                if c_del.button("🔥 Eliminar Bitácoras Seleccionadas", type="primary", use_container_width=True):
                    filas_borrar = df_estados[df_estados["ELIMINAR"] == True]
                    if not filas_borrar.empty:
                        # Convertimos estrictamente los IDs a enteros para evitar errores de tipo en Supabase
                        ids_borrar = [int(x) for x in filas_borrar['id'].tolist()]
                        try:
                            borradas_exito = 0
                            for id_b in ids_borrar:
                                # 1. Borramos primero todas las líneas hijas asociadas a esta bitácora
                                supabase.table("bitacoras_lineas").delete().eq("bitacora_id", id_b).execute()
                                # 2. Borramos la cabecera principal de la bitácora
                                supabase.table("bitacoras_taller").delete().eq("id", id_b).execute()
                                borradas_exito += 1
                                
                            st.success(f"Se eliminaron {borradas_exito} bitácoras permanentemente de la base de datos.")
                            # Limpiamos caché de sesión si se borró la bitácora activa
                            if st.session_state.get('id_bitacora_activa') in ids_borrar:
                                st.session_state.id_bitacora_activa = None
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error crítico al eliminar en base de datos: {e}")
                    else:
                        st.warning("Debe marcar al menos una bitácora en la columna 🗑️ para eliminarla.")
                        
                st.caption("---")
                id_abrir = st.number_input("O digite el ID de Bitácora manualmente:", min_value=1, step=1)
                if st.button("🔓 Abrir por ID Manual", type="secondary"):
                    st.session_state.id_bitacora_activa = int(id_abrir)
                    st.rerun()
            else:
                st.info("No hay bitácoras bajo este criterio.")

        # MANEJO DE ESTADO DE ÉXITO PERSISTENTE
        if st.session_state.get('bitacora_creada_exito'):
            st.success(st.session_state.bitacora_creada_exito)
            st.session_state.bitacora_creada_exito = None

        with tab_alta_nueva:
            with st.form("form_alta_inicial"):
                f_n = st.date_input("FECHA:", value=date.today(), format="DD/MM/YYYY")
                o_n = st.text_input("Nº ORDEN:")
                m_n = st.text_input("TIPO DE MUEBLE:")
                mt_n = st.selectbox("MOTIVO:", options=lista_mot, index=safe_idx(lista_mot, "Nuevo Pedido"))
                cl_n = st.text_input("CLIENTE:")
                pr_n = st.selectbox("PROYECTO:", options=lista_proy)
                sl_n = st.selectbox("SOLICITADO POR:", options=lista_usu)
                sp_n = st.text_input("SUP. DE PRODUCCION:", value="DOMÉNICO MORÓN")
                
                if st.form_submit_button("🚀 Inicializar Bitácora", type="primary"):
                    if not str(o_n).strip():
                        st.error("⚠️ El Nº DE ORDEN es obligatorio para crear una bitácora.")
                    else:
                        n_orden_limpio = str(o_n).strip()
                        res_check = supabase.table("bitacoras_taller").select("id").eq("n_orden", n_orden_limpio).execute()
                        
                        if res_check.data and len(res_check.data) > 0:
                            st.error(f"❌ ¡ATENCIÓN! Ya existe una bitácora con el Nº de Orden '{n_orden_limpio}'. No se permiten duplicados.")
                        else:
                            try:
                                res_ins = supabase.table("bitacoras_taller").insert({
                                    "fecha": f_n.isoformat(), "n_orden": n_orden_limpio, "tipo_mueble": m_n,
                                    "motivo": mt_n, "cliente": cl_n, "proyecto": pr_n,
                                    "solicitado_por": sl_n, "sup_production": sp_n, "estado": "Pendiente"
                                }).execute()
                                
                                st.session_state.bitacora_creada_exito = f"✅ Bitácora '{n_orden_limpio}' creada exitosamente."
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al conectar con la base de datos: {e}")

        # ADICIÓN DEL CUARTO MAESTRO DINÁMICO EN LA PESTAÑA DE GESTIÓN CORPORATIVA
        with tab_config:
            st.caption("Administración corporativa de catálogos activos para los componentes predictivos de planta.")
            
            # 1️⃣ CORRECCIÓN: "Motivos de Bitácora" agregado a la lista
            sel_maestro = st.selectbox("Seleccione el Catálogo a gestionar:", ["Responsables (Operarios)", "Materiales (Descripciones)", "Tipos de Canto", "Origen de Material (Tablero/Retazo)", "Motivos de Bitácora"])
            
            if sel_maestro == "Responsables (Operarios)":
                st.markdown("#### 👨‍🔧 Registro de Operarios de Planta")
                with st.form("form_op"):
                    nuevo_op = st.text_input("Nombre completo del Operario:")
                    if st.form_submit_button("➕ Registrar Operario"):
                        if nuevo_op.strip():
                            supabase.table("cfg_operarios").insert({"nombre": nuevo_op.strip().upper()}).execute()
                            st.success("Operario registrado."); st.rerun()
                try:
                    df_ops = pd.DataFrame(supabase.table("cfg_operarios").select("*").order("nombre").execute().data)
                    st.data_editor(df_ops, column_config={"id": None}, hide_index=True, use_container_width=True)
                except: st.info("Catálogo vacío.")

            # 2️⃣ CORRECCIÓN: Cambiado de 'if' a 'elif'
            elif sel_maestro == "Motivos de Bitácora":
                st.markdown("#### 📌 Catálogo de Motivos")
                with st.form("form_motivo"):
                    nuevo_mot = st.text_input("Nuevo Motivo:")
                    if st.form_submit_button("➕ Añadir Motivo"):
                        if nuevo_mot.strip():
                            supabase.table("cfg_motivos").insert({"motivo": nuevo_mot.strip().upper()}).execute()
                            st.success("Motivo registrado."); st.rerun()
                try:
                    df_mots = pd.DataFrame(supabase.table("cfg_motivos").select("*").order("motivo").execute().data)
                    st.data_editor(df_mots, column_config={"id": None}, hide_index=True, use_container_width=True)
                except: st.info("Catálogo vacío.")
                    
            elif sel_maestro == "Materiales (Descripciones)":
                st.markdown("#### 🪵 Catálogo Maestro de Melamina y Tableros")
                
                # Formulario para registro manual (individual) CON CÓDIGO
                with st.form("form_mat"):
                    c_form1, c_form2 = st.columns([1, 3])
                    nuevo_codigo = c_form1.text_input("Código (Ej. 1BLA):")
                    nuevo_mat = c_form2.text_input("Detalle/Nombre comercial del Tablero:")
                    
                    if st.form_submit_button("➕ Añadir Material"):
                        if nuevo_mat.strip():
                            # Se inserta tanto el detalle como el código en Supabase
                            supabase.table("cfg_descripciones").insert({
                                "detalle": nuevo_mat.strip().upper(),
                                "codigo": nuevo_codigo.strip().upper() if nuevo_codigo.strip() else None
                            }).execute()
                            st.success("Material añadido con éxito."); st.rerun()
                        else:
                            st.warning("El nombre/detalle del material es obligatorio.")
                
                # --- NUEVA SECCIÓN: IMPORTACIÓN MASIVA DESDE EXCEL ---
                st.markdown("---")
                st.markdown("##### 📥 Importación Masiva desde Excel")
                st.info("El archivo debe ser un Excel (.xlsx) y puede contener las columnas **'Codigo'** y **'Material'**.")
                
                archivo_subido = st.file_uploader("Seleccione el archivo Excel de colores/tableros:", type=["xlsx", "xls"], key="uploader_materiales")
                
                if archivo_subido is not None:
                    try:
                        df_importado = pd.read_excel(archivo_subido)
                        # Normalizar nombres de columnas a mayúsculas para evitar errores tipográficos
                        df_importado.columns = [str(c).strip().upper() for c in df_importado.columns]
                        
                        if "MATERIAL" in df_importado.columns:
                            # Aseguramos que la columna CODIGO exista, si no la creamos vacía
                            if "CODIGO" not in df_importado.columns:
                                df_importado["CODIGO"] = ""
                                
                            df_materiales = df_importado[["CODIGO", "MATERIAL"]].dropna(subset=["MATERIAL"])
                            df_materiales["MATERIAL"] = df_materiales["MATERIAL"].astype(str).str.strip().str.upper()
                            df_materiales["CODIGO"] = df_materiales["CODIGO"].fillna("").astype(str).str.strip().str.upper()
                            
                            # Eliminamos duplicados basados en el nombre del material para la vista previa
                            df_unicos = df_materiales.drop_duplicates(subset=["MATERIAL"])
                            
                            st.write(f"📊 Registros válidos encontrados en el archivo: **{len(df_unicos)}**")
                            
                            if st.button("🚀 Confirmar e Importar a Base de Datos", type="primary", key="btn_confirmar_importacion"):
                                with st.spinner("Procesando importación..."):
                                    res_existentes = supabase.table("cfg_descripciones").select("detalle").execute()
                                    materiales_existentes = {row["detalle"].strip().upper() for row in res_existentes.data} if res_existentes.data else set()
                                    
                                    nuevos_materiales = []
                                    for _, row in df_unicos.iterrows():
                                        mat_nombre = row["MATERIAL"]
                                        if mat_nombre and mat_nombre not in materiales_existentes:
                                            codigo_val = row["CODIGO"] if row["CODIGO"] else None
                                            nuevos_materiales.append({"detalle": mat_nombre, "codigo": codigo_val})
                                            # Añadimos al set local para evitar duplicados dentro del mismo lote
                                            materiales_existentes.add(mat_nombre) 
                                    
                                    if nuevos_materiales:
                                        supabase.table("cfg_descripciones").insert(nuevos_materiales).execute()
                                        st.success(f"🎉 Se han importado con éxito **{len(nuevos_materiales)}** nuevos materiales con sus códigos.")
                                    else:
                                        st.warning("⚠️ Todos los materiales del archivo ya existen en el catálogo actual.")
                                    st.rerun()
                        else:
                            st.error("❌ Estructura inválida. El documento debe contener al menos una columna llamada **'Material'**.")
                    except Exception as e:
                        st.error(f"❌ Error al procesar el archivo: {e}")
                # ----------------------------------------------------
                
                try:
                    df_mats = pd.DataFrame(supabase.table("cfg_descripciones").select("id, codigo, detalle").order("detalle").execute().data)
                    # Reordenamos columnas para que ID no se vea, y el Código aparezca antes del Detalle
                    if not df_mats.empty:
                        config_grid = {
                            "id": None,
                            "codigo": st.column_config.TextColumn("CÓDIGO", width="small"),
                            "detalle": st.column_config.TextColumn("NOMBRE DEL MATERIAL", width="large")
                        }
                        st.data_editor(df_mats, column_config=config_grid, hide_index=True, use_container_width=True)
                except Exception as e_grid: 
                    st.info("Catálogo vacío o error al cargar.")

        # =========================================================================
        # IMPORTACIÓN DIRECTA (Excel .xlsx) - OPTIMIZADA Y ROBUSTA
        # =========================================================================
        with tab_importacion_historica: 
            st.subheader("📥 Importación Automatizada (Excel)")
            st.info("El archivo Excel debe contener las columnas: **n_orden, cantidad, tipo_tablero_retazo, tipo_canto, descripcion, fecha_inicio, proceso_bloque, obs_incidencias**.")
            
            archivo_historico = st.file_uploader("Seleccione el archivo Excel (.xlsx)", type=["xlsx"], key="up_junio_xlsx_v3")

            if archivo_historico is not None:
                try:
                    df = pd.read_excel(archivo_historico)
                    df.columns = df.columns.str.strip()

                    st.markdown("<b>🔍 Vista previa de los datos a importar:</b>", unsafe_allow_html=True)
                    st.dataframe(df.head(10), use_container_width=True)

                    if st.button("🚀 Migrar Registros de Excel", type="primary"):
                        with st.spinner("Procesando y sincronizando con Supabase..."):
                            res_taller = supabase.table("bitacoras_taller").select("id, n_orden").execute()
                            dict_ops = {str(r["n_orden"]).strip(): int(r["id"]) for r in res_taller.data} if res_taller.data else {}
                            
                            registros_lineas = []
                            oks_creadas = 0
                            
                            for _, row in df.iterrows():
                                n_orden_raw = row.get('n_orden')
                                if pd.isna(n_orden_raw): 
                                    continue
                                    
                                n_orden = str(int(n_orden_raw)) if isinstance(n_orden_raw, (int, float)) else str(n_orden_raw).strip()
                                if not n_orden or n_orden == 'nan': 
                                    continue

                                if n_orden not in dict_ops:
                                    fecha_op = str(row.get('fecha_inicio')) if pd.notna(row.get('fecha_inicio')) else date.today().isoformat()
                                    fecha_op = fecha_op.split("T")[0] if "T" in fecha_op else fecha_op[:10]
                                    
                                    nueva_op_res = supabase.table("bitacoras_taller").insert({
                                        "n_orden": n_orden,
                                        "fecha": fecha_op,
                                        "estado": "Cerrada",
                                        "tipo_mueble": "IMPORTADO",
                                        "motivo": "CARGA HISTÓRICA"
                                    }).execute()
                                    
                                    if nueva_op_res.data:
                                        new_id = int(nueva_op_res.data[0]["id"])
                                        dict_ops[n_orden] = new_id
                                        oks_creadas += 1

                                def get_num(col):
                                    val = row.get(col)
                                    if pd.isna(val) or str(val).strip() in ['-', '', 'nan', 'None']:
                                        return 0.0
                                    try:
                                        return float(val)
                                    except:
                                        return 0.0

                                def get_str(col):
                                    val = row.get(col)
                                    if pd.isna(val) or str(val).strip() in ['nan', 'None']:
                                        return ""
                                    return str(val).strip()

                                def get_date(col):
                                    val = row.get(col)
                                    if pd.isna(val) or str(val).strip() in ['nan', 'None', '']:
                                        return date.today().isoformat()
                                    s = str(val).strip()
                                    return s.split("T")[0] if "T" in s else s[:10]

                                reg = {
                                    "bitacora_id": dict_ops[n_orden],
                                    "proceso_bloque": get_str('proceso_bloque').upper() if get_str('proceso_bloque') else "SECCIONADORA",
                                    "cantidad": get_num('cantidad'),
                                    "descripcion": get_str('descripcion'),
                                    "tipo_tablero_retazo": get_str('tipo_tablero_retazo') if get_str('tipo_tablero_retazo') else None,
                                    "tipo_canto": get_str('tipo_canto') if get_str('tipo_canto') else None,
                                    "fecha_inicio": get_date('fecha_inicio'),
                                    "obs_incidencias": get_str('obs_incidencias') if get_str('obs_incidencias') else None
                                }
                                registros_lineas.append(reg)
                            
                            if registros_lineas:
                                tam_lote = 100
                                for i in range(0, len(registros_lineas), tam_lote):
                                    lote = registros_lineas[i:i + tam_lote]
                                    supabase.table("bitacoras_lineas").insert(lote).execute()
                                    
                                st.success(f"✅ ¡Migración completada con éxito! Se registraron {len(registros_lineas)} líneas de producción y se crearon {oks_creadas} nuevas OPs en el taller.")
                            else:
                                st.warning("⚠️ No se detectaron filas válidas procesables dentro del archivo Excel.")
                except Exception as e:
                    st.error(f"❌ Error crítico al procesar el archivo Excel: {e}")
