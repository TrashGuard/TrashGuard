#!/usr/bin/env python3
import time
import os
import datetime

# Um zu sehen, ob der Dämon läuft, lassen wir ihn eine kleine Log-Datei schreiben
LOG_FILE = os.path.expanduser("~/.config/trashguard/trashguard_daemon_log.txt")

def main():
    # Ordner erstellen, falls er nicht existiert
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    
    with open(LOG_FILE, "a") as f:
        f.write(f"[{datetime.datetime.now()}] Dämon-Prozess wurde gestartet.\n")

    try:
        while True:
            # Der Dämon "lebt" und schläft 10 Sekunden
            # In dieser Zeit kannst du im System-Monitor nach "TrashGuard.py" suchen
            time.sleep(10)
            
            with open(LOG_FILE, "a") as f:
                f.write(f"[{datetime.datetime.now()}] Dämon ist aktiv und wartet...\n")
                
    except KeyboardInterrupt:
        # Falls wir ihn manuell im Terminal stoppen
        pass
    finally:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{datetime.datetime.now()}] Dämon-Prozess wurde beendet.\n")

if __name__ == "__main__":
    main()