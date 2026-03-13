import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client

# =========================================================
# 1. CONEXIÓN Y CONFIGURACIÓN
# =========================================================

def conectar():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

def inicializar_bd():
    """Función mantenida para evitar errores de importación."""
    pass

# =========================================================
# 2. GESTIÓN DE USUARIOS
# =========================================================

def validar_usuario(usuario, clave):
    supabase = conectar()
    res = supabase.table("usuarios").select("*").eq("nombre_usuario", usuario).eq("contrasena", clave).execute()
    return res.data[0] if res.data else None

def obtener_supervisores():
    supabase = conectar()
    res = supabase.table("usuarios").select("id, nombre_real, rol").in_("rol", ['Administrador', 'Gerente', 'Supervisor']).execute()
    return pd.DataFrame(res.data)

# =========================================================
# 3. GESTIÓN DE PROYECTOS
# =========================================================

def obtener_proyectos(busqueda="", supervisor_id=None):
    supabase = conectar()
    query = supabase.table("proyectos").select("*")
    if supervisor_id:
        query = query.eq("supervisor_id", supervisor_id)
    res = query.execute()
    df = pd.DataFrame(res.data)
    if not df.empty and busqueda:
        df = df[df['proyecto_text'].str.contains(busqueda, case=False) | df['cliente'].str.contains(busqueda, case=False)]
    return df

def actualizar_proyecto(id_p, campos):
    supabase = conectar()
    supabase.table("proyectos").update(campos).eq("id", id_p).execute()

def eliminar_proyecto(id_p):
    supabase = conectar()
    supabase.table("proyectos").delete().eq("id", id_p).execute()

def obtener_datos_reporte(id_proyecto):
    """Extrae el inventario detallado desde la nube para exportación a Excel y WhatsApp."""
    try:
        supabase = conectar()
        res = supabase.table("productos").select("ubicacion, tipo, ctd, ml").eq("proyecto_id", id_proyecto).execute()
        
        df = pd.DataFrame(res.data)
        if not df.empty:
            # Renombramos las columnas para que el Excel se vea profesional
            df.columns = ['Ubicación', 'Tipo', 'Cantidad', 'Metros Lineales']
            return df
        return pd.DataFrame() # Devuelve un DataFrame vacío si no hay datos
    except Exception as e:
        st.error(f"Error al generar reporte: {e}")
        return pd.DataFrame()

# =========================================================
# 4. GESTIÓN DE PRODUCTOS Y AVANCE
# =========================================================

def agregar_producto_manual(id_p, u, t, c, m):
    supabase = conectar()
    supabase.table("productos").insert({"proyecto_id": id_p, "ubicacion": u, "tipo": t, "ctd": c, "ml": m}).execute()

def obtener_resumen_inventario(id_proyecto):
    """Calcula la sumatoria de cantidades y metros lineales de un proyecto desde la nube."""
    try:
        supabase = conectar()
        # Traemos solo las columnas necesarias para ahorrar ancho de banda
        res = supabase.table("productos").select("ctd, ml").eq("proyecto_id", id_proyecto).execute()
        
        if res.data:
            df = pd.DataFrame(res.data)
            total_ctd = df['ctd'].sum()
            total_ml = df['ml'].sum()
            return total_ctd, total_ml
        return 0, 0
    except Exception as e:
        # En caso de error, devolvemos ceros para que la app no colapse
        return 0, 0

def actualizar_avance_real(id_p):
    supabase = conectar()
    prods = supabase.table("productos").select("id").eq("proyecto_id", id_p).execute()
    total = len(prods.data)
    if total == 0: return
    ids = [p['id'] for p in prods.data]
    segs = supabase.table("seguimiento").select("id").in_("producto_id", ids).execute()
    nuevo_avance = (len(segs.data) / (total * 8)) * 100
    supabase.table("proyectos").update({"avance": nuevo_avance}).eq("id", id_p).execute()
    
def obtener_gantt_real_data(id_p):
    supabase = conectar()
    prods = supabase.table("productos").select("id").eq("proyecto_id", id_p).execute()
    ids = [p['id'] for p in prods.data]
    res = supabase.table("seguimiento").select("hito, fecha").in_("producto_id", ids).execute()
    return pd.DataFrame(res.data)

# =========================================================
# 5. GESTIÓN DE INCIDENCIAS
# =========================================================

def registrar_incidencia_detallada(proy_id, tipo_inc, motivo, piezas, materiales, user_id):
    supabase = conectar()
    inc = supabase.table("incidencias").insert({
        "proyecto_id": proy_id, "tipo_requerimiento": tipo_inc, 
        "categoria": motivo, "fecha_reporte": date.today().isoformat(), "usuario_id": user_id
    }).execute()
    inc_id = inc.data[0]['id']
    if piezas:
        for p in piezas:
            p['incidencia_id'] = inc_id
            supabase.table("detalles_piezas").insert(p).execute()
    if materiales:
        for m in materiales:
            m['incidencia_id'] = inc_id
            supabase.table("detalles_materiales").insert(m).execute()

def obtener_incidencias_resumen():
    supabase = conectar()
    res = supabase.table("incidencias").select("*, proyectos(proyecto_text), usuarios(nombre_real)").execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['proyecto_text'] = df['proyectos'].apply(lambda x: x['proyecto_text'] if x else "")
        df['nombre_real'] = df['usuarios'].apply(lambda x: x['nombre_real'] if x else "")
    return df


