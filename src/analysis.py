# analysis.py
"""
Funciones de análisis que operan sobre un chunk (lista de líneas) de un fichero de log.

Interfaz principal:
- analyze_chunk(lines) -> dict
  Devuelve un dict con resultados parciales con la siguiente estructura aproximada:
  {
    "lines_total": int,
    "by_level": {"INFO": n, "WARNING": m, "ERROR": k},
    "top_ips": {"192.168.1.10": 12, ...},  # Counter serializable
    "errors_by_hour": {"2025-10-08 09": 5, ...}  # clave: "YYYY-MM-DD HH"
  }

- merge_partial_results(accumulator: dict, partial: dict) -> dict
  Combina dos resultados parciales (útil en el proceso principal).
"""

from collections import Counter
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

# Usamos tu parser ligero desde log_utils para mantener coherencia
from pathlib import Path
import log_utils

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def _safe_parse_datetime(dt_str: str) -> Optional[datetime]:
    """
    Intenta convertir el string datetime del log al objeto datetime.
    Formato esperado: "YYYY-MM-DD HH:MM:SS,ms" (ej: 2025-10-08 08:32:15,124)
    Si falla, devuelve None (no lanza excepción).
    """
    if not dt_str:
        return None
    formats = ["%Y-%m-%d %H:%M:%S,%f", "%Y-%m-%d %H:%M:%S"]  # permitir sin milisegundos
    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt)
        except Exception:
            continue
    return None


def analyze_chunk(lines: List[str]) -> Dict[str, Any]:
    """
    Análisis sobre un chunk (lista de líneas).
    Devuelve un diccionario con resultados parciales:
      - lines_total: número de líneas procesadas
      - by_level: Counter para niveles INFO/WARNING/ERROR (como dict)
      - top_ips: Counter de IPs (como dict)
      - errors_by_hour: dict con claves "YYYY-MM-DD HH" y conteo de ERRORs en esa hora
    El resultado está diseñado para ser serializable y fácil de combinar.
    """
    lines_total = 0
    level_counter = Counter()
    ip_counter = Counter()
    errors_by_hour = Counter()

    for line in lines:
        lines_total += 1
        parsed = log_utils.parse_log_line(line)
        if not parsed:
            # Si la línea no sigue el formato esperado la ignoramos (pero podríamos contabilizar)
            continue

        # Nivel (INFO/WARNING/ERROR...), normalizamos a mayúsculas sin corchetes
        level = (parsed.get("level") or "").upper()
        if level:
            level_counter[level] += 1

        # IP
        ip = parsed.get("ip") or ""
        if ip:
            ip_counter[ip] += 1

        # Errores por hora: sólo contamos si level == ERROR (o contiene ERROR)
        if level == "ERROR":
            dt_str = parsed.get("datetime") or ""
            dt = _safe_parse_datetime(dt_str)
            if dt:
                # clave por hora (ej: "2025-10-08 09")
                key = dt.strftime("%Y-%m-%d %H")
            else:
                # si no podemos parsear datetime, agrupar bajo "unknown"
                key = "unknown"
            errors_by_hour[key] += 1

    # Serializamos counters a dict simples para facilitar envío por Queue/Manager
    return {
        "lines_total": lines_total,
        "by_level": dict(level_counter),
        "top_ips": dict(ip_counter),
        "errors_by_hour": dict(errors_by_hour),
    }


def merge_partial_results(acc: Dict[str, Any], part: Dict[str, Any]) -> Dict[str, Any]:
    """
    Combina un acumulador 'acc' con un resultado parcial 'part'.
    Las claves esperadas son las mismas que produce analyze_chunk.
    Devuelve el acumulador actualizado (mutación in-place).
    """
    # Inicializar estructuras si es necesario
    if "lines_total" not in acc:
        acc["lines_total"] = 0
    if "by_level" not in acc:
        acc["by_level"] = {}
    if "top_ips" not in acc:
        acc["top_ips"] = {}
    if "errors_by_hour" not in acc:
        acc["errors_by_hour"] = {}

    # Sumar líneas
    acc["lines_total"] += part.get("lines_total", 0)

    # Sumar contadores por nivel
    for lvl, cnt in (part.get("by_level") or {}).items():
        acc["by_level"][lvl] = acc["by_level"].get(lvl, 0) + cnt

    # Sumar IPs
    for ip, cnt in (part.get("top_ips") or {}).items():
        acc["top_ips"][ip] = acc["top_ips"].get(ip, 0) + cnt

    # Sumar errores por hora
    for key, cnt in (part.get("errors_by_hour") or {}).items():
        acc["errors_by_hour"][key] = acc["errors_by_hour"].get(key, 0) + cnt

    return acc


def get_top_n_ips_from_acc(acc: Dict[str, Any], n: int = 10) -> List[tuple]:
    """
    A partir del acumulador combinado, devuelve una lista de tuplas (ip, count)
    con las N IPs más activas ordenadas por número de eventos descendente.
    """
    ip_dict = acc.get("top_ips") or {}
    # Convertir a lista de tuplas y ordenar
    items = sorted(ip_dict.items(), key=lambda kv: kv[1], reverse=True)
    return items[:n]
