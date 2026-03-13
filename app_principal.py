import streamlit as st
import pandas as pd
from datetime import timedelta, datetime, date
from base_datos import *
import seguimiento, ejecucion, login, usuarios, incidencias 
import plotly.express as px

# =========================================================
# CONFIGURACIÓN INICIAL Y SESIÓN
# =========================================================
st.set_page_config(layout="wide", page_title="Carpintería Pro V2")
inicializar_bd()

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if 'id_p_sel' not in st.session_state:
    st.session_state.id_p_sel = None 

if not st.session_state.autenticado:
    login.login_screen()
    st.stop()

rol_usuario = st.session_state.rol
id_usuario = st.session_state.id_usuario
ETAPAS = ["Diseño", "Fabricación", "Traslado", "Instalación", "Entrega"]

# =========================================================
# BARRA LATERAL (SIDEBAR)
# =========================================================
with st.sidebar:
    st.title("🪚 PRACTIFORMAS")
    st.write(f"Usuario: **{st.session_state.nombre_real}**")
    st.caption(f"Rol: {rol_usuario}")
    
    if st.button("🔄 Ver Todos los Proyectos"):
        st.session_state.id_p_sel = None
        st.rerun()
    
    opciones = ["Seguimiento", "Incidencias", "Gantt", "Usuarios"] 
    if rol_usuario in ["Administrador", "Gerente"]:
        opciones.insert(0, "Proyectos")
        opciones.insert(1, "Crear Nuevo")
    
    menu = st.sidebar.radio("MENÚ PRINCIPAL", opciones)
    
    st.write("---")
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

# =========================================================
# MÓDULO: CARTERA DE PROYECTOS
# =========================================================
if menu == "Proyectos":
    if st.session_state.id_p_sel is None:
        st.header("📂 Cartera de Proyectos")
        bus_cartera = st.text_input("🔍 Buscar proyecto o cliente...", key="bus_main_cartera")
        df_cartera = obtener_proyectos(bus_cartera)
        
        if df_cartera.empty:
            st.info("No se encontraron proyectos activos.")
        
        if rol_usuario in ["Administrador", "Gerente"] and not df_cartera.empty:
            opciones_limpieza = {f"{r['proyecto_text']} — {r['cliente']}": r['id'] for _, r in df_cartera.iterrows()}
            with st.expander("🗑️ Zona de Limpieza Masiva"):
                st.warning("Esta acción eliminará todos los productos del proyecto seleccionado.")
                proy_a_vaciar = st.selectbox("Proyecto a vaciar:", ["Seleccione..."] + list(opciones_limpieza.keys()), key="vaciar_proy")
                if st.button("⚠️ ELIMINAR TODOS LOS PRODUCTOS", type="secondary", key="btn_limpieza_masiva"):
                    if proy_a_vaciar != "Seleccione...":
                        borrar_productos_proyecto(opciones_limpieza[proy_a_vaciar])
                        st.success("Productos eliminados correctamente.")
                        st.rerun()

        for _, p in df_cartera.iterrows():
            total_unidades, total_ml = obtener_resumen_inventario(p['id'])
            try:
                f_ini_dt = datetime.strptime(str(p['f_ini']), '%Y-%m-%d').strftime('%d/%m/%Y')
                f_fin_dt = datetime.strptime(str(p['f_fin']), '%Y-%m-%d').strftime('%d/%m/%Y')
            except:
                f_ini_dt, f_fin_dt = "N/A", "N/A"

            with st.container(border=True):
                col_info, col_btn = st.columns([5, 1.5])
                with col_info:
                    st.subheader(f"🚀 {p['proyecto_text']}")
                    st.write(f"👤 **Cliente:** {p['cliente']}")
                    st.caption(f"🏷️ **Partida:** {p['partida']} | 📅 {f_ini_dt} al {f_fin_dt}")
                with col_btn:
                    if st.button("⚙️ GESTIONAR", key=f"btn_gest_{p['id']}", use_container_width=True):
                        st.session_state.id_p_sel = p['id']
                        st.rerun()
                m1, m2, m3 = st.columns(3)
                m1.metric("Unidades", int(total_unidades))
                m2.metric("Total ML", f"{total_ml:.2f}")
                m3.metric("Avance", f"{int(p['avance'])}%")
                st.progress(float(p['avance'])/100)

# =========================================================
# MÓDULO: PANEL DE GESTIÓN DETALLADA
# =========================================================
    else:
        id_p = st.session_state.id_p_sel
        supabase = conectar()
        res_aux = supabase.table("proyectos").select("*").eq("id", id_p).execute()
        
        if not res_aux.data:
            st.error("⚠️ El proyecto seleccionado ya no existe.")
            st.session_state.id_p_sel = None
            if st.button("🔄 Volver"): st.rerun()
            st.stop()
        
        p_data = res_aux.data[0]
        if st.sidebar.button("⬅️ VOLVER A LA CARTERA"):
            st.session_state.id_p_sel = None
            st.rerun()

        st.title(f"🚀 {p_data['proyecto_text']} — {p_data['cliente']}")
        t1, t2, t3 = st.tabs(["📋 Productos e Inventario", "📅 Cronograma Contractual", "🚨 Zona de Peligro"])
        
        with t1:
            st.subheader("📦 Gestión de Inventario")
            col_izq, col_der = st.columns(2)
            with col_izq:
                with st.expander("➕ Creación Manual"):
                    with st.form("nuevo_manual", clear_on_submit=True):
                        u_m = st.text_input("Ubicación")
                        t_m = st.text_input("Tipo")
                        c_cant = st.number_input("Cantidad", min_value=1, step=1)
                        c_ml = st.number_input("Metros Lineales (ML)", min_value=0.0, format="%.2f")
                        if st.form_submit_button("Añadir Producto"):
                            agregar_producto_manual(id_p, u_m, t_m, c_cant, c_ml)
                            st.rerun()
            with col_der:
                with st.expander("📥 Importación"):
                    f_up = st.file_uploader("Documento Archicad (.xlsx)", type=["xlsx"])
                    if f_up and st.button("🚀 Procesar Documento"):
                        df_ex = pd.read_excel(f_up)
                        if df_ex.iloc[0].isnull().all(): df_ex = pd.read_excel(f_up, skiprows=1)
                        for _, r in df_ex.iterrows():
                            agregar_producto_manual(id_p, r['UBICACION'], r['TIPO'], r['CTD'], r['Medidas (ml)'])
                        st.success("Productos importados"); st.rerun()

            st.divider()
            # Lista de productos con edición
            prods_res = supabase.table("productos").select("*").eq("proyecto_id", id_p).execute()
            if prods_res.data:
                for r in prods_res.data:
                    with st.container(border=True):
                        cols = st.columns([2, 2, 1, 1, 0.5, 0.5])
                        nu = cols[0].text_input("U", r['ubicacion'], key=f"u_{r['id']}", label_visibility="collapsed")
                        nt = cols[1].text_input("T", r['tipo'], key=f"t_{r['id']}", label_visibility="collapsed")
                        nc = cols[2].number_input("C", value=int(r['ctd']), key=f"c_{r['id']}", label_visibility="collapsed")
                        nm = cols[3].number_input("M", value=float(r['ml']), key=f"m_{r['id']}", label_visibility="collapsed")
                        if cols[4].button("💾", key=f"s_{r['id']}"):
                            actualizar_producto(r['id'], nu, nt, nc, nm)
                            st.toast("Guardado")
                        if cols[5].button("🗑️", key=f"d_{r['id']}"):
                            eliminar_producto(r['id'])
                            st.rerun()

            # Exportación
            st.divider()
            df_reporte = obtener_datos_reporte(id_p)
            if not df_reporte.empty:
                col_ex1, col_ex2 = st.columns(2)
                import io
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_reporte.to_excel(writer, index=False, sheet_name='Inventario')
                col_ex1.download_button("📥 Descargar Excel", buffer.getvalue(), f"Inventario_{p_data['proyecto_text']}.xlsx", use_container_width=True)
                
                msg = f"📋 *REPORTE PRACTIFORMAS*%0A*Proyecto:* {p_data['proyecto_text']}%0A*Total Unidades:* {int(df_reporte['Cantidad'].sum())}%0A_Generado desde la App_"
                st.link_button("🟢 Enviar WhatsApp", f"https://wa.me/?text={msg}", use_container_width=True)

        with t2:
            st.subheader("📅 Gantt Planificado")
            # Mapeo dinámico para el Gantt Planificado de la Nube
            etapas_conf = [
                ("Diseño", "p_dis_i", "p_dis_f"), ("Fabricación", "p_fab_i", "p_fab_f"),
                ("Traslado", "p_tra_i", "p_tra_f"), ("Instalación", "p_ins_i", "p_ins_f"),
                ("Entrega", "p_ent_i", "p_ent_f")
            ]
            data_gantt_plan = [dict(Etapa=e, Inicio=p_data[i], Fin=p_data[f], Color="#D5DBDB") for e, i, f in etapas_conf]
            fig = px.timeline(pd.DataFrame(data_gantt_plan), x_start="Inicio", x_end="Fin", y="Etapa", color="Color", color_discrete_map="identity")
            fig.update_yaxes(categoryorder="array", categoryarray=["Entrega", "Instalación", "Traslado", "Fabricación", "Diseño"])
            st.plotly_chart(fig, use_container_width=True)

        with t3:
            if rol_usuario == "Administrador":
                if st.button("🚨 ELIMINAR PROYECTO COMPLETO", type="primary"):
                    eliminar_proyecto(id_p)
                    st.session_state.id_p_sel = None
                    st.rerun()

# =========================================================
# MÓDULO: CREAR NUEVO PROYECTO (AJUSTADO A SUPABASE)
# =========================================================
elif menu == "Crear Nuevo":
    st.header("🏗️ Registro de Proyecto")
    df_sups = obtener_supervisores()
    dict_sups = {r['nombre_real']: r['id'] for _, r in df_sups.iterrows()}

    with st.form("crear_p"):
        c1, c2, c3 = st.columns(3)
        cli = c1.text_input("Cliente")
        pro = c2.text_input("Proyecto")
        par = c3.text_input("Partida")
        sup_nom = st.selectbox("Responsable:", options=list(dict_sups.keys()))
        fi = c1.date_input("Inicio", format="DD/MM/YYYY")
        ff = c2.date_input("Término", value=date.today()+timedelta(days=30), format="DD/MM/YYYY")
        
        pcts = {}; cols = st.columns(5)
        for i, et in enumerate(ETAPAS): 
            pcts[et] = cols[i].number_input(f"{et} %", 0, 100, 20)
        
        if st.form_submit_button("💾 REGISTRAR PROYECTO"):
            if cli and pro and sum(pcts.values()) == 100:
                cron = {}; act = fi
                for et in ETAPAS:
                    d = round((ff-fi).days * (pcts[et]/100))
                    f_f = act + timedelta(days=d)
                    cron[et] = (str(act), str(f_f))
                    act = f_f + timedelta(days=1)
                
                datos_nube = {
                    "cliente": cli, "proyecto_text": pro, "partida": par, 
                    "f_ini": str(fi), "f_fin": str(ff), "supervisor_id": dict_sups[sup_nom],
                    "p_dis_i": cron["Diseño"][0], "p_dis_f": cron["Diseño"][1],
                    "p_fab_i": cron["Fabricación"][0], "p_fab_f": cron["Fabricación"][1],
                    "p_tra_i": cron["Traslado"][0], "p_tra_f": cron["Traslado"][1],
                    "p_ins_i": cron["Instalación"][0], "p_ins_f": cron["Instalación"][1],
                    "p_ent_i": cron["Entrega"][0], "p_ent_f": cron["Entrega"][1]
                }
                conectar().table("proyectos").insert(datos_nube).execute()
                st.success("✅ Proyecto creado"); st.rerun()

# =========================================================
# OTROS MÓDULOS (LLAMADAS EXTERNAS)
# =========================================================
elif menu == "Seguimiento": 
    seguimiento.mostrar(supervisor_id=id_usuario if rol_usuario == "Supervisor" else None)
elif menu == "Gantt": 
    ejecucion.mostrar()
elif menu == "Usuarios":
    usuarios.mostrar()
elif menu == "Incidencias":
    incidencias.mostrar()

