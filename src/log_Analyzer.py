import os, re, json, time, fnmatch, multiprocessing, threading, logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import psutil

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

#Expresiones regulares(IPV4,Logs,Fechas)
IP_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
LEVEL_RE = re.compile(r"\b(INFO|WARN(?:ING)?|ERROR)\b", re.I)
DATE_DAY_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")

def worker_entry(state: dict, task_queue, result_queue):
    while True:
        chunk = task_queue.get()
        if chunk is None:
            break
        total = 0
        by_level = {"INFO": 0, "WARNING": 0, "ERROR": 0}
        ips: Dict[str,int] = {}
        errors_by_day: Dict[str,int] = {}

        for line in chunk:
            total += 1
            if not line:
                continue
            m = LEVEL_RE.search(line)
            if m:
                lvl = m.group(1).upper()
                if lvl.startswith("WARN"):
                    lvl = "WARNING"
                if lvl not in by_level:
                    continue
                by_level[lvl] += 1

            im = IP_RE.search(line)
            if im:
                ip = im.group(0)
                ips[ip] = ips.get(ip, 0) + 1

            if re.search(r"\bERROR\b", line, re.I):
                dm = DATE_DAY_RE.search(line)
                if dm:
                    day = dm.group(1)
                    errors_by_day[day] = errors_by_day.get(day, 0) + 1

        result_queue.put({
            "total_lines": total,
            "by_level": by_level,
            "ip_counts": ips,
            "errors_by_day": errors_by_day
        })

class LogAnalyzer:
    
    def __init__(self,
                 log_dir: str,
                 lines_per_chunk: int =300,
                 workers: int = 4,
                 encoding: str = "utf-8",
                 monitor: bool = True,
                 patterns: Optional[List[str]] = None,
                 open_errors_strategy: str = "replace",
                 info_dir: Optional[str] = None,
                 output: Optional[str] = None):
        self.log_dir = log_dir
        self.lines_per_chunk = max(1, int(lines_per_chunk))
        self.workers = max(1, int(workers))
        self.encoding = encoding
        self.monitor = bool(monitor)
        self.patterns = patterns or ["*.log"]
        self.open_errors_strategy = open_errors_strategy
        self.info_dir = info_dir or os.path.join(os.getcwd(), "info")

        os.makedirs(self.info_dir, exist_ok=True)
        self.output = output or os.path.join(self.info_dir, "resultado.json")

        if not os.path.isdir(self.log_dir):
            raise FileNotFoundError(f"Directorio Logs no encontrado: {self.log_dir}")

    def _start_monitor(self, worker_pids: Optional[List[int]] = None, interval: float = 1.0):

        if psutil is None:
            raise RuntimeError("psutil no está instalado. Instale con: pip install psutil")

        stop = {"run": True}

        def _mon():

            psutil.cpu_percent(interval=None)

            proc_objs = {}
            while stop["run"]:
                try:
                    
                    cpu = psutil.cpu_percent(interval=None)
                    mem = psutil.virtual_memory().percent
                    msg = f"MONITOR — CPU_sistema: {cpu:.1f}%  MEM_sistema: {mem:.1f}%"
                    if worker_pids:
                        per_proc = []
                        for pid in worker_pids:
                            try:
                                p = proc_objs.get(pid) or psutil.Process(pid)
                                proc_objs[pid] = p
                                p_cpu = p.cpu_percent(interval=None)
                                p_rss = p.memory_info().rss / (1024 * 1024)
                                per_proc.append(f"PID {pid}: CPU {p_cpu:.1f}% MEM {p_rss:.1f}MB")
                            except psutil.NoSuchProcess:
                                per_proc.append(f"PID {pid}: terminado")
                            except Exception:
                                per_proc.append(f"PID {pid}: métricas no disponibles")
                        if per_proc:
                            msg += " — " + " | ".join(per_proc)
                    logger.info(msg)
                except Exception as e:
                    logger.exception("Error en monitor: %s", e)
                time.sleep(interval)

        # Creacion de un hilos para ejecutar la monitorización
        th = threading.Thread(target=_mon, daemon=True)
        th._stop_flag = stop
        th.start()
        return th

    def analyze(self) -> Dict[str, Any]:

        ctx = multiprocessing.get_context()
        task_q = ctx.Queue(maxsize=self.workers * 4)
        result_q = ctx.Queue()
        workers = []
        state = {"encoding": self.encoding, "open_errors_strategy": self.open_errors_strategy}

        for i in range(self.workers):
            p = ctx.Process(target=worker_entry, args=(state, task_q, result_q))
            p.start()
            workers.append(p)

            try:
                rss = psutil.Process(p.pid).memory_info().rss / (1024 * 1024) if psutil else None
            except Exception:
                rss = None

            if psutil:
                try:
                    cpu_now = psutil.cpu_percent(interval=None)
                    mem_now = psutil.virtual_memory().percent
                    if rss is not None:
                        logger.info("Worker %d (PID %d) — CPU_sistema: %.1f%%  MEM_total: %.1f%%  MEM_proc: %.1f MB",
                                    i+1, p.pid, cpu_now, mem_now, rss)
                    else:
                        logger.info("Worker %d (PID %d) — CPU_sistema: %.1f%%  MEM_total: %.1f%%  MEM_proc: n/d",
                                    i+1, p.pid, cpu_now, mem_now)
                except Exception:
                    logger.info("Worker %d (PID %d) — métricas no disponibles", i+1, p.pid)
            else:
                logger.info("Worker %d (PID %d) — psutil no instalado", i+1, p.pid)

        mon_thread = None
        if self.monitor:
            if psutil is None:

                raise RuntimeError("Psutil no disponible. Instale psutil: pip install psutil")
            worker_pids = [p.pid for p in workers if p.pid is not None]
            mon_thread = self._start_monitor(worker_pids, 1.0)

        files = 0
        chunks_sent = 0
        for fname in sorted(os.listdir(self.log_dir)):
            if not any(fnmatch.fnmatch(fname, pat) for pat in self.patterns):
                continue
            path = os.path.join(self.log_dir, fname)
            if not os.path.isfile(path):
                continue
            files += 1
            try:
                with open(path, "r", encoding=self.encoding, errors=self.open_errors_strategy) as fh:
                    buf: List[str] = []
                    for line in fh:
                        buf.append(line)
                        if len(buf) >= self.lines_per_chunk:
                            task_q.put(buf)
                            chunks_sent += 1
                            if chunks_sent % 100 == 0:
                                logger.info("Chunks enviados=%d (archivo=%s)", chunks_sent, fname)
                            buf = []
                    if buf:
                        task_q.put(buf)
                        chunks_sent += 1
            except Exception as e:
                logger.exception("Error leyendo %s: %s", path, e)

        logger.info("Productor finalizado: archivos=%d, chunks=%d", files, chunks_sent)
        for _ in workers:
            task_q.put(None)

        partials: List[Dict[str,Any]] = []
        import queue as _q
        alive = len(workers)
        while alive > 0:
            try:
                part = result_q.get(timeout=1.0)
                partials.append(part)
            except _q.Empty:
                alive = sum(1 for p in workers if p.is_alive())

        try:
            while True:
                partials.append(result_q.get_nowait())
        except Exception:
            pass

        for p in workers:
            p.join(timeout=2.0)

        if mon_thread:
            mon_thread._stop_flag["run"] = False
            mon_thread.join(timeout=1.0)

        return self._merge(partials)

    def _merge(self, parts: List[Dict[str,Any]]) -> Dict[str,Any]:
        total = 0
        levels = {"INFO": 0, "WARNING": 0, "ERROR": 0}
        ips: Dict[str,int] = {}
        errors_by_day: Dict[str,int] = {}

        for p in parts:
            total += p.get("total_lines", 0)
            for k in levels.keys():
                levels[k] += p.get("by_level", {}).get(k, 0)
            for ip, c in p.get("ip_counts", {}).items():
                ips[ip] = ips.get(ip, 0) + c
            for d, c in p.get("errors_by_day", {}).items():
                errors_by_day[d] = errors_by_day.get(d, 0) + c

        top_ips = [{"ip": ip, "count": cnt} for ip, cnt in sorted(ips.items(), key=lambda x: x[1], reverse=True)[:10]]

        return {
            "lines_total": total,
            "by_level": levels,
            "top_10_ips": top_ips,
            "ip_counts": ips,
            "errors_by_day": errors_by_day
        }
    
    @staticmethod
    def save_json_report(acc: Dict[str,Any], outfile: str, params: Optional[Dict[str,Any]] = None) -> str:
        params = params or {}
        report = {"meta": {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "params": params},
                  "data": acc}
        base, ext = os.path.splitext(outfile)
        if not ext:
            ext = ".json"
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        out = f"{base}_{ts}{ext}"
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

        with open(out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)
        logger.info("Informe JSON guardado en %s", out)
        return out
