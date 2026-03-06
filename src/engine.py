import os
import shutil

class TrashEngine:
    def __init__(self):
        # Der Standardpfad für den Papierkorb unter fast allen Linux-Distributionen
        self.trash_path = os.path.expanduser("~/.local/share/Trash/files")

    def get_trash_size(self):
        """Berechnet die aktuelle Größe des Papierkorbs in Bytes."""
        total_size = 0
        if os.path.exists(self.trash_path):
            for dirpath, dirnames, filenames in os.walk(self.trash_path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    # Überspringe Dateien, die während der Berechnung gelöscht werden
                    if os.path.exists(fp):
                        total_size += os.path.getsize(fp)
        return total_size

    def get_system_info(self):
        """Holt Informationen über den Speicherplatz im Home-Verzeichnis."""
        # shutil.disk_usage gibt uns (total, used, free) in Bytes
        stats = shutil.disk_usage(os.path.expanduser("~"))
        return {
            "free_gb": stats.free / (1024**3),
            "total_gb": stats.total / (1024**3),
            "free_percent": (stats.free / stats.total) * 100
        }

# Kleiner Testlauf, wenn man die Datei direkt ausführt
if __name__ == "__main__":
    engine = TrashEngine()
    info = engine.get_system_info()
    
    trash_mb = engine.get_trash_size() / (1024**2)
    
    print("--- TrashGuard Engine Test ---")
    print(f"Papierkorb-Größe: {trash_mb:.2f} MB")
    print(f"Freier Speicherplatz: {info['free_gb']:.2f} GB ({info['free_percent']:.1f}%)")
