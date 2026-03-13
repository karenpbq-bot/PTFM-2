import streamlit as st
import pandas as pd
from base_datos import conectar

def validar_usuario(usuario, clave):
    """Consulta la base de datos para verificar las credenciales."""
    query = "SELECT * FROM usuarios WHERE nombre_usuario = ? AND contrasena = ?"
    with conectar() as conn:
        df = pd.read_sql_query(query, conn, params=(usuario, clave))
    return df.iloc[0] if not df.empty else None

def login_screen():
    """Muestra la interfaz de inicio de sesión."""
    col1, col2, col3 = st.columns([1, 1.5, 1])
    
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center;'>🪵</h1>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center;'>Control de Producción</h2>", unsafe_allow_html=True)
        
        with st.container(border=True):
            st.subheader("Acceso al Sistema")
            with st.form("login_form", clear_on_submit=True):
                usuario = st.text_input("Usuario", placeholder="Ej: admin")
                clave = st.text_input("Contraseña", type="password", placeholder="••••••••")
                
                submit = st.form_submit_button("Iniciar Sesión", use_container_width=True)
                
                if submit:
                    if usuario and clave:
                        user_data = validar_usuario(usuario, clave)
                        
                        if user_data is not None:
                            # --- GUARDAR ESTADO DE SESIÓN ---
                            st.session_state.autenticado = True
                            st.session_state.usuario = user_data['nombre_usuario']
                            st.session_state.rol = user_data['rol']
                            # Sincronizamos nombres de ID para evitar errores en otras pantallas
                            st.session_state.id_usuario = user_data['id']
                            st.session_state.usuario_id = user_data['id'] 
                            st.session_state.nombre_real = user_data['nombre_real']
                            
                            st.success(f"Bienvenido(a), {user_data['nombre_real']}")
                            st.rerun() 
                        else:
                            st.error("❌ Usuario o contraseña incorrectos.")
                    else:
                        st.warning("⚠️ Por favor, complete ambos campos.")

        st.markdown("<p style='text-align: center; color: gray; font-size: 12px;'>Carpintería Pro V2 - © 2026</p>", unsafe_allow_html=True)