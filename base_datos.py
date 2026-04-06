import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta

# =========================================================
# 1. CONEXIÓN Y CONFIGURACIÓN
# =========================================================

def conectar():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

def inicializar_bd():
    """Mantenida para compatibilidad de importación."""
    pass

# =========================================================
# 2. GESTIÓN DE USUARIOS
# =========================================================

def validar_usuario(usuario, clave):
    supabase = conectar()
    res = supabase.table("usuarios").select("*").eq("nombre_usuario", usuario).eq("contrasena", clave).execute()
    return res.data[0] if res.data else None

def obtener_supervisores():
    try:
        supabase = conectar()
        res = supabase.table("usuarios").select("id, nombre_completo, rol").in_("rol", ['Administrador', 'Gerente', 'Supervisor']).execute()
        df = pd.DataFrame(res.data)
        if not df.empty:
            df = df.rename(columns={'nombre_completo': 'nombre_real'})
        return df
    except Exception as e:
        st.error(f"Error al obtener supervisores: {e}")
        return pd.DataFrame(columns=['id', 'nombre_real', 'rol'])

# =========================================================
# 3. GESTIÓN DE PROYECTOS
# =========================================================

def obtener_proyectos(palabra_clave=""):
    try:
        supabase = conectar()
        query = supabase.table("proyectos").select("*")
        if palabra_clave:
            query = query.or_(f"codigo.ilike.%{palabra_clave}%,proyecto_text.ilike.%{palabra_clave}%,cliente.ilike.%{palabra_clave}%")
        res = query.execute()
        df = pd.DataFrame(res.data)
        if not df.empty:
            df['proyecto_display'] = "[" + df['codigo'].astype(str) + "] " + df['proyecto_text']
        return df
    except Exception as e:
        st.error(f"Error crítico en la consulta: {e}")
        return pd.DataFrame()

def crear_proyecto(codigo, nombre, cliente, partida):
    try:
        supabase = conectar()
        data = {
            "codigo": codigo, "proyecto_text": nombre, "cliente": cliente,
            "partida": partida, "estatus": "Activo", "avance": 0
        }
        return supabase.table("proyectos").insert(data).execute()
    except Exception as e:
        st.error(f"Error al crear proyecto: {e}")
        return None

# Agrega esta función al final de base_datos.py o busca la existente para mejorarla

def eliminar_proyecto_completo(id_proyecto):
    """Borra toda la información vinculada a un proyecto en orden jerárquico."""
    try:
        supabase = conectar()
        
        # 1. Obtener IDs de los productos vinculados al proyecto
        res_prods = supabase.table("productos").select("id").eq("proyecto_id", id_proyecto).execute()
        ids_productos = [p['id'] for p in res_prods.data]
        
        if ids_productos:
            # 2. Borrar seguimientos de esos productos (Usando una subconsulta o filtro por proyecto si fuera posible)
            # Como los seguimientos no tienen 'proyecto_id' directo, lo ideal es borrarlos por lotes o así:
            supabase.table("seguimiento").delete().in_("producto_id", ids_productos).execute()
        
        # 3. Borrar incidencias/requerimientos del proyecto
        supabase.table("incidencias").delete().eq("proyecto_id", id_proyecto).execute()

        # NUEVO: Borrar registros de auditoría (IMPORTANTE)
        # Tienes una tabla llamada 'productos_avance_valor' que también guarda datos por producto
        if ids_productos:
            supabase.table("productos_avance_valor").delete().in_("producto_id", ids_productos).execute()
        
        # 5. Finalmente, borrar el proyecto
        res = supabase.table("proyectos").delete().eq("id", id_proyecto).execute()
        
        return True
    except Exception as e:
        st.error(f"Error técnico al eliminar: {e}")
        return False

# =========================================================
# 4. GESTIÓN DE PRODUCTOS Y SEGUIMIENTO
# =========================================================

def obtener_productos_por_proyecto(id_proyecto):
    supabase = conectar()
    res = supabase.table("productos").select("*").eq("proyecto_id", id_proyecto).order("codigo_etiqueta").execute()
    return pd.DataFrame(res.data)

def obtener_seguimiento(id_producto):
    supabase = conectar()
    res = supabase.table("seguimiento").select("*").eq("producto_id", id_producto).execute()
    return pd.DataFrame(res.data)

def obtener_pesos_seguimiento():
    """Retorna la ponderación porcentual de cada hito."""
    return {
        "Diseñado": 15, "Fabricado": 40, "Material en Obra": 5,
        "Material en Ubicación": 5, "Instalación de Estructura": 15,
        "Instalación de Puertas o Frentes": 10, "Revisión y Observaciones": 5, "Entrega": 5
    }

def obtener_avance_por_hitos(id_proyecto, df_productos_filtrados=None):
    """Calcula el % de cumplimiento por hito para los productos (opcionalmente filtrados)."""
    supabase = conectar()
    if df_productos_filtrados is None:
        res = supabase.table("productos").select("id").eq("proyecto_id", id_proyecto).execute()
        df_p = pd.DataFrame(res.data)
    else:
        df_p = df_productos_filtrados

    if df_p.empty: 
        # Si no hay productos, devolvemos 0% para todos los hitos
        HITOS_LIST = ["Diseñado", "Fabricado", "Material en Obra", "Material en Ubicación", 
                      "Instalación de Estructura", "Instalación de Puertas o Frentes", 
                      "Revisión y Observaciones", "Entrega"]
        return {h: 0.0 for h in HITOS_LIST}

    ids = df_p['id'].tolist()
    res_seg = supabase.table("seguimiento").select("hito").in_("producto_id", ids).execute()
    df_s = pd.DataFrame(res_seg.data)
    
    avances = {}
    HITOS_LIST = ["Diseñado", "Fabricado", "Material en Obra", "Material en Ubicación", 
                  "Instalación de Estructura", "Instalación de Puertas o Frentes", 
                  "Revisión y Observaciones", "Entrega"]
    
    total = len(df_p)
    if total == 0: 
        return {h: 0.0 for h in HITOS_LIST}

    # Si no hay datos en seguimiento, devolvemos todo en 0 rápidamente
    if df_s.empty:
        return {h: 0.0 for h in HITOS_LIST}

    for h in HITOS_LIST:
        conteo = len(df_s[df_s['hito'] == h])
        avances[h] = round((conteo / total) * 100, 1)
        
    return avances

# =========================================================
# 5. MOTOR DE SINCRONIZACIÓN ESTRUCTURAL
# =========================================================

def sincronizar_avances_estructural(codigo_p):
    """Motor Optimizado V2: Procesa 500+ productos en milisegundos usando lógica de conjuntos."""
    try:
        supabase = conectar()
        
        # 1. Obtener datos del proyecto (Una sola consulta)
        res_p = supabase.table("proyectos").select("id, proyecto_text, cliente").eq("codigo", codigo_p).single().execute()
        if not res_p.data: return
        p_id, p_nom, p_cli = res_p.data['id'], res_p.data['proyecto_text'], res_p.data['cliente']
        
        # 2. Obtener IDs de productos (Una sola consulta)
        res_prods = supabase.table("productos").select("id").eq("proyecto_id", p_id).execute()
        if not res_prods.data: return
        df_p = pd.DataFrame(res_prods.data)
        ids_prods = df_p['id'].tolist()
        num_prods = len(ids_prods)

        # 3. Obtener TODO el seguimiento del proyecto (Una sola consulta)
        # Esto evita miles de viajes de ida y vuelta al servidor
        res_seg = supabase.table("seguimiento").select("producto_id, hito, fecha").in_("producto_id", ids_prods).execute()
        df_seg = pd.DataFrame(res_seg.data) if res_seg.data else pd.DataFrame(columns=['producto_id', 'hito', 'fecha'])

        # 4. Consolidación Horizontal para el Gantt
        # Definimos los grupos de hitos que componen cada etapa del Gantt
        GRUPOS = {
            "av_diseno": ["Diseñado"], 
            "av_fabricacion": ["Fabricado"],
            "av_traslado": ["Material en Obra", "Material en Ubicación"],
            "av_instalacion": ["Instalación de Estructura", "Instalación de Puertas o Frentes"],
            "av_entrega": ["Revisión y Observaciones", "Entrega"]
        }

        fila_horizontal = {
            "codigo": codigo_p, 
            "proyecto_nombre": p_nom, 
            "cliente": p_cli,
            "ultima_actualizacion": datetime.now().isoformat()
        }

        # Procesamos las fechas para obtener el inicio y fin real del proyecto
        fechas_reales = []
        if not df_seg.empty:
            df_seg['f_dt'] = pd.to_datetime(df_seg['fecha'], errors='coerce', dayfirst=True)
            fechas_reales = df_seg['f_dt'].dropna().tolist()

        # CÁLCULO DE AVANCES POR ETAPA (Lógica de Pandas)
        for col, hitos in GRUPOS.items():
            # Filtramos el seguimiento que pertenece a esta etapa
            conteo_etapa = len(df_seg[df_seg['hito'].isin(hitos)])
            # Capacidad máxima: (Hitos de la etapa) x (Número de productos)
            max_posible = len(hitos) * num_prods
            fila_horizontal[col] = round((conteo_etapa / max_posible) * 100, 1) if max_posible > 0 else 0

        # Determinamos las fechas extremas para las barras del Gantt Real
        if fechas_reales:
            fila_horizontal["fecha_inicio_real"] = min(fechas_reales).strftime('%Y-%m-%d')
            fila_horizontal["fecha_fin_real"] = max(fechas_reales).strftime('%Y-%m-%d')

        # 5. ESCRITURA FINAL: Una sola petición para todo el proyecto
        supabase.table("avances_etapas").upsert(fila_horizontal, on_conflict="codigo").execute()
        
    except Exception as e:
        st.error(f"Falla en motor estructural optimizado: {e}")

# =========================================================
# 6. GESTIÓN DE INCIDENCIAS E HISTORIAL
# =========================================================

def registrar_incidencia_detallada(proyecto_id, tipo, motivo, piezas, materiales, usuario_id):
    supabase = conectar()
    detalle_final = piezas if tipo == "Piezas" else materiales
    data = {
        "proyecto_id": proyecto_id, "tipo_requerimiento": tipo, "categoria": motivo,
        "detalles": detalle_final, "supervisor_id": usuario_id, "estado": "Pendiente",
        "created_at": datetime.now().isoformat()
    }
    try:
        return supabase.table("incidencias").insert(data).execute()
    except Exception as e:
        print(f"Error en incidencia: {e}"); return None

def obtener_incidencias_resumen():
    try:
        supabase = conectar()
        # El select("*") debería traer las nuevas columnas si ya las creaste en Supabase
        res = supabase.table("incidencias").select("*, proyectos(proyecto_text)").order("created_at", desc=True).execute()
        if not res.data: return pd.DataFrame()
        for r in res.data:
            r['proyecto_text'] = r['proyectos'].get('proyecto_text', 'N/A') if r.get('proyectos') else "Sin Proyecto"
        return pd.DataFrame(res.data)
    except Exception as e:
        print(f"Error en historial incidencias: {e}"); return pd.DataFrame()

def actualizar_gestion_incidencia(inc_id, datos_dict):
    """Actualiza los campos de seguimiento de un requerimiento."""
    try:
        supabase = conectar()
        # Aseguramos que los valores sean texto o vacíos
        datos_limpios = {k: (str(v) if v else "") for k, v in datos_dict.items()}
        return supabase.table("incidencias").update(datos_limpios).eq("id", inc_id).execute()
    except Exception as e:
        st.error(f"Error en base de datos: {e}")
        return None
        
# =========================================================
# 7. FUNCIONES DE COMPATIBILIDAD (Legacy)
# =========================================================

def sincronizar_avances_etapas(id_p):
    """Alias para compatibilidad con módulos antiguos."""
    actualizar_avance_real(id_p)

def obtener_gantt_real_data(id_p):
    """Función de compatibilidad para evitar errores de importación en ejecucion.py"""
    try:
        supabase = conectar()
        res_prods = supabase.table("productos").select("id").eq("proyecto_id", id_p).execute()
        ids = [p['id'] for p in res_prods.data]
        if not ids: return pd.DataFrame()
        res = supabase.table("seguimiento").select("hito, fecha").in_("producto_id", ids).execute()
        return pd.DataFrame(res.data)
    except:
        return pd.DataFrame()

def actualizar_avance_real(id_p):
    """Redirige llamadas antiguas al nuevo motor estructural"""
    try:
        res = conectar().table("proyectos").select("codigo").eq("id", id_p).single().execute()
        if res.data:
            sincronizar_avances_estructural(res.data['codigo'])
    except:
        pass

# --- AGREGAR AL FINAL DE LA SECCIÓN 2 (GESTIÓN DE USUARIOS) ---

def eliminar_usuario_bd(id_usuario):
    supabase = conectar()
    # Asegúrate que la columna en Supabase se llame 'id'
    return supabase.table("usuarios").delete().eq("id", id_usuario).execute()

def actualizar_usuario_bd(id_usuario, datos):
    supabase = conectar()
    return supabase.table("usuarios").update(datos).eq("id", id_usuario).execute()
