# processor.py
"""
Processor: adaptador entre los chunks leídos (log_utils) y el análisis (analysis).

Proporciona:
- Clase Processor con métodos para procesar un chunk y para usar como worker en multiprocessing.
- Funciones de ayuda para ejecutar en modo secuencial (debug) o como target de procesos.

Principios:
- No modifica config, log_utils ni analysis.
- Manejo seguro de excepciones por chunk (un chunk que falla no rompe toda la ejecución).
- Resultado parcial siempre serializable (dict con metadata + resultado de analysis.analyze_chunk).
"""

from typing import List, Dict, Any, Optional, Tuple
import logging
import traceback

import analysis  # usa las funciones analyze_chunk / merge_partial_results
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


class Processor:
    """
    Clase ligera que encapsula la lógica de procesar chunks usando analysis.analyze_chunk.
    No mantiene estado entre llamadas (stateless), por lo que es segura para ejecutarse
    en múltiples procesos.
    """

    def __init__(self, name: Optional[str] = None):
        """
        name: identificador opcional del procesador (útil en logs).
        """
        self.name = name or "Processor"

    def process_chunk(self, file_path: Path, chunk_index: int, lines: List[str]) -> Dict[str, Any]:
        """
        Procesa un chunk (lista de líneas) y devuelve un diccionario serializable con:
          - file: str(ruta)
          - chunk_index: int
          - status: "ok" o "error"
          - result: dict (resultado de analysis.analyze_chunk) o mensaje de error
          - error_trace: str (opcional, sólo si hay error)
        Esta envoltura garantiza que el caller siempre reciba un objeto con estructura conocida.
        """
        meta = {
            "file": str(file_path),
            "chunk_index": int(chunk_index),
            "processor": self.name,
        }

        try:
            result = analysis.analyze_chunk(lines)
            return {
                **meta,
                "status": "ok",
                "result": result,
            }
        except Exception as exc:
            # Capturamos el traceback para diagnóstico, pero devolvemos un objeto serializable.
            tb = traceback.format_exc()
            logger.error("Error procesando chunk %s:%s — %s", file_path, chunk_index, exc)
            return {
                **meta,
                "status": "error",
                "result": None,
                "error_message": str(exc),
                "error_trace": tb,
            }


def worker_loop(task_q, result_q, worker_id: Optional[int] = None, stop_on_exception: bool = False):
    """
    Target para multiprocessing.Process.
    - task_q: cola de tareas; cada tarea es tuple(file_path, chunk_index, lines)
    - result_q: cola donde se ponen los resultados (lo que devuelve Processor.process_chunk)
    - worker_id: id numérico opcional para identificar logs
    - stop_on_exception: si True, el worker deja de procesar al primer error grave;
                         si False, reporta el error y continúa.
    Protocolo de terminación:
      - Si recibe None como tarea, sale del bucle y finaliza.
    NOTA: task_q and result_q pueden ser multiprocessing.Queue o similares.
    """
    proc_name = f"worker-{worker_id}" if worker_id is not None else "worker"
    p = Processor(name=proc_name)
    logger.info("%s arrancado", proc_name)

    while True:
        task = task_q.get()
        # Señal de terminación
        if task is None:
            logger.info("%s recibida señal de terminación", proc_name)
            break

        try:
            # task -> (file_path, chunk_index, lines)
            file_path, chunk_index, lines = task
            res = p.process_chunk(Path(file_path), int(chunk_index), lines)
            result_q.put(res)
        except Exception as exc:
            # Control muy defensivo: atrapar cualquier excepción de la cola/serialización
            tb = traceback.format_exc()
            logger.exception("%s falló al obtener/ejecutar tarea: %s", proc_name, exc)
            # Intentamos informar al collector de que hubo un error crítico en el worker
            err_obj = {
                "file": str(task[0]) if isinstance(task, (list, tuple)) and len(task) > 0 else None,
                "chunk_index": task[1] if isinstance(task, (list, tuple)) and len(task) > 1 else None,
                "processor": proc_name,
                "status": "error",
                "result": None,
                "error_message": str(exc),
                "error_trace": tb,
                "fatal": True,
            }
            try:
                result_q.put(err_obj)
            except Exception:
                logger.error("%s no pudo reportar error al result_q", proc_name)
            if stop_on_exception:
                logger.error("%s deteniéndose por stop_on_exception=True", proc_name)
                break

    logger.info("%s finalizado", proc_name)


# Metodo que no utiliza Procesos Paralelos, a modo de debug (Se encarga de comprobar la logica)
def run_sequential_from_dir(lines_per_chunk: Optional[int] = None, patterns: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Conveniencia para ejecutar el análisis secuencialmente (sin multiprocessing).
    - Recorre los chunks producidos por log_utils.iter_chunks_from_dir(...)
    - Combina parciales usando analysis.merge_partial_results
    - Devuelve el acumulador final (acc)
    Útil para debug, pruebas unitarias o ejecución en entornos donde no quieras paralelismo.
    """
    import log_utils

    acc: Dict[str, Any] = {}
    total_chunks = 0
    for file_path, chunk_index, lines in log_utils.iter_chunks_from_dir(lines_per_chunk, patterns):
        total_chunks += 1
        try:
            # Reutilizamos Processor para consistencia
            p = Processor(name="sequential")
            res_obj = p.process_chunk(file_path, chunk_index, lines)
            if res_obj.get("status") == "ok":
                analysis.merge_partial_results(acc, res_obj["result"])
            else:
                # Registrar pero no romper el bucle
                logger.warning("Chunk %s:%s produjo error: %s", file_path, chunk_index, res_obj.get("error_message"))
        except Exception as exc:
            logger.exception("Error procesando %s:%s de forma secuencial: %s", file_path, chunk_index, exc)

    logger.info("Ejecución secuencial finalizada. Chunks procesados: %d", total_chunks)
    return acc
