"""
Consulta interactiva del índice documental.

Ejecutar desde la raíz del proyecto:
    python consultar.py

Permite formular preguntas y observar qué fragmentos recupera el sistema, con
sus similitudes y su procedencia. No interviene aún ningún modelo de lenguaje:
se evalúa exclusivamente el componente de recuperación.

Comandos disponibles durante la sesión:
    :k <n>        cambia el número de fragmentos recuperados
    :umbral <n>   cambia el umbral de relevancia
    :todo         muestra el texto completo de los fragmentos
    :corto        muestra solo un extracto (por defecto)
    :corpus       muestra los documentos indexados
    :salir        termina la sesión
"""

import sys

from src.config import TOP_K, UMBRAL_RELEVANCIA
from src.recuperacion.buscador import Buscador

SEP = "=" * 78


def mostrar_bienvenida(buscador: Buscador, k: int, umbral: float) -> None:
    resumen = buscador.resumen_corpus()

    print("\n" + SEP)
    print("CONSULTA DEL ÍNDICE DOCUMENTAL")
    print(SEP)
    print(f"Fragmentos indexados : {resumen['total_fragmentos']}")
    print(f"Documentos           : {resumen['total_documentos']}")
    print(f"Fragmentos por consulta (k) : {k}")
    print(f"Umbral de relevancia        : {umbral}")
    print("\nEscriba una pregunta, o :salir para terminar.")
    print("Otros comandos: :k <n>, :umbral <n>, :todo, :corto, :corpus")
    print(SEP)


def mostrar_corpus(buscador: Buscador) -> None:
    resumen = buscador.resumen_corpus()
    print(f"\nDocumentos indexados ({resumen['total_documentos']}):")
    for nombre in resumen["documentos"]:
        print(f"  - {nombre}")


def mostrar_resultados(busqueda: dict, completo: bool) -> None:
    print()

    if not busqueda["hay_evidencia"]:
        print("SIN EVIDENCIA SUFICIENTE EN EL CORPUS")
        print(f"Similitud más alta obtenida: {busqueda['similitud_maxima']:.4f}")
        print("(ningún fragmento alcanzó el umbral de relevancia)")
        return

    print(f"Fragmentos relevantes: {busqueda['total_relevantes']} "
          f"de {busqueda['total_recuperados']} recuperados")
    print("-" * 78)

    for posicion, resultado in enumerate(busqueda["resultados"], start=1):
        print(f"\n{posicion}. [similitud {resultado['similitud']:.4f}]")
        print(f"   {resultado['documento']} — {resultado['referencia']}")
        print()

        texto = resultado["texto"]
        if not completo and len(texto) > 350:
            texto = texto[:350] + "..."

        # Indenta el texto para distinguirlo de los metadatos.
        for linea in texto.split("\n"):
            print(f"   {linea}")

    tiempo_total = busqueda["tiempo_embedding"] + busqueda["tiempo_busqueda"]
    print("\n" + "-" * 78)
    print(f"Tiempo: {1000 * tiempo_total:.1f} ms "
          f"(vectorización {1000 * busqueda['tiempo_embedding']:.1f} ms, "
          f"búsqueda {1000 * busqueda['tiempo_busqueda']:.1f} ms)")


def main() -> None:
    try:
        buscador = Buscador()
    except FileNotFoundError as error:
        print(f"\n{error}")
        sys.exit(1)

    k = TOP_K
    umbral = UMBRAL_RELEVANCIA
    completo = False

    mostrar_bienvenida(buscador, k, umbral)

    while True:
        try:
            entrada = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSesión terminada.")
            break

        if not entrada:
            continue

        # --- comandos ---
        if entrada.lower() in (":salir", ":q", "salir"):
            print("Sesión terminada.")
            break

        if entrada.lower() == ":corpus":
            mostrar_corpus(buscador)
            continue

        if entrada.lower() == ":todo":
            completo = True
            print("Se mostrará el texto completo de los fragmentos.")
            continue

        if entrada.lower() == ":corto":
            completo = False
            print("Se mostrará solo un extracto de los fragmentos.")
            continue

        if entrada.lower().startswith(":k "):
            try:
                k = int(entrada.split()[1])
                print(f"Fragmentos por consulta: {k}")
            except (IndexError, ValueError):
                print("Uso: :k <número>")
            continue

        if entrada.lower().startswith(":umbral "):
            try:
                umbral = float(entrada.split()[1])
                print(f"Umbral de relevancia: {umbral}")
            except (IndexError, ValueError):
                print("Uso: :umbral <número decimal>")
            continue

        # --- consulta ---
        busqueda = buscador.buscar(entrada, k=k, umbral=umbral)
        mostrar_resultados(busqueda, completo)


if __name__ == "__main__":
    main()
