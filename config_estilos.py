# =========================================================
# ARCHIVO: config_estilos.py
# FUNCIÓN: Definir la identidad visual (Azul Marino y Naranja)
# =========================================================

# --- 1. PALETA DE COLORES CORPORATIVOS ---
# Definimos las variables para usarlas en todo el sistema
AZUL_CLARO_MENU = "#E6F2FF"  # Fondo del menú (Azul muy suave)
TEXTO_MENU = "#002147"       # Color oscuro para las letras del menú
NARANJA_ACENTO = "#FF8C00"   # Color para botones y alertas importantes
BLANCO_FONDO = "#F5F5F5"     # Gris muy claro para el fondo de pantalla
TEXTO_GENERAL = "#333333"    # Color para lectura cómoda en el cuerpo

# --- 2. CONFIGURACIÓN DE PÁGINA ---
TITULO_APP = "Gestión de Carpintería Industrial"
ICONO_FAVICON = "📐"

# --- 3. ESTILOS CSS PERSONALIZADOS ---
# Aquí aplicamos los colores a la estructura visual de la web
ESTILOS_CSS = f"""
<style>
    /* Estilo para los botones principales (Naranja) */
    .stButton>button {{
        background-color: {NARANJA_ACENTO};
        color: white;
        border-radius: 8px;
        border: none;
        font-weight: bold;
    }}
    
    /* Configuración del Menú Lateral (Fondo claro) */
    [data-testid="stSidebar"] {{
        background-color: {AZUL_CLARO_MENU};
    }}
    
    /* Forzar que todos los textos del menú sean oscuros */
    [data-testid="stSidebar"] * {{
        color: {TEXTO_MENU} !important;
    }}

    /* Estilo opcional: Títulos del cuerpo en azul oscuro */
    h1, h2, h3 {{
        color: {TEXTO_MENU};
    }}
</style>
"""