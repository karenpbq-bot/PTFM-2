import streamlit as st
import pandas as pd
from base_datos import conectar

def mostrar():
    st.header("👤 Gestión de Usuarios y Perfil")
    supabase = conectar()
    
    # =========================================================
    # SECCIÓN 1: PERFIL UNIVERSAL (Autogestión de Clave)
    # =========================================================
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
                # Ajuste Nube: Consulta de validación
                res = supabase.table("usuarios").select("contrasena").eq("nombre_usuario", st.session_state.usuario).execute()
                datos = res.data[0] if res.data else None
                
                if datos and datos['contrasena'] == clave_actual:
                    if nueva_clave == confirmar_clave and nueva_clave != "":
                        # Ajuste Nube: Update de contraseña
                        supabase.table("usuarios").update({"contrasena": nueva_clave}).eq("nombre_usuario", st.session_state.usuario).execute()
                        st.success("✅ Tu contraseña ha sido actualizada correctamente.")
                    else:
                        st.error("❌ Las nuevas contraseñas no coinciden o están vacías.")
                else:
                    st.error("❌ La contraseña actual es incorrecta.")

    # =========================================================
    # SECCIÓN 2: CONTROL DE EQUIPO (Restringido a Admin)
    # =========================================================
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
                            # Ajuste Nube: Inserción de nuevo registro
                            supabase.table("usuarios").insert({
                                "nombre_usuario": u_nombre,
                                "contrasena": u_pass,
                                "rol": u_rol,
                                "nombre_real": u_real
                            }).execute()
                            st.success(f"✅ {u_real} registrado como {u_rol}.")
                        except Exception:
                            st.error("Error: El nombre de usuario ya existe en la base de datos.")
                    else:
                        st.warning("Por favor, complete todos los campos.")

        with tab2:
            st.subheader("Colaboradores con acceso")
            try:
                # Ajuste Nube: Lectura de tabla para DataFrame
                res_u = supabase.table("usuarios").select("nombre_real, nombre_usuario, rol").execute()
                df_u = pd.DataFrame(res_u.data)
                
                if not df_u.empty:
                    # Renombrar columnas para la visualización original
                    df_u.columns = ['Nombre', 'Usuario', 'Rol']
                    st.dataframe(df_u, use_container_width=True, hide_index=True)
                else:
                    st.info("No hay otros usuarios registrados.")
            except Exception:
                st.error("Error al cargar la lista de equipo desde la nube.")

        # =========================================================
        # SECCIÓN 3: HERRAMIENTA DE RESCATE (Reset Maestro)
        # =========================================================
        seccion_seguridad()

def seccion_security_nube(user, password):
    """Función auxiliar para ejecutar el cambio en la nube."""
    supabase = conectar()
    supabase.table("usuarios").update({"contrasena": password}).eq("nombre_usuario", user).execute()

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
                    try:
                        # Ajuste Nube: Update maestro
                        seccion_security_nube(user_to_change, new_pass)
                        st.success(f"✅ La contraseña de **{user_to_change}** ha sido actualizada.")
                    except Exception as e:
                        st.error(f"Error al actualizar: {e}")
                else:
                    st.error("Por favor, rellena ambos campos.")
