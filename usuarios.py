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
                u_rol = st.selectbox("Rol y Permisos", ["Supervisor", "Gerente", "Administrador"])
                
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
                # 1. Recuperamos los datos incluyendo el ID necesario para las acciones
                res_u = supabase.table("usuarios").select("id, nombre_completo, nombre_usuario, rol").execute()
                
                if res_u.data:
                    # Encabezados de tabla personalizados para mejor lectura
                    c_h1, c_h2, c_h3, c_h4 = st.columns([2.5, 2, 1.5, 1])
                    c_h1.subheader("Nombre Real")
                    c_h2.subheader("Usuario")
                    c_h3.subheader("Rol")
                    c_h4.subheader("Acción")
                    st.divider()

                    for user in res_u.data:
                        col1, col2, col3, col4 = st.columns([2.5, 2, 1.5, 1])
                        
                        col1.write(user['nombre_completo'])
                        col2.write(user['nombre_usuario'])
                        col3.write(user['rol'])
                        
                        # Usamos un popover para agrupar Editar y Eliminar y no saturar la fila
                        with col4.popover("⚙️"):
                            if st.button("📝 Editar", key=f"edit_{user['id']}", use_container_width=True):
                                st.session_state.editando_id = user['id']
                                st.session_state.datos_editar = user
                                st.rerun()
                            
                            if st.button("🗑️ Borrar", key=f"del_{user['id']}", use_container_width=True):
                                # Evitar que el usuario activo se borre a sí mismo
                                if user['id'] == st.session_state.id_usuario:
                                    st.error("No puedes eliminar tu propia cuenta.")
                                else:
                                    from base_datos import eliminar_usuario
                                    if eliminar_usuario(user['id']):
                                        st.success("Usuario eliminado.")
                                        st.rerun()
                        st.divider()

                # 2. FORMULARIO FLOTANTE DE EDICIÓN
                if "editando_id" in st.session_state:
                    st.markdown("---")
                    with st.expander("🛠️ EDITANDO USUARIO", expanded=True):
                        with st.form("form_edicion_rapida"):
                            u_id = st.session_state.editando_id
                            nuevo_nom = st.text_input("Nombre Completo:", value=st.session_state.datos_editar['nombre_completo'])
                            nuevo_user = st.text_input("Nombre de Usuario:", value=st.session_state.datos_editar['nombre_usuario'])
                            
                            # Mantenemos la consistencia con los roles originales
                            roles_lista = ["Supervisor", "Gerente", "Administrador"]
                            idx_rol = roles_lista.index(st.session_state.datos_editar['rol']) if st.session_state.datos_editar['rol'] in roles_lista else 0
                            nuevo_rol = st.selectbox("Cambiar Rol:", roles_lista, index=idx_rol)
                            
                            col_btn1, col_btn2 = st.columns(2)
                            if col_btn1.form_submit_button("✅ Guardar Cambios"):
                                from base_datos import actualizar_datos_usuario
                                exito = actualizar_datos_usuario(u_id, {
                                    "nombre_completo": nuevo_nom,
                                    "nombre_usuario": nuevo_user,
                                    "rol": nuevo_rol
                                })
                                if exito:
                                    del st.session_state.editando_id
                                    st.success("Usuario actualizado correctamente.")
                                    st.rerun()
                            
                            if col_btn2.form_submit_button("❌ Cancelar"):
                                del st.session_state.editando_id
                                st.rerun()

            except Exception as e:
                st.error(f"Error al cargar la lista de equipo: {e}")
