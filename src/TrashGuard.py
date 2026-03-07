#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, os, gi, json, gettext, shutil
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio

# --- PFADE UND KONFIGURATION ---
APP_ID = "com.oluja.trashguard"
# Absoluter Pfad zum TrashGuard-Hauptordner
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALE_DIR = os.path.join(BASE_DIR, 'locale')
CONFIG_FILE = os.path.abspath(os.path.expanduser("~/.config/trashguard/config.json"))
LOG_FILE = os.path.abspath(os.path.expanduser("~/.config/trashguard/trashguard_log.txt"))

class TrashGuardApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.connect("activate", self.on_activate)
        self.load_settings()
        self.update_translation()
        self.is_loading = True

    def load_settings(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f: self.settings = json.load(f)
            except: self.set_default_settings()
        else:
            self.set_default_settings()

    def set_default_settings(self):
        self.settings = {
            "service_enabled": False, "interval_idx": 1, "fixed_gb_val": 2.0, 
            "percent_val": 10, "del_strategy_idx": 0, "language_code": "de"
        }

    def update_translation(self):
        lang = self.settings.get("language_code", "de")
        
        # DEBUG: Wir prüfen, ob der Ordner existiert
        if not os.path.exists(LOCALE_DIR):
            print(f"KRITISCH: {LOCALE_DIR} nicht gefunden!")
        
        print(f"DEBUG: Versuche Sprache '{lang}' zu laden...")
        
        try:
            # Das ist die Standard-Methode
            el = gettext.translation('trashguard', localedir=LOCALE_DIR, languages=[lang])
            el.install() # Installiert _() global (optional, aber hilft oft)
            self.t = el.gettext
            
            # Wichtig für GTK-interne Prozesse
            gettext.bindtextdomain('trashguard', LOCALE_DIR)
            gettext.textdomain('trashguard')
            
            print(f"DEBUG: '{lang}' erfolgreich geladen.")
        except Exception as e:
            print(f"DEBUG: Ladefehler bei '{lang}': {e}")
            # Fallback: Versuche 'de', wenn 'hr' fehlschlägt
            self.t = lambda s: s

    def save_settings(self):
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w") as f: json.dump(self.settings, f, indent=4)

    def show_msg(self, text):
        dialog = Adw.MessageDialog(transient_for=self.win, heading="TrashGuard", body=text)
        dialog.add_response("ok", "OK")
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.present()

    def create_help_btn(self, msg_id):
        btn = Gtk.Button.new_from_icon_name("help-info-symbolic")
        btn.add_css_class("flat")
        def on_help_clicked(button):
            popover = Gtk.Popover()
            label = Gtk.Label(label=self.t(msg_id), margin_all=10, max_width_chars=30, wrap=True)
            popover.set_child(label)
            popover.set_parent(button)
            popover.popup()
        btn.connect("clicked", on_help_clicked)
        return btn

    def on_activate(self, app):
        self.win = Adw.ApplicationWindow(application=app, title="TrashGuard", default_width=450)
        self.win.connect("close-request", self.on_close_request)
        
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.append(Adw.HeaderBar())

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_all=15)
        self.lbl_free = Gtk.Label(xalign=0, css_classes=["caption"])
        content.append(self.lbl_free)

        # UI-Elemente initialisieren
        self.row_lang = Adw.ActionRow(); self.drop_lang = Gtk.DropDown.new_from_strings(["Deutsch", "English", "Hrvatski"])
        self.row_lang.add_suffix(self.drop_lang)

        self.row_daemon = Adw.ActionRow(); self.sw_daemon = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.row_daemon.add_suffix(self.sw_daemon)

        self.row_gb = Adw.ActionRow(); self.spin_gb = Gtk.SpinButton.new_with_range(0.1, 100.0, 0.1)
        self.row_gb.add_suffix(self.spin_gb); self.row_gb.add_prefix(self.create_help_btn("help_gb"))

        self.row_pct = Adw.ActionRow(); self.scale_pct = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 50, 1)
        self.lbl_pct_val = Gtk.Label(); pbox = Gtk.Box(spacing=10); pbox.append(self.scale_pct); pbox.append(self.lbl_pct_val)
        self.row_pct.add_suffix(pbox); self.row_pct.add_prefix(self.create_help_btn("help_pct"))

        self.row_int = Adw.ActionRow(); self.drop_int = Gtk.DropDown.new_from_strings(["30 Min", "1 Std", "24 Std", "7 Tage"])
        self.row_int.add_suffix(self.drop_int); self.row_int.add_prefix(self.create_help_btn("help_interval"))

        self.row_strat = Adw.ActionRow(); self.drop_strat = Gtk.DropDown.new_from_strings(["Oldest", "Biggest", "Random"])
        self.row_strat.add_suffix(self.drop_strat); self.row_strat.add_prefix(self.create_help_btn("help_strat"))

        for r in [self.row_lang, self.row_daemon, self.row_gb, self.row_pct, self.row_int, self.row_strat]:
            lb = Gtk.ListBox(css_classes=["boxed-list"], margin_bottom=5); lb.append(r); content.append(lb)

        self.btn_log = Gtk.Button(css_classes=["suggested-action", "pill"])
        self.btn_log.connect("clicked", lambda _: Gio.AppInfo.launch_default_for_uri(Gio.File.new_for_path(LOG_FILE).get_uri(), None))
        content.append(self.btn_log)

        # Signale verbinden
        for widget in [self.drop_lang, self.sw_daemon, self.spin_gb, self.scale_pct, self.drop_int, self.drop_strat]:
            widget.connect("notify::selected" if isinstance(widget, Gtk.DropDown) else "notify::active" if isinstance(widget, Gtk.Switch) else "value-changed", self.on_ui_change)

        main_box.append(content)
        self.win.set_content(main_box)
        self.is_loading = False
        self.refresh_ui()
        self.win.present()

    def on_ui_change(self, *args):
        if self.is_loading: return
        old_lang = self.settings["language_code"]
        new_lang = ["de", "en", "hr"][self.drop_lang.get_selected()]
        
        self.settings.update({
            "language_code": new_lang, "service_enabled": self.sw_daemon.get_active(),
            "fixed_gb_val": round(self.spin_gb.get_value(), 2), "percent_val": int(self.scale_pct.get_value()),
            "interval_idx": self.drop_int.get_selected(), "del_strategy_idx": self.drop_strat.get_selected()
        })
        self.save_settings()
        
        if old_lang != new_lang:
            self.update_translation()
            # Der Dialog sollte jetzt in der NEUEN Sprache erscheinen
            self.show_msg(self.t("restart_msg"))
            self.refresh_ui()

    def on_close_request(self, window):
        if not self.sw_daemon.get_active():
            dialog = Adw.MessageDialog(transient_for=self.win, heading="TrashGuard", body=self.t("daemon_warning"))
            dialog.add_response("cancel", "No"); dialog.add_response("close", "Yes")
            dialog.set_response_appearance("close", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.connect("response", lambda d, r: self.win.destroy() if r == "close" else d.destroy())
            dialog.present()
            return True
        return False

    def refresh_ui(self):
        self.is_loading = True
        s = self.settings
        self.drop_lang.set_selected(["de", "en", "hr"].index(s["language_code"]))
        self.sw_daemon.set_active(s["service_enabled"])
        self.spin_gb.set_value(s["fixed_gb_val"])
        self.scale_pct.set_value(s["percent_val"])
        self.lbl_pct_val.set_label(f"{int(s['percent_val'])}%")
        self.drop_int.set_selected(s["interval_idx"])
        self.drop_strat.set_selected(s["del_strategy_idx"])
        
        # Texte aktualisieren - RUFT JEDES MAL self.t() AUF
        total, used, free = shutil.disk_usage(os.path.expanduser("~"))
        self.lbl_free.set_label(f"{self.t('free_space')}: {free/(1024**3):.2f} GB")
        self.row_lang.set_title(self.t("lang_title"))
        self.row_daemon.set_title(self.t("daemon_title"))
        self.row_gb.set_title(self.t("limit_gb_title"))
        self.row_pct.set_title(self.t("limit_pct_title"))
        self.row_int.set_title(self.t("interval_title"))
        self.row_strat.set_title(self.t("strat_title"))
        self.btn_log.set_label(self.t("btn_log_title"))
        self.is_loading = False

if __name__ == "__main__":
    app = TrashGuardApp()
    app.run(sys.argv)