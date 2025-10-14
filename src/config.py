import os

# Carpeta donde buscar los archivos de log
LOG_DIR = os.path.join(os.getcwd(), "logs")

# Patrones de ficheros que consideraremos logs
LOG_PATTERNS = ["*.log"]

# Archivo donde se guardará el informe final
OUTPUT_FILE = os.path.join(os.getcwd(), "resultado.json")

# Número de líneas por fragmento
DEFAULT_LINES_PER_CHUNK = 1000

# Número máximo de procesos en paralelo
DEFAULT_MAX_WORKERS = 4

# Codificación al leer los ficheros
ENCODING = "utf-8"
OPEN_ERRORS_STRATEGY = "replace"

# Funciones de validación simples
def validate_positive_int(name: str, value):
    """Valida que value sea int >= 1"""
    if not isinstance(value, int):
        raise ValueError(f"{name} debe ser un entero. Valor: {value!r}")
    if value < 1:
        raise ValueError(f"{name} debe ser >= 1. Valor: {value}")
    return value

def ensure_log_dir_exists():
    """Devuelve True si LOG_DIR existe y es un directorio; False si no"""
    return os.path.isdir(LOG_DIR)
