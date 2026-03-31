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
# 2. CONFIGURACIÓN DE PÁGINA (MODIFICADO: Incorpora tu logo)
# =========================================================
# Esta debe ser la PRIMERA llamada de Streamlit que se ejecute
st.set_page_config(
    layout="wide", 
    page_title="PRACTIFORMAS | SGI PTFM", # <--- Título actualizado
    page_icon=ruta_logo_pestaña if os.path.exists(ruta_logo_pestaña) else "🪚" # <--- Tu logo aquí
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
