"""
Generación de respuestas fundamentadas en el corpus documental.

Recibe una consulta, obtiene los fragmentos pertinentes del módulo de
recuperación y solicita al modelo de lenguaje la elaboración de una respuesta
ajustada a dicho contexto.

El módulo implementa la política de comportamiento ante ausencia de evidencia
documental, que constituye uno de los mecanismos centrales del sistema: cuando
ningún fragmento recuperado alcanza el umbral de relevancia, no se invoca al
modelo generativo. La respuesta de ausencia se produce estructuralmente, sin
depender de que el modelo cumpla una instrucción de abstención.

Esta decisión reviste importancia conceptual. Una instrucción incorporada al
prompt puede ser ignorada por el modelo, de modo que la garantía de no
responder sin fundamento quedaría condicionada a su obediencia. Al resolver la
abstención antes de la invocación, dicha garantía pasa a ser una propiedad de
la arquitectura y no un comportamiento esperado del modelo. Como efecto
secundario, se evita el costo asociado a una consulta que no produciría una
respuesta válida.
"""

from src.config import TOP_K, UMBRAL_RELEVANCIA
from src.generacion.cliente_llm import obtener_cliente, ErrorLLM
from src.recuperacion.buscador import Buscador

INSTRUCCIONES = """\
Eres un asistente que responde preguntas sobre documentos académicos.

Dispones de fragmentos extraídos de los documentos del usuario. Cada fragmento \
viene precedido de su identificación entre corchetes, con el nombre del \
documento y su ubicación.

Reglas que debes seguir:

1. Responde únicamente con información contenida en los fragmentos \
proporcionados. No incorpores conocimiento propio ni completes lo que los \
fragmentos no digan.

2. Indica de dónde procede la información citando el documento y la ubicación \
tal como aparecen entre corchetes. Intégralo en la redacción de forma natural, \
por ejemplo: «Según el documento X, en la página Y, ...».

3. Si los fragmentos contienen la respuesta solo de forma parcial, responde con \
lo disponible e indica explícitamente qué parte no consta en ellos.

4. Si los fragmentos no permiten responder la pregunta, dilo con claridad. No \
elabores una respuesta aproximada a partir de información relacionada.

5. Redacta de forma clara y didáctica, adecuada para un estudiante. Explica con \
tus palabras en lugar de reproducir el texto literalmente, salvo cuando la \
formulación exacta resulte necesaria, como ocurre con las fórmulas.

6. Sé conciso. Extensión habitual: entre uno y tres párrafos.
"""

MENSAJE_SIN_EVIDENCia = (
    "No encontré información sobre esto en los documentos cargados.\n\n"
    "Esto puede deberse a que el tema no está tratado en ellos, a que el "
    "documento correspondiente no pudo procesarse —los archivos escaneados "
    "sin capa de texto no son legibles para el sistema—, o a que la pregunta "
    "está formulada de un modo que no coincide con el contenido disponible. "
    "Puedes intentar reformularla con otros términos."
)

# Alias para evitar problemas de escritura en el identificador.
MENSAJE_SIN_EVIDENCIA = MENSAJE_SIN_EVIDENCia


def construir_contexto(fragmentos: list[dict]) -> str:
    """
    Compone el contexto documental que se transmite al modelo.

    Cada fragmento se precede de su identificación de origen, lo que permite
    al modelo atribuir correctamente la información que emplea y constituye
    la base de la trazabilidad de la respuesta.
    """
    partes = []

    for numero, fragmento in enumerate(fragmentos, start=1):
        encabezado = (
            f"[Fragmento {numero} — {fragmento['documento']}, "
            f"{fragmento['referencia']}]"
        )
        partes.append(f"{encabezado}\n{fragmento['texto']}")

    return "\n\n".join(partes)


def construir_consulta(pregunta: str, contexto: str, historial: str = "") -> str:
    """Compone el mensaje completo que recibe el modelo."""
    secciones = []

    if historial:
        secciones.append(f"Conversación previa:\n{historial}")

    secciones.append(f"Fragmentos de los documentos:\n\n{contexto}")
    secciones.append(f"Pregunta: {pregunta}")

    return "\n\n".join(secciones)


class Generador:
    """Sistema completo de consulta documental."""

    def __init__(self, buscador: Buscador | None = None):
        self.buscador = buscador if buscador is not None else Buscador()
        self.cliente = obtener_cliente()

    def responder(
        self,
        pregunta: str,
        k: int = TOP_K,
        umbral: float = UMBRAL_RELEVANCIA,
        historial: str = "",
    ) -> dict:
        """
        Elabora una respuesta fundamentada en el corpus documental.

        Args:
            pregunta: consulta en lenguaje natural.
            k: número de fragmentos a recuperar.
            umbral: similitud mínima exigida.
            historial: turnos previos de la conversación, si los hubiera.

        Returns:
            Diccionario con la respuesta y los datos del proceso:
                {
                    "respuesta": str,
                    "hay_evidencia": bool,
                    "fuentes": list[dict],
                    "similitud_maxima": float,
                    "tiempo_recuperacion": float,
                    "tiempo_generacion": float,
                    "tokens_entrada": int,
                    "tokens_salida": int,
                    "modelo": str,
                }
        """
        busqueda = self.buscador.buscar(pregunta, k=k, umbral=umbral)

        tiempo_recuperacion = (
            busqueda["tiempo_embedding"] + busqueda["tiempo_busqueda"]
        )

        base = {
            "hay_evidencia": busqueda["hay_evidencia"],
            "similitud_maxima": busqueda["similitud_maxima"],
            "tiempo_recuperacion": tiempo_recuperacion,
            "tiempo_generacion": 0.0,
            "tokens_entrada": 0,
            "tokens_salida": 0,
            "modelo": "",
        }

        # Política ante ausencia de evidencia: no se invoca al modelo.
        if not busqueda["hay_evidencia"]:
            return {
                **base,
                "respuesta": MENSAJE_SIN_EVIDENCIA,
                "fuentes": [],
            }

        fragmentos = busqueda["resultados"]
        contexto = construir_contexto(fragmentos)
        consulta = construir_consulta(pregunta, contexto, historial)

        try:
            resultado = self.cliente.generar(INSTRUCCIONES, consulta)
        except ErrorLLM as error:
            return {
                **base,
                "respuesta": (
                    "No se pudo generar la respuesta por un problema de "
                    f"comunicación con el modelo de lenguaje.\n\n{error}\n\n"
                    "Los fragmentos relevantes sí se localizaron y se muestran "
                    "a continuación."
                ),
                "fuentes": self._fuentes(fragmentos),
                "error": str(error),
            }

        return {
            **base,
            "respuesta": resultado["texto"],
            "fuentes": self._fuentes(fragmentos),
            "tiempo_generacion": resultado["tiempo"],
            "tokens_entrada": resultado["tokens_entrada"],
            "tokens_salida": resultado["tokens_salida"],
            "modelo": resultado["modelo"],
        }

    @staticmethod
    def _fuentes(fragmentos: list[dict]) -> list[dict]:
        """Extrae la información de origen de los fragmentos empleados."""
        return [
            {
                "documento": f["documento"],
                "referencia": f["referencia"],
                "similitud": f["similitud"],
                "texto": f["texto"],
            }
            for f in fragmentos
        ]

    def descripcion_modelo(self) -> str:
        """Devuelve la identificación del proveedor y modelo en uso."""
        return self.cliente.descripcion()
