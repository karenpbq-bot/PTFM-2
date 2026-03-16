import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client
from datetime import datetime

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
    try:
        supabase = conectar()
        # Cambiamos nombre_real por nombre_completo según lo visto en login.py
        res = supabase.table("usuarios").select("id, nombre_completo, rol").in_("rol", ['Administrador', 'Gerente', 'Supervisor']).execute()
        df = pd.DataFrame(res.data)
        
        # Renombramos para que el resto del código (proyectos.py) no falle
        if not df.empty and 'nombre_completo' in df.columns:
            df = df.rename(columns={'nombre_completo': 'nombre_real'})
            
        return df
    except Exception as e:
        st.error(f"Error al obtener supervisores: {e}")
        return pd.DataFrame(columns=['id', 'nombre_real', 'rol'])

# =========================================================
# 3. GESTIÓN DE PROYECTOS (ACTUALIZADA V2)
# =========================================================

def obtener_proyectos(palabra_clave=""):
    """Buscador Universal: Filtra por Código, Nombre o Cliente."""
    supabase = conectar()
    query = supabase.table("proyectos").select("id, codigo, proyecto_text, cliente, estatus, avance, partida")
    
    if palabra_clave:
        # Lógica OR para palabras clave en múltiples campos
        query = query.or_(f"codigo.ilike.%{palabra_clave}%,proyecto_text.ilike.%{palabra_clave}%,cliente.ilike.%{palabra_clave}%")
    
    res = query.execute()
    df = pd.DataFrame(res.data)
    
    if not df.empty:
        # Crea la etiqueta para los selectbox: [PTF-001] Proyecto Ejemplo
        df['proyecto_display'] = "[" + df['codigo'].astype(str) + "] " + df['proyecto_text']
        
    return df

def crear_proyecto(codigo, nombre, cliente, partida):
    """Inserta un nuevo proyecto con su DNI/Código único."""
    try:
        supabase = conectar()
        data = {
            "codigo": codigo,
            "proyecto_text": nombre,
            "cliente": cliente,
            "partida": partida,
            "estatus": "Activo",
            "avance": 0
        }
        return supabase.table("proyectos").insert(data).execute()
    except Exception as e:
        st.error(f"Error al crear: {e}")
        return None

def eliminar_proyecto(id_p):
    """Borra un proyecto y sus datos asociados (Cascada)."""
    return conectar().table("proyectos").delete().eq("id", id_p).execute()
    
# =========================================================
# 4. GESTIÓN DE PRODUCTOS Y SEGUIMIENTO (AJUSTES)
# =========================================================

def obtener_productos_por_proyecto(id_proyecto):
    """Recupera los productos asociados a un proyecto específico."""
    supabase = conectar()
    res = supabase.table("productos").select("*").eq("proyecto_id", id_proyecto).execute()
    return pd.DataFrame(res.data)

def obtener_seguimiento(id_producto):
    """Obtiene el historial de hitos de un producto."""
    supabase = conectar()
    res = supabase.table("seguimiento").select("*").eq("producto_id", id_producto).execute()
    return pd.DataFrame(res.data)

def guardar_seguimiento(id_producto, hito, fecha):
    """Guarda o actualiza un hito. Maneja el formato de fecha para la DB."""
    try:
        supabase = conectar()
        # Intentamos convertir DD/MM/YYYY a YYYY-MM-DD para la base de datos
        try:
            fecha_db = datetime.strptime(fecha, '%d/%m/%Y').strftime('%Y-%m-%d')
        except:
            fecha_db = fecha # Si falla, enviamos el texto original
            
        data = {
            "producto_id": id_producto,
            "hito": hito,
            "fecha": fecha_db
        }
        # upsert: inserta si no existe, actualiza si existe (requiere UNIQUE en producto_id y hito)
        res = supabase.table("seguimiento").upsert(data).execute()
        
        # Actualizamos el avance del proyecto automáticamente
        res_prod = supabase.table("productos").select("proyecto_id").eq("id", id_producto).execute()
        if res_prod.data:
            actualizar_avance_real(res_prod.data[0]['proyecto_id'])
            
        return res
    except Exception as e:
        st.error(f"Error al guardar hito: {e}")
        return None
# =========================================================
# 5. GESTIÓN DE INCIDENCIAS
# =========================================================

from datetime import datetime # Asegúrate de que esté al inicio del archivo

def registrar_incidencia_detallada(proyecto_id, tipo, motivo, piezas, materiales, usuario_id):
    supabase = conectar()
    
    # Seleccionamos el set de datos que no esté vacío
    detalle_final = piezas if tipo == "Piezas" else materiales
    
    data = {
        "proyecto_id": proyecto_id,
        "tipo_requerimiento": tipo,
        "categoria": motivo,
        "detalles": detalle_final,
        "supervisor_id": usuario_id,
        "estado": "Pendiente",
        "created_at": datetime.now().isoformat() # Aquí es donde fallaba
    }
    
    try:
        res = supabase.table("incidencias").insert(data).execute()
        return res
    except Exception as e:
        print(f"Error: {e}")
        return None

def obtener_incidencias_resumen():
    supabase = conectar()
    try:
        # Consultamos incidencias incluyendo el campo proyecto_text de la tabla proyectos
        res = supabase.table("incidencias").select("*, proyectos(proyecto_text)").order("created_at", desc=True).execute()
        
        if not res.data:
            return pd.DataFrame()
        
        # PROCESAMIENTO CRÍTICO: Extraer el texto del objeto anidado
        for registro in res.data:
            if registro.get('proyectos'):
                # Pasamos el valor de registro['proyectos']['proyecto_text'] a la raíz del diccionario
                registro['proyecto_text'] = registro['proyectos'].get('proyecto_text', 'N/A')
            else:
                registro['proyecto_text'] = "Sin Proyecto"
                
        return pd.DataFrame(res.data)
    except Exception as e:
        print(f"Error en historial: {e}")
        return pd.DataFrame()

def obtener_gantt_real_data(id_p):
    """Extrae datos de hitos reales para el cronograma."""
    supabase = conectar()
    # 1. Obtiene los productos del proyecto
    prods = supabase.table("productos").select("id").eq("proyecto_id", id_p).execute()
    ids = [p['id'] for p in prods.data]
    if not ids: return pd.DataFrame()
    
    # 2. Obtiene los hitos registrados en seguimiento
    res = supabase.table("seguimiento").select("hito, fecha").in_("producto_id", ids).execute()
    return pd.DataFrame(res.data)

def actualizar_avance_real(id_p):
    """Calcula el avance basado en 8 hitos por producto."""
    supabase = conectar()
    prods = supabase.table("productos").select("id").eq("proyecto_id", id_p).execute()
    total_esperado = len(prods.data) * 8
    if total_esperado == 0: return
    ids = [p['id'] for p in prods.data]
    segs = supabase.table("seguimiento").select("id").in_("producto_id", ids).execute()
    nuevo_avance = (len(segs.data) / total_esperado) * 100
    supabase.table("proyectos").update({"avance": nuevo_avance}).eq("id", id_p).execute()

# =========================================================
# 6. MOTOR DE CÁLCULO PARA GANTT PONDERADO
# =========================================================

def obtener_pesos_seguimiento():
    """Retorna la ponderación porcentual de cada hito."""
    return {
        "Diseñado": 15, 
        "Fabricado": 40, 
        "Material en Obra": 5,
        "Material en Ubicación": 5, 
        "Instalación de Estructura": 15, 
        "Instalación de Puertas o Frentes": 10, 
        "Revisión y Observaciones": 5, 
        "Entrega": 5
    }

def obtener_datos_gantt_procesados(id_proyecto):
    """Procesa hitos de la DB y los agrupa en las 5 etapas del Gantt."""
    supabase = conectar()
    pesos = obtener_pesos_seguimiento()
    
    # 1. Obtener todos los productos del proyecto
    res_prods = supabase.table("productos").select("id").eq("proyecto_id", id_proyecto).execute()
    ids_prods = [p['id'] for p in res_prods.data]
    
    if not ids_prods:
        return []

    # 2. Obtener todo el historial de seguimiento de esos productos
    res_segs = supabase.table("seguimiento").select("*").in_("producto_id", ids_prods).execute()
    df_segs = pd.DataFrame(res_segs.data)
    
    if df_segs.empty:
        return []

    # 3. Definición de Grupos de Etapas (Tu reconfiguración final)
    GRUPOS = {
        "Diseño": ["Diseñado"],
        "Fabricación": ["Fabricado"],
        "Traslado": ["Material en Obra", "Material en Ubicación"],
        "Instalación": ["Instalación de Estructura", "Instalación de Puertas o Frentes"],
        "Entrega": ["Revisión y Observaciones", "Entrega"]
    }

    procesado = []
    
    for etapa, hitos in GRUPOS.items():
        # Filtramos los datos que pertenecen a los hitos de esta etapa
        df_etapa = df_segs[df_segs['hito'].isin(hitos)]
        
        if not df_etapa.empty:
            # Determinamos fechas reales (Inicio: primer check / Fin: último check)
            df_etapa['fecha_dt'] = pd.to_datetime(df_etapa['fecha'])
            inicio_real = df_etapa['fecha_dt'].min()
            fin_real = df_etapa['fecha_dt'].max()
            
            # Si el inicio y fin son iguales, extendemos 1 día para que sea visible en el Gantt
            if inicio_real == fin_real:
                fin_real += pd.Timedelta(days=1)

            # --- CÁLCULO PONDERADO ---
            # Suma de pesos teóricos de los hitos que conforman esta etapa
            peso_max_etapa = sum([pesos.get(h, 0) for h in hitos])
            puntos_obtenidos = 0
            
            # Calculamos cuánto aporta cada hito completado al total de la etapa
            for h in hitos:
                cant_completados = len(df_etapa[df_etapa['hito'] == h])
                # El avance es: (Peso del hito * cantidad de productos que lo tienen) / total productos
                puntos_obtenidos += (pesos.get(h, 0) * (cant_completados / len(ids_prods)))
            
            # Porcentaje final de la etapa (0 a 100)
            avance_etapa = (puntos_obtenidos / peso_max_etapa) * 100 if peso_max_etapa > 0 else 0
            
            procesado.append({
                "Etapa": etapa,
                "Inicio": inicio_real,
                "Fin": fin_real,
                "Avance": avance_etapa,
                "Tipo": "Ejecutado"
            })
            
    return procesado


