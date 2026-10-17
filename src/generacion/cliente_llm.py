"""
Capa de abstracción del modelo de lenguaje.

Centraliza la comunicación con el proveedor del modelo generativo. El resto
del sistema solicita respuestas a través de esta interfaz sin conocer qué
proveedor la atiende ni cómo se construye la solicitud.

Esta separación responde a un principio de diseño y a una consideración
práctica. El principio: el modelo de lenguaje constituye un componente
sustituible del sistema y no su fundamento, de modo que la arquitectura debe
preservar su validez ante el reemplazo de dicho componente. La consideración
práctica: la oferta de modelos disponibles evoluciona con rapidez, y el
acoplamiento a un proveedor específico comprometería la vigencia del sistema.

La incorporación de un nuevo proveedor requiere únicamente añadir una clase
que implemente el método 'generar'.
"""

import time
from abc import ABC, abstractmethod

from src.config import (
    PROVEEDOR_LLM,
    MODELO_LLM,
    API_KEY_LLM,
    TEMPERATURA,
    MAX_TOKENS_RESPUESTA,
)


class ErrorLLM(Exception):
    """Error en la comunicación con el proveedor del modelo."""


class ClienteLLM(ABC):
    """Interfaz que debe implementar todo proveedor de modelo de lenguaje."""

    @abstractmethod
    def generar(self, instrucciones: str, consulta: str) -> dict:
        """
        Solicita una respuesta al modelo.

        Args:
            instrucciones: directrices de comportamiento del sistema.
            consulta: contenido de la solicitud, incluyendo el contexto
                documental y la pregunta del usuario.

        Returns:
            Diccionario con la respuesta y los datos de la solicitud:
                {
                    "texto": str,
                    "modelo": str,
                    "tokens_entrada": int,
                    "tokens_salida": int,
                    "tiempo": float,
                }
        """

    @abstractmethod
    def descripcion(self) -> str:
        """Devuelve una descripción del proveedor y modelo en uso."""


class ClienteOpenAI(ClienteLLM):
    """Implementación para los modelos accesibles mediante la API de OpenAI."""

    def __init__(self, modelo: str = MODELO_LLM, clave: str = API_KEY_LLM):
        if not clave:
            raise ErrorLLM(
                "No hay credencial configurada. "
                "Añade tu clave en el archivo .env, en la línea API_KEY_LLM="
            )

        if not modelo:
            raise ErrorLLM(
                "No hay modelo configurado. "
                "Añade el identificador en el archivo .env, en MODELO_LLM="
            )

        from openai import OpenAI

        self.modelo = modelo
        self.cliente = OpenAI(api_key=clave)

    def generar(self, instrucciones: str, consulta: str) -> dict:
        inicio = time.perf_counter()

        try:
            respuesta = self.cliente.chat.completions.create(
                model=self.modelo,
                messages=[
                    {"role": "system", "content": instrucciones},
                    {"role": "user", "content": consulta},
                ],
                max_completion_tokens=MAX_TOKENS_RESPUESTA,
            )
        except Exception as error:
            raise ErrorLLM(f"Error en la solicitud al proveedor: {error}")

        tiempo = time.perf_counter() - inicio

        uso = respuesta.usage

        return {
            "texto": respuesta.choices[0].message.content.strip(),
            "modelo": self.modelo,
            "tokens_entrada": uso.prompt_tokens if uso else 0,
            "tokens_salida": uso.completion_tokens if uso else 0,
            "tiempo": tiempo,
        }

    def descripcion(self) -> str:
        return f"OpenAI / {self.modelo}"


def obtener_cliente() -> ClienteLLM:
    """
    Devuelve el cliente correspondiente al proveedor configurado.

    La selección se realiza a partir del archivo de configuración, de modo que
    el cambio de proveedor no requiere modificar el código del sistema.
    """
    proveedor = (PROVEEDOR_LLM or "").lower()

    if proveedor == "openai":
        return ClienteOpenAI()

    raise ErrorLLM(
        f"Proveedor no reconocido: '{PROVEEDOR_LLM}'. "
        "Proveedores disponibles: openai."
    )
