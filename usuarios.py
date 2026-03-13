import streamlit as st
import pandas as pd # Importante para la pestaña de Lista
from base_datos import conectar

def mostrar():
    st.header("👤 Gestión de Usuarios y Perfil")
    
    # --- SECCIÓN 1: PERFIL UNIVERSAL (Visible para Supervisor, Gerente y Admin) ---
    # Todos los colaboradores de Practiformas pueden gestionar su propia clave aquí.
    with st.expander("👤 Mi Perfil y Seguridad", expanded=True):
        st.write(f"**Usuario actual:** {st.session_state.get('usuario', 'No definido')}")
        st.write(f"**Nombre:** {st.session_state.get('nombre_real', 'No definido')}")
        st.write(f"**Nivel de Acceso:** {st.session_state.get('rol', 'No definido')}")
        
        st.divider()
        st.subheader("Cambiar mi contraseña")
        with st.form("form_auto_cambio", clear_on_submit=True):
            clave_actual = st.text_input("Contraseña Actual:", type="password")
            nueva_clave = st.text_input("Nueva Contraseña:", type="password")
            confirmar_clave = st.text_input("Confirmar Nueva Contraseña:", type="password")
            
            if st.form_submit_button("Actualizar mi contraseña"):
                # Validar clave actual contra la base de datos
                with conectar() as conn:
                    datos = conn.execute(
                        "SELECT contrasena FROM usuarios WHERE nombre_usuario = ?", 
                        (st.session_state.usuario,)
                    ).fetchone()
                
                if datos and datos[0] == clave_actual:
                    if nueva_clave == confirmar_clave and nueva_clave != "":
                        with conectar() as conn:
                            conn.execute(
                                "UPDATE usuarios SET contrasena = ? WHERE nombre_usuario = ?", 
                                (nueva_clave, st.session_state.usuario)
                            )
                            conn.commit()
                        st.success("✅ Tu contraseña ha sido actualizada correctamente.")
                    else:
                        st.error("❌ Las nuevas contraseñas no coinciden o están vacías.")
                else:
                    st.error("❌ La contraseña actual es incorrecta.")

    # --- SECCIÓN 2: CONTROL DE EQUIPO (RESTRICCIÓN: Solo Administrador) ---
    rol_actual = st.session_state.get('rol', 'Invitado')

    if rol_actual == "Administrador":
        st.markdown("---")
        st.subheader("⚙️ Panel de Administración de Equipo")
        
        tab1, tab2 = st.tabs(["➕ Crear Usuario", "👥 Lista de Equipo"])
            
        with tab1:
            with st.form("nuevo_usuario", clear_on_submit=True):
                st.subheader("Datos del Colaborador")
                u_real = st.text_input("Nombre Completo (Ej: Juan Pérez)")
                u_nombre = st.text_input("Nombre de Usuario (Login)")
                u_pass = st.text_input("Contraseña Temporal", type="password")
                
                u_rol = st.selectbox("Rol y Permisos", [
                    "Supervisor", 
                    "Gerente", 
                    "Administrador"
                ], help="Supervisor: Proyectos propios. Gerente: Lectura total. Admin: Control total.")
                
                if st.form_submit_button("Registrar en el Sistema"):
                    if u_nombre and u_pass and u_real:
                        try:
                            with conectar() as conn:
                                conn.execute(
                                    "INSERT INTO usuarios (nombre_usuario, contrasena, rol, nombre_real) VALUES (?,?,?,?)",
                                    (u_nombre, u_pass, u_rol, u_real)
                                )
                            st.success(f"✅ {u_real} registrado como {u_rol}.")
                        except Exception:
                            st.error("Error: El usuario ya existe.")
                    else:
                        st.warning("Por favor, complete todos los campos.")

        with tab2:
            st.subheader("Colaboradores con acceso")
            try:
                df_u = pd.read_sql_query("SELECT nombre_real as 'Nombre', nombre_usuario as 'Usuario', rol as 'Rol' FROM usuarios", conectar())
                if not df_u.empty:
                    st.dataframe(df_u, use_container_width=True, hide_index=True)
                else:
                    st.info("No hay otros usuarios registrados.")
            except Exception:
                st.error("Error al cargar la lista de equipo.")

        # Herramienta de rescate de cuentas
        seccion_seguridad()

def seccion_seguridad():
    st.markdown("---")
    st.subheader("🛡️ Seguridad del Sistema")
    
    with st.expander("Cambiar contraseña de cualquier cuenta (Reset Maestro)"):
        with st.form("cambio_pass_form"):
            user_to_change = st.text_input("Nombre de usuario:")
            new_pass = st.text_input("Nueva contraseña segura:", type="password")
            submitted = st.form_submit_button("Actualizar Credenciales")
            
            if submitted:
                if user_to_change and new_pass:
                    with conectar() as conn:
                        conn.execute(
                            "UPDATE usuarios SET contrasena = ? WHERE nombre_usuario = ?", 
                            (new_pass, user_to_change)
                        )
                        conn.commit()
                    st.success(f"✅ La contraseña de **{user_to_change}** ha sido actualizada.")
                else:
                    st.error("Por favor, rellena ambos campos.")