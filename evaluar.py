"""
Evaluación del componente de recuperación.

Ejecutar desde la raíz del proyecto:
    python evaluar.py

Ejecuta el conjunto de preguntas de prueba sobre el índice y calcula las
métricas definidas en la sección 3.4.2 del documento escrito: precisión de
recuperación, posición del fragmento correcto y comportamiento ante consultas
sin respuesta en el corpus.

Opciones:
    python evaluar.py --k 3 5 8      compara distintos valores de k
    python evaluar.py --detalle      muestra el resultado de cada pregunta
"""

import argparse
import json
import re
import statistics
import sys

from src.config import EVALUACION_DIR, TOP_K
from src.recuperacion.buscador import Buscador

ARCHIVO_PREGUNTAS = EVALUACION_DIR / "preguntas.json"
SEP = "=" * 78


def cargar_preguntas() -> list[dict]:
    """Carga el conjunto de preguntas de evaluación."""
    if not ARCHIVO_PREGUNTAS.exists():
        print(f"No se encontró el archivo de preguntas: {ARCHIVO_PREGUNTAS}")
        sys.exit(1)

    with open(ARCHIVO_PREGUNTAS, encoding="utf-8") as archivo:
        datos = json.load(archivo)

    return datos["preguntas"]


def ubicaciones_validas(pregunta: dict) -> set[str]:
    """
    Reúne todas las ubicaciones donde la respuesta puede considerarse correcta.

    Una misma respuesta puede aparecer en varios lugares del documento. El
    campo 'nota' recoge estas ubicaciones alternativas, que se extraen aquí
    para no penalizar al sistema por recuperar una de ellas en lugar de la
    señalada como principal.
    """
    validas = set()

    principal = str(pregunta.get("ubicacion", "")).strip()
    if principal:
        validas.add(principal)

    # Extrae las páginas mencionadas en la nota ("también en p. 9 y p. 12").
    nota = pregunta.get("nota", "")
    for numero in re.findall(r"\bp\.?\s*(\d{1,3})\b", nota, re.IGNORECASE):
        validas.add(numero)

    return validas


def fragmento_cubre(resultado: dict, pregunta: dict) -> bool:
    """
    Determina si un fragmento recuperado contiene la respuesta esperada.

    Para documentos PDF se comprueba si alguna de las ubicaciones válidas cae
    dentro del rango de páginas que abarca el fragmento. Para documentos Word
    se compara el nombre de la sección.
    """
    if resultado["documento"] != pregunta["documento"]:
        return False

    validas = ubicaciones_validas(pregunta)
    if not validas:
        return False

    if resultado.get("formato") == "pdf":
        inicio = resultado.get("pagina_inicio")
        fin = resultado.get("pagina_fin", inicio)

        if inicio is None:
            return False

        for ubicacion in validas:
            if ubicacion.isdigit() and inicio <= int(ubicacion) <= fin:
                return True

        return False

    # Documentos Word: comparación por sección.
    seccion = (resultado.get("seccion") or "").lower()

    for ubicacion in validas:
        objetivo = ubicacion.lower()
        if objetivo in seccion or seccion in objetivo:
            return True

    # Cuando la sección no coincide, se acepta el documento correcto si el
    # texto del fragmento menciona términos de la respuesta esperada. Los
    # documentos sin estilos de título producen una única sección, lo que
    # hace inviable la comparación por nombre.
    esperada = pregunta.get("respuesta_esperada", "").lower()
    palabras = [p for p in re.findall(r"\w{5,}", esperada)]

    if palabras:
        texto = resultado["texto"].lower()
        coincidencias = sum(1 for p in palabras if p in texto)
        return coincidencias >= max(1, len(palabras) // 2)

    return False


def evaluar_pregunta(buscador: Buscador, pregunta: dict, k: int, umbral: float) -> dict:
    """Ejecuta una pregunta y evalúa el resultado obtenido."""
    busqueda = buscador.buscar(pregunta["pregunta"], k=k, umbral=umbral)

    sin_respuesta = pregunta["categoria"] == "sin_respuesta"

    # Posición del primer fragmento que contiene la respuesta.
    posicion_acierto = None

    if not sin_respuesta:
        for indice, resultado in enumerate(busqueda["resultados"], start=1):
            if fragmento_cubre(resultado, pregunta):
                posicion_acierto = indice
                break

    if sin_respuesta:
        # El acierto consiste en no entregar resultados.
        correcto = not busqueda["hay_evidencia"]
    else:
        correcto = posicion_acierto is not None

    return {
        "id": pregunta["id"],
        "categoria": pregunta["categoria"],
        "pregunta": pregunta["pregunta"],
        "correcto": correcto,
        "posicion": posicion_acierto,
        "similitud_maxima": busqueda["similitud_maxima"],
        "hay_evidencia": busqueda["hay_evidencia"],
        "documento_esperado": pregunta.get("documento", ""),
        "documento_recuperado": (
            busqueda["resultados"][0]["documento"] if busqueda["resultados"] else ""
        ),
        "tiempo": busqueda["tiempo_embedding"] + busqueda["tiempo_busqueda"],
    }


def resumir(resultados: list[dict]) -> dict:
    """Calcula las métricas agregadas de una ejecución."""
    con_respuesta = [r for r in resultados if r["categoria"] != "sin_respuesta"]
    sin_respuesta = [r for r in resultados if r["categoria"] == "sin_respuesta"]

    aciertos = [r for r in con_respuesta if r["correcto"]]
    posiciones = [r["posicion"] for r in aciertos if r["posicion"]]

    abstenciones = [r for r in sin_respuesta if r["correcto"]]

    # Similitudes máximas de cada grupo, empleadas para determinar el umbral.
    sim_con = [r["similitud_maxima"] for r in con_respuesta]
    sim_sin = [r["similitud_maxima"] for r in sin_respuesta]

    return {
        "total": len(resultados),
        "con_respuesta": len(con_respuesta),
        "sin_respuesta": len(sin_respuesta),
        "aciertos": len(aciertos),
        "precision": len(aciertos) / len(con_respuesta) if con_respuesta else 0,
        "posicion_media": statistics.mean(posiciones) if posiciones else 0,
        "abstenciones_correctas": len(abstenciones),
        "tasa_abstencion": len(abstenciones) / len(sin_respuesta) if sin_respuesta else 0,
        "sim_con_media": statistics.mean(sim_con) if sim_con else 0,
        "sim_con_minima": min(sim_con) if sim_con else 0,
        "sim_sin_media": statistics.mean(sim_sin) if sim_sin else 0,
        "sim_sin_maxima": max(sim_sin) if sim_sin else 0,
        "tiempo_medio": statistics.mean([r["tiempo"] for r in resultados]),
    }


def mostrar_detalle(resultados: list[dict]) -> None:
    """Imprime el resultado de cada pregunta."""
    print("\nDETALLE POR PREGUNTA")
    print("-" * 78)

    for resultado in resultados:
        marca = "OK " if resultado["correcto"] else "FALLA"
        posicion = f"pos. {resultado['posicion']}" if resultado["posicion"] else "—"

        print(f"\n{marca} [{resultado['id']:2}] {resultado['pregunta'][:60]}")
        print(f"      categoría: {resultado['categoria']} | {posicion} | "
              f"sim. máx. {resultado['similitud_maxima']:.4f}")

        if not resultado["correcto"]:
            if resultado["categoria"] == "sin_respuesta":
                print(f"      devolvió resultados cuando no debía")
            else:
                print(f"      esperado: {resultado['documento_esperado']}")
                print(f"      primero : {resultado['documento_recuperado'] or '(ninguno)'}")


def mostrar_resumen(resumen: dict, k: int, umbral: float) -> None:
    """Imprime las métricas agregadas."""
    print(f"\n{SEP}")
    print(f"RESULTADOS  (k={k}, umbral={umbral})")
    print(SEP)

    print(f"\nPreguntas con respuesta en el corpus: {resumen['con_respuesta']}")
    print(f"  Aciertos                 : {resumen['aciertos']}")
    print(f"  Precisión de recuperación: {resumen['precision']:.1%}")
    print(f"  Posición media del acierto: {resumen['posicion_media']:.2f}")

    print(f"\nPreguntas sin respuesta en el corpus: {resumen['sin_respuesta']}")
    print(f"  Abstenciones correctas   : {resumen['abstenciones_correctas']}")
    print(f"  Tasa de abstención       : {resumen['tasa_abstencion']:.1%}")

    print(f"\nDistribución de similitudes (para calibrar el umbral):")
    print(f"  Con respuesta — media: {resumen['sim_con_media']:.4f} | "
          f"mínima: {resumen['sim_con_minima']:.4f}")
    print(f"  Sin respuesta — media: {resumen['sim_sin_media']:.4f} | "
          f"máxima: {resumen['sim_sin_maxima']:.4f}")

    separacion = resumen["sim_con_minima"] - resumen["sim_sin_maxima"]
    if separacion > 0:
        sugerido = (resumen["sim_con_minima"] + resumen["sim_sin_maxima"]) / 2
        print(f"  Los dos grupos no se solapan. Umbral sugerido: {sugerido:.4f}")
    else:
        print(f"  Los grupos se solapan en {abs(separacion):.4f}. "
              f"Ningún umbral los separa por completo.")

    print(f"\nTiempo medio por consulta: {1000 * resumen['tiempo_medio']:.1f} ms")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluación de la recuperación")
    parser.add_argument("--k", type=int, nargs="+", default=[TOP_K],
                        help="valores de k a evaluar")
    parser.add_argument("--umbral", type=float, default=0.0,
                        help="umbral de relevancia (0 para no filtrar)")
    parser.add_argument("--detalle", action="store_true",
                        help="muestra el resultado de cada pregunta")
    args = parser.parse_args()

    preguntas = cargar_preguntas()

    try:
        buscador = Buscador()
    except FileNotFoundError as error:
        print(f"\n{error}")
        sys.exit(1)

    print(f"\nEVALUACIÓN DEL COMPONENTE DE RECUPERACIÓN")
    print(f"Preguntas: {len(preguntas)}")

    comparativa = []

    for k in args.k:
        resultados = [
            evaluar_pregunta(buscador, p, k, args.umbral)
            for p in preguntas
        ]
        resumen = resumir(resultados)

        if args.detalle:
            mostrar_detalle(resultados)

        mostrar_resumen(resumen, k, args.umbral)
        comparativa.append((k, resumen))

    # Tabla comparativa cuando se evalúan varios valores de k.
    if len(comparativa) > 1:
        print(f"\n{SEP}")
        print("COMPARATIVA POR VALOR DE k")
        print(SEP)
        print(f"\n{'k':>4} | {'Precisión':>10} | {'Pos. media':>11} | "
              f"{'Tiempo (ms)':>12}")
        print("-" * 46)

        for k, resumen in comparativa:
            print(f"{k:>4} | {resumen['precision']:>9.1%} | "
                  f"{resumen['posicion_media']:>11.2f} | "
                  f"{1000 * resumen['tiempo_medio']:>12.1f}")


if __name__ == "__main__":
    main()
