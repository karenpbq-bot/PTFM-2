import streamlit as st
import pandas as pd
from datetime import timedelta, datetime, date
from base_datos import *
import seguimiento, ejecucion, login, usuarios  # <--- Asegúrate que diga 'usuarios' al final
import plotly.express as px

st.set_page_config(layout="wide", page_title="Carpintería Pro V2")
inicializar_bd()

# --- LÓGICA DE SESIÓN Y LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

# INICIALIZACIÓN CRÍTICA: Evita que la App colapse al arrancar
if 'id_p_sel' not in st.session_state:
    st.session_state.id_p_sel = None 

if not st.session_state.autenticado:
    login.login_screen()
    st.stop()

# Si llega aquí, el usuario está logueado
rol_usuario = st.session_state.rol
id_usuario = st.session_state.id_usuario

ETAPAS = ["Diseño", "Fabricación", "Traslado", "Instalación", "Entrega"]

# Lógica de barra lateral
with st.sidebar:
    st.title("🪚 PRACTIFORMAS")
    st.write(f"Usuario: **{st.session_state.nombre_real}**")
    st.caption(f"Rol: {rol_usuario}")
    
    if st.button("🔄 Ver Todos los Proyectos"):
        st.session_state.id_p_sel = None
        st.rerun()
    
    # Definir opciones base para todos
    opciones = ["Seguimiento", "Gantt", "Usuarios"] 
    
    # Los Gerentes y Administradores ven además la gestión de proyectos
    if rol_usuario in ["Administrador", "Gerente"]:
        opciones.insert(0, "Proyectos")
        opciones.insert(1, "Crear Nuevo")
    
    menu = st.sidebar.radio("Módulos", opciones)
    
    st.write("---")
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

# --- MÓDULO PROYECTOS ---
if menu == "Proyectos":
    # 1. ESCENARIO: CARTERA DE PROYECTOS (LISTADO)
    if 'id_p_sel' not in st.session_state or st.session_state.id_p_sel is None:
        st.header("📂 Cartera de Proyectos")
        
        bus_cartera = st.text_input("🔍 Buscar proyecto o cliente...", key="bus_main_cartera")
        df_cartera = obtener_proyectos(bus_cartera)
        
        if df_cartera.empty:
            st.info("No se encontraron proyectos activos.")
        
        for _, p in df_cartera.iterrows():
            # Obtener métricas desde base_datos.py
            total_unidades, total_ml = obtener_resumen_inventario(p['id'])
            
            try:
                f_ini_dt = datetime.strptime(p['f_ini'], '%Y-%m-%d').strftime('%d/%m/%Y')
                f_fin_dt = datetime.strptime(p['f_fin'], '%Y-%m-%d').strftime('%d/%m/%Y')
            except:
                f_ini_dt, f_fin_dt = "N/A", "N/A"

            with st.container(border=True):
                # Diseño optimizado para móviles y escritorio
                col_info, col_vacia, col_btn = st.columns([5, 0.5, 1.5])
                
                with col_info:
                    st.subheader(f"🚀 {p['proyecto_text']}")
                    st.write(f"👤 **Cliente:** {p['cliente']}")
                    st.caption(f"🏷️ **Partida:** {p['partida']} | 📅 {f_ini_dt} al {f_fin_dt}")
                
                with col_btn:
                    st.write("<br>", unsafe_allow_html=True)
                    if st.button("⚙️ GESTIONAR", key=f"btn_gest_{p['id']}", use_container_width=True):
                        st.session_state.id_p_sel = p['id']
                        st.rerun()

                # Métricas en tres columnas debajo de la info principal
                m1, m2, m3 = st.columns(3)
                m1.metric("Unidades", int(total_unidades))
                m2.metric("Total ML", f"{total_ml:.2f}")
                m3.metric("Avance", f"{int(p['avance'])}%")
                st.progress(p['avance']/100)
    
    # 2. ESCENARIO: PANEL DE GESTIÓN (DETALLE)
    else:
        id_p = st.session_state.id_p_sel
        
        # Validación de seguridad para evitar IndexError
        df_aux = pd.read_sql_query("SELECT * FROM proyectos WHERE id=?", conectar(), params=(id_p,))
        
        if df_aux.empty:
            st.error("⚠️ El proyecto seleccionado ya no existe.")
            st.session_state.id_p_sel = None
            if st.button("🔄 Volver a la Cartera"): st.rerun()
            st.stop()
        
        p_data = df_aux.iloc[0]
        
        # Cabecera con botón de retroceso en el Sidebar para mayor comodidad
        if st.sidebar.button("⬅️ VOLVER A LA CARTERA"):
            st.session_state.id_p_sel = None
            st.rerun()

        st.title(f"🚀 {p_data['proyecto_text']} — {p_data['cliente']}")
        
        t1, t2, t3 = st.tabs(["📋 Productos e Inventario", "📅 Cronograma Contractual", "🚨 Zona de Peligro"])
        
        # --- TAB 1: PRODUCTOS E INVENTARIO ---
        with t1:
            st.subheader("📦 Gestión de Inventario")
            col_izq, col_der = st.columns(2)
            
            with col_izq:
                with st.expander("➕ Creación Manual"):
                    with st.form("nuevo_manual", clear_on_submit=True):
                        u_m = st.text_input("Ubicación")
                        t_m = st.text_input("Tipo")
                        c_m1, c_m2 = st.columns(2)
                        c_cant = c_m1.number_input("Cantidad", min_value=1, step=1)
                        c_ml = c_m2.number_input("Metros Lineales (ML)", min_value=0.0, format="%.2f")
                        if st.form_submit_button("Añadir Producto"):
                            if u_m and t_m:
                                with conectar() as conn:
                                    conn.execute("INSERT INTO productos (proyecto_id, ubicacion, tipo, ctd, ml) VALUES (?,?,?,?,?)",
                                                 (id_p, u_m, t_m, c_cant, c_ml))
                                st.rerun()

            with col_der:
                with st.expander("📥 Importación"):
                    f_up = st.file_uploader("Documento Archicad (.xlsx)", type=["xlsx"])
                    if f_up and st.button("🚀 Procesar Documento"):
                        df_ex = pd.read_excel(f_up)
                        if df_ex.iloc[0].isnull().all(): df_ex = pd.read_excel(f_up, skiprows=1)
                        with conectar() as conn:
                            for _, r in df_ex.iterrows():
                                conn.execute("INSERT INTO productos (proyecto_id, ubicacion, tipo, ctd, ml) VALUES (?,?,?,?,?)",
                                             (id_p, r['UBICACION'], r['TIPO'], r['CTD'], r['Medidas (ml)']))
                        st.success("Productos importados"); st.rerun()

            st.divider()
            with st.expander("📋 Ver / Editar Inventario de Productos", expanded=True):
                prods = pd.read_sql_query("SELECT * FROM productos WHERE proyecto_id=?", conectar(), params=(id_p,))
                if not prods.empty:
                    # Cabecera de la tabla manual
                    h = st.columns([2, 2, 1, 1, 0.5, 0.5])
                    h[0].write("**Ubicación**"); h[1].write("**Tipo**"); h[2].write("**Cant.**"); h[3].write("**ML**")
                    
                    for _, r in prods.iterrows():
                        with st.container(border=True):
                            cols = st.columns([2, 2, 1, 1, 0.5, 0.5])
                            nu = cols[0].text_input("U", r['ubicacion'], key=f"u_{r['id']}", label_visibility="collapsed")
                            nt = cols[1].text_input("T", r['tipo'], key=f"t_{r['id']}", label_visibility="collapsed")
                            nc = cols[2].number_input("C", value=int(r['ctd']), key=f"c_{r['id']}", label_visibility="collapsed")
                            nm = cols[3].number_input("M", value=float(r['ml']), key=f"m_{r['id']}", label_visibility="collapsed")
                            
                            if cols[4].button("💾", key=f"s_{r['id']}"):
                                with conectar() as conn:
                                    conn.execute("UPDATE productos SET ubicacion=?, tipo=?, ctd=?, ml=? WHERE id=?", (nu, nt, nc, nm, r['id']))
                                st.toast("Guardado")
                            if cols[5].button("🗑️", key=f"d_{r['id']}"):
                                with conectar() as conn:
                                    conn.execute("DELETE FROM productos WHERE id=?", (r['id'],))
                                st.rerun()
                else:
                    st.info("No hay productos registrados.")

            # --- PEGA LA NUEVA SECCIÓN AQUÍ (Dentro de t1 todavía) ---
            st.divider()
            st.subheader("📤 Exportar Reporte")
            
            df_reporte = obtener_datos_reporte(id_p)
            
            if not df_reporte.empty:
                col_ex1, col_ex2 = st.columns(2)
                
                # A. Generar Excel en memoria
                import io
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_reporte.to_excel(writer, index=False, sheet_name='Inventario')
                
                col_ex1.download_button(
                    label="📥 Descargar Excel",
                    data=buffer.getvalue(),
                    file_name=f"Inventario_{p_data['proyecto_text']}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                
                # B. Botón de WhatsApp
                total_unid = df_reporte['Cantidad'].sum()
                total_ml_rep = df_reporte['Metros Lineales'].sum()
                msg = f"📋 *REPORTE PRACTIFORMAS*%0A*Proyecto:* {p_data['proyecto_text']}%0A*Cliente:* {p_data['cliente']}%0A--------------------%0A*Total Unidades:* {int(total_unid)}%0A*Total ML:* {total_ml_rep:.2f}m%0A--------------------%0A_Generado desde la App_"
                
                ws_link = f"https://wa.me/?text={msg}"
                col_ex2.link_button("🟢 Enviar Resumen por WhatsApp", ws_link, use_container_width=True)
            else:
                st.info("Agregue productos para habilitar la exportación.")

        # --- TAB 2: CRONOGRAMA ---
        with t2:
            st.subheader("📅 Gantt Planificado")
            data_gantt_plan = []
            etapas_plan = [
                ("Diseño", p_data['p_dis_i'], p_data['p_dis_f'], "#D5DBDB"),
                ("Fabricación", p_data['p_fab_i'], p_data['p_fab_f'], "#7F8C8D"),
                ("Traslado", p_data['p_tra_i'], p_data['p_tra_f'], "#D5DBDB"),
                ("Instalación", p_data['p_ins_i'], p_data['p_ins_f'], "#D5DBDB"),
                ("Entrega", p_data['p_ent_i'], p_data['p_ent_f'], "#D5DBDB")
            ]
            for et, ini, fin, color in etapas_plan:
                data_gantt_plan.append(dict(Etapa=et, Inicio=ini, Fin=fin, Color=color))
            
            fig = px.timeline(pd.DataFrame(data_gantt_plan), x_start="Inicio", x_end="Fin", y="Etapa", color="Color", color_discrete_map="identity")
            fig.update_yaxes(categoryorder="array", categoryarray=["Entrega", "Instalación", "Traslado", "Fabricación", "Diseño"])
            fig.update_xaxes(dtick="W1", tickformat="%d/%b", showgrid=True, griddash='dot')
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("📝 Editar Datos y Fechas Contractuales"):
                with st.form("edit_fechas_proy"):
                    e_cli = st.text_input("Cliente", p_data['cliente'])
                    e_pro = st.text_input("Proyecto", p_data['proyecto_text'])
                    e_par = st.text_input("Partida", p_data['partida'])
                    e_est = st.selectbox("Estatus", ["Activo", "Cerrado"], index=0 if p_data['estatus']=="Activo" else 1)
                    if st.form_submit_button("Actualizar Proyecto"):
                        actualizar_proyecto(id_p, {"cliente": e_cli, "proyecto_text": e_pro, "partida": e_par, "estatus": e_est})
                        st.rerun()

        # --- TAB 3: ZONA DE PELIGRO ---
        with t3:
            if rol_usuario == "Administrador":
                st.warning("⚠️ CUIDADO: Esta acción es irreversible.")
                if st.button("🚨 ELIMINAR PROYECTO COMPLETO", type="primary"):
                    eliminar_proyecto(id_p)
                    st.session_state.id_p_sel = None
                    st.success("Proyecto eliminado correctamente.")
                    st.rerun()
            elif rol_usuario == "Gerente":
                st.info("ℹ️ Perfil de Gerencia: Usted tiene permisos para gestionar, pero la eliminación definitiva está restringida al Administrador.")
            else:
                st.error("Acceso denegado. Solo el Administrador puede borrar proyectos.")

# --- MÓDULO CREAR NUEVO ---
elif menu == "Crear Nuevo":
    st.header("🏗️ Registro de Proyecto")
    
    # 1. Obtener personal con capacidad de gestión
    df_sups = obtener_supervisores()
    dict_sups = {r['nombre_real']: r['id'] for _, r in df_sups.iterrows()}

    with st.form("crear_p", clear_on_submit=False):
        st.subheader("📝 Datos del Proyecto")
        c1, c2, c3 = st.columns(3)
        cli = c1.text_input("Cliente")
        pro = c2.text_input("Proyecto")
        par = c3.text_input("Partida")
        
        sup_nom = st.selectbox(
            "Responsable a Cargo:", 
            options=list(dict_sups.keys()),
            help="Seleccione quién supervisará directamente los avances de este proyecto."
        )
        
        fi = c1.date_input("Inicio", format="DD/MM/YYYY")
        ff = c2.date_input("Término", value=date.today()+timedelta(days=30), format="DD/MM/YYYY")
        
        st.divider()
        st.subheader("📅 Distribución de Tiempos (%)")
        st.caption("Asegúrese de que la suma sea exactamente 100%")
        pcts = {}; cols = st.columns(5)
        for i, et in enumerate(ETAPAS): 
            pcts[et] = cols[i].number_input(f"{et}", 0, 100, 20, key=f"pct_{et}")
        
        st.divider()
        # --- AJUSTE AQUÍ: Definición de botones dentro del form ---
        col_btn1, col_btn2 = st.columns(2)
        btn_previs = col_btn1.form_submit_button("🔍 PREVISUALIZAR CRONOGRAMA")
        submit_crear = col_btn2.form_submit_button("💾 REGISTRAR PROYECTO")

        # 2. Lógica de Previsualización (Ahora la variable btn_previs existe)
        if btn_previs:
            if sum(pcts.values()) == 100:
                st.info("### 📅 Cronograma Calculado")
                total_d = (ff - fi).days
                act = fi
                for et in ETAPAS:
                    d = round(total_d * (pcts[et]/100))
                    f_et_f = act + timedelta(days=d)
                    st.write(f"**{et}:** {act.strftime('%d/%m/%Y')} al {f_et_f.strftime('%d/%m/%Y')} ({d} días)")
                    act = f_et_f + timedelta(days=1)
            else:
                st.error(f"La suma actual es {sum(pcts.values())}%. Debe ser exactamente 100%.")

        # 3. Lógica de Guardado Real
        if submit_crear:
            if cli and pro and sum(pcts.values()) == 100:
                id_sup_asignado = dict_sups[sup_nom]
                cron = {}; act = fi
                for et in ETAPAS:
                    d = round((ff-fi).days * (pcts[et]/100))
                    f_f = act + timedelta(days=d)
                    cron[et] = (act, f_f)
                    act = f_f + timedelta(days=1)
                
                vals = [cli, pro, par, str(fi), str(ff)]
                for et in ETAPAS: vals.extend([str(cron[et][0]), str(cron[et][1])])
                vals.append(id_sup_asignado)
                
                with conectar() as conn:
                    query = f"""
                        INSERT INTO proyectos (
                            cliente, proyecto_text, partida, f_ini, f_fin, 
                            p_dis_i, p_dis_f, p_fab_i, p_fab_f, p_tra_i, p_tra_f, 
                            p_ins_i, p_ins_f, p_ent_i, p_ent_f, supervisor_id
                        ) VALUES ({','.join(['?']*16)})
                    """
                    conn.execute(query, vals)
                
                st.success(f"✅ Proyecto '{pro}' creado y asignado a {sup_nom} con éxito.")
                st.balloons()
                st.rerun()
            elif sum(pcts.values()) != 100:
                st.error("❌ La suma de porcentajes debe ser exactamente 100%")
            else:
                st.error("❌ Faltan campos obligatorios (Cliente o Proyecto)")

elif menu == "Seguimiento": 
    # Si es supervisor, solo verá sus proyectos asignados
    sup_id_filtro = id_usuario if rol_usuario == "Supervisor" else None
    seguimiento.mostrar(supervisor_id=sup_id_filtro)
    
elif menu == "Gantt": 
    ejecucion.mostrar()

elif menu == "Usuarios":
    # Eliminamos el IF de aquí para que Gerentes y Supervisores puedan entrar a ver su perfil
    usuarios.mostrar()