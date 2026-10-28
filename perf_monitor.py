"""perf_monitor.py - วัด latency + CPU/RAM/อุณหภูมิ Pi ระหว่างที่ Ollama ประเมิน
วางไว้โฟลเดอร์เดียวกับ app.py   (pip install psutil --break-system-packages)
"""
import csv
import os
import statistics
import subprocess
import threading
import time
from datetime import datetime

import psutil

LOG_FILE = "perf_log.csv"


def _vcgencmd(*args):
    """เรียก vcgencmd (มีเฉพาะบน Raspberry Pi) ถ้าไม่มีคืน None"""
    try:
        out = subprocess.check_output(["vcgencmd", *args], stderr=subprocess.DEVNULL).decode().strip()
        return out.split("=", 1)[1]
    except Exception:
        return None


def read_temp():
    v = _vcgencmd("measure_temp")
    try:
        return float(v.replace("'C", ""))
    except Exception:
        return None


def read_clock_mhz():
    v = _vcgencmd("measure_clock", "arm")
    try:
        return int(v) / 1e6
    except Exception:
        return None


class PiMonitor:
    """เก็บตัวอย่างทุก `interval` วินาทีใน background thread"""

    def __init__(self, interval=0.5):
        self.interval = interval
        self._stop = threading.Event()
        self._thread = None
        self.cpu, self.ram, self.temp, self.clock = [], [], [], []

    def _loop(self):
        psutil.cpu_percent(interval=None)  # prime
        while not self._stop.is_set():
            time.sleep(self.interval)
            self.cpu.append(psutil.cpu_percent(interval=None))
            self.ram.append(psutil.virtual_memory().percent)
            t, c = read_temp(), read_clock_mhz()
            if t is not None:
                self.temp.append(t)
            if c is not None:
                self.clock.append(c)

    def start(self):
        self.temp_start = read_temp()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        avg = lambda xs: round(statistics.mean(xs), 1) if xs else None
        mx = lambda xs: round(max(xs), 1) if xs else None
        return {
            "cpu_avg": avg(self.cpu), "cpu_max": mx(self.cpu),
            "ram_avg": avg(self.ram), "ram_max": mx(self.ram),
            "temp_start": self.temp_start, "temp_max": mx(self.temp),
            "clock_min": round(min(self.clock)) if self.clock else None,
            "throttled": _vcgencmd("get_throttled"),
            "samples": len(self.cpu),
        }


def run_with_monitor(post_fn, *args, interval=0.5, **kwargs):
    """ครอบ requests.post: คืน (response, stats) โดย stats มี wall-clock + ค่า Pi"""
    mon = PiMonitor(interval)
    mon.start()
    t0 = time.perf_counter()
    try:
        response = post_fn(*args, **kwargs)
    finally:
        wall = time.perf_counter() - t0
        stats = mon.stop()
    stats["wall_s"] = round(wall, 2)
    return response, stats


def log_perf(case_id, stats, ollama_json=None, model=""):
    """พิมพ์สรุปลง terminal + ต่อท้ายไฟล์ perf_log.csv + คืนข้อความสั้นสำหรับโชว์ในเว็บ"""
    d = ollama_json or {}
    ns = 1e9
    load_s = d.get("load_duration", 0) / ns
    prompt_s = d.get("prompt_eval_duration", 0) / ns
    gen_s = d.get("eval_duration", 0) / ns
    toks = d.get("eval_count", 0)
    tok_s = toks / gen_s if gen_s else 0.0
    thr = stats["throttled"]
    thr_txt = "N/A" if thr is None else (f"{thr} OK" if thr == "0x0" else f"{thr} WARNING")

    print("\n" + "=" * 52)
    print(f" PERFORMANCE  case #{case_id}   model: {model}")
    print("-" * 52)
    print(f" Latency (wall-clock) : {stats['wall_s']:7.2f} s")
    print(f"   - Load model       : {load_s:7.2f} s")
    print(f"   - Prompt eval      : {prompt_s:7.2f} s ({d.get('prompt_eval_count', 0)} tok)")
    print(f"   - Generate         : {gen_s:7.2f} s ({toks} tok)")
    print(f" Speed                : {tok_s:7.2f} tokens/s")
    print(f" CPU   avg / max      : {stats['cpu_avg']} / {stats['cpu_max']} %")
    print(f" RAM   avg / max      : {stats['ram_avg']} / {stats['ram_max']} %")
    print(f" Temp  start / max    : {stats['temp_start']} / {stats['temp_max']} C")
    print(f" CPU clock (min)      : {stats['clock_min']} MHz (ปกติ 1500)")
    print(f" Throttled            : {thr_txt}")
    print("=" * 52, flush=True)

    new_file = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["time", "case_id", "model", "wall_s", "load_s", "prompt_s", "gen_s",
                        "tokens", "tok_per_s", "cpu_avg", "cpu_max", "ram_avg", "ram_max",
                        "temp_start", "temp_max", "clock_min", "throttled"])
        w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), case_id, model,
                    stats["wall_s"], round(load_s, 2), round(prompt_s, 2), round(gen_s, 2),
                    toks, round(tok_s, 2), stats["cpu_avg"], stats["cpu_max"],
                    stats["ram_avg"], stats["ram_max"], stats["temp_start"],
                    stats["temp_max"], stats["clock_min"], thr])

    return (f"⏱️ {stats['wall_s']:.1f} วินาที | {tok_s:.1f} tok/s | "
            f"CPU สูงสุด {stats['cpu_max']}% | RAM {stats['ram_max']}% | "
            f"อุณหภูมิสูงสุด {stats['temp_max']}°C")