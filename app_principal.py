# =========================================================
# 1. IMPORTACIONES (MODIFICADO: Incluye 'os')
# =========================================================
import streamlit as st
import pandas as pd
from datetime import timedelta, datetime, date
import plotly.express as px
from base_datos import *
import os  # <-- Importante para manejar rutas de archivos
import seguimiento, ejecucion, login, usuarios, incidencias, proyectos 

# --- Lógica para localizar el logo ---
# Esto debe estar ANTES de st.set_page_config
directorio_actual = os.path.dirname(__file__)
nombre_logo_pestaña = "LOGO PRACTIFORMAS SIN FONDO.PNG" # Nombre exacto del archivo
ruta_logo_pestaña = os.path.join(directorio_actual, nombre_logo_pestaña)

# =========================================================
# 2. CONFIGURACIÓN DE PÁGINA (MODIFICADO: Menú Fijo)
# =========================================================
st.set_page_config(
    layout="wide", 
    page_title="PRACTIFORMAS | PROYECTOS", 
    page_icon=ruta_logo_pestaña if os.path.exists(ruta_logo_pestaña) else "🪚",
    initial_sidebar_state="expanded" # <--- ESTO hace que el menú inicie SIEMPRE abierto
)

# --- ESTILO SEGURO (Mantenemos limpieza sin bloquear acceso) ---
st.markdown("""
    <style>
    /* Ocultamos basura de Streamlit pero NO el header completo */
    .stDeployButton {display:none;}
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}

    /* Ajuste para que el contenido no se pegue al borde superior */
    .block-container {
        padding-top: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CÓDIGO PARA PERSONALIZAR SIN PERDER EL MENÚ EN MÓVILES ---
st.markdown("""
    <style>
    /* 1. Ocultamos el botón de 'Deploy' y la marca de agua de Streamlit */
    .stDeployButton {display:none;}
    footer {visibility: hidden;}
    
    /* 2. En lugar de ocultar el header completo, ocultamos solo los elementos 
       innecesarios pero DEJAMOS el botón del menú (hamburguesa) */
    header {
        background-color: rgba(0,0,0,0); /* Lo hacemos transparente */
    }
    
    /* Ocultamos el menú de opciones predeterminado de Streamlit (el de la derecha) */
    #MainMenu {visibility: hidden;}

    /* 3. Ajustamos el espacio superior para que no se desperdicie espacio en el iPhone */
    .block-container {
        padding-top: 3rem;
        padding-bottom: 0rem;
    }

    /* 4. OPCIONAL: Si quieres que el título del Sidebar sea más llamativo */
    [data-testid="stSidebarNav"] {
        padding-top: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)

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
