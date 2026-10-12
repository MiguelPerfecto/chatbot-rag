"""
Verificación del filtrado de fragmentos de navegación.

Ejecutar desde la raíz del proyecto:
    python verificar_filtrado.py

Muestra qué fragmentos descartaría el filtro y por qué motivo, sin modificar
el índice. Permite comprobar que no se esté suprimiendo contenido legítimo
antes de aplicar el filtro a la indexación.
"""

import sys

from src.config import DOCUMENTOS_DIR
from src.ingesta.extractor_pdf import extraer_pdf
from src.ingesta.extractor_docx import extraer_docx
from src.procesamiento.limpieza import limpiar_documento
from src.procesamiento.fragmentacion import fragmentar_documento
from src.procesamiento.filtrado import filtrar_fragmentos, analizar_fragmento

SEP = "=" * 78


def main() -> None:
    rutas = sorted(
        list(DOCUMENTOS_DIR.glob("*.pdf")) + list(DOCUMENTOS_DIR.glob("*.docx"))
    )

    if not rutas:
        print(f"No se encontraron documentos en: {DOCUMENTOS_DIR}")
        sys.exit(1)

    print("\nFRAGMENTOS QUE SE DESCARTARÁN")
    print(SEP)

    total_conservados = 0
    total_descartados = 0
    todos_descartados = []

    for ruta in rutas:
        bloques = (
            extraer_pdf(ruta) if ruta.suffix.lower() == ".pdf"
            else extraer_docx(ruta)
        )

        if not bloques:
            continue

        limpios = limpiar_documento(bloques)
        fragmentos = fragmentar_documento(limpios)
        conservados, descartados = filtrar_fragmentos(fragmentos)

        total_conservados += len(conservados)
        total_descartados += len(descartados)
        todos_descartados.extend(descartados)

        marca = f"  descarta {len(descartados)}" if descartados else ""
        print(f"\n{ruta.name}")
        print(f"  Fragmentos: {len(fragmentos)} → conserva {len(conservados)}{marca}")

    print("\n" + SEP)
    print(f"TOTAL: {total_conservados} conservados, {total_descartados} descartados")
    print(SEP)

    if not todos_descartados:
        print("\nNo se descartó ningún fragmento.")
        return

    print("\nDETALLE DE LOS FRAGMENTOS DESCARTADOS")
    print(SEP)
    print("\nRevise cada uno: si alguno contiene información consultable,")
    print("el filtro requiere ajuste.\n")

    for numero, fragmento in enumerate(todos_descartados, start=1):
        indicadores = analizar_fragmento(fragmento["texto"])

        print("-" * 78)
        print(f"{numero}. {fragmento['documento']} — {fragmento['referencia']}")
        print(f"   Motivo: {fragmento['motivo_descarte']}")
        print(f"   Entradas de índice: {indicadores['proporcion_indice']:.0%} | "
              f"Números: {indicadores['densidad_numerica']:.0%} | "
              f"Verbos/100p: {indicadores['densidad_verbal']:.1f}")
        print()

        texto = fragmento["texto"][:300]
        for linea in texto.split("\n"):
            print(f"   {linea}")
        if len(fragmento["texto"]) > 300:
            print("   ...")
        print()


if __name__ == "__main__":
    main()
