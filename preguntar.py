"""
Consulta del sistema con generación de respuestas.

Ejecutar desde la raíz del proyecto:
    python preguntar.py

Formula preguntas en lenguaje natural y obtén respuestas fundamentadas en los
documentos indexados, con indicación de su procedencia.

Comandos disponibles durante la sesión:
    :fuentes      muestra el texto completo de los fragmentos empleados
    :breve        muestra solo la referencia de las fuentes (por defecto)
    :k <n>        cambia el número de fragmentos recuperados
    :umbral <n>   cambia el umbral de relevancia
    :corpus       muestra los documentos indexados
    :costo        muestra el consumo acumulado de la sesión
    :salir        termina la sesión
"""

import sys

from src.config import TOP_K, UMBRAL_RELEVANCIA
from src.generacion.generador import Generador
from src.generacion.cliente_llm import ErrorLLM

SEP = "=" * 78


def mostrar_bienvenida(generador: Generador, k: int, umbral: float) -> None:
    resumen = generador.buscador.resumen_corpus()

    print("\n" + SEP)
    print("ASISTENTE DOCUMENTAL")
    print(SEP)
    print(f"Documentos indexados : {resumen['total_documentos']}")
    print(f"Fragmentos           : {resumen['total_fragmentos']}")
    print(f"Modelo               : {generador.descripcion_modelo()}")
    print(f"Fragmentos por consulta: {k} | Umbral: {umbral}")
    print("\nEscribe tu pregunta, o :salir para terminar.")
    print(SEP)


def mostrar_respuesta(resultado: dict, ver_fuentes: bool) -> None:
    print()
    print(resultado["respuesta"])

    if resultado["fuentes"]:
        print("\n" + "-" * 78)
        print("FUENTES")

        for numero, fuente in enumerate(resultado["fuentes"], start=1):
            print(f"\n{numero}. {fuente['documento']} — {fuente['referencia']} "
                  f"[similitud {fuente['similitud']:.4f}]")

            if ver_fuentes:
                texto = fuente["texto"]
                for linea in texto.split("\n"):
                    print(f"   {linea}")

    # Datos de la consulta.
    print("\n" + "-" * 78)
    recuperacion = 1000 * resultado["tiempo_recuperacion"]
    generacion = 1000 * resultado["tiempo_generacion"]

    if resultado["hay_evidencia"]:
        print(f"Tiempo: {recuperacion:.0f} ms recuperación + "
              f"{generacion:.0f} ms generación = "
              f"{recuperacion + generacion:.0f} ms")
        print(f"Tokens: {resultado['tokens_entrada']} entrada, "
              f"{resultado['tokens_salida']} salida")
    else:
        print(f"Tiempo: {recuperacion:.0f} ms (sin invocación al modelo)")
        print(f"Similitud máxima obtenida: {resultado['similitud_maxima']:.4f}")


def main() -> None:
    try:
        generador = Generador()
    except FileNotFoundError as error:
        print(f"\n{error}")
        sys.exit(1)
    except ErrorLLM as error:
        print(f"\n{error}")
        sys.exit(1)

    k = TOP_K
    umbral = UMBRAL_RELEVANCIA
    ver_fuentes = False

    total_entrada = 0
    total_salida = 0
    consultas = 0

    mostrar_bienvenida(generador, k, umbral)

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

        if entrada.lower() == ":fuentes":
            ver_fuentes = True
            print("Se mostrará el texto completo de las fuentes.")
            continue

        if entrada.lower() == ":breve":
            ver_fuentes = False
            print("Se mostrará solo la referencia de las fuentes.")
            continue

        if entrada.lower() == ":corpus":
            resumen = generador.buscador.resumen_corpus()
            print(f"\nDocumentos indexados ({resumen['total_documentos']}):")
            for nombre in resumen["documentos"]:
                print(f"  - {nombre}")
            continue

        if entrada.lower() == ":costo":
            print(f"\nConsultas realizadas : {consultas}")
            print(f"Tokens de entrada    : {total_entrada:,}")
            print(f"Tokens de salida     : {total_salida:,}")
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
        print("\nBuscando...", end="\r")
        resultado = generador.responder(entrada, k=k, umbral=umbral)
        print("           ", end="\r")

        mostrar_respuesta(resultado, ver_fuentes)

        total_entrada += resultado["tokens_entrada"]
        total_salida += resultado["tokens_salida"]
        if resultado["hay_evidencia"]:
            consultas += 1


if __name__ == "__main__":
    main()
