import streamlit as st
import pandas as pd
from base_datos import conectar

def mostrar():
    st.header("👤 Gestión de Usuarios y Perfil")
    supabase = conectar()
    
    # 1. INFORMACIÓN DE SESIÓN (DEBUG)
    rol_actual = st.session_state.get('rol', 'Invitado')

    # =========================================================
    # SECCIÓN 1: PERFIL UNIVERSAL (Autogestión de Clave)
    # =========================================================
    with st.expander("👤 Mi Perfil y Seguridad", expanded=False):
        st.write(f"**Usuario:** {st.session_state.get('usuario')}")
        st.write(f"**Nombre:** {st.session_state.get('nombre_real')}")
        st.write(f"**Nivel:** {rol_actual}")
        
        st.divider()
        with st.form("form_auto_cambio"):
            st.subheader("Cambiar mi contraseña")
            clave_act = st.text_input("Contraseña Actual:", type="password")
            nueva_cl = st.text_input("Nueva Contraseña:", type="password")
            conf_cl = st.text_input("Confirmar Nueva Contraseña:", type="password")
            
            if st.form_submit_button("Actualizar mi contraseña"):
                res = supabase.table("usuarios").select("contrasena").eq("nombre_usuario", st.session_state.usuario).execute()
                if res.data and res.data[0]['contrasena'] == clave_act:
                    if nueva_cl == conf_cl and nueva_cl != "":
                        supabase.table("usuarios").update({"contrasena": nueva_cl}).eq("nombre_usuario", st.session_state.usuario).execute()
                        st.success("✅ Actualizada.")
                    else: st.error("❌ Las contraseñas no coinciden.")
                else: st.error("❌ Contraseña actual incorrecta.")

    # =========================================================
    # SECCIÓN 2: CONTROL DE EQUIPO (Restringido a Administrador)
    # =========================================================
    if rol_actual == "Administrador":
        st.markdown("---")
        st.subheader("⚙️ Panel de Administración de Equipo")
        
        tab1, tab2 = st.tabs(["➕ Crear Usuario", "👥 Lista de Equipo"])
            
        with tab1:
            with st.form("nuevo_usuario", clear_on_submit=True):
                u_real = st.text_input("Nombre Completo (Ej: Juan Pérez)")
                u_nombre = st.text_input("Nombre de Usuario (Login)")
                u_pass = st.text_input("Contraseña Temporal", type="password")
                u_rol = st.selectbox("Rol y Permisos", ["Supervisor", "Gerente", "Administrador"])
                
                if st.form_submit_button("Registrar en el Sistema"):
                    if u_nombre and u_pass and u_real:
                        try:
                            supabase.table("usuarios").insert({
                                "nombre_usuario": u_nombre,
                                "contrasena": u_pass,
                                "rol": u_rol,
                                "nombre_completo": u_real  # Columna correcta en tu DB
                            }).execute()
                            st.success(f"✅ {u_real} registrado con éxito.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: El usuario ya existe o hay falla de conexión.")
                    else:
                        st.warning("Complete todos los campos.")

        with tab2:
            try:
                res_u = supabase.table("usuarios").select("nombre_completo, nombre_usuario, rol").execute()
                if res_u.data:
                    df_u = pd.DataFrame(res_u.data)
                    df_u.columns = ['Nombre', 'Usuario', 'Rol']
                    st.dataframe(df_u, use_container_width=True, hide_index=True)
            except:
                st.error("No se pudo cargar la lista.")

        # SECCIÓN 3: RESET MAESTRO
        st.markdown("---")
        with st.expander("🛡️ Reset Maestro de Contraseñas (Seguridad)"):
            with st.form("reset_maestro"):
                u_reset = st.text_input("Usuario a resetear:")
                p_reset = st.text_input("Nueva contraseña:", type="password")
                if st.form_submit_button("Ejecutar Reset"):
                    if u_reset and p_reset:
                        supabase.table("usuarios").update({"contrasena": p_reset}).eq("nombre_usuario", u_reset).execute()
                        st.success(f"✅ Password de {u_reset} cambiada.")
    else:
        st.info("ℹ️ Tu nivel de acceso solo permite gestionar tu perfil personal.")
