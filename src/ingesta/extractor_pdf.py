"""
Extracción de texto desde archivos PDF.

Se utiliza PyMuPDF en lugar de otras librerías porque conserva el número de
página de cada bloque de texto extraído. Esa información es la que permite,
más adelante, indicar al usuario de qué documento y de qué página proviene
cada respuesta generada por el sistema.
"""

from pathlib import Path

import pymupdf


def extraer_pdf(ruta: Path) -> list[dict]:
    """
    Extrae el texto de un archivo PDF, página por página.

    Args:
        ruta: ruta al archivo PDF.

    Returns:
        Lista de diccionarios, uno por página con contenido. Cada uno incluye
        el texto y los metadatos necesarios para rastrear su origen:
            {
                "texto": str,
                "documento": str,   # nombre del archivo
                "pagina": int,      # número de página, empezando en 1
                "formato": "pdf",
            }

    Raises:
        FileNotFoundError: si la ruta no existe.
        ValueError: si el archivo no puede abrirse como PDF.
    """
    ruta = Path(ruta)

    if not ruta.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {ruta}")

    try:
        documento = pymupdf.open(ruta)
    except Exception as error:
        raise ValueError(f"No se pudo abrir '{ruta.name}' como PDF: {error}")

    paginas = []

    with documento:
        for numero, pagina in enumerate(documento, start=1):
            texto = pagina.get_text("text")

            # Una página sin texto extraíble suele ser una imagen escaneada.
            # Se omite: el sistema no contempla OCR (ver alcance del proyecto).
            if not texto.strip():
                continue

            paginas.append({
                "texto": texto,
                "documento": ruta.name,
                "pagina": numero,
                "formato": "pdf",
            })

    return paginas


def diagnosticar_pdf(ruta: Path) -> dict:
    """
    Revisa un PDF sin extraer todo su contenido.

    Sirve para detectar documentos problemáticos antes de procesarlos: PDFs
    escaneados sin capa de texto, o archivos donde la extracción rendiría
    muy poco. Los hallazgos alimentan la sección 4.5 del documento escrito.

    Returns:
        Diccionario con el nombre del archivo, total de páginas, cuántas
        tienen texto extraíble y el promedio de caracteres por página.
    """
    ruta = Path(ruta)

    with pymupdf.open(ruta) as documento:
        total_paginas = len(documento)
        paginas_con_texto = 0
        total_caracteres = 0

        for pagina in documento:
            texto = pagina.get_text("text").strip()
            if texto:
                paginas_con_texto += 1
                total_caracteres += len(texto)

    promedio = total_caracteres / paginas_con_texto if paginas_con_texto else 0

    return {
        "documento": ruta.name,
        "total_paginas": total_paginas,
        "paginas_con_texto": paginas_con_texto,
        "paginas_sin_texto": total_paginas - paginas_con_texto,
        "caracteres_totales": total_caracteres,
        "promedio_caracteres_por_pagina": round(promedio, 1),
    }
