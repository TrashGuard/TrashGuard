import sys
import os
import gettext
import locale
import gi

# GTK initialisieren
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio

from engine import TrashEngine
from config import ConfigManager

# 1. Konfiguration laden, um die gewählte Sprache zu kennen
config = ConfigManager()
chosen_lang = config.settings.get("language", "de")

# 2. Dem System die Sprache mitteilen
# Das setzt die Umgebungsvariable für dieses Programm auf die gespeicherte Sprache
os.environ["LANGUAGE"] = chosen_lang
locale.setlocale(locale.LC_ALL, '')

# 3. Sprach-Setup
LOCALE_DIR = os.path.join(os.path.dirname(__file__), '..', 'locale')
gettext.bindtextdomain('trashguard', LOCALE_DIR)
gettext.textdomain('trashguard')
_ = gettext.gettext

class TrashGuardApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.oluja.trashguard')
        self.engine = TrashEngine()
        self.config = ConfigManager()

    def do_activate(self):
        # Hauptfenster erstellen
        win = Adw.ApplicationWindow(application=self)
        win.set_title("TrashGuard")
        win.set_default_size(400, 450)

        # Haupt-Container
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(20)
        box.set_margin_end(20)
        win.set_content(box)

        # 1. Sprachauswahl
        lang_label = Gtk.Label(label=_("Language"))
        box.append(lang_label)
        
        self.lang_combo = Gtk.DropDown.new_from_strings(["Deutsch", "Hrvatski"])
        current_lang = self.config.settings.get("language", "de")
        self.lang_combo.set_selected(0 if current_lang == "de" else 1)
        self.lang_combo.connect("notify::selected", self.on_language_changed)
        box.append(self.lang_combo)

        # 2. Status-Anzeige (Dynamischer Text mit Übersetzung)
        info = self.engine.get_system_info()
        status_text = _("Free Space: {gb:.2f} GB").format(gb=info['free_gb'])
        self.status_label = Gtk.Label(label=status_text)
        self.status_label.add_css_class("title-1")
        box.append(self.status_label)

        # 3. Schieberegler für das Limit
        limit_text = _("Limit (%)")
        slider_label = Gtk.Label(label=limit_text)
        box.append(slider_label)
        
        self.slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 50, 1)
        self.slider.set_value(self.config.settings.get("limit_percent", 20))
        self.slider.connect("value-changed", self.on_limit_changed)
        box.append(self.slider)

        # 4. Prüf-Button
        btn = Gtk.Button(label=_("Check Trash now"))
        btn.add_css_class("suggested-action")
        btn.connect("clicked", self.on_check_clicked)
        box.append(btn)

        win.present()

    def on_language_changed(self, combo, pspec):
        selected = combo.get_selected()
        new_lang = "de" if selected == 0 else "hr"
        self.config.settings["language"] = new_lang
        self.config.save()
        # Hinweis: Für einen echten Sprachwechsel zur Laufzeit müsste man 
        # die UI-Elemente hier neu laden. Für den Test reicht ein Neustart.
        print(f"Sprache in Config gespeichert: {new_lang}")

    def on_limit_changed(self, slider):
        val = int(slider.get_value())
        self.config.settings["limit_percent"] = val
        self.config.save()

    def on_check_clicked(self, button):
        size_mb = self.engine.get_trash_size() / (1024**2)
        print(f"Papierkorb Check: {size_mb:.2f} MB")

if __name__ == "__main__":
    app = TrashGuardApp()
    app.run(sys.argv)
