import random
import datetime
import os

# configuracion
NUM_LOGS = 1000
LOG_FOLDER = os.path.join(os.path.dirname(__file__), "../logs")
LOG_FILENAME = "system_logs.log"

levels = ["INFO", "WARNING", "ERROR"]
ips = [f"192.168.1.{i}" for i in range(10, 30)]
messages = [
    "User 'admin' logged in successfully.",
    "Disk usage at 85% on /dev/sda1.",
    "Failed to connect to database 'inventory'.",
    "Scheduled backup completed in 32.4 seconds.",
    "HTTP request from {ip}:200 GET /api/items 200 OK",
    "Unexpected end of file while reading config.yaml.",
    "CPU temperature high (87°C).",
    "User 'guest' requested resource /public/info.",
    "Service 'nginx' restarted successfully.",
    "Permission denied accessing /var/www/html.",
    "Low memory detected: only 512MB free.",
    "Network latency detected on {ip}.",
    "Backup failed: insufficient disk space.",
    "Configuration file /etc/app/config.yaml updated.",
    "Database 'users' synchronized successfully."
]
# Crea carpeta si no existe
os.makedirs(LOG_FOLDER, exist_ok=True)

# Ruta del archivo
file_path = os.path.join(LOG_FOLDER, LOG_FILENAME)

# Generador de logs
with open(file_path, "w", encoding="utf-8") as log_file:
    for _ in range(NUM_LOGS):
        
        date = datetime.date(
            2025,
            random.randint(1, 12),
            random.randint(1, 28)
        ).strftime("%Y-%m-%d")

        level = random.choice(levels)
        ip = random.choice(ips)
        msg_template = random.choice(messages)
        message = msg_template.format(ip=ip)

        log_file.write(f"{date} [{level}] {ip} {message}\n")

print(f"✅ Archivo '{LOG_FILENAME}' generado con {NUM_LOGS} registros en la carpeta '{LOG_FOLDER}'.")
