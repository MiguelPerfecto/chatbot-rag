"""
Configuración central del sistema.

Todos los parámetros ajustables del proyecto viven aquí. Ningún otro módulo
debe tener valores "quemados": si algo se puede cambiar, se cambia en este
archivo. Esto permite ejecutar los experimentos del Capítulo V modificando
un solo valor y volviendo a correr, en lugar de editar código disperso.
"""

from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# RUTAS
# ---------------------------------------------------------------------------
# BASE_DIR apunta a la raíz del proyecto sin importar desde dónde se ejecute
# el programa. Se usan rutas relativas para que el proyecto sea portable.

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
DOCUMENTOS_DIR = DATA_DIR / "documentos"   # corpus de prueba (PDF y DOCX)
INDICE_DIR = DATA_DIR / "indice"           # índice FAISS persistido
EVALUACION_DIR = BASE_DIR / "evaluacion"   # preguntas de prueba y resultados

for _ruta in (DATA_DIR, DOCUMENTOS_DIR, INDICE_DIR, EVALUACION_DIR):
    _ruta.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# INGESTA DE DOCUMENTOS
# ---------------------------------------------------------------------------

EXTENSIONES_PERMITIDAS = {".pdf", ".docx"}

# Tamaño máximo aceptado por archivo, en megabytes.
TAMANO_MAXIMO_MB = 50


# ---------------------------------------------------------------------------
# FRAGMENTACIÓN (CHUNKING)
# ---------------------------------------------------------------------------
# Estos dos valores son los que se comparan en la sección 5.3 del escrito.
# Configuraciones sugeridas para el experimento:
#   (500, 50)   fragmentos cortos, mayor precisión, riesgo de perder contexto
#   (800, 150)  configuración base
#   (1200, 200) fragmentos largos, más contexto, mayor ruido y costo

TAMANO_FRAGMENTO = 800      # caracteres por fragmento
SOLAPAMIENTO = 150          # caracteres compartidos entre fragmentos vecinos

# Un fragmento con menos caracteres que esto se descarta (encabezados sueltos,
# números de página, líneas residuales de la extracción).
MINIMO_CARACTERES_FRAGMENTO = 100


# ---------------------------------------------------------------------------
# EMBEDDINGS
# ---------------------------------------------------------------------------
# Modelo local, sin costo por consulta y sin dependencia de conexión.
# Se ejecuta en CPU sin problema. Alternativas a evaluar en el Capítulo V:
#   "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"  (384 dim, rápido)
#   "intfloat/multilingual-e5-base"                                (768 dim, mejor calidad)

MODELO_EMBEDDINGS = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DIMENSION_EMBEDDINGS = 384

# Cantidad de fragmentos que se vectorizan por lote durante la indexación.
LOTE_EMBEDDINGS = 32


# ---------------------------------------------------------------------------
# RECUPERACIÓN
# ---------------------------------------------------------------------------
# TOP_K es el número de fragmentos que se recuperan por consulta.
# Se compara en la sección 5.4.2 del escrito: valores típicos 3, 5 y 8.

TOP_K = 5

# Similitud coseno mínima para considerar un fragmento suficientemente
# relevante. Si ningún fragmento supera este umbral, el sistema responde que
# no encontró evidencia en los documentos en lugar de inventar una respuesta.
# El valor definitivo se determina experimentalmente (sección 5.4.3).
UMBRAL_RELEVANCIA = 0.35


# ---------------------------------------------------------------------------
# MODELO DE LENGUAJE (LLM)
# ---------------------------------------------------------------------------
# El proveedor se define aquí y no en el código de generación. La capa de
# abstracción del Bloque 6 lee estos valores, de modo que cambiar de proveedor
# no obliga a modificar la lógica del sistema.

PROVEEDOR_LLM = os.getenv("PROVEEDOR_LLM", "openai")
MODELO_LLM = os.getenv("MODELO_LLM", "gpt-4o-mini")
API_KEY_LLM = os.getenv("API_KEY_LLM", "")

TEMPERATURA = 0.2           # baja: se prioriza fidelidad al contexto
MAX_TOKENS_RESPUESTA = 800


# ---------------------------------------------------------------------------
# CONTEXTO CONVERSACIONAL
# ---------------------------------------------------------------------------

# Turnos previos de la conversación que se envían junto con la consulta.
TURNOS_HISTORIAL = 3


# ---------------------------------------------------------------------------
# REGISTRO (LOGGING)
# ---------------------------------------------------------------------------

NIVEL_LOG = "INFO"
