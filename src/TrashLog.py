import os
import shutil
import time
import logging

class TrashEngine:
    def __init__(self):
        self.trash_path = os.path.expanduser("~/.local/share/Trash")
        self.log_path = os.path.expanduser("~/.config/trashguard/trashguard.log")
        
        # Logging initialisieren
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        logging.basicConfig(
            filename=self.log_path,
            level=logging.INFO,
            format='%(asctime)s - %(message)s',
            datefmt='%d.%m.%Y %H:%M:%S'
        )

    def get_trash_size(self):
        """Berechnet die aktuelle Größe des Papierkorbs in Bytes."""
        total_size = 0
        files_path = os.path.join(self.trash_path, "files")
        if not os.path.exists(files_path):
            return 0
            
        for dirpath, dirnames, filenames in os.walk(files_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
        return total_size

    def enforce_limit(self, settings):
        """Überprüft das Limit und löscht bei Bedarf die ältesten Dateien."""
        # Falls der Dienst deaktiviert wurde, brechen wir ab
        if not settings.get("service_enabled", False):
            return

        # Limit ermitteln (Prozent oder GB)
        total_disk, _, _ = shutil.disk_usage("/")
        
        if settings.get("use_percentage", False):
            limit_bytes = (total_disk * settings.get("percent_val", 10)) / 100
        else:
            limit_bytes = settings.get("fixed_gb_val", 2.0) * (1024**30)

        current_size = self.get_trash_size()

        if current_size > limit_bytes:
            logging.info(f"Limit überschritten: {current_size/(1024**30):.2f} GB > {limit_bytes/(1024**30):.2f} GB. Starte Bereinigung...")
            self.cleanup(limit_bytes)
        else:
            # Optional: Nur für Debugging, sonst wird das Log zu voll
            # logging.info("Papierkorb im grünen Bereich.")
            pass

    def cleanup(self, limit_bytes):
        """Löscht Dateien nach Alter (älteste zuerst), bis das Limit unterschritten ist."""
        files_path = os.path.join(self.trash_path, "files")
        info_path = os.path.join(self.trash_path, "info")
        
        if not os.path.exists(files_path):
            return

        # Liste aller Dateien mit Zeitstempel erstellen
        items = []
        for name in os.listdir(files_path):
            p = os.path.join(files_path, name)
            items.append((p, os.path.getmtime(p), name))

        # Nach Zeitstempel sortieren (älteste zuerst)
        items.sort(key=lambda x: x[1])

        current_size = self.get_trash_size()
        
        for item_path, _, item_name in items:
            if current_size <= limit_bytes:
                break
                
            try:
                item_size = os.path.getsize(item_path)
                
                # Datei/Ordner löschen
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
                
                # Zugehörige .trashinfo Datei löschen
                info_file = os.path.join(info_path, item_name + ".trashinfo")
                if os.path.exists(info_file):
                    os.remove(info_file)
                
                current_size -= item_size
                logging.info(f"Gelöscht: {item_name} ({item_size / (1024**2):.2f} MB)")
                
            except Exception as e:
                logging.error(f"Fehler beim Löschen von {item_name}: {e}")