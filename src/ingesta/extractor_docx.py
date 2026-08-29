"""
Extracción de texto desde archivos Word (.docx).

A diferencia del PDF, un documento .docx no tiene páginas: la paginación la
calcula Word al momento de mostrarlo, según la fuente, los márgenes y la
impresora. El formato almacena una secuencia continua de párrafos y tablas.

Por eso aquí la unidad de referencia no es la página sino la sección,
delimitada por los títulos del documento. Al usuario se le indicará entonces
el documento y el apartado del que proviene la respuesta, que en la práctica
resulta una referencia más útil que un número de página.
"""

from pathlib import Path

import docx
from docx.document import Document as TipoDocumento
from docx.table import Table
from docx.text.paragraph import Paragraph


def _es_titulo(parrafo: Paragraph) -> bool:
    """Determina si un párrafo funciona como título de sección."""
    nombre_estilo = (parrafo.style.name or "").lower()
    return nombre_estilo.startswith(("heading", "título", "titulo"))


def _tabla_a_texto(tabla: Table) -> str:
    """
    Convierte una tabla en texto plano legible.

    Las celdas de cada fila se separan con barras verticales para preservar
    la estructura tabular. Sin esto, el contenido de las tablas se perdería
    o quedaría como una secuencia de palabras sin relación aparente.
    """
    filas = []

    for fila in tabla.rows:
        celdas = [celda.text.strip() for celda in fila.cells]
        if any(celdas):
            filas.append(" | ".join(celdas))

    return "\n".join(filas)


def _recorrer_bloques(documento: TipoDocumento):
    """
    Recorre párrafos y tablas en el orden real en que aparecen.

    python-docx expone las listas de párrafos y de tablas por separado, lo
    que hace perder el orden original del documento. Para conservarlo se
    recorre directamente el árbol XML del cuerpo.
    """
    from docx.oxml.ns import qn

    cuerpo = documento.element.body

    for elemento in cuerpo.iterchildren():
        if elemento.tag == qn("w:p"):
            yield Paragraph(elemento, documento)
        elif elemento.tag == qn("w:tbl"):
            yield Table(elemento, documento)


def extraer_docx(ruta: Path) -> list[dict]:
    """
    Extrae el texto de un archivo Word, agrupado por secciones.

    Args:
        ruta: ruta al archivo .docx.

    Returns:
        Lista de diccionarios, uno por sección detectada:
            {
                "texto": str,
                "documento": str,   # nombre del archivo
                "seccion": str,     # título de la sección
                "formato": "docx",
            }

    Raises:
        FileNotFoundError: si la ruta no existe.
        ValueError: si el archivo no puede abrirse como documento Word.
    """
    ruta = Path(ruta)

    if not ruta.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {ruta}")

    try:
        documento = docx.Document(str(ruta))
    except Exception as error:
        raise ValueError(f"No se pudo abrir '{ruta.name}' como documento Word: {error}")

    secciones = []
    titulo_actual = "Inicio del documento"
    contenido_actual = []

    def cerrar_seccion() -> None:
        """Guarda la sección acumulada si tiene contenido."""
        texto = "\n".join(contenido_actual).strip()
        if texto:
            secciones.append({
                "texto": texto,
                "documento": ruta.name,
                "seccion": titulo_actual,
                "formato": "docx",
            })

    for bloque in _recorrer_bloques(documento):
        if isinstance(bloque, Table):
            texto_tabla = _tabla_a_texto(bloque)
            if texto_tabla:
                contenido_actual.append(texto_tabla)
            continue

        texto = bloque.text.strip()
        if not texto:
            continue

        if _es_titulo(bloque):
            # Un título cierra la sección anterior e inicia una nueva.
            cerrar_seccion()
            titulo_actual = texto
            contenido_actual = []
        else:
            contenido_actual.append(texto)

    cerrar_seccion()

    return secciones


def diagnosticar_docx(ruta: Path) -> dict:
    """
    Revisa un documento Word sin procesar todo su contenido.

    Returns:
        Diccionario con el nombre del archivo, número de secciones detectadas,
        total de caracteres y promedio por sección.
    """
    secciones = extraer_docx(ruta)

    total_caracteres = sum(len(s["texto"]) for s in secciones)
    promedio = total_caracteres / len(secciones) if secciones else 0

    return {
        "documento": Path(ruta).name,
        "secciones": len(secciones),
        "caracteres_totales": total_caracteres,
        "promedio_caracteres_por_seccion": round(promedio, 1),
        "titulos": [s["seccion"] for s in secciones],
    }
