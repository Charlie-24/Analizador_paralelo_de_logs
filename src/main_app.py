#!/usr/bin/env python3
import json, time, logging
from typing import List, Optional
import os
from log_Analyzer import LogAnalyzer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

class MainApp:
    
    # argv: Optional[List[str]] = None --> Argumentos del programa 
    def __init__(self, argv: Optional[List[str]] = None):
        self.argv = argv

    # Una vez creado el objeto de argumentos, se le da un valor a todas las variables 
    def run(self):
        # --- CONFIGURACIÓN FIJA DESDE EL MAIN ---
        # Puedes cambiar aquí las rutas o parámetros que desees
        base_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.normpath(os.path.join(base_dir, "..", "logs"))     # Carpeta con logs
        info_dir = os.path.normpath(os.path.join(base_dir, "..", "info"))    # Carpeta info de salida
        lines_per_chunk = 100                                                # Líneas por bloque
        workers =4                                                          # Número de procesos paralelos
        monitor = True                                                       # Mostrar progreso
        patterns = ["*.log"]                                                 # Patrón de ficheros a analizar
        output = os.path.join(info_dir, "resultado.json")                    # Fichero de salida JSON

        # Log de configuración (similar al anterior cfg.to_dict())
        cfg_dict = {
            "log_dir": log_dir,
            "lines_per_chunk": lines_per_chunk,
            "workers": workers,
            "monitor": monitor,
            "patterns": patterns,
            "info_dir": info_dir,
            "output": output
        }
        logger.info("Configuración: %s", cfg_dict)

        # --- INICIALIZA EL ANALIZADOR ---
        try:
            analyzer = LogAnalyzer(
                log_dir=log_dir,
                lines_per_chunk=lines_per_chunk,
                workers=workers,
                monitor=monitor,
                patterns=patterns,
                info_dir=info_dir,
                output=output
            )
        except FileNotFoundError as e:
            logger.error(e)
            return

        # --- EJECUTA EL ANÁLISIS ---
        start = time.time()
        try:
            result = analyzer.analyze()
        except Exception as e:
            logger.exception("Error durante el análisis: %s", e)
            return

        # --- TIEMPO DE EJECUCIÓN ---
        duration = round(time.time() - start, 2)
        result["tiempo_total_segundos"] = duration

        # --- GUARDA EL INFORME EN JSON ---
        out = LogAnalyzer.save_json_report(result, analyzer.output, params={
            "lines_per_chunk": analyzer.lines_per_chunk,
            "workers": analyzer.workers,
            "log_dir": analyzer.log_dir
        })
        logger.info("Análisis completado en %.2f s. Salida: %s", duration, out)


if __name__ == "__main__":
    MainApp().run()
