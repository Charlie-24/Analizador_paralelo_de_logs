# parallel_manager.py
"""
Gestión de ejecución paralela de análisis de logs usando multiprocessing y monitorización con psutil.

Funciones principales:
- Ejecutar todos los chunks de logs en procesos separados.
- Recoger resultados parciales y combinarlos.
- Monitorizar CPU y memoria durante la ejecución.
"""

import multiprocessing
from multiprocessing import Queue, Process
from typing import Optional, List, Dict, Any
import time
import psutil
import logging

from pathlib import Path
import log_utils
import analysis
from processor import Processor
import config

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


class ParallelManager:
    def __init__(self, lines_per_chunk: Optional[int] = None, max_workers: Optional[int] = None, patterns: Optional[List[str]] = None):
        """
        Inicializa parámetros de ejecución paralela.
        """
        self.lines_per_chunk = lines_per_chunk or config.DEFAULT_LINES_PER_CHUNK
        self.max_workers = max_workers or config.DEFAULT_MAX_WORKERS
        self.patterns = patterns
        self.task_q: Queue = Queue()
        self.result_q: Queue = Queue()
        self.processes: List[Process] = []
        self.results: List[Dict[str, Any]] = []

    def _start_workers(self):
        """Crea y arranca procesos worker."""
        for i in range(self.max_workers):
            p = Process(target=Processor.worker_loop, args=(self.task_q, self.result_q))
            p.daemon = True  # Se cierra si termina el proceso principal
            p.start()
            self.processes.append(p)
            logger.info(f"Worker {i} iniciado.")

    def _stop_workers(self):
        """Envía señal de finalización a todos los workers y espera a que terminen."""
        for _ in self.processes:
            self.task_q.put(None)  # None indica finalización
        for p in self.processes:
            p.join()
            logger.info(f"Worker {p.pid} finalizado.")

    def _enqueue_tasks(self):
        """Añade todos los chunks de logs a la cola de tareas."""
        for file_path, chunk_index, lines in log_utils.iter_chunks_from_dir(self.lines_per_chunk, self.patterns):
            self.task_q.put((file_path, chunk_index, lines))

    def _collect_results(self):
        """Recoge resultados parciales de la cola result_q."""
        while any(p.is_alive() for p in self.processes) or not self.result_q.empty():
            try:
                result = self.result_q.get(timeout=0.5)
                self.results.append(result)
            except Exception:
                pass  # Timeout, seguimos

    def _monitor_performance(self, interval=1.0):
        """Opcional: imprime uso de CPU y RAM mientras los procesos están activos."""
        logger.info("Monitorización iniciada (Ctrl+C para detener).")
        try:
            while any(p.is_alive() for p in self.processes):
                cpu = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory().percent
                logger.info(f"CPU: {cpu:.1f}%, RAM: {mem:.1f}%")
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.warning("Monitorización interrumpida por el usuario.")

    def run(self) -> Dict[str, Any]:
        """Ejecuta el análisis en paralelo y devuelve el resultado combinado."""
        logger.info("Preparando ejecución paralela...")
        self._start_workers()
        self._enqueue_tasks()
        # Monitorización opcional en hilo aparte si quieres más detalle
        self._monitor_performance(interval=1.0)
        self._collect_results()
        self._stop_workers()
        # Combinar resultados parciales
        final_result = analysis.merge_partial_results(self.results)
        return final_result
