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

# Un guion al final de línea suele indicar una palabra cortada por
# separación silábica, no un guion real del texto.
GUION_FINAL = re.compile(r"(\w)-\n(\w)")

# Fin de párrafo: la línea termina en signo de puntuación de cierre.
FIN_PARRAFO = re.compile(r"[.:;!?»\"']\s*$")


def normalizar_unicode(texto: str) -> str:
    """
    Unifica la representación de los caracteres acentuados.

    Un mismo carácter puede codificarse de varias formas equivalentes en
    Unicode. Sin esta normalización, dos textos visualmente idénticos podrían
    producir representaciones vectoriales distintas.
    """
    texto = unicodedata.normalize("NFC", texto)

    # Comillas y guiones tipográficos se reemplazan por sus equivalentes
    # simples para reducir la variabilidad del texto.
    reemplazos = {
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u00a0": " ", "\u2013": "-", "\u2014": "-", "\u2026": "...",
        "\u200b": "",
    }
    for original, reemplazo in reemplazos.items():
        texto = texto.replace(original, reemplazo)

    return texto


def unir_palabras_cortadas(texto: str) -> str:
    """Reconstruye las palabras separadas por guion al final de línea."""
    return GUION_FINAL.sub(r"\1\2", texto)


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

        # Línea en blanco: cierra el párrafo en curso.
        if not actual:
            if acumulado:
                resultado.append(acumulado)
                acumulado = ""
            continue

        # Una viñeta inicia siempre un elemento nuevo.
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

    En los PDF el símbolo de viñeta y su contenido ocupan posiciones
    horizontales distintas, por lo que la extracción los devuelve con
    frecuencia en líneas separadas.
    """
    lineas = texto.split("\n")
    resultado = []
    i = 0

    while i < len(lineas):
        actual = lineas[i].strip()

        # Línea que contiene únicamente un símbolo de viñeta.
        if re.fullmatch(rf"{VINETAS}", actual) and i + 1 < len(lineas):
            siguiente = lineas[i + 1].strip()
            if siguiente:
                resultado.append(f"{actual} {siguiente}")
                i += 2
                continue

        resultado.append(actual)
        i += 1

    return "\n".join(resultado)


def detectar_lineas_repetidas(bloques: list[dict], umbral: float = 0.5) -> set[str]:
    """
    Identifica encabezados y pies de página.

    Estos elementos se repiten en la mayoría de las páginas de un documento y
    carecen de valor informativo, pero contaminan los fragmentos y pueden
    provocar recuperaciones erróneas.

    Args:
        bloques: bloques extraídos de un mismo documento.
        umbral: proporción mínima de páginas en que debe aparecer una línea
            para considerarla repetida.

    Returns:
        Conjunto de líneas a eliminar.
    """
    if len(bloques) < 4:
        # En documentos muy cortos no hay evidencia suficiente para
        # distinguir un encabezado de contenido legítimo.
        return set()

    contador = Counter()

    for bloque in bloques:
        # Se consideran solo las primeras y últimas líneas de cada página,
        # que es donde aparecen encabezados y pies.
        lineas = [l.strip() for l in bloque["texto"].split("\n") if l.strip()]
        candidatas = lineas[:2] + lineas[-2:]

        for linea in set(candidatas):
            # Las líneas largas rara vez son encabezados.
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


def normalizar_espacios(texto: str) -> str:
    """Unifica espacios múltiples y elimina líneas en blanco consecutivas."""
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def limpiar_texto(texto: str, lineas_eliminar: set[str] | None = None) -> str:
    """
    Aplica la secuencia completa de limpieza a un bloque de texto.

    El orden de las operaciones es relevante: las palabras cortadas se unen
    antes de reconstruir los párrafos, y las viñetas se reunifican antes de
    que la reconstrucción de párrafos pueda interpretarlas incorrectamente.
    """
    texto = normalizar_unicode(texto)
    texto = unir_palabras_cortadas(texto)

    if lineas_eliminar:
        texto = eliminar_lineas(texto, lineas_eliminar)

    texto = unir_vinetas_huerfanas(texto)
    texto = reconstruir_parrafos(texto)
    texto = normalizar_espacios(texto)

    return texto


def limpiar_documento(bloques: list[dict]) -> list[dict]:
    """
    Limpia todos los bloques de un mismo documento.

    La detección de encabezados repetidos requiere analizar el documento
    completo, por lo que se ejecuta antes de limpiar cada bloque por separado.

    Args:
        bloques: lista de bloques extraídos de un documento, en el formato
            que producen los extractores del módulo de ingesta.

    Returns:
        La misma lista con el texto limpio. Los bloques que quedan vacíos
        tras la limpieza se descartan.
    """
    lineas_repetidas = detectar_lineas_repetidas(bloques)

    limpios = []

    for bloque in bloques:
        texto = limpiar_texto(bloque["texto"], lineas_repetidas)

        if not texto.strip():
            continue

        nuevo = dict(bloque)
        nuevo["texto"] = texto
        limpios.append(nuevo)

    return limpios
