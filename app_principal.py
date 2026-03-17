import streamlit as st
import pandas as pd
from datetime import timedelta, datetime, date
import plotly.express as px
from base_datos import *
import seguimiento, ejecucion, login, usuarios, incidencias, proyectos 


# =========================================================
# CONFIGURACIÓN INICIAL Y SESIÓN
# =========================================================
st.set_page_config(
    page_title="Carpintería Pro V2",
    layout="wide", 
    initial_sidebar_state="collapsed"
)

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

# =========================================================
# BARRA LATERAL (SIDEBAR)
# =========================================================
with st.sidebar:
    st.title("🪚 PRACTIFORMAS")
    st.write(f"Usuario: **{st.session_state.nombre_real}**")
    st.caption(f"Rol: {rol_usuario}")
    
    # Definición limpia de opciones del menú
    opciones = ["Proyectos", "Seguimiento", "Gantt", "Incidencias", "Usuarios"]
    menu = st.radio("MENÚ PRINCIPAL", opciones)
    
    st.write("---")
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

# =========================================================
# ENRUTADOR DE MÓDULOS (LLAMADAS EXTERNAS)
# =========================================================
# Este bloque es el "director de orquesta": según lo que elijas en el menú,
# llama al archivo correspondiente.

if menu == "Proyectos":
    proyectos.mostrar() 

elif menu == "Seguimiento": 
    seguimiento.mostrar(supervisor_id=id_usuario if rol_usuario == "Supervisor" else None)

elif menu == "Gantt": 
    ejecucion.mostrar()

elif menu == "Usuarios":
    usuarios.mostrar()

elif menu == "Incidencias":
    incidencias.mostrar()
