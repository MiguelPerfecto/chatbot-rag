"""
Fragmentación del contenido documental.

Divide el texto limpio en unidades de tamaño acotado que constituyen la unidad
mínima de recuperación del sistema.

Dos decisiones de diseño rigen este módulo:

1. Un fragmento puede abarcar varias páginas de un mismo documento, pero nunca
   dos documentos distintos. Cuando abarca varias páginas se registra el rango
   completo (por ejemplo, "páginas 4-6"), de modo que la referencia mostrada al
   usuario sigue siendo veraz. La alternativa de fragmentar dentro de cada
   página se descartó porque en documentos de baja densidad textual, como las
   presentaciones exportadas a PDF, produciría fragmentos sin contexto
   suficiente.

2. La división se realiza en cascada, respetando la estructura del texto en la
   medida de lo posible: primero se intenta cortar en límites de párrafo, luego
   en límites de oración, y solo como último recurso por número de caracteres.
   Este mecanismo permite manejar tanto documentos bien estructurados como
   aquellos que carecen de estructura recuperable.
"""

import re

from src.config import (
    TAMANO_FRAGMENTO,
    SOLAPAMIENTO,
    MINIMO_CARACTERES_FRAGMENTO,
)

# Fin de oración: signo de puntuación seguido de espacio y mayúscula.
FIN_ORACION = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿¡])")


def dividir_en_parrafos(texto: str) -> list[str]:
    """Separa el texto en párrafos, descartando los vacíos."""
    return [p.strip() for p in texto.split("\n") if p.strip()]


def dividir_en_oraciones(texto: str) -> list[str]:
    """Separa un párrafo en oraciones."""
    return [o.strip() for o in FIN_ORACION.split(texto) if o.strip()]


def dividir_por_caracteres(texto: str, tamano: int) -> list[str]:
    """
    Divide por número de caracteres, respetando límites de palabra.

    Último recurso, aplicable cuando una sola oración excede el tamaño
    máximo de fragmento.
    """
    partes = []
    inicio = 0

    while inicio < len(texto):
        fin = min(inicio + tamano, len(texto))

        # Retrocede hasta el espacio más próximo para no partir una palabra.
        if fin < len(texto):
            espacio = texto.rfind(" ", inicio, fin)
            if espacio > inicio:
                fin = espacio

        parte = texto[inicio:fin].strip()
        if parte:
            partes.append(parte)

        inicio = fin

    return partes


def dividir_texto(texto: str, tamano: int) -> list[str]:
    """
    Divide un texto aplicando el mecanismo en cascada.

    Se agrupan párrafos consecutivos mientras el resultado no exceda el
    tamaño máximo. Los párrafos que por sí solos lo exceden se subdividen en
    oraciones, y las oraciones excesivamente largas, por caracteres.
    """
    unidades = []

    for parrafo in dividir_en_parrafos(texto):
        if len(parrafo) <= tamano:
            unidades.append(parrafo)
            continue

        # El párrafo excede el tamaño: se divide en oraciones.
        for oracion in dividir_en_oraciones(parrafo):
            if len(oracion) <= tamano:
                unidades.append(oracion)
            else:
                unidades.extend(dividir_por_caracteres(oracion, tamano))

    # Agrupa las unidades en fragmentos del tamaño objetivo.
    fragmentos = []
    actual = []
    longitud = 0

    for unidad in unidades:
        if longitud + len(unidad) > tamano and actual:
            fragmentos.append(" ".join(actual))
            actual = []
            longitud = 0

        actual.append(unidad)
        longitud += len(unidad) + 1

    if actual:
        fragmentos.append(" ".join(actual))

    return fragmentos


def aplicar_solapamiento(fragmentos: list[str], solapamiento: int) -> list[str]:
    """
    Añade a cada fragmento el final del anterior.

    Reduce la probabilidad de que una idea quede seccionada de forma que
    ningún fragmento la contenga íntegramente.
    """
    if solapamiento <= 0 or len(fragmentos) < 2:
        return fragmentos

    resultado = [fragmentos[0]]

    for i in range(1, len(fragmentos)):
        anterior = fragmentos[i - 1]
        cola = anterior[-solapamiento:]

        # Recorta la cola hasta el inicio de palabra más próximo.
        espacio = cola.find(" ")
        if espacio > 0:
            cola = cola[espacio + 1:]

        resultado.append(f"{cola} {fragmentos[i]}")

    return resultado


def _referencia(bloques: list[dict]) -> dict:
    """
    Construye la referencia de origen a partir de los bloques agrupados.

    Para documentos PDF devuelve el rango de páginas cubierto; para
    documentos Word, la sección o secciones de procedencia.
    """
    formato = bloques[0]["formato"]

    if formato == "pdf":
        paginas = sorted({b["pagina"] for b in bloques})
        return {
            "pagina_inicio": paginas[0],
            "pagina_fin": paginas[-1],
            "referencia": (
                f"página {paginas[0]}" if len(paginas) == 1
                else f"páginas {paginas[0]}-{paginas[-1]}"
            ),
        }

    secciones = []
    for bloque in bloques:
        if bloque["seccion"] not in secciones:
            secciones.append(bloque["seccion"])

    return {
        "seccion": secciones[0],
        "referencia": (
            f"sección «{secciones[0]}»" if len(secciones) == 1
            else f"secciones «{secciones[0]}» a «{secciones[-1]}»"
        ),
    }


def fragmentar_documento(
    bloques: list[dict],
    tamano: int = TAMANO_FRAGMENTO,
    solapamiento: int = SOLAPAMIENTO,
) -> list[dict]:
    """
    Fragmenta los bloques de un documento conservando su procedencia.

    Los bloques se procesan de forma acumulativa: se van uniendo hasta
    alcanzar el tamaño objetivo, momento en que se cierra un fragmento y se
    registra el rango de páginas o secciones que abarca.

    Args:
        bloques: bloques limpios de un mismo documento.
        tamano: tamaño objetivo en caracteres.
        solapamiento: caracteres compartidos entre fragmentos consecutivos.

    Returns:
        Lista de fragmentos, cada uno con su texto y sus metadatos de origen.
    """
    if not bloques:
        return []

    nombre_documento = bloques[0]["documento"]
    fragmentos = []

    # Bloques acumulados que aún no han formado un fragmento.
    acumulados = []
    texto_acumulado = ""

    def cerrar() -> None:
        """Convierte los bloques acumulados en uno o más fragmentos."""
        if not texto_acumulado.strip() or not acumulados:
            return

        referencia = _referencia(acumulados)

        for texto in dividir_texto(texto_acumulado, tamano):
            if len(texto) < MINIMO_CARACTERES_FRAGMENTO:
                continue

            fragmento = {
                "texto": texto,
                "documento": nombre_documento,
                "formato": acumulados[0]["formato"],
            }
            fragmento.update(referencia)
            fragmentos.append(fragmento)

    for bloque in bloques:
        acumulados.append(bloque)
        texto_acumulado = (
            f"{texto_acumulado}\n{bloque['texto']}" if texto_acumulado
            else bloque["texto"]
        )

        if len(texto_acumulado) >= tamano:
            cerrar()
            acumulados = []
            texto_acumulado = ""

    cerrar()

    # El solapamiento se aplica al final, sobre los textos ya formados.
    if solapamiento > 0 and len(fragmentos) > 1:
        textos = aplicar_solapamiento([f["texto"] for f in fragmentos], solapamiento)
        for fragmento, texto in zip(fragmentos, textos):
            fragmento["texto"] = texto

    # Identificador secuencial dentro del documento.
    for indice, fragmento in enumerate(fragmentos):
        fragmento["id"] = f"{nombre_documento}::{indice}"

    return fragmentos


def estadisticas(fragmentos: list[dict]) -> dict:
    """Calcula métricas descriptivas de un conjunto de fragmentos."""
    if not fragmentos:
        return {
            "total": 0, "longitud_media": 0,
            "longitud_minima": 0, "longitud_maxima": 0,
            "multipagina": 0,
        }

    longitudes = [len(f["texto"]) for f in fragmentos]

    multipagina = sum(
        1 for f in fragmentos
        if f.get("pagina_fin") is not None
        and f.get("pagina_inicio") is not None
        and f["pagina_fin"] > f["pagina_inicio"]
    )

    return {
        "total": len(fragmentos),
        "longitud_media": round(sum(longitudes) / len(longitudes), 1),
        "longitud_minima": min(longitudes),
        "longitud_maxima": max(longitudes),
        "multipagina": multipagina,
    }
