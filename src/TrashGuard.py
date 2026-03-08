#!/usr/bin/env python3
import time
import os
import sys
import json
import datetime
import signal
import shutil

# Pfade definieren
CONFIG_DIR = os.path.expanduser("~/.config/trashguard")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
DEBUG_FLAG = os.path.join(CONFIG_DIR, "debug.trashguard")
DAEMON_LOG = os.path.join(CONFIG_DIR, "trashguard_daemon_log.txt")
CLEANING_LOG = os.path.join(CONFIG_DIR, "trashguard_cleaning_log.txt")

TRASH_FILES = os.path.expanduser("~/.local/share/Trash/files")
TRASH_INFO = os.path.expanduser("~/.local/share/Trash/info")

class TrashGuardDaemon:
    def __init__(self):
        self.running = True
        self.max_log_size = 20 * 1024 * 1024  # 20 MB Limit
        self.keep_lines = 100                 # Zeilen, die bei Rotation bleiben
        
        # Signale für sauberes Beenden (SIGTERM von System/GUI)
        signal.signal(signal.SIGTERM, self.handle_exit)
        signal.signal(signal.SIGINT, self.handle_exit)
        
        os.makedirs(CONFIG_DIR, exist_ok=True)
        self.log_daemon("Daemon initialized. Standing by.")

    def _rotate_log(self, log_path):
        """Hält die Logfiles unter 20MB und bewahrt die letzten 100 Zeilen."""
        if os.path.exists(log_path) and os.path.getsize(log_path) > self.max_log_size:
            try:
                with open(log_path, "r", errors='ignore') as f:
                    lines = f.readlines()
                
                new_content = lines[-self.keep_lines:]
                
                with open(log_path, "w") as f:
                    f.write(f"--- Log rotated on {datetime.datetime.now()} (Kept last {self.keep_lines} lines) ---\n")
                    f.writelines(new_content)
            except Exception as e:
                print(f"Rotation failed for {log_path}: {e}")

    def log_daemon(self, message):
        """System-Status Log (Englisch)."""
        self._rotate_log(DAEMON_LOG)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(DAEMON_LOG, "a") as f:
            f.write(f"[{timestamp}] {message}\n")

    def log_cleaning(self, message):
        """Lösch-Protokoll Log (Englisch)."""
        self._rotate_log(CLEANING_LOG)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(CLEANING_LOG, "a") as f:
            f.write(f"[{timestamp}] {message}\n")

    def handle_exit(self, signum, frame):
        self.log_daemon(f"Shutdown signal ({signum}) received.")
        self.running = False

    def load_config(self):
        """Lädt die config.json sicher ein."""
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r") as f:
                    return json.load(f)
        except Exception as e:
            self.log_daemon(f"Config load error: {e}")
        return None

    def get_trash_size(self):
        """Größe des Papierkorbs in Bytes."""
        total_size = 0
        if os.path.exists(TRASH_FILES):
            for dirpath, dirnames, filenames in os.walk(TRASH_FILES):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.exists(fp):
                        total_size += os.path.getsize(fp)
        return total_size

    def get_free_disk_percent(self):
        """Freier Speicherplatz auf / in Prozent."""
        total, used, free = shutil.disk_usage("/")
        return (free / total) * 100

    def clean_trash(self, strategy, target_size_bytes):
        """Lösch-Vorgang nach gewählter Strategie."""
        if not os.path.exists(TRASH_FILES): return
        
        files = []
        for f in os.listdir(TRASH_FILES):
            file_path = os.path.join(TRASH_FILES, f)
            if os.path.exists(file_path):
                files.append({
                    'name': f,
                    'path': file_path,
                    'size': os.path.getsize(file_path),
                    'mtime': os.path.getmtime(file_path)
                })

        # Sortierung basierend auf Strategie-String
        if strategy == "strat_oldest":
            files.sort(key=lambda x: x['mtime'])
            strat_name = "Oldest First"
        elif strategy == "strat_biggest":
            files.sort(key=lambda x: x['size'], reverse=True)
            strat_name = "Biggest First"
        else:
            import random
            random.shuffle(files)
            strat_name = "Random Selection"

        self.log_cleaning(f"Cleaning triggered. Strategy: {strat_name}")
        
        freed_space = 0
        deleted_count = 0
        
        for file_obj in files:
            # Stoppen, wenn Zielgröße erreicht
            if self.get_trash_size() <= target_size_bytes:
                break
                
            try:
                # 1. Die echte Datei löschen
                os.remove(file_obj['path'])
                
                # 2. Die dazugehörige .trashinfo löschen
                info_path = os.path.join(TRASH_INFO, file_obj['name'] + ".trashinfo")
                if os.path.exists(info_path):
                    os.remove(info_path)
                
                size_mb = file_obj['size'] / (1024 * 1024)
                self.log_cleaning(f"DELETED: {file_obj['name']} ({size_mb:.2f} MB)")
                freed_space += file_obj['size']
                deleted_count += 1
            except Exception as e:
                self.log_daemon(f"Error deleting {file_obj['name']}: {e}")

        self.log_cleaning(f"Finished. Deleted: {deleted_count} files. Freed: {(freed_space/(1024*1024)):.2f} MB.")

    def run(self):
        self.log_daemon(f"Daemon started. PID: {os.getpid()}")
        
        # Mapping für das Intervall (Index aus GUI zu Minuten)
        interval_map = {0: 30, 1: 60, 2: 1440, 3: 10080}
        # Mapping für Lösch-Strategien (Index aus GUI zu String)
        strategy_map = {0: "strat_oldest", 1: "strat_biggest", 2: "strat_random"}

        while self.running:
            is_debug = os.path.exists(DEBUG_FLAG)
            config = self.load_config()
            
            if not config:
                time.sleep(10)
                continue

            # 1. Intervall bestimmen (Mapping von interval_idx)
            idx = config.get("interval_idx", 1)
            if is_debug:
                interval_seconds = 5
                self.log_daemon("DEBUG MODE: 5s interval active.")
            else:
                interval_seconds = interval_map.get(idx, 60) * 60

            # 2. Werte ermitteln
            trash_size_bytes = self.get_trash_size()
            trash_gb = trash_size_bytes / (1024**3)
            free_disk_pct = self.get_free_disk_percent()
            
            self.log_daemon(f"Scan: {trash_gb:.2f} GB in trash, {free_disk_pct:.1f}% disk free.")

            # 3. Grenzwerte aus GUI-Variablen prüfen
            limit_gb = float(config.get("fixed_gb_val", 2.0))
            use_fixed = config.get("use_fixed", True)
            
            # Ziel ist 90% des Limits
            target_size_bytes = (limit_gb * 0.9) * (1024**3) 
            
            should_clean = False
            
            if not use_fixed: # Dynamisches Prozent-Limit aktiv
                pct_limit = float(config.get("percent_val", 10.0))
                if free_disk_pct < pct_limit:
                    self.log_cleaning(f"Threshold met: Disk free ({free_disk_pct:.1f}%) < Limit ({pct_limit}%).")
                    should_clean = True
            else: # Fixer GB-Wert aktiv
                if trash_gb > limit_gb:
                    self.log_cleaning(f"Threshold met: Trash ({trash_gb:.2f} GB) > Limit ({limit_gb} GB).")
                    should_clean = True

            if should_clean:
                # Strategie-Index in String umwandeln
                strat_idx = config.get("del_strategy_idx", 0)
                strat_name = strategy_map.get(strat_idx, "strat_oldest")
                self.clean_trash(strat_name, target_size_bytes)

            # Warten (unterbrechbar alle 5 Sek)
            for _ in range(max(1, interval_seconds // 5)):
                if not self.running: break
                time.sleep(5)

        self.log_daemon("Daemon shut down safely.")

if __name__ == "__main__":
    if "--daemon" in sys.argv:
        daemon = TrashGuardDaemon()
        daemon.run()
    else:
        print("TrashGuard Daemon: Please use --daemon flag to start.")