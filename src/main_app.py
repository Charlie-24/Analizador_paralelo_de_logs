#!/usr/bin/env python3
import json, time, logging
from typing import List, Optional
import os
from log_Analyzer import LogAnalyzer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

class MainApp:
    
    def __init__(self, argv: Optional[List[str]] = None):
        self.argv = argv

    def run(self):

        # Parametros de configuracion 
        base_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.normpath(os.path.join(base_dir, "..", "logs"))    
        info_dir = os.path.normpath(os.path.join(base_dir, "..", "info"))   
        lines_per_chunk = 100                                                
        workers =4                                                          
        monitor = True                                                       
        patterns = ["*.log"]                                                 
        output = os.path.join(info_dir, "resultado.json")                   

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
