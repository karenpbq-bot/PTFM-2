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

def eliminar_proyecto(id_p):
    return conectar().table("proyectos").delete().eq("id", id_p).execute()

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

    if df_p.empty: return {}

    ids = df_p['id'].tolist()
    res_seg = supabase.table("seguimiento").select("hito").in_("producto_id", ids).execute()
    df_s = pd.DataFrame(res_seg.data)
    
    avances = {}
    HITOS_LIST = ["Diseñado", "Fabricado", "Material en Obra", "Material en Ubicación", 
                  "Instalación de Estructura", "Instalación de Puertas o Frentes", 
                  "Revisión y Observaciones", "Entrega"]
    
    total = len(df_p)
    for h in HITOS_LIST:
        conteo = len(df_s[df_s['hito'] == h]) if not df_s.empty else 0
        avances[h] = round((conteo / total) * 100, 1)
    return avances

# =========================================================
# 5. MOTOR DE SINCRONIZACIÓN ESTRUCTURAL
# =========================================================

def sincronizar_avances_estructural(codigo_p):
    """Actualiza la tabla de auditoría (0/1) y la consolidación horizontal (avances_etapas)."""
    try:
        supabase = conectar()
        # A. Obtener datos maestros
        res_p = supabase.table("proyectos").select("id, proyecto_text, cliente").eq("codigo", codigo_p).single().execute()
        if not res_p.data: return
        p_id, p_nom, p_cli = res_p.data['id'], res_p.data['proyecto_text'], res_p.data['cliente']
        
        pesos_dict = obtener_pesos_seguimiento()
        
        # B. Obtener Productos y Seguimiento real
        res_prods = supabase.table("productos").select("id").eq("proyecto_id", p_id).execute()
        if not res_prods.data: return
        ids_prods = [p['id'] for p in res_prods.data]
        num_prods = len(ids_prods)
        
        res_seg = supabase.table("seguimiento").select("producto_id, hito, fecha").in_("producto_id", ids_prods).execute()
        df_seg = pd.DataFrame(res_seg.data) if res_seg.data else pd.DataFrame(columns=['producto_id', 'hito', 'fecha'])

        # C. Actualizar Tabla de Auditoría (productos_avance_valor) para exportaciones 0/1
        lote_conteo = []
        for pid in ids_prods:
            for hito_nom, peso_val in pesos_dict.items():
                esta_logrado = 1 if not df_seg[(df_seg['producto_id'] == pid) & (df_seg['hito'] == hito_nom)].empty else 0
                lote_conteo.append({
                    "codigo_proyecto": codigo_p, "producto_id": pid, "hito": hito_nom,
                    "logrado": esta_logrado, "valor_porcentual": peso_val
                })
        if lote_conteo:
            supabase.table("productos_avance_valor").upsert(lote_conteo, on_conflict="producto_id, hito").execute()

        # D. Consolidación Horizontal para Gantt y Reporte Matricial
        GRUPOS = {
            "av_diseno": ["Diseñado"], "av_fabricacion": ["Fabricado"],
            "av_traslado": ["Material en Obra", "Material en Ubicación"],
            "av_instalacion": ["Instalación de Estructura", "Instalación de Puertas o Frentes"],
            "av_entrega": ["Revisión y Observaciones", "Entrega"]
        }

        fila_horizontal = {
            "codigo": codigo_p, "proyecto_nombre": p_nom, "cliente": p_cli,
            "ultima_actualizacion": datetime.now().isoformat()
        }

        fechas_globales = []
        for col, hitos in GRUPOS.items():
            df_etapa = df_seg[df_seg['hito'].isin(hitos)]
            conteo_total = len(df_etapa)
            max_posible = len(hitos) * num_prods
            fila_horizontal[col] = round((conteo_total / max_posible) * 100, 1)

            if not df_etapa.empty:
                df_etapa['f_dt'] = pd.to_datetime(df_etapa['fecha'], errors='coerce', dayfirst=True)
                df_etapa = df_etapa.dropna(subset=['f_dt'])
                if not df_etapa.empty:
                    f_min, f_max = df_etapa['f_dt'].min(), df_etapa['f_dt'].max()
                    if f_min == f_max: f_max = f_max + timedelta(days=1)
                    fechas_globales.extend([f_min, f_max])

        if fechas_globales:
            fila_horizontal["fecha_inicio_real"] = min(fechas_globales).strftime('%Y-%m-%d')
            fila_horizontal["fecha_fin_real"] = max(fechas_globales).strftime('%Y-%m-%d')

        supabase.table("avances_etapas").upsert(fila_horizontal).execute()
        
    except Exception as e:
        st.error(f"Error en sincronización estructural: {e}")

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
        res = supabase.table("incidencias").select("*, proyectos(proyecto_text)").order("created_at", desc=True).execute()
        if not res.data: return pd.DataFrame()
        for r in res.data:
            r['proyecto_text'] = r['proyectos'].get('proyecto_text', 'N/A') if r.get('proyectos') else "Sin Proyecto"
        return pd.DataFrame(res.data)
    except Exception as e:
        print(f"Error en historial incidencias: {e}"); return pd.DataFrame()

# =========================================================
# 7. FUNCIONES DE COMPATIBILIDAD (Legacy)
# =========================================================

def actualizar_avance_real(id_p):
    """Mantenida para no romper llamadas antiguas. Redirige a la nueva lógica."""
    res = conectar().table("proyectos").select("codigo").eq("id", id_p).single().execute()
    if res.data: sincronizar_avances_estructural(res.data['codigo'])

def sincronizar_avances_etapas(id_p):
    """Alias para compatibilidad con módulos antiguos."""
    actualizar_avance_real(id_p)
