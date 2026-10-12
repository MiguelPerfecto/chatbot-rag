"""
Limpieza y normalización del texto extraído.

El texto que se obtiene de un documento PDF conserva los artefactos propios
del formato: las líneas se cortan según el ancho de composición y no según
unidades de sentido, las viñetas quedan separadas del texto que introducen, y
los encabezados y pies se repiten en cada página.

Estos artefactos no impiden el funcionamiento del sistema, pero degradan la
calidad de las representaciones vectoriales: un fragmento con cortes
arbitrarios se vectoriza peor que uno con párrafos completos. Este módulo
normaliza el contenido antes de fragmentarlo.
"""

import re
import unicodedata
from collections import Counter

# Caracteres empleados como viñeta en documentos de uso corriente.
VINETAS = r"[•●○◦▪▫–—\-\*\+]"

# El guion suave (U+00AD) marca los puntos donde el maquetador puede separar
# una palabra. Es invisible al leer pero aparece en la extracción, partiendo
# palabras como "pro-ceso" o "estable-cerse". Debe eliminarse junto con el
# espacio o salto de línea que lo acompaña.
GUION_SUAVE = re.compile(r"\u00ad\s*")

# Un guion ordinario al final de línea suele indicar separación silábica.
GUION_FINAL = re.compile(r"(\w)-\n(\w)")

# Fin de párrafo: la línea termina en signo de puntuación de cierre.
FIN_PARRAFO = re.compile(r"[.:;!?»\"']\s*$")

# Número de página aislado en su propia línea.
NUMERO_PAGINA = re.compile(r"^\s*\d{1,4}\s*$")

# Número de página pegado al texto, precedido de punto y seguido de mayúscula
# o de un elemento de navegación. Patrón frecuente en PDF maquetados.
NUMERO_INCRUSTADO = re.compile(r"(?<=[.\s])\d{1,3}\s+(?=[A-ZÁÉÍÓÚÑ]{4,})")

# Secuencia de puntos de relleno, propia de los índices de contenido.
PUNTOS_INDICE = re.compile(r"\.{4,}")


def normalizar_unicode(texto: str) -> str:
    """
    Unifica la representación de los caracteres equivalentes.

    Un mismo carácter puede codificarse de varias formas en Unicode. Sin esta
    normalización, dos textos visualmente idénticos podrían producir
    representaciones vectoriales distintas.
    """
    texto = unicodedata.normalize("NFC", texto)

    reemplazos = {
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u00a0": " ", "\u2013": "-", "\u2014": "-", "\u2026": "...",
        "\u200b": "",   # espacio de ancho cero
        "\u200c": "",   # no-unión de ancho cero
        "\ufeff": "",   # marca de orden de bytes
    }
    for original, reemplazo in reemplazos.items():
        texto = texto.replace(original, reemplazo)

    return texto


def eliminar_guiones_suaves(texto: str) -> str:
    """
    Suprime los guiones suaves y reconstruye las palabras afectadas.

    Debe ejecutarse antes que cualquier otra operación sobre el texto: si se
    reconstruyen los párrafos primero, los guiones suaves quedan incorporados
    al interior de las líneas y las palabras permanecen partidas.
    """
    return GUION_SUAVE.sub("", texto)


def unir_palabras_cortadas(texto: str) -> str:
    """Reconstruye las palabras separadas por guion al final de línea."""
    return GUION_FINAL.sub(r"\1\2", texto)


def eliminar_numeros_pagina(texto: str) -> str:
    """
    Suprime los números de página.

    Se tratan dos casos: el número aislado en su propia línea, y el número
    incrustado en el flujo del texto antes de un elemento en mayúsculas, que
    corresponde típicamente a la secuencia «número de página + encabezado».
    """
    lineas = [
        linea for linea in texto.split("\n")
        if not NUMERO_PAGINA.match(linea)
    ]
    texto = "\n".join(lineas)

    return NUMERO_INCRUSTADO.sub("", texto)


def limpiar_indices(texto: str) -> str:
    """Elimina las secuencias de puntos de relleno propias de los índices."""
    return PUNTOS_INDICE.sub(" ", texto)


def reconstruir_parrafos(texto: str) -> str:
    """
    Une las líneas que pertenecen a un mismo párrafo.

    Criterio: una línea continúa en la siguiente salvo que termine en signo
    de puntuación de cierre, que la siguiente comience con viñeta, o que
    exista una línea en blanco entre ambas.
    """
    lineas = texto.split("\n")
    resultado = []
    acumulado = ""

    for linea in lineas:
        actual = linea.strip()

        if not actual:
            if acumulado:
                resultado.append(acumulado)
                acumulado = ""
            continue

        if re.match(rf"^{VINETAS}\s*", actual):
            if acumulado:
                resultado.append(acumulado)
            acumulado = actual
            continue

        if not acumulado:
            acumulado = actual
        elif FIN_PARRAFO.search(acumulado):
            resultado.append(acumulado)
            acumulado = actual
        else:
            acumulado += " " + actual

    if acumulado:
        resultado.append(acumulado)

    return "\n".join(resultado)


def unir_vinetas_huerfanas(texto: str) -> str:
    """
    Une los símbolos de viñeta con el texto que introducen.

    En los PDF el símbolo y su contenido ocupan posiciones horizontales
    distintas, por lo que la extracción los devuelve con frecuencia en
    líneas separadas.
    """
    lineas = texto.split("\n")
    resultado = []
    i = 0

    while i < len(lineas):
        actual = lineas[i].strip()

        if re.fullmatch(rf"{VINETAS}", actual) and i + 1 < len(lineas):
            siguiente = lineas[i + 1].strip()
            if siguiente:
                resultado.append(f"{actual} {siguiente}")
                i += 2
                continue

        resultado.append(actual)
        i += 1

    return "\n".join(resultado)


def detectar_fragmentos_navegacion(bloques: list[dict], umbral: float = 0.4) -> list[str]:
    """
    Identifica los elementos de navegación recurrentes del documento.

    A diferencia de los encabezados y pies, que ocupan la primera o la última
    línea de la página, estos elementos pueden aparecer en cualquier posición
    del texto extraído, dado que su ubicación en el PDF no se corresponde
    necesariamente con el orden de lectura. Los marcadores de navegación de
    los documentos maquetados profesionalmente son un caso característico.

    El procedimiento identifica secuencias breves de palabras en mayúsculas
    que se repiten en una proporción elevada de las páginas.

    Args:
        bloques: bloques extraídos de un mismo documento.
        umbral: proporción mínima de páginas en que debe aparecer la
            secuencia para considerarla elemento de navegación.

    Returns:
        Lista de secuencias a eliminar, ordenadas de mayor a menor longitud
        para que la sustitución comience por las más específicas.
    """
    if len(bloques) < 5:
        return []

    patron = re.compile(r"\b(?:[A-ZÁÉÍÓÚÑ]{3,}\s+){1,3}[A-ZÁÉÍÓÚÑ]{3,}\b")
    contador = Counter()

    for bloque in bloques:
        encontradas = set(patron.findall(bloque["texto"]))
        for secuencia in encontradas:
            contador[secuencia.strip()] += 1

    minimo = max(3, int(len(bloques) * umbral))

    candidatas = [
        secuencia for secuencia, veces in contador.items()
        if veces >= minimo
    ]

    return sorted(candidatas, key=len, reverse=True)


def detectar_lineas_repetidas(bloques: list[dict], umbral: float = 0.5) -> set[str]:
    """
    Identifica encabezados y pies de página.

    Estos elementos se repiten en la mayoría de las páginas y carecen de valor
    informativo, pero contaminan los fragmentos y pueden provocar
    recuperaciones erróneas.
    """
    if len(bloques) < 4:
        return set()

    contador = Counter()

    for bloque in bloques:
        lineas = [l.strip() for l in bloque["texto"].split("\n") if l.strip()]
        candidatas = lineas[:2] + lineas[-2:]

        for linea in set(candidatas):
            if 3 < len(linea) < 100:
                contador[linea] += 1

    minimo = max(3, int(len(bloques) * umbral))
    return {linea for linea, veces in contador.items() if veces >= minimo}


def eliminar_lineas(texto: str, lineas_eliminar: set[str]) -> str:
    """Suprime del texto las líneas identificadas como repetidas."""
    if not lineas_eliminar:
        return texto

    conservadas = [
        linea for linea in texto.split("\n")
        if linea.strip() not in lineas_eliminar
    ]
    return "\n".join(conservadas)


def eliminar_secuencias(texto: str, secuencias: list[str]) -> str:
    """Suprime del texto las secuencias de navegación identificadas."""
    for secuencia in secuencias:
        texto = texto.replace(secuencia, " ")
    return texto


def normalizar_espacios(texto: str) -> str:
    """Unifica espacios múltiples y elimina líneas en blanco consecutivas."""
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    texto = re.sub(r" +\n", "\n", texto)
    return texto.strip()


def limpiar_texto(
    texto: str,
    lineas_eliminar: set[str] | None = None,
    secuencias_eliminar: list[str] | None = None,
) -> str:
    """
    Aplica la secuencia completa de limpieza a un bloque de texto.

    El orden de las operaciones es relevante. Los guiones suaves se eliminan
    en primer lugar, antes de que la reconstrucción de párrafos los incorpore
    al interior de las líneas. Las viñetas se reunifican antes de dicha
    reconstrucción, que de otro modo las interpretaría incorrectamente.
    """
    texto = normalizar_unicode(texto)
    texto = eliminar_guiones_suaves(texto)
    texto = unir_palabras_cortadas(texto)
    texto = limpiar_indices(texto)

    if lineas_eliminar:
        texto = eliminar_lineas(texto, lineas_eliminar)

    if secuencias_eliminar:
        texto = eliminar_secuencias(texto, secuencias_eliminar)

    texto = eliminar_numeros_pagina(texto)
    texto = unir_vinetas_huerfanas(texto)
    texto = reconstruir_parrafos(texto)
    texto = normalizar_espacios(texto)

    return texto


def limpiar_documento(bloques: list[dict]) -> list[dict]:
    """
    Limpia todos los bloques de un mismo documento.

    La detección de encabezados y de elementos de navegación requiere analizar
    el documento completo, por lo que se ejecuta antes de limpiar cada bloque
    por separado.

    Args:
        bloques: lista de bloques extraídos de un documento, en el formato
            que producen los extractores del módulo de ingesta.

    Returns:
        La misma lista con el texto limpio. Los bloques que quedan vacíos
        tras la limpieza se descartan.
    """
    lineas_repetidas = detectar_lineas_repetidas(bloques)
    secuencias_navegacion = detectar_fragmentos_navegacion(bloques)

    limpios = []

    for bloque in bloques:
        texto = limpiar_texto(
            bloque["texto"],
            lineas_repetidas,
            secuencias_navegacion,
        )

        if not texto.strip():
            continue

        nuevo = dict(bloque)
        nuevo["texto"] = texto
        limpios.append(nuevo)

    return limpios


def diagnosticar_limpieza(bloques: list[dict]) -> dict:
    """
    Informa de los elementos que la limpieza identificará como eliminables.

    Permite verificar que la detección no esté suprimiendo contenido legítimo
    antes de aplicarla sobre el corpus completo.
    """
    return {
        "lineas_repetidas": sorted(detectar_lineas_repetidas(bloques)),
        "secuencias_navegacion": detectar_fragmentos_navegacion(bloques),
    }
