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
    # AJUSTE DE MÁRGENES UNIFICADOS Y AMPLIACIÓN DE FUENTE PARA OPERARIOS
    st.markdown("""
        <style>
        /* Unificación de márgenes externos e internos al 100% */
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
        
        /* Alineación exacta de márgenes para las secciones 2, 3 y 4 con la 1 y 5 */
        div[data-testid="stDataEditor"] {
            font-size: 12.5px !important;
            font-family: monospace !important;
            margin-bottom: 2px !important;
            padding: 0px !important;
            width: 100% !important;
        }
        
        /* Forzar simetría y altura idéntica en las 6 filas sin deformaciones */
        div[data-testid="stDataEditor"] div[role="rowgroup"] div[role="row"] {
            min-height: 24px !important;
            height: 24px !important;
            display: flex;
            align-items: center;
        }
        
        div[data-testid="stForm"] { padding: 4px 6px !important; }
        div[data-testid="stVerticalBlock"] > div { padding-bottom: 2px !important; padding-top: 2px !important; }
        
        @media print {
            html, body { height: 100%; overflow: hidden; }
            div[data-testid="stDataEditor"] { font-size: 12px !important; }
        }
        </style>
    """, unsafe_allow_html=True)

    supabase = conectar()
    
    if 'id_bitacora_activa' not in st.session_state:
        st.session_state.id_bitacora_activa = None

    # =========================================================================
    # VISTA DE EDICIÓN / APERTURA SIMÉTRICA
    # =========================================================================
    if st.session_state.id_bitacora_activa:
        id_act = st.session_state.id_bitacora_activa
        
        if st.button("⬅️ Volver al Listado de Bitácoras"):
            st.session_state.id_bitacora_activa = None
            st.rerun()
            
        cab = supabase.table("bitacoras_taller").select("*").eq("id", id_act).execute().data[0]
        
        # SECCIÓN 1: DATOS GENERALES DEL FORMATO
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

        lista_ops = [""] + [op['nombre'] for op in supabase.table("cfg_operarios").select("nombre").order("nombre").execute().data]
        lista_mats = [""] + [mat['detalle'] for mat in supabase.table("cfg_descripciones").select("detalle").order("detalle").execute().data]
        lista_cantos = [""] + [can['tipo'] for can in supabase.table("cfg_cantos").select("tipo").order("tipo").execute().data]

        def filtrar_bloque(df, bloque_nom):
            if df.empty: return pd.DataFrame()
            sub_df = df[df['proceso_bloque'] == bloque_nom].copy()
            for col_f in ['fecha_inicio', 'fecha_termino']:
                if col_f in sub_df.columns:
                    sub_df[col_f] = sub_df[col_f].apply(lambda x: f"{x[5:7]}/{x[8:10]}" if (x and len(str(x)) >= 10 and str(x)[4] == '-') else x)
            return sub_df

        # CORRECCIÓN ESTRUCTURAL DE ANCHO PARA FILAS 4, 5 Y 6 (DATAFRAME HOMOGÉNEO)
        def garantizar_6_filas_limpias(df_bloque, bloque_id):
            columnas_base = ['id', 'cantidad', 'descripcion', 'tipo_canto', 'fecha_inicio', 'hora_inicio', 'hora_termino', 'fecha_termino', 'cant_final_pl_pzs', 'obs_incidencias']
            
            if df_bloque.empty:
                df_bloque = pd.DataFrame(columns=columnas_base)
            
            # Asegurar que todas las columnas existan con tipos consistentes
            for col in columnas_base:
                if col not in df_bloque.columns:
                    df_bloque[col] = None
            
            actuales = len(df_bloque)
            if actuales < 6:
                filas_faltantes = 6 - actuales
                nuevas_filas = []
                for _ in range(filas_faltantes):
                    nuevas_filas.append({
                        "id": "", "bitacora_id": id_act, "proceso_bloque": bloque_id,
                        "cantidad": None, "descripcion": "", "tipo_canto": "",
                        "fecha_inicio": "", "hora_inicio": "", "hora_termino": "",
                        "fecha_termino": "", "cant_final_pl_pzs": "", "obs_incidencias": ""
                    })
                df_bloque = pd.concat([df_bloque, pd.DataFrame(nuevas_filas)], ignore_index=True)
            
            # REQUERIMIENTO: Limpieza absoluta de campos para impresión limpia en campo
            df_bloque['id'] = df_bloque['id'].fillna("")
            df_bloque['descripcion'] = df_bloque['descripcion'].fillna("")
            df_bloque['tipo_canto'] = df_bloque['tipo_canto'].fillna("")
            
            # Si la fila es una fila vacía de contingencia, removemos cualquier residuo numérico
            for idx, row in df_bloque.iterrows():
                if row['id'] == "":
                    df_bloque.at[idx, 'cantidad'] = None
                    df_bloque.at[idx, 'cant_final_pl_pzs'] = ""
                    
            return df_bloque.head(6)

        df_secc = garantizar_6_filas_limpias(filtrar_bloque(df_l, 'SECCIONADORA'), 'SECCIONADORA')
        df_escu = garantizar_6_filas_limpias(filtrar_bloque(df_l, 'ESCUADRADORA'), 'ESCUADRADORA')
        df_cant = garantizar_6_filas_limpias(filtrar_bloque(df_l, 'CANTEO'), 'CANTEO')

        def generar_bloque_interfaz(titulo, bloque_id, df_bloque, col_salida_label):
            st.markdown(f'<div class="section-header">{titulo}</div>', unsafe_allow_html=True)
            
            op_actual1, op_actual2 = "", ""
            df_con_datos = df_bloque[df_bloque['id'] != ""]
            if not df_con_datos.empty:
                op_actual1 = df_con_datos['nombre_firma_operario'].iloc[0] or ""
                op_actual2 = df_con_datos['nombre_firma_operario2'].iloc[0] or ""
                
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
            
            # REORDENADO CON SALIDA POSTERIOR A F.T. Y AMPLIACIÓN DE DESCRIPCIÓN
            if bloque_id == 'CANTEO':
                columnas_visibles = ['id', 'cantidad', 'descripcion', 'tipo_canto', 'fecha_inicio', 'hora_inicio', 'hora_termino', 'fecha_termino', 'cant_final_pl_pzs', 'obs_incidencias']
                config_columnas = {
                    "id": None,
                    "cantidad": st.column_config.NumberColumn("CANT.", format="%.2f", width="small"),
                    "descripcion": st.column_config.SelectboxColumn("DESCRIPCIÓN", options=lista_mats, required=False, width="large"),
                    "tipo_canto": st.column_config.SelectboxColumn("TIPO CANTO", options=lista_cantos, required=False, width="medium"),
                    "fecha_inicio": st.column_config.TextColumn("F.I.", width="small"),
                    "hora_inicio": st.column_config.TextColumn("H.I.", width="small"),
                    "hora_termino": st.column_config.TextColumn("H.T.", width="small"),
                    "fecha_termino": st.column_config.TextColumn("F.T.", width="small"),
                    "cant_final_pl_pzs": st.column_config.TextColumn(col_salida_label, width="medium"),
                    "obs_incidencias": st.column_config.TextColumn("OBS.", width="small")
                }
            else:
                columnas_visibles = ['id', 'cantidad', 'descripcion', 'fecha_inicio', 'hora_inicio', 'hora_termino', 'fecha_termino', 'cant_final_pl_pzs', 'obs_incidencias']
                config_columnas = {
                    "id": None,
                    "cantidad": st.column_config.NumberColumn("CANT.", format="%.2f", width="small"),
                    "descripcion": st.column_config.SelectboxColumn("DESCRIPCIÓN", options=lista_mats, required=False, width="large"),
                    "fecha_inicio": st.column_config.TextColumn("F.I.", width="small"),
                    "hora_inicio": st.column_config.TextColumn("H.I.", width="small"),
                    "hora_termino": st.column_config.TextColumn("H.T.", width="small"),
                    "fecha_termino": st.column_config.TextColumn("F.T.", width="small"),
                    "cant_final_pl_pzs": st.column_config.TextColumn(col_salida_label, width="medium"),
                    "obs_incidencias": st.column_config.TextColumn("OBS.", width="small")
                }

            df_limpio = df_bloque[columnas_visibles].copy()
            res_ed = st.data_editor(
                df_limpio, column_config=config_columnas, hide_index=True, use_container_width=True, key=f"grid_{bloque_id}_{id_act}"
            )
            return res_ed, op_val1, op_val2

        ed_secc, op_secc1, op_secc2 = generar_bloque_interfaz("🪚 SECCIÓN 2: CORTE SECCIONADORA", "SECCIONADORA", df_secc, "N° PL.")
        ed_escu, op_escu1, op_escu2 = generar_bloque_interfaz("📐 SECCIÓN 3: CORTE ESCUADRADORA", "ESCUADRADORA", df_escu, "N° PZAS")
        ed_cant, op_cant1, op_cant2 = generar_bloque_interfaz("⚙️ SECCIÓN 4: CANTEO", "CANTEO", df_cant, "ML CANTO")

        # SECCIÓN 5: LOGÍSTICA
        st.markdown('<div class="section-header">🚚 SECCIÓN 5: ARMADO Y DESPACHO</div>', unsafe_allow_html=True)
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
                st.markdown("<b>📦 ZONA DE DESPACHO (Obra)</b>", unsafe_allow_html=True)
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
            u_log_observaciones = st.text_area("Observaciones de Logística:", value=cab.get('log_observaciones') or "", height=40)

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
                            "fecha_inicio": normalizar_fecha_iso(r['F.I.'] if 'F.I.' in r else r.get('fecha_inicio')),
                            "hora_inicio": str(r['H.I.'] if 'H.I.' in r else r.get('hora_inicio')).strip(),
                            "cant_final_pl_pzs": str(r['cant_final_pl_pzs']).strip() if 'cant_final_pl_pzs' in r else None,
                            "hora_termino": str(r['H.T.'] if 'H.T.' in r else r.get('hora_termino')).strip(),
                            "fecha_termino": normalizar_fecha_iso(r['F.T.'] if 'F.T.' in r else r.get('fecha_termino')),
                            "obs_incidencias": str(r['OBS.'] if 'OBS.' in r else r.get('obs_incidencias')).strip(),
                            "nombre_firma_operario": op1, "nombre_firma_operario2": op2
                        }
                        if pd.notna(r['id']) and r['id'] != "":
                            supabase.table("bitacoras_lineas").update(payload).eq("id", int(r['id'])).execute()
                        else:
                            supabase.table("bitacoras_lineas").insert(payload).execute()

                procesar_lote_guardado(ed_secc, "SECCIONADORA", op_secc1, op_secc2)
                procesar_lote_guardado(ed_escu, "ESCUADRADORA", op_escu1, op_escu2)
                procesar_lote_guardado(ed_cant, "CANTEO", op_cant1, op_cant2)
                st.success("🎉 Cambios de alineación y datos de campo guardados."); st.rerun()
            except Exception as e:
                st.error(f"Falla de sincronización: {e}")
        
        # MOTOR REPORTLAB OPTIMIZADO - INCREMENTO DE LETRA Y REDUCCIÓN DE MÁRGENES ESTÉRILES
        try:
            buffer_pdf = io.BytesIO()
            # Bajamos los márgenes a 8 para ganar espacio útil y poder subir la letra a 9pt
            doc_pdf = SimpleDocTemplate(buffer_pdf, pagesize=A4, rightMargin=8, leftMargin=8, topMargin=8, bottomMargin=8)
            story = []
            styles = getSampleStyleSheet()
            
            style_normal = ParagraphStyle('Norm', fontName='Helvetica', fontSize=9, leading=11)
            style_bold = ParagraphStyle('Bld', fontName='Helvetica-Bold', fontSize=9, leading=11)
            style_title = ParagraphStyle('Tit', fontName='Helvetica-Bold', fontSize=14, leading=16, alignment=1)
            
            story.append(Paragraph("<b>BITÁCORA UNIFICADA DE PRODUCCIÓN</b>", style_title))
            story.append(Spacer(1, 2))
            
            data_s1 = [
                [Paragraph("<b>FECHA:</b>", style_normal), Paragraph(u_fecha.strftime("%d/%m/%Y"), style_normal), Paragraph("<b>Nº ORDEN:</b>", style_normal), Paragraph(u_n_orden, style_normal)],
                [Paragraph("<b>MUEBLE:</b>", style_normal), Paragraph(u_tipo_mueble, style_normal), Paragraph("<b>MOTIVO:</b>", style_normal), Paragraph(u_motivo, style_normal)],
                [Paragraph("<b>CLIENTE:</b>", style_normal), Paragraph(u_cliente, style_normal), Paragraph("<b>PROYECTO:</b>", style_normal), Paragraph(u_proyecto, style_normal)]
            ]
            t_s1 = Table(data_s1, colWidths=[75, 210, 75, 219])
            t_s1.setStyle(TableStyle([('BACKGROUND', (0,0), (0,2), colors.lightgrey), ('BACKGROUND', (2,0), (2,2), colors.lightgrey), ('GRID', (0,0), (-1,-1), 0.5, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2)]))
            story.append(t_s1)
            story.append(Spacer(1, 2))
            
            def inyectar_tabla_pdf(titulo, cabeceras, df_ed, op1, op2, ancho_cols):
                op_text = f"{op1} / {op2}".strip(" / ")
                story.append(Paragraph(f"<b>{titulo}</b> | <font size=7.5>Responsables: {op_text}</font>", style_bold))
                rows_pdf = [[Paragraph(f"<b>{h}</b>", style_bold) for h in cabeceras]]
                
                for _, r in df_ed.iterrows():
                    fila = []
                    es_vacia = (r['id'] == "")
                    for col_id in df_ed.columns:
                        if col_id != 'id':
                            val_t = "" if es_vacia else str(r[col_id])
                            if val_t == "None" or val_t == "0.0": val_t = ""
                            fila.append(Paragraph(val_t, style_normal))
                    rows_pdf.append(fila)
                        
                t_block = Table(rows_pdf, colWidths=ancho_cols)
                t_block.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.lightgrey), ('GRID', (0,0), (-1,-1), 0.5, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2)]))
                story.append(t_block)
                story.append(Spacer(1, 2))

            # ANCHOS RECALCULADOS AL 100% (DESCRIPCIÓN MAXIMIZADA, OBS REDUCIDA)
            inyectar_tabla_pdf("🪚 SECCIÓN 2: CORTE SECCIONADORA", ["CANT.", "DESCRIPCIÓN", "F.I.", "H.I.", "H.T.", "F.T.", "N° PL.", "OBS."], ed_secc, op_secc1, op_secc2, [35, 239, 36, 36, 36, 36, 46, 75])
            inyectar_tabla_pdf("📐 SECCIÓN 3: CORTE ESCUADRADORA", ["CANT.", "DESCRIPCIÓN", "F.I.", "H.I.", "H.T.", "F.T.", "N° PZAS", "OBS."], ed_escu, op_escu1, op_escu2, [35, 239, 36, 36, 36, 36, 46, 75])
            inyectar_tabla_pdf("⚙️ SECCIÓN 4: CANTEO", ["CANT.", "DESCRIPCIÓN", "TIPO CANTO", "F.I.", "H.I.", "H.T.", "F.T.", "ML CANTO", "OBS."], ed_cant, op_cant1, op_cant2, [30, 184, 65, 36, 36, 36, 36, 51, 105])

            story.append(Paragraph("<b>🚚 SECCIÓN 5: ARMADO Y DESPACHO</b>", style_bold))
            f_arm_p = u_log_armado_fecha.strftime("%d/%m/%Y") if u_log_armado_fecha else ""
            f_des_p = u_log_despacho_fecha.strftime("%d/%m/%Y") if u_log_despacho_fecha else ""
            f_sal_p = u_log_salida_fecha.strftime("%d/%m/%Y") if u_log_salida_fecha else ""

            data_log_tab = [
                [Paragraph("<b>ZONA DE ARMADO (Taller)</b>", style_bold), Paragraph("<b>ZONA DE DESPACHO (Obra)</b>", style_bold)],
                [Paragraph(f"F. RECEPCIÓN: {f_arm_p} | PALLETS: {u_log_armado_cant} | VºBº: {u_log_armado_vob}", style_normal),
                 Paragraph(f"F. RECEPCIÓN: {f_des_p} | PALLETS: {u_log_despacho_cant} | VºBº: {u_log_despacho_vob}", style_normal)],
                [Paragraph(f"<b>DESPACHO A OBRA:</b> F. SALIDA: {f_sal_p} | CHOFER: {u_log_salida_conductor} | VºBº: {u_log_salida_vob}", style_normal),
                 Paragraph(f"<b>OBSERVACIONES:</b> {u_log_observaciones}", style_normal)]
            ]
            t_log = Table(data_log_tab, colWidths=[289, 290])
            t_log.setStyle(TableStyle([('BACKGROUND', (0,0), (1,0), colors.lightgrey), ('GRID', (0,0), (-1,-1), 0.5, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2)]))
            story.append(t_log)
            
            doc_pdf.build(story)
            c_pdf.download_button("🖨️ EXPORTAR EN UN SOLO FOLIO (PDF)", data=buffer_pdf.getvalue(), file_name=f"Format_B_{u_n_orden}.pdf", mime="application/pdf", use_container_width=True)
        except Exception as e_pdf:
            c_pdf.error(f"Aviso de compactación: {e_pdf}")

    # =========================================================================
    # ENTORNO INICIAL (PESTAÑAS HISTORIAL, ALTA Y CONFIGURACIÓN MAESTROS)
    # =========================================================================
    else:
        tab_listado, tab_alta_nueva, tab_config = st.tabs(["🗂️ Listado de Bitácoras", "➕ Nueva Bitácora", "⚙️ Configuración de Catálogos"])
        
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
                    
                id_abrir = st.number_input("ID de Bitácora a editar:", min_value=1, step=1)
                if st.button("🔓 Abrir Formato Simétrico en Pantalla", type="primary"):
                    st.session_state.id_bitacora_activa = int(id_abrir)
                    st.rerun()
            else:
                st.info("No hay bitácoras bajo este criterio.")

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
                    st.success("Bitácora creada con éxito."); st.rerun()

        with tab_config:
            st.caption("Administración corporativa de catálogos activos para los componentes predictivos de planta.")
            sel_maestro = st.selectbox("Seleccione el Catálogo a gestionar:", ["Responsables (Operarios)", "Materiales (Descripciones)", "Tipos de Canto"])
            
            if sel_maestro == "Responsables (Operarios)":
                st.markdown("#### 👨‍🔧 Registro de Operarios de Planta")
                with st.form("form_op"):
                    nuevo_op = st.text_input("Nombre completo del Operario:")
                    if st.form_submit_button("➕ Añadir a Planta"):
                        if nuevo_op.strip():
                            supabase.table("cfg_operarios").insert({"nombre": nuevo_op.strip().upper()}).execute()
                            st.success("Operario registrado."); st.rerun()
                try:
                    df_ops = pd.DataFrame(supabase.table("cfg_operarios").select("*").order("nombre").execute().data)
                    st.data_editor(df_ops, column_config={"id": None}, hide_index=True, use_container_width=True)
                except: st.info("Catálogo vacío.")
                
            elif sel_maestro == "Materiales (Descripciones)":
                st.markdown("#### 🪵 Catálogo Maestro de Melamina y Tableros")
                with st.form("form_mat"):
                    nuevo_mat = st.text_input("Detalle/Nombre comercial del Tablero:")
                    if st.form_submit_button("➕ Añadir Material"):
                        if nuevo_mat.strip():
                            supabase.table("cfg_descripciones").insert({"detalle": nuevo_mat.strip().upper()}).execute()
                            st.success("Material añadido."); st.rerun()
                try:
                    df_mats = pd.DataFrame(supabase.table("cfg_descripciones").select("*").order("detalle").execute().data)
                    st.data_editor(df_mats, column_config={"id": None}, hide_index=True, use_container_width=True)
                except: st.info("Catálogo vacío.")
                
            elif sel_maestro == "Tipos de Canto":
                st.markdown("#### ⚙️ Espesores y Variaciones de Canto")
                with st.form("form_can"):
                    nuevo_can = st.text_input("Variación de Canto (ej. DELGADO 0.4MM):")
                    if st.form_submit_button("➕ Añadir Canto"):
                        if nuevo_can.strip():
                            supabase.table("cfg_cantos").insert({"tipo": nuevo_can.strip().upper()}).execute()
                            st.success("Variación añadida."); st.rerun()
                try:
                    df_cans = pd.DataFrame(supabase.table("cfg_cantos").select("*").order("tipo").execute().data)
                    st.data_editor(df_cans, column_config={"id": None}, hide_index=True, use_container_width=True)
                except: st.info("Catálogo vacío.")
