"""
Filtrado de fragmentos sin contenido consultable.

No todo el texto de un documento constituye información susceptible de
responder una consulta. Los índices de contenido, las listas de figuras y las
portadas son texto legítimo del documento, pero su función es orientar la
navegación, no transmitir conocimiento.

Estos fragmentos resultan especialmente problemáticos en un sistema de
recuperación semántica. Un índice concentra una elevada densidad de términos
temáticos en poco texto, lo que produce representaciones vectoriales muy
próximas a cualquier consulta sobre dichos temas. En consecuencia, compiten
con ventaja frente a los párrafos que efectivamente contienen la respuesta,
donde el término aparece una sola vez dentro de una exposición más extensa.

El presente módulo identifica estos fragmentos mediante rasgos estructurales y
los excluye de la indexación.
"""

import re

# Línea de índice: texto seguido de puntos de relleno o espacios y un número
# de página al final.
LINEA_INDICE = re.compile(r"^.{3,80}?[\s.]{2,}\d{1,4}\s*$")

# Número aislado entre espacios, residuo habitual de los índices una vez
# eliminados los puntos de relleno.
NUMERO_SUELTO = re.compile(r"(?:^|\s)\d{1,4}(?:\s|$)")

# Terminación de oración.
FIN_ORACION = re.compile(r"[.!?]\s")

# Formas verbales conjugadas frecuentes en español. Su presencia indica
# redacción expositiva; su ausencia, una enumeración de títulos.
VERBOS = re.compile(
    r"\b(?:es|son|est[áa]n?|ser[áa]|fue|hay|tiene|tienen|puede|pueden|"
    r"debe|deben|permite|permiten|se\s+\w+[ae]|consiste|define|"
    r"corresponde|representa|constituye|implica|requiere|incluye)\b",
    re.IGNORECASE,
)


def proporcion_lineas_indice(texto: str) -> float:
    """Calcula qué proporción de las líneas tienen forma de entrada de índice."""
    lineas = [l.strip() for l in texto.split("\n") if l.strip()]

    if not lineas:
        return 0.0

    coincidencias = sum(1 for linea in lineas if LINEA_INDICE.match(linea))
    return coincidencias / len(lineas)


def densidad_numerica(texto: str) -> float:
    """
    Calcula la proporción de tokens que son números sueltos.

    Un índice presenta una densidad numérica muy superior a la de un texto
    expositivo, dado que cada entrada termina en un número de página.
    """
    tokens = texto.split()

    if not tokens:
        return 0.0

    numeros = sum(1 for token in tokens if token.strip(".,;:()").isdigit())
    return numeros / len(tokens)


def densidad_verbal(texto: str) -> float:
    """
    Calcula la frecuencia de formas verbales por cada cien palabras.

    Un texto expositivo contiene verbos conjugados con regularidad. Una lista
    de títulos, en cambio, se compone mayoritariamente de sintagmas
    nominales.
    """
    palabras = len(texto.split())

    if palabras == 0:
        return 0.0

    return 100 * len(VERBOS.findall(texto)) / palabras


def densidad_oraciones(texto: str) -> float:
    """Calcula el número de terminaciones de oración por cada cien palabras."""
    palabras = len(texto.split())

    if palabras == 0:
        return 0.0

    return 100 * len(FIN_ORACION.findall(texto)) / palabras


def longitud_media_linea(texto: str) -> float:
    """
    Calcula la longitud media de las líneas del fragmento.

    Las entradas de un índice son breves; los párrafos de un texto
    expositivo, considerablemente más extensos.
    """
    lineas = [l.strip() for l in texto.split("\n") if l.strip()]

    if not lineas:
        return 0.0

    return sum(len(l) for l in lineas) / len(lineas)


def analizar_fragmento(texto: str) -> dict:
    """Calcula todos los indicadores estructurales de un fragmento."""
    return {
        "proporcion_indice": proporcion_lineas_indice(texto),
        "densidad_numerica": densidad_numerica(texto),
        "densidad_verbal": densidad_verbal(texto),
        "densidad_oraciones": densidad_oraciones(texto),
        "longitud_media_linea": longitud_media_linea(texto),
        "caracteres": len(texto),
    }


def es_navegacion(texto: str) -> tuple[bool, str]:
    """
    Determina si un fragmento corresponde a contenido de navegación.

    La decisión se basa en la combinación de varios indicadores, y no en uno
    solo: un párrafo legítimo puede presentar alta densidad numérica si trata
    de cifras, y un índice breve puede contener algún verbo. Exigir la
    concurrencia de varios rasgos reduce la probabilidad de descartar
    contenido válido.

    Returns:
        Par formado por la decisión y el motivo que la justifica.
    """
    indicadores = analizar_fragmento(texto)

    # Criterio 1: predominio de líneas con forma de entrada de índice.
    if indicadores["proporcion_indice"] >= 0.4:
        return True, "predominio de entradas de índice"

    # Criterio 2: alta densidad numérica junto a escasa redacción.
    if (indicadores["densidad_numerica"] >= 0.12
            and indicadores["densidad_verbal"] < 2.0):
        return True, "alta densidad numérica sin redacción expositiva"
    
    return False, ""


def filtrar_fragmentos(fragmentos: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Separa los fragmentos consultables de los de navegación.

    Args:
        fragmentos: fragmentos generados por el módulo de fragmentación.

    Returns:
        Par formado por los fragmentos conservados y los descartados. Estos
        últimos incorporan el campo 'motivo_descarte', lo que permite
        inspeccionar las decisiones del filtro y verificar que no se esté
        suprimiendo contenido legítimo.
    """
    conservados = []
    descartados = []

    for fragmento in fragmentos:
        descartar, motivo = es_navegacion(fragmento["texto"])

        if descartar:
            copia = dict(fragmento)
            copia["motivo_descarte"] = motivo
            descartados.append(copia)
        else:
            conservados.append(fragmento)

    return conservados, descartados
