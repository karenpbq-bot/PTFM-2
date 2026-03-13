import streamlit as st
import pandas as pd
from base_datos import validar_usuario # Importamos directamente la función ajustada

# --- ELIMINAMOS LA FUNCIÓN LOCAL validar_usuario PORQUE YA ESTÁ EN base_datos.py ---
# Al estar centralizada en base_datos.py, evitamos conflictos de conexión.

def login_screen():
    """Muestra la interfaz de inicio de sesión."""
    # Estética: Centrar el formulario usando columnas
    col1, col2, col3 = st.columns([1, 1.5, 1])
    
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        # Puedes cambiar este emoji por una URL de imagen de tu logo si deseas
        st.markdown("<h1 style='text-align: center;'>🪵</h1>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center;'>Control de Producción</h2>", unsafe_allow_html=True)
        
        with st.container(border=True):
            st.subheader("Acceso al Sistema")
            with st.form("login_form", clear_on_submit=True):
                usuario = st.text_input("Usuario", placeholder="Ej: admin")
                clave = st.text_input("Contraseña", type="password", placeholder="••••••••")
                
                # Botón que ocupa todo el ancho
                submit = st.form_submit_button("Iniciar Sesión", use_container_width=True)
                
                if submit:
                    if usuario and clave:
                        # LLAMADA A LA FUNCIÓN DE NUBE
                        user_data = validar_usuario(usuario, clave)
                        
                        if user_data is not None:
                            # --- GUARDAR ESTADO DE SESIÓN ---
                            # Nota: En Supabase, user_data ya es un diccionario, no un DataFrame.
                            st.session_state.autenticado = True
                            st.session_state.usuario = user_data['nombre_usuario']
                            st.session_state.rol = user_data['rol']
                            st.session_state.id_usuario = user_data['id']
                            st.session_state.nombre_real = user_data['nombre_real']
                            
                            st.success(f"Bienvenido(a), {user_data['nombre_real']}")
                            st.rerun() # Reinicia para mostrar el menú principal
                        else:
                            st.error("❌ Usuario o contraseña incorrectos.")
                    else:
                        st.warning("⚠️ Por favor, complete ambos campos.")

        st.markdown("<p style='text-align: center; color: gray; font-size: 12px;'>Carpintería Pro V2 - © 2026</p>", unsafe_allow_html=True)
