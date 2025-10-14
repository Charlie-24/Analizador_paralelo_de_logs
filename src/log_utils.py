# log_utils.py
"""
Utilidades para localizar, leer y fragmentar (chunk) ficheros de log.

Interfaz principal:
- list_log_files(): devuelve lista de rutas absolutas de logs según config.LOG_DIR y config.LOG_PATTERNS
- chunk_file_lines(): genera fragmentos (listas de líneas) de un fichero dado
- iter_chunks_from_dir(): genera tuplas (file_path, chunk_index, lines_list) para todos los ficheros encontrados
- count_lines_in_file(): cuenta líneas de un fichero (útil para planificación / estadísticas)
- is_file_empty(): True si el fichero tiene 0 líneas
- parse_log_line(): (función ligera) intenta extraer los campos básicos de una línea de log (fecha, nivel, ip, mensaje)
"""

from pathlib import Path
from typing import Iterator, List, Tuple, Optional, Dict
import glob
import os
import logging

# Importamos config.py
import config

# El log adquiere el nombre de el fichero del cual viene
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def _ensure_log_dir() -> Path:
    """Devuelve Path de LOG_DIR si existe, si no lanza FileNotFoundError."""
    log_dir = Path(config.LOG_DIR)
    if not log_dir.exists() or not log_dir.is_dir():
        raise FileNotFoundError(f"El directorio de logs no existe: {log_dir}")
    return log_dir.resolve()


# Parámetro opcional:
# patterns → lista de patrones tipo ["*.log", "*.txt"].
# Si no se pasa nada (None), usará los patrones por defecto definidos en config.LOG_PATTERNS.
def list_log_files(patterns: Optional[List[str]] = None) -> List[Path]:
    """
    Devuelve una lista de Path de ficheros de log encontrados en LOG_DIR
    según config.LOG_PATTERNS (por defecto).
    - patterns: lista de patrones tipo glob (ej: ["*.log","*.txt"])
    """
    patterns = patterns or config.LOG_PATTERNS
    log_dir = _ensure_log_dir()

    files = []
    for pat in patterns:
        # Busca archivos con el patron "*.log" y glob.glob los añade a files[] la ruta como String
        matches = glob.glob(str(log_dir / pat))
        files.extend(matches)

    # Convertir el string a Path y filtrar sólo archivos regulares
    paths = [Path(p).resolve() for p in files if Path(p).is_file()]
    # Ordenamos para reproducibilidad
    paths.sort()
    return paths


def _open_file(path: Path): 
    """
    Abre un fichero con la codificación y la estrategia de errores definidas en config.
    Devuelve un objeto file (context manager).
    """
    return open(path, mode="r", encoding=config.ENCODING, errors=config.OPEN_ERRORS_STRATEGY)


def chunk_file_lines(
    file_path: Path,
    lines_per_chunk: Optional[int] = None,
) -> Iterator[Tuple[int, List[str]]]:
    """
    Generador que itera por fragmentos de un fichero.
    - file_path: Path del fichero a leer
    - lines_per_chunk: número de líneas por fragmento (si None, usa DEFAULT_LINES_PER_CHUNK)
    Devuelve tuplas (chunk_index, lines_list), donde chunk_index empieza en 0.
    Lectura en streaming: no carga todo el fichero en memoria.

    lines_per_chunk si es None coge valor por defecto y si es un valor indicado, valida que sea un entero positivo
    """
    lines_per_chunk = config.DEFAULT_LINES_PER_CHUNK if lines_per_chunk is None else config.validate_positive_int("lines_per_chunk", lines_per_chunk)

    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"Fichero no encontrado: {file_path}")

    chunk = []
    idx = 0
    # El bloque with asegura que el archivo se cierre automáticamente al terminar, incluso si hay errores
    with _open_file(file_path) as f:
        for line in f:
            # rstrip borra el salto de linea al final
            chunk.append(line.rstrip("\n"))
            if len(chunk) >= lines_per_chunk:
                yield idx, chunk
                idx += 1
                chunk = []
        # yield del último fragmento si tiene contenido
        if chunk:
            yield idx, chunk


def iter_chunks_from_dir(
    lines_per_chunk: Optional[int] = None,
    patterns: Optional[List[str]] = None,
) -> Iterator[Tuple[Path, int, List[str]]]:
    """
    Generador que itera por todos los ficheros del directorio de logs y sus fragmentos.
    Devuelve (file_path, chunk_index, lines_list).
    Útil para alimentar una cola de trabajos en multiprocessing.
    """
    files = list_log_files(patterns)
    if not files:
        logger.warning("No se encontraron ficheros de log en %s", config.LOG_DIR)
    for p in files:
        for chunk_index, lines in chunk_file_lines(p, lines_per_chunk):
            yield p, chunk_index, lines


def count_lines_in_file(file_path: Path) -> int:
    """Cuenta de forma eficiente el número total de líneas de un fichero."""
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"Fichero no encontrado: {file_path}")
    count = 0
    with _open_file(file_path) as f:
        for _ in f:
            count += 1
    return count


def is_file_empty(file_path: Path) -> bool:
    """Devuelve True si el fichero existe y tiene 0 líneas (o está vacío)."""
    return count_lines_in_file(file_path) == 0


def parse_log_line(line: str) -> Optional[Dict[str, str]]:
    """
    Intento simple y seguro de parsear una línea de log con la estructura esperada:
    'YYYY-MM-DD HH:MM:SS,ms [LEVEL] IP mensaje...'
    Devuelve dict con keys: 'datetime', 'level', 'ip', 'message' o None si no cumple.
    NOTA: Esto es un parser sencillo para usar en análisis; para logs más complejos se recomienda usar regex más completas.
    """
    try:
        # separación básica: fecha, resto
        # ejemplo: "2025-10-08 08:32:15,124 [INFO] 192.168.1.10 User 'admin' ..."
        parts = line.split(" ", 3)
        if len(parts) < 4:
            return None
        datetime_part = f"{parts[0]} {parts[1]}"
        # parts[2] debería ser '[LEVEL]'
        level_part = parts[2].strip()
        # extraer ip y mensaje
        rest = parts[3].strip()
        # rest empieza por 'IP ...' en el formato esperado
        rest_parts = rest.split(" ", 1)
        ip_part = rest_parts[0] if rest_parts else ""
        message_part = rest_parts[1] if len(rest_parts) > 1 else ""

        return {
            "datetime": datetime_part,
            "level": level_part.strip("[]"),
            "ip": ip_part,
            "message": message_part,
        }
    except Exception:
        # parser seguro: no lanza excepciones al usuario
        return None
