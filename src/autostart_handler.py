import os
import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib

class AutostartManager:
    APP_ID = "com.dejanovic.trashguard"
    AUTOSTART_DIR = os.path.expanduser("~/.config/autostart")
    AUTOSTART_FILE = os.path.join(AUTOSTART_DIR, f"{APP_ID}.daemon.desktop")

    @staticmethod
    def is_flatpak():
        """Prüft, ob die App in einer Flatpak-Sandbox läuft."""
        return os.path.exists("/.flatpak-info")

    @staticmethod
    def set_autostart(enabled=True):
        if AutostartManager.is_flatpak():
            return AutostartManager._set_portal_autostart(enabled)
        else:
            return AutostartManager._set_classic_autostart(enabled)

    @staticmethod
    def _set_portal_autostart(enabled):
        """Der offizielle Weg für Flatpaks (XDG-Portal)."""
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            proxy = Gio.DBusProxy.new_sync(
                bus, Gio.DBusProxyFlags.NONE, None,
                "org.freedesktop.portal.Desktop",
                "/org/freedesktop/portal/desktop",
                "org.freedesktop.portal.Background", None
            )
            options = {
                "handle_token": GLib.Variant('s', 'trashguard_daemon'),
                "reason": GLib.Variant('s', 'Hintergrunddienst zur Papierkorb-Verwaltung.'),
                "autostart": GLib.Variant('b', enabled),
                "commandline": GLib.Variant('as', ['flatpak', 'run', AutostartManager.APP_ID, '--daemon'])
            }
            proxy.RequestBackground('(sa{sv})', "", options)
            return True
        except Exception as e:
            print(f"Portal-Fehler (Flatpak): {e}")
            return False

    @staticmethod
    def _set_classic_autostart(enabled):
        """Der klassische Weg für Skripte (.desktop Datei)."""
        if not os.path.exists(AutostartManager.AUTOSTART_DIR):
            os.makedirs(AutostartManager.AUTOSTART_DIR, exist_ok=True)

        if enabled:
            daemon_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "TrashGuard.py")
            content = f"""[Desktop Entry]
Type=Application
Name=TrashGuard Daemon
Exec=python3 {daemon_script} --daemon
Icon=org.gnome.Settings-trash-symbolic
X-GNOME-Autostart-enabled=true
"""
            try:
                with open(AutostartManager.AUTOSTART_FILE, "w") as f:
                    f.write(content)
                return True
            except Exception as e:
                print(f"Datei-Fehler (Skript): {e}")
                return False
        else:
            if os.path.exists(AutostartManager.AUTOSTART_FILE):
                os.remove(AutostartManager.AUTOSTART_FILE)
            return True