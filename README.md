#  Documentación Analizador_Paralelo_de_logs

## Clase `LogAnalyzer`

### Descripción
Clase principal encargada de analizar archivos de logs de forma paralela utilizando múltiples procesos (`workers`)
.Divide los ficheros en fragmentos (`chunks`), lanza los procesos, recoge resultados y genera un informe en formato JSON.

## Función externa `worker_entry(state, task_queue, result_queue)`

Ejecuta el análisis de cada bloque de líneas.  
**Entrada:**  
- `state (dict)`: datos compartidos.  
- `task_queue (Queue)`: cola con listas de líneas a procesar.  
- `result_queue (Queue)`: cola donde se envían los resultados.


---

## Métodos

### `__init__(self, log_dir, lines_per_chunk=300, workers=4, encoding="utf-8", monitor=False, patterns=None, info_dir="info", output="info.json")` (valores por defecto)
Inicializa la clase con los parámetros necesario y as estancias.  
**Entrada:** parámetros de configuración del análisis

---

### `_start_monitor(self, worker_pids: Optional[List[int]] = None, interval: float = 1.0)`
Inicia un **hilo** que monitoriza el sistema y los procesos usando `psutil`.  
**Entrada:**  
- `worker_pids: Optional[List[int]]` — lista de PIDs de los procesos a monitorizar 
- `interval: float` — intervalo en segundos entre muestras (por defecto `1.0`)


--- 

### ``analyze(self) -> Dict[str, Any]`
Se realiza el análisis paralelo de logs
- Crea procesos worker
- Reparte chunks de líneas mediante una cola
- Devuelve el resultado agregado.  
**Salida:** `Dict[str, Any]` — diccionario con estadísticas agregadas 

---

### `_mergue(self, parts: List[Dict[str,Any]])`  
Combina los resultados parciales generados por los workers.    
**Entrada:** lista de diccionarios (`list[dict]`) con estadísticas parciales.  
**Salida:** diccionario (`dict`) con todas las listas de cada worker juntas.  

---

### `save_json_report(self, results)`  
Guarda los resultados del análisis en un archivo JSON dentro de `/info`  
**Entrada:** diccionario (`dict`) devuelto por `_mergue()`  
**Salida:** ruta del archivo creado  


---



## Debug de la aplicacion (consola)
#### Se inicia la aplicación principal y se carga la configuración completa del analizador:
```bash
10:35:05 INFO: Configuración: {
    'log_dir': 'c:\\Users\\carlo\\.vscode\\Analizador_paralelo_de_logs\\logs',
    'lines_per_chunk': 100,
    'workers': 4,
    'encoding': 'utf-8',
    'monitor': True,
    'patterns': ['*.log'],
    'open_errors_strategy': 'replace',
    'info_dir': 'c:\\Users\\carlo\\.vscode\\Analizador_paralelo_de_logs\\info',
    'output': 'c:\\Users\\carlo\\.vscode\\Analizador_paralelo_de_logs\\info\\resultado.json'
}
```

####   Se crean los 4 workers (procesos hijos). En este momento el monitor detecta su PID y mide su CPU y memoria inicial
####   Cada línea muestra el consumo del sistema (CPU_sistema, MEM_total) y de cada worker (MEM_proc)

```bash
10:35:05 INFO: Worker 1 (PID 17448) — CPU_sistema: 26.1%  MEM_total: 43.5%  MEM_proc: 1.5 MB
10:35:05 INFO: Worker 2 (PID 11752) — CPU_sistema: 0.0%  MEM_total: 43.5%  MEM_proc: 1.5 MB 
10:35:05 INFO: Worker 3 (PID 6868)  — CPU_sistema: 100.0% MEM_total: 43.5% MEM_proc: 1.6 MB
10:35:05 INFO: Worker 4 (PID 9392)  — CPU_sistema: 50.0%  MEM_total: 43.5% MEM_proc: 1.5 MB
```
#### Cada intervalo de tiempo marcado, en nuestro caso 1s, se monitorea tambien del uso de memoria y del consumo de cada proceso 
#### Los workers aún no están procesando datos, por eso su CPU está al 0%

```bash
10:35:06 INFO: MONITOR — CPU_sistema: 0.0%  MEM_sistema: 43.5% —
PID 17448: CPU 0.0% MEM 10.8MB | PID 11752: CPU 0.0% MEM 9.9MB | PID 6868: CPU 0.0% MEM 9.1MB | PID 9392: CPU 0.0% MEM 7.9MB
```

#### Aquí el proceso principal (Productor) termina de dividir los archivos en ("chunks") y las envía a los workers
#### Luego, los workers comienzan a analizar los datos en paralelo

```bash
10:35:06 INFO: Productor finalizado: archivos=1, chunks=10
```

#### El monitor detecta que los procesos han terminado su trabajo
#### Todos los PID aparecen como "terminado", lo que indica que el análisis paralelo ha finalizado

```bash
10:35:07 INFO: MONITOR — CPU_sistema: 42.6%  MEM_sistema: 44.2% —
PID 17448: terminado | PID 11752: terminado | PID 6868: terminado | PID 9392: terminado
```

#### Una vez que todos los procesos finalizan, se genera y guarda el informe JSON con los resultados del análisis
```bash
10:35:08 INFO: Informe JSON guardado en c:\Users\carlo\.vscode\Analizador_paralelo_de_logs\info\resultado_20251105T103508.json
```
#### El sistema informa el tiempo total de ejecución y la ubicación del archivo de salida
```bash
10:35:08 INFO: Análisis completado en 2.13 s.
Salida: c:\Users\carlo\.vscode\Analizador_paralelo_de_logs\info\resultado_20251105T103508.json
```
