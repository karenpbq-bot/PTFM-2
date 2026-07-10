import streamlit as st
import pandas as pd
from datetime import datetime, date
import io
from base_datos import conectar

# Intentar importar ReportLab para la compilación del PDF nativo de una página
try:
    from reportlab.lib.pagesizes import letter, A4
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

    # =========================================================================
    # VISTA DE EDICIÓN / APERTURA SIMÉTRICA (4 SECCIONES ORIGINALES + 5TA SECCIÓN)
    # =========================================================================
    if st.session_state.id_bitacora_activa:
        id_act = st.session_state.id_bitacora_activa
        
        if st.button("⬅️ Volver al Listado de Bitácoras"):
            st.session_state.id_bitacora_activa = None
            st.rerun()
            
        # Cargar metadatos de la cabecera
        cab = supabase.table("bitacoras_taller").select("*").eq("id", id_act).execute().data[0]
        
        # SECCIÓN 1: DATOS GENERALES
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

        # Carga y normalización de líneas operativas desde Supabase
        res_l = supabase.table("bitacoras_lineas").select("*").eq("bitacora_id", id_act).order("id").execute()
        df_l = pd.DataFrame(res_l.data) if res_l.data else pd.DataFrame()
        
        # Auxiliar para separar los bloques de máquinas
        def filtrar_bloque(df, bloque_nom):
            if df.empty:
                return pd.DataFrame()
            sub_df = df[df['proceso_bloque'] == bloque_nom].copy()
            # Si las fechas vienen en formato ISO AAAA-MM-DD, convertirlas a formato corto DD/MM para el taller
            for col_f in ['fecha_inicio', 'fecha_termino']:
                if col_f in sub_df.columns:
                    sub_df[col_f] = sub_df[col_f].apply(lambda x: f"{x[5:7]}/{x[8:10]}" if (x and len(str(x)) >= 10 and str(x)[4] == '-') else x)
            return sub_df

        df_secc = filtrar_bloque(df_l, 'SECCIONADORA')
        df_escu = filtrar_bloque(df_l, 'ESCUADRADORA')
        df_cant = filtrar_bloque(df_l, 'CANTEO')
        df_sec5 = filtrar_bloque(df_l, 'SECCION5')

        # Procesador para inyectar filas y capturar el operario en la cabecera del bloque
        def generar_bloque_interfaz(titulo, bloque_id, df_bloque, col_cant_nom):
            st.markdown(f'<div class="section-header">{titulo}</div>', unsafe_allow_html=True)
            
            # Recuperar operario asignado previamente del primer registro si existe
            op_actual = ""
            if not df_bloque.empty and 'nombre_firma_operario' in df_bloque.columns:
                op_actual = df_bloque['nombre_firma_operario'].iloc[0] or ""
                
            cx1, cx2 = st.columns([2, 3])
            btn_ins = cx1.button(f"➕ Insertar Registro a {titulo.split(': ')[1]}", key=f"btn_ins_{bloque_id}")
            op_val = cx2.text_input("👨‍🔧 OPERARIO / FIRMA RESPONSABLE:", value=op_actual, key=f"op_val_{bloque_id}", placeholder="Nombre del operario asignado...")
            
            if btn_ins:
                supabase.table("bitacoras_lineas").insert({
                    "bitacora_id": id_act, "proceso_bloque": bloque_id, "cantidad": 0.0, "nombre_firma_operario": op_val
                }).execute()
                st.rerun()
            
            # 1. Definir columnas visibles base
            columnas_visibles = ['id', 'cantidad', 'descripcion', 'fecha_inicio', 'hora_inicio', 'cant_final_pl_pzs', 'hora_termino', 'fecha_termino', 'obs_incidencias']
            
            # 2. Configuración base adaptable de columnas
            config_columnas = {
                "id": None,
                "cantidad": st.column_config.NumberColumn("CANT.", format="%.2f"),
                "descripcion": st.column_config.TextColumn("DESCRIPCION"),
                "fecha_inicio": st.column_config.TextColumn("F. INICIO (DD/MM)"),
                "hora_inicio": st.column_config.TextColumn("H. INICIO"),
                "cant_final_pl_pzs": st.column_config.TextColumn(col_cant_nom),
                "hora_termino": st.column_config.TextColumn("H. TERMINO"),
                "fecha_termino": st.column_config.TextColumn("F. TERMINO (DD/MM)"),
                "obs_incidencias": st.column_config.TextColumn("OBS/INCIDENCIAS")
            }
            
            # 3. Ajuste estricto y simétrico exclusivo para el bloque de Canteo
            if bloque_id == 'CANTEO':
                columnas_visibles = ['id', 'cantidad', 'descripcion', 'tipo_canto', 'fecha_inicio', 'hora_inicio', 'cant_final_pl_pzs', 'fecha_termino', 'obs_incidencias']
                config_columnas = {
                    "id": None,
                    "cantidad": st.column_config.NumberColumn("CANT.", format="%.2f"),
                    "descripcion": st.column_config.TextColumn("DESCRIPCION"),
                    "tipo_canto": st.column_config.TextColumn("TIPO DE CANTO"),
                    "fecha_inicio": st.column_config.TextColumn("F. INICIO (DD/MM)"),
                    "hora_inicio": st.column_config.TextColumn("H. INICIAL"),
                    "cant_final_pl_pzs": st.column_config.TextColumn("CANTO USADO"),
                    "fecha_termino": st.column_config.TextColumn("F. FINAL (DD/MM)"),
                    "obs_incidencias": st.column_config.TextColumn("OBS/INCIDENCIAS")
                }

            # 4. Asegurar la creación simétrica del DataFrame y forzar casilleros vacíos a texto limpio
            if not df_bloque.empty:
                for col_obligatoria in columnas_visibles:
                    if col_obligatoria not in df_bloque.columns:
                        df_bloque[col_obligatoria] = ""
                df_limpio = df_bloque[columnas_visibles].copy()
            else:
                df_limpio = pd.DataFrame(columns=columnas_visibles)

            # BLINDAJE CRÍTICO DE TIPOS AUTOMÁTICO
            for col_c in df_limpio.columns:
                if col_c == "cantidad":
                    df_limpio[col_c] = pd.to_numeric(df_limpio[col_c]).fillna(0.0)
                elif col_c != "id":
                    # Forzar de manera segura a que cualquier otro campo operativo sea tratado como texto limpio (String)
                    df_limpio[col_c] = df_limpio[col_c].fillna("").astype(str).str.strip()

            # Renderizado seguro libre de excepciones de validación
            res_ed = st.data_editor(
                df_limpio,
                column_config=config_columnas,
                hide_index=True,
                use_container_width=True,
                key=f"editor_grid_{bloque_id}_{id_act}"
            )
            return res_ed, op_val

        # Despliegue secuencial de las tablas de manufactura (Secciones 2, 3 y 4)
        ed_secc, op_secc = generar_bloque_interfaz("🪚 SECCIÓN 2: CORTE SECCIONADORA", "SECCIONADORA", df_secc, "CANT. FINAL PL.")
        ed_escu, op_escu = generar_bloque_interfaz("📐 SECCIÓN 3: CORTE ESCUADRADORA", "ESCUADRADORA", df_escu, "CANT. PIEZAS")
        ed_cant, op_cant = generar_bloque_interfaz("⚙️ SECCIÓN 4: CANTEO", "CANTEO", df_cant, "CANTO USADO")

        # SECCIÓN 5: LOGÍSTICA (Réplica exacta de la distribución de la imagen física)
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
                st.markdown("<font color='#4B5563'><b>?. ZONA DE DESPACHO (Obra)</b></font>", unsafe_allow_html=True)
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
            u_log_observaciones = st.text_area("Registre novedades del flete, embalaje o despacho general:", value=cab.get('log_observaciones') or "", height=80, label_visibility="collapsed")

        # Guardado unificado y procesamiento inteligente de fechas cortas (DD/MM -> AAAA-MM-DD)
        st.divider()
        c_save, c_pdf = st.columns(2)
        
        if c_save.button("💾 GUARDAR AVANCES Y CAMBIOS", type="primary", use_container_width=True):
            try:
                # Actualizar datos generales e incluir los campos fijos de la Sección 5 (Logística)
                supabase.table("bitacoras_taller").update({
                    "fecha": u_fecha.isoformat(), 
                    "n_orden": u_n_orden, 
                    "tipo_mueble": u_tipo_mueble,
                    "motivo": u_motivo, 
                    "cliente": u_cliente, 
                    "proyecto": u_proyecto,
                    "solicitado_por": u_sol_por, 
                    "sup_production": u_sup_prod, 
                    "estado": u_estado,
                    "log_armado_fecha": u_log_armado_fecha.isoformat() if u_log_armado_fecha else None,
                    "log_armado_cant": u_log_armado_cant,
                    "log_armado_vob": u_log_armado_vob,
                    "log_despacho_fecha": u_log_despacho_fecha.isoformat() if u_log_despacho_fecha else None,
                    "log_despacho_cant": u_log_despacho_cant,
                    "log_despacho_vob": u_log_despacho_vob,
                    "log_salida_fecha": u_log_salida_fecha.isoformat() if u_log_salida_fecha else None,
                    "log_salida_conductor": u_log_salida_conductor,
                    "log_salida_vob": u_log_salida_vob,
                    "log_observaciones": u_log_observaciones
                }).eq("id", id_act).execute()
                
                # Función para empaquetar y formatear las fechas del taller a ISO
                def procesar_lote_guardado(df_editor, bloque_id, op_nombre):
                    for _, r in df_editor.iterrows():
                        def normalizar_fecha_iso(valor_celda):
                            if not valor_celda or pd.isna(valor_celda): return None
                            texto = str(valor_celda).strip()
                            if len(texto) == 5 and "/" in texto: # Formato DD/MM
                                return f"2026-{texto[3:5]}-{texto[0:2]}"
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
                            "nombre_firma_operario": op_nombre
                        }
                        supabase.table("bitacoras_lineas").update(payload).eq("id", int(r['id'])).execute()

                procesar_lote_guardado(ed_secc, "SECCIONADORA", op_secc)
                procesar_lote_guardado(ed_escu, "ESCUADRADORA", op_escu)
                procesar_lote_guardado(ed_cant, "CANTEO", op_cant)
                
                st.success("🎉 Trazabilidad y sección logística guardadas con éxito."); st.rerun()
            except Exception as e:
                st.error(f"Falla de sincronización: {e}")
        
        # MOTOR DE COMPILACIÓN NATIVA PDF EN UNA SOLA PÁGINA A4
        try:
            buffer_pdf = io.BytesIO()
            doc_pdf = SimpleDocTemplate(buffer_pdf, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=15, bottomMargin=15)
            story = []
            
            styles = getSampleStyleSheet()
            # MODIFICADO: Campos de texto un 60% más grandes (de 7pt a 11pt)
            style_normal = ParagraphStyle('Norm', fontName='Helvetica', fontSize=11, leading=14)
            style_bold = ParagraphStyle('Bld', fontName='Helvetica-Bold', fontSize=11, leading=14)
            style_title = ParagraphStyle('Tit', fontName='Helvetica-Bold', fontSize=11, leading=14, alignment=1)
            
            # MODIFICADO: Título principal un 45% más grande (de 14pt a 20pt)
            style_main_title = ParagraphStyle('MainTit', fontName='Helvetica-Bold', fontSize=20, leading=24, alignment=1)
            
            # NUEVO ESTILO: Títulos de sección un 95% más grandes (de 7pt a 14pt) para aislar del texto común
            style_section_title = ParagraphStyle('SecTit', fontName='Helvetica-Bold', fontSize=14, leading=18)
            
            # NUEVO: Inyectar título superior en el documento PDF
            story.append(Paragraph("BITÁCORA DE PRODUCCIÓN", style_main_title))
            story.append(Spacer(1, 10)) # Espacio de separación antes de la cabecera de datos generales
            
            # Cabecera de Datos Generales en PDF
            fecha_str = u_fecha.strftime("%d/%m/%Y")
            data_s1 = [
                [Paragraph("<b>FECHA:</b>", style_normal), Paragraph(fecha_str, style_normal), Paragraph("<b>Nº ORDEN:</b>", style_normal), Paragraph(u_n_orden, style_normal)],
                [Paragraph("<b>TIPO DE MUEBLE:</b>", style_normal), Paragraph(u_tipo_mueble, style_normal), Paragraph("<b>MOTIVO:</b>", style_normal), Paragraph(u_motivo, style_normal)],
                [Paragraph("<b>CLIENTE:</b>", style_normal), Paragraph(u_cliente, style_normal), Paragraph("<b>PROYECTO:</b>", style_normal), Paragraph(u_proyecto, style_normal)],
                [Paragraph("<b>SOLICITADO POR:</b>", style_normal), Paragraph(u_sol_por, style_normal), Paragraph("<b>SUP. DE PRODUCCIÓN:</b>", style_normal), Paragraph(u_sup_prod, style_normal)]
            ]
            t_s1 = Table(data_s1, colWidths=[100, 180, 100, 175])
            t_s1.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (0,3), colors.lightgrey), ('BACKGROUND', (2,0), (2,3), colors.lightgrey),
                ('GRID', (0,0), (-1,-1), 0.5, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ]))
            story.append(t_s1)
            story.append(Spacer(1, 8))
            
            # Función constructora de matrices compactas para el PDF único
            def inyectar_tabla_pdf(titulo, cabeceras, df_ed, op_nom, es_canteo=False):
                story.append(Paragraph(f"<b>{titulo}</b>  |  <font size=7>Responsable: {op_nom}</font>", style_bold))
                story.append(Spacer(1, 2))
                
                rows_pdf = [[Paragraph(f"<b>{h}</b>", style_bold) for h in cabeceras]]
                
                if not df_ed.empty:
                    for _, r in df_ed.iterrows():
                        fila = []
                        for col_id in df_ed.columns:
                            if col_id != 'id':
                                val_t = str(r[col_id]) if (r[col_id] is not None and not pd.isna(r[col_id])) else ""
                                fila.append(Paragraph(val_t, style_normal))
                        rows_pdf.append(fila)
                else:
                    # Rellenar con 2 líneas vacías si está vacío el avance para impresión manual limpia
                    for _ in range(2):
                        rows_pdf.append([Paragraph("", style_normal) for _ in cabeceras])
                        
                # NUEVO: Ajuste estricto a 555 puntos totales para alineación perfecta con Sec. 1 y 5
                if not es_canteo:
                    # Total: 35 + 140 + 50 + 50 + 65 + 50 + 50 + 115 = 555
                    ancho_cols = [35, 140, 50, 50, 65, 50, 50, 115]
                else:
                    # Total: 35 + 120 + 60 + 45 + 45 + 55 + 45 + 150 = 555
                    ancho_cols = [35, 120, 60, 45, 45, 55, 45, 150]
                
                ancho_cols = ancho_cols[:len(cabeceras)]
                
                t_block = Table(rows_pdf, colWidths=ancho_cols)
                t_block.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    # MODIFICADO: Incremento de altura interna (padding) para evitar el efecto apiñado
                    ('TOPPADDING', (0,0), (-1,-1), 5),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                ]))
                story.append(t_block)
                story.append(Spacer(1, 6))

            inyectar_tabla_pdf("CORTE SECCIONADORA", ["CANT.", "DESCRIPCIÓN", "F. INICIO", "H. INICIO", "CANT. FINAL PL.", "H. TERMINO", "F. TERMINO", "OBS/INCIDENCIAS"], ed_secc, op_secc)
            inyectar_tabla_pdf("CORTE ESCUADRADORA", ["CANT.", "DESCRIPCIÓN", "F. INICIO", "H. INICIO", "CANT. PIEZAS", "H. TERMINO", "F. TERMINO", "OBS/INCIDENCIAS"], ed_escu, op_escu)
            inyectar_tabla_pdf("CANTEO", ["CANT.", "DESCRIPCIÓN", "TIPO DE CANTO", "F. INICIO", "H. INICIAL", "CANTO USADO", "F. FINAL", "OBS/INCIDENCIAS"], ed_cant, op_cant, es_canteo=True)

            # --- NUEVA SECCIÓN 5 FIJA EN EL PDF (Réplica exacta de la distribución física) ---
            story.append(Paragraph("<b> ARMADO, ENRUTAMIENTO Y DESPACHO</b>", style_bold))
            story.append(Spacer(1, 3))
            
            f_arm_p = u_log_armado_fecha.strftime("%d/%m/%Y") if u_log_armado_fecha else ""
            f_des_p = u_log_despacho_fecha.strftime("%d/%m/%Y") if u_log_despacho_fecha else ""
            f_sal_p = u_log_salida_fecha.strftime("%d/%m/%Y") if u_log_salida_fecha else ""

            data_log_tab = [
                [Paragraph("<b>ZONA DE ARMADO (Piezas en Planta)</b>", style_bold), Paragraph("<b>ZONA DE DESPACHO (Directo a Obra)</b>", style_bold)],
                [Paragraph(f"FECHA RECEPCIÓN: {f_arm_p}", style_normal), Paragraph(f"FECHA RECEPCIÓN: {f_des_p}", style_normal)],
                [Paragraph(f"Nº PALLETS / PIEZAS: {u_log_armado_cant}", style_normal), Paragraph(f"Nº PALLETS / PIEZAS: {u_log_despacho_cant}", style_normal)],
                [Paragraph(f"VºBº SUP. PRODUCCIÓN: {u_log_armado_vob}", style_normal), Paragraph(f"VºBº ALMACÉN / DESPACHO: {u_log_despacho_vob}", style_normal)]
            ]
            t_log = Table(data_log_tab, colWidths=[277, 278])
            t_log.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (1,0), colors.lightgrey),
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2), ('TOPPADDING', (0,0), (-1,-1), 2),
            ]))
            story.append(t_log)
            story.append(Spacer(1, 4))

            data_salida = [
                [Paragraph(f"<b>FECHA SALIDA A OBRA:</b> {f_sal_p}", style_normal), 
                 Paragraph(f"<b>CONDUCTOR:</b> {u_log_salida_conductor}", style_normal), 
                 Paragraph(f"<b>VºBº ALMACÉN:</b> {u_log_salida_vob}", style_normal)]
            ]
            t_sal = Table(data_salida, colWidths=[150, 250, 155])
            t_sal.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 3), ('TOPPADDING', (0,0), (-1,-1), 3),
            ]))
            story.append(t_sal)
            story.append(Spacer(1, 4))

            data_obs = [
                [Paragraph("<b>OBSERVACIONES / INCIDENCIAS DE LOGÍSTICA:</b>", style_bold)],
                [Paragraph(u_log_observaciones if u_log_observaciones.strip() else "", style_normal)]
            ]
            t_obs = Table(data_obs, colWidths=[555])
            t_obs.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (0,0), colors.lightgrey),
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                # MODIFICADO: Incremento a 40 para hacer la caja 4 veces más alta en la impresión
                ('BOTTOMPADDING', (0,1), (0,1), 40), 
                ('LEFTPADDING', (0,1), (0,1), 6),
                ('VALIGN', (0,1), (0,1), 'TOP'),
            ]))
            story.append(t_obs)
            
            doc_pdf.build(story)

            c_pdf.download_button("🖨️ EXPORTAR BITÁCORA EN PDF", data=buffer_pdf.getvalue(), file_name=f"Bitacora_{u_n_orden}.pdf", mime="application/pdf", use_container_width=True)
        except Exception as e_pdf:
            c_pdf.error(f"Alerta en motor PDF: {e_pdf}")

    # =========================================================================
    # ENTORNO INICIAL: HISTORIAL Y LISTADOS
    # =========================================================================
    else:
        tab_listado, tab_alta_nueva = st.tabs(["🗂️ Listado de Bitácoras", "➕ Nueva Bitácora"])
        
        with tab_listado:
            filtro = st.text_input("🔍 Filtro rápido de búsqueda:", placeholder="Escriba el número de OP, cliente o mueble...")
            
            try:
                res_t = supabase.table("bitacoras_taller").select("*").execute()
                df_t = pd.DataFrame(res_t.data) if res_t.data else pd.DataFrame()
            except:
                df_t = pd.DataFrame()
                
            if filtro and not df_t.empty:
                df_t = df_t[df_t['n_orden'].astype(str).str.contains(filtro, case=False) | df_t['cliente'].astype(str).str.contains(filtro, case=False)]
                
            if not df_t.empty:
                df_t = df_t.sort_values(by="fecha", ascending=False)
                
                # Modificador instantáneo de flujos de control
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
            else:
                st.info("No hay bitácoras bajo este criterio.")

        with tab_alta_nueva:
            with st.form("form_alta_inicial"):
                st.caption("Complete los datos de la Sección 1. Los bloques de máquinas se habilitarán vacíos automáticamente.")
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
                        for _ in range(2): # Generar dos líneas guía por cada máquina
                            lineas_iniciales.append({"bitacora_id": b_id, "proceso_bloque": "SECCIONADORA", "cantidad": 0.0})
                            lineas_iniciales.append({"bitacora_id": b_id, "proceso_bloque": "ESCUADRADORA", "cantidad": 0.0})
                            lineas_iniciales.append({"bitacora_id": b_id, "proceso_bloque": "CANTEO", "cantidad": 0.0})
                            lineas_iniciales.append({"bitacora_id": b_id, "proceso_bloque": "SECCION5", "cantidad": 0.0})
                        supabase.table("bitacoras_lineas").insert(lineas_iniciales).execute()
                        st.session_state.id_bitacora_activa = b_id
                        st.rerun()
