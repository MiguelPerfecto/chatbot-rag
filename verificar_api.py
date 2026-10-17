"""
Verificación de la conexión con el proveedor del modelo de lenguaje.

Ejecutar desde la raíz del proyecto:
    python verificar_api.py

Comprueba que la credencial configurada es válida y consulta los modelos
disponibles para la cuenta. El identificador que devuelve esta consulta es el
que debe emplearse en la configuración del sistema, dado que corresponde al
nombre técnico del modelo y no a su denominación comercial.
"""

import sys

from openai import OpenAI

from src.config import API_KEY_LLM, MODELO_LLM

SEP = "=" * 78


def main() -> None:
    if not API_KEY_LLM:
        print("\nNo hay credencial configurada.")
        print("Añade tu clave en el archivo .env, en la línea API_KEY_LLM=")
        sys.exit(1)

    # Se muestran únicamente los primeros y últimos caracteres, suficientes
    # para identificar la credencial sin exponerla.
    print(f"\nCredencial detectada: {API_KEY_LLM[:8]}...{API_KEY_LLM[-4:]}")

    cliente = OpenAI(api_key=API_KEY_LLM)

    try:
        modelos = cliente.models.list()
    except Exception as error:
        print(f"\nNo se pudo establecer la conexión:\n  {error}")
        print("\nCausas habituales: credencial incorrecta, credencial revocada,")
        print("ausencia de saldo en la cuenta o falta de conexión a la red.")
        sys.exit(1)

    identificadores = sorted(modelo.id for modelo in modelos.data)

    print(f"\n{SEP}")
    print(f"MODELOS DISPONIBLES ({len(identificadores)})")
    print(SEP)

    for identificador in identificadores:
        print(f"  {identificador}")

    print(f"\n{SEP}")
    print("CONFIGURACIÓN ACTUAL")
    print(SEP)

    if not MODELO_LLM:
        print("\nNo hay modelo configurado.")
        print("Elige uno de la lista anterior y añádelo al archivo .env,")
        print("en la línea MODELO_LLM=")
    elif MODELO_LLM in identificadores:
        print(f"\nModelo configurado: {MODELO_LLM}")
        print("El modelo está disponible para esta cuenta.")
    else:
        print(f"\nModelo configurado: {MODELO_LLM}")
        print("ADVERTENCIA: este identificador no figura entre los disponibles.")
        print("Verifica que esté correctamente escrito.")


if __name__ == "__main__":
    main()
