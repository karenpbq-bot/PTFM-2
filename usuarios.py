import streamlit as st
import pandas as pd
from base_datos import conectar

def mostrar():
    st.header("👤 Gestión de Usuarios y Perfil")
    supabase = conectar()
    
    # --- DIAGNÓSTICO DE ROL (Solo para ti en consola/pantalla) ---
    # Esto nos dirá qué valor exacto tiene tu rol en la base de datos
    rol_actual = str(st.session_state.get('rol', 'Invitado')).strip()
    
    # 1. PERFIL PERSONAL (Siempre visible)
    with st.expander("👤 Mi Perfil y Seguridad", expanded=False):
        st.write(f"**Usuario:** {st.session_state.get('usuario')}")
        st.write(f"**Nombre:** {st.session_state.get('nombre_real')}")
        st.write(f"**Nivel de Acceso:** {rol_actual}")
        
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
                        st.success("✅ Contraseña actualizada.")
                    else: st.error("❌ Las contraseñas no coinciden.")
                else: st.error("❌ Contraseña actual incorrecta.")

   # --- ESTE ES EL AJUSTE DE LA INSTRUCCIÓN 1 ---
    # Definimos que tanto 'admin' como 'administrador' son jefes
    roles_jefes = ["administrador", "admin"]
    
    if rol_actual.lower() in roles_jefes:
        st.markdown("---")
        st.subheader("⚙️ Panel de Administración de Equipo")
        
        # Aquí siguen tus pestañas (tabs) de Crear Usuario y Lista...
        
        tab1, tab2 = st.tabs(["➕ Crear Usuario", "👥 Lista de Equipo"])
            
        with tab1:
            with st.form("nuevo_usuario", clear_on_submit=True):
                st.write("### Datos del Nuevo Colaborador")
                u_real = st.text_input("Nombre Completo (Ej: Juan Pérez)")
                u_nombre = st.text_input("Nombre de Usuario (Login)")
                u_pass = st.text_input("Contraseña Temporal", type="password")
                u_rol = st.selectbox("Rol y Permisos", ["admin", "Gerente", "Supervisor"])
                
                if st.form_submit_button("🚀 Registrar en el Sistema"):
                    if u_nombre and u_pass and u_real:
                        try:
                            # Inserción directa con columna correcta
                            supabase.table("usuarios").insert({
                                "nombre_usuario": u_nombre,
                                "contrasena": u_pass,
                                "rol": u_rol,
                                "nombre_completo": u_real 
                            }).execute()
                            st.success(f"✅ {u_real} ha sido registrado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error técnico: {e}")
                    else:
                        st.warning("⚠️ Rellene todos los campos.")

        # UBICACIÓN: Dentro de 'with tab2:'
        with tab2:
            try:
                # CAMBIO CRÍTICO: Seleccionamos el 'id' explícitamente
                res_u = supabase.table("usuarios").select("id, nombre_completo, nombre_usuario, rol").execute()
                if res_u.data:
                    for user in res_u.data:
                        # Diseño modular en filas
                        c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
                        c1.write(f"**{user['nombre_completo']}**")
                        c2.write(f"@{user['nombre_usuario']}")
                        c3.write(f"Role: {user['rol']}")
                        
                        # Botones de Acción
                        with c4.popover("⚙️"):
                            if st.button("Editar", key=f"btn_ed_{user['id']}"):
                                st.session_state.user_edit_id = user['id']
                                st.session_state.user_edit_data = user
                                st.rerun()
                            
                            if st.button("Eliminar", key=f"btn_del_{user['id']}"):
                                if user['id'] == st.session_state.id_usuario:
                                    st.error("No puedes eliminarte a ti mismo.")
                                else:
                                    from base_datos import eliminar_usuario_bd
                                    eliminar_usuario_bd(user['id'])
                                    st.success("Eliminado.")
                                    st.rerun()
                        st.divider()

                # MODAL DE EDICIÓN (Aparece solo al dar click en Editar)
                if "user_edit_id" in st.session_state:
                    with st.expander("📝 Editar Datos de Usuario", expanded=True):
                        with st.form("edit_form"):
                            n_nom = st.text_input("Nombre Real", value=st.session_state.user_edit_data['nombre_completo'])
                            n_usu = st.text_input("Usuario (Login)", value=st.session_state.user_edit_data['nombre_usuario'])
                            n_rol = st.selectbox("Rol", ["admin", "Gerente", "Supervisor"], 
                                               index=["admin", "Gerente", "Supevisor"].index(st.session_state.user_edit_data['rol']))
                            
                            col_f1, col_f2 = st.columns(2)
                            if col_f1.form_submit_button("Guardar"):
                                from base_datos import actualizar_usuario_bd
                                actualizar_usuario_bd(st.session_state.user_edit_id, {
                                    "nombre_completo": n_nom,
                                    "nombre_usuario": n_usu,
                                    "rol": n_rol
                                })
                                del st.session_state.user_edit_id
                                st.rerun()
                            if col_f2.form_submit_button("Cancelar"):
                                del st.session_state.user_edit_id
                                st.rerun()

            except Exception as e:
                st.error(f"Error: {e}")
