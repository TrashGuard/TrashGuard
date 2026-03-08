import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib, Gdk
import json
import os
import gettext
import sys
import shutil
import webbrowser
import subprocess

class TrashGuardApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(application_id='com.dejanovic.trashguard', **kwargs)
        self.config_dir = os.path.expanduser("~/.config/trashguard")
        self.config_path = os.path.join(self.config_dir, "config.json")
        self.pid_file = os.path.join(self.config_dir, "daemon.pid")
        
        # Logfile Pfade
        self.daemon_log = os.path.join(self.config_dir, "trashguard_daemon_log.txt")
        self.cleaning_log = os.path.join(self.config_dir, "trashguard_cleaning_log.txt")
        
        self.load_config()
        self.sync_daemon_status()
        self.connect('activate', self.on_activate)

    def load_config(self):
        self.config = {
            "language": "de", "service_enabled": False,
            "fixed_gb_val": 2.0, "percent_val": 10,
            "interval_idx": 1, "del_strategy_idx": 0, "use_fixed": True,
            "window_width": 450, "window_height": 850
        }
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    self.config.update(json.load(f))
            except: pass

    def is_daemon_running(self):
        if os.path.exists(self.pid_file):
            try:
                with open(self.pid_file, "r") as f:
                    pid = int(f.read().strip())
                os.kill(pid, 0)
                return True
            except: return False
        return False

    def sync_daemon_status(self):
        should_run = self.config.get("service_enabled", False)
        is_running = self.is_daemon_running()
        daemon_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "TrashGuard.py")
        if should_run and not is_running and os.path.exists(daemon_script):
            try:
                # Hier wurde das --daemon Flag hinzugefügt
                proc = subprocess.Popen(["python3", daemon_script, "--daemon"])
                with open(self.pid_file, "w") as f: f.write(str(proc.pid))
            except: pass
        elif not should_run and is_running:
            try:
                with open(self.pid_file, "r") as f: pid = int(f.read().strip())
                os.kill(pid, 15)
                if os.path.exists(self.pid_file): os.remove(self.pid_file)
            except: pass

    def save_config(self):
        os.makedirs(self.config_dir, exist_ok=True)
        with open(self.config_path, "w") as f: json.dump(self.config, f, indent=4)

    def update_translation(self):
        lang = self.config.get("language", "de")
        os.environ['LANGUAGE'] = lang
        locale_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'locale')
        try:
            el = gettext.translation('trashguard', locale_dir, languages=[lang], fallback=True)
            el.install()
            self._ = el.gettext
        except: self._ = lambda s: s

    def get_trash_size(self):
        """Berechnet die aktuelle Größe des Papierkorbs in GB."""
        trash_path = os.path.expanduser("~/.local/share/Trash/files")
        total_size = 0
        if os.path.exists(trash_path):
            for dirpath, dirnames, filenames in os.walk(trash_path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if not os.path.islink(fp):
                        total_size += os.path.getsize(fp)
        return total_size / (1024**3)

    def on_activate(self, app):
        self.update_translation()
        GLib.set_prgname('com.dejanovic.trashguard')
        GLib.set_application_name("TrashGuard")
        
        self.win = Adw.ApplicationWindow(application=app, title="TrashGuard")
        
        width = self.config.get("window_width", 450)
        height = self.config.get("window_height", 850)
        
        self.win.set_size_request(-1, 850)
        self.win.set_default_size(width, height)
        
        self.win.connect("close-request", self.on_close_requested)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.win.set_content(self.main_box)
        self.build_ui()
        self.win.present()

    def build_ui(self):
        child = self.main_box.get_first_child()
        while child:
            self.main_box.remove(child)
            child = self.main_box.get_first_child()

        header = Adw.HeaderBar()
        self.log_btn = Gtk.Button(label="Logfiles")
        self.log_btn.connect("clicked", self.on_show_logs)
        header.pack_start(self.log_btn)

        about_btn = Gtk.Button.new_from_icon_name("dialog-information-symbolic")
        about_btn.connect("clicked", self.show_about)
        header.pack_end(about_btn)
        self.main_box.append(header)

        page = Adw.PreferencesPage()
        page.set_vexpand(True)
        self.main_box.append(page)

        usage = shutil.disk_usage(os.path.expanduser("~"))
        self.free_gb_now = usage.free / (1024**3)
        self.trash_gb_now = self.get_trash_size()

        group_base = Adw.PreferencesGroup()
        page.add(group_base)

        self.lang_row = Adw.ComboRow(title=self._("lang_title"))
        self.lang_row.set_subtitle(self._("help_lang"))
        self.lang_row.set_model(Gtk.StringList.new(["Deutsch", "English", "HR / SRB / BIH"]))
        self.lang_row.set_selected({"de":0, "en":1, "hr":2}.get(self.config["language"], 0))
        self.lang_row.connect("notify::selected", self.on_language_changed)
        group_base.add(self.lang_row)

        self.service_switch = Adw.SwitchRow(title=self._("daemon_title"))
        self.service_switch.set_subtitle(self._("help_daemon"))
        self.service_switch.set_active(self.config["service_enabled"])
        self.service_switch.connect("notify::active", self.on_daemon_toggled)
        group_base.add(self.service_switch)

        # Beschreibung aktualisiert: Freier Speicher und Papierkorbgröße
        limit_desc = f"{self._('free_space')}: {self.free_gb_now:.2f} GB | {self._('trash_size')}: {self.trash_gb_now:.2f} GB"
        group_limit = Adw.PreferencesGroup(title="Limit-Modus", description=limit_desc)
        page.add(group_limit)

        self.fixed_check_row = Adw.SwitchRow(title=self._("check_fixed_title"))
        self.fixed_check_row.set_subtitle(self._("help_fixed_mode"))
        self.fixed_check_row.set_active(self.config["use_fixed"])
        self.fixed_check_row.connect("notify::active", self.on_mode_toggled, "fixed")
        group_limit.add(self.fixed_check_row)

        self.fixed_val_row = Adw.ActionRow(title=self._("limit_gb_title"))
        self.gb_spin = Gtk.SpinButton.new_with_range(0.1, self.free_gb_now, 0.1)
        self.gb_spin.set_value(min(self.config["fixed_gb_val"], self.free_gb_now))
        self.gb_spin.connect("value-changed", self.sync_from_gb)
        self.fixed_val_row.add_suffix(self.gb_spin)
        group_limit.add(self.fixed_val_row)

        self.dyn_check_row = Adw.SwitchRow(title=self._("check_dynamic_title"))
        self.dyn_check_row.set_subtitle(self._("help_dynamic_mode"))
        self.dyn_check_row.set_active(not self.config["use_fixed"])
        self.dyn_check_row.connect("notify::active", self.on_mode_toggled, "dyn")
        group_limit.add(self.dyn_check_row)

        self.dyn_val_row = Adw.ActionRow(title=self._("limit_pct_title"))
        self.pct_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 50, 1)
        self.pct_scale.set_value(min(self.config["percent_val"], 50))
        self.pct_scale.set_hexpand(True)
        self.pct_scale.connect("value-changed", self.sync_from_pct)
        self.pct_label = Gtk.Label(label=f"{int(self.pct_scale.get_value())}%")
        scale_box = Gtk.Box(spacing=10); scale_box.append(self.pct_scale); scale_box.append(self.pct_label)
        self.dyn_val_row.add_suffix(scale_box)
        group_limit.add(self.dyn_val_row)

        group_run = Adw.PreferencesGroup()
        page.add(group_run)

        self.interval_row = Adw.ComboRow(title=self._("interval_title"))
        self.interval_row.set_subtitle(self._("help_interval"))
        self.interval_row.set_model(Gtk.StringList.new(["30 min", "1 h", "24 h", "7 d"]))
        self.interval_row.set_selected(self.config["interval_idx"])
        self.interval_row.connect("notify::selected", self.on_config_changed)
        group_run.add(self.interval_row)

        self.strategy_row = Adw.ComboRow(title=self._("strat_title"))
        self.strategy_row.set_subtitle(self._("help_strat"))
        self.strategy_row.set_model(Gtk.StringList.new([self._("strat_oldest"), self._("strat_biggest"), self._("strat_random")]))
        self.strategy_row.set_selected(self.config["del_strategy_idx"])
        self.strategy_row.connect("notify::selected", self.on_config_changed)
        group_run.add(self.strategy_row)

        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Slavic_by_nature.svg")
        if os.path.exists(logo_path):
            footer_group = Adw.PreferencesGroup()
            logo_img = Gtk.Image.new_from_file(logo_path)
            logo_img.set_pixel_size(80)
            logo_img.set_margin_top(20)
            logo_img.set_margin_bottom(40)
            logo_img.set_opacity(0.3)
            footer_group.add(logo_img)
            page.add(footer_group)

        self.update_sensitivity()

    def on_show_logs(self, btn):
        log_win = Adw.Window(transient_for=self.win, title="TrashGuard Logs", modal=True)
        log_win.set_default_size(600, 500)
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(15)
        box.set_margin_bottom(15)
        box.set_margin_start(15)
        box.set_margin_end(15)
        
        stack = Adw.ViewStack()
        
        log_configs = [
            (self._("log_daemon_title"), self.daemon_log),
            (self._("log_cleaning_title"), self.cleaning_log)
        ]
        
        for name, path in log_configs:
            scr = Gtk.ScrolledWindow(vexpand=True)
            txt = Gtk.TextView(editable=False, cursor_visible=False, left_margin=10, right_margin=10, top_margin=10, bottom_margin=10)
            txt.set_monospace(True)
            
            content = ""
            if os.path.exists(path):
                try:
                    with open(path, "r") as f: content = f.read()
                except: content = "Fehler beim Lesen der Datei."
            else:
                content = "Bisher keine Einträge vorhanden."
            
            txt.get_buffer().set_text(content)
            scr.set_child(txt)
            stack.add_titled(scr, name, name)
        
        switcher = Adw.ViewSwitcher(stack=stack)
        box.append(switcher)
        box.append(stack)

        close_btn = Gtk.Button(label=self._("btn_close"))
        close_btn.set_halign(Gtk.Align.CENTER)
        close_btn.add_css_class("suggested-action")
        close_btn.set_margin_top(10)
        close_btn.connect("clicked", lambda b: log_win.close())
        box.append(close_btn)
        
        log_win.set_content(box)
        log_win.present()

    def on_daemon_toggled(self, row, pspec):
        active = row.get_active()
        
        # 1. Einstellung speichern
        self.on_config_changed()
        
        # 2. Pfad zum Dämon-Skript ermitteln
        daemon_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "TrashGuard.py")
        
        # 3. Den Autostart-Handler rufen (Portal-Logik)
        try:
            from autostart_handler import AutostartManager
            AutostartManager.set_autostart(active)
        except ImportError:
            print("Fehler: autostart_handler.py nicht im Verzeichnis!")

        # 4. Den Prozess sofort starten oder stoppen
        if active:
            if not self.is_daemon_running() and os.path.exists(daemon_script):
                try:
                    # HINZUGEFÜGT: Das "--daemon" Flag
                    proc = subprocess.Popen(["python3", daemon_script, "--daemon"])
                    with open(self.pid_file, "w") as f: 
                        f.write(str(proc.pid))
                except Exception as e:
                    print(f"Fehler beim Starten des Prozesses: {e}")
        else:
            # Dämon stoppen via PID
            if os.path.exists(self.pid_file):
                try:
                    with open(self.pid_file, "r") as f: 
                        pid = int(f.read().strip())
                    os.kill(pid, 15) # SIGTERM senden
                except: 
                    pass
                finally:
                    if os.path.exists(self.pid_file): 
                        os.remove(self.pid_file)

    def show_about(self, btn):
        dialog = Adw.MessageDialog(transient_for=self.win, heading=self._("legal_title"))
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Slavic_by_nature.svg")
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        if os.path.exists(logo_path):
            logo_img = Gtk.Image.new_from_file(logo_path)
            logo_img.set_pixel_size(96)
            content_box.append(logo_img)
        label = Gtk.Label(use_markup=True, wrap=True, justify=Gtk.Justification.CENTER)
        label.set_markup(f"<b>TrashGuard</b>\n\n{self._('legal_text')}")
        content_box.append(label)
        dialog.set_extra_child(content_box)
        dialog.add_response("close", self._("btn_close"))
        dialog.add_response("report", self._("btn_report"))
        dialog.connect("response", lambda d, r: webbrowser.open("mailto:trashguard@alpenjodel.de") if r == "report" else None)
        dialog.present()

    def on_close_requested(self, win):
        self.config["window_width"] = win.get_width()
        self.config["window_height"] = win.get_height()
        self.save_config()

        if not self.service_switch.get_active():
            diag = Adw.MessageDialog(transient_for=self.win, heading=self._("warn_title"), body=self._("warn_body"))
            diag.add_response("cancel", self._("warn_cancel"))
            diag.add_response("exit", self._("warn_confirm"))
            diag.set_response_appearance("exit", Adw.ResponseAppearance.DESTRUCTIVE)
            diag.connect("response", lambda d, r: self.quit() if r == "exit" else None)
            diag.present()
            return True
        return False

    def sync_from_gb(self, spin):
        val = spin.get_value()
        pct = (val / self.free_gb_now) * 100 if self.free_gb_now > 0 else 0
        self.pct_scale.handler_block_by_func(self.sync_from_pct)
        self.pct_scale.set_value(min(pct, 50))
        self.pct_label.set_text(f"{int(self.pct_scale.get_value())}%")
        self.pct_scale.handler_unblock_by_func(self.sync_from_pct)
        self.on_config_changed()

    def sync_from_pct(self, scale):
        pct = scale.get_value()
        val = (pct / 100) * self.free_gb_now
        self.pct_label.set_text(f"{int(pct)}%")
        self.gb_spin.handler_block_by_func(self.sync_from_gb)
        self.gb_spin.set_value(val)
        self.gb_spin.handler_unblock_by_func(self.sync_from_gb)
        self.on_config_changed()

    def on_mode_toggled(self, row, pspec, mode):
        fixed_active = self.fixed_check_row.get_active()
        dyn_active = self.dyn_check_row.get_active()

        if not fixed_active and not dyn_active:
            row.handler_block_by_func(self.on_mode_toggled)
            row.set_active(True)
            row.handler_unblock_by_func(self.on_mode_toggled)
            return

        if row.get_active():
            if mode == "fixed":
                self.dyn_check_row.set_active(False)
            else:
                self.fixed_check_row.set_active(False)
        
        GLib.idle_add(self.update_sensitivity)
        self.on_config_changed()

    def update_sensitivity(self):
        fixed = self.fixed_check_row.get_active()
        dyn = self.dyn_check_row.get_active()
        self.fixed_val_row.set_sensitive(fixed)
        self.dyn_val_row.set_sensitive(dyn)

    def on_config_changed(self, *args):
        langs = ["de", "en", "hr"]
        self.config.update({
            "service_enabled": self.service_switch.get_active(),
            "fixed_gb_val": round(self.gb_spin.get_value(), 2),
            "percent_val": int(self.pct_scale.get_value()),
            "interval_idx": self.interval_row.get_selected(),
            "del_strategy_idx": self.strategy_row.get_selected(),
            "use_fixed": self.fixed_check_row.get_active(),
            "language": langs[self.lang_row.get_selected()]
        })
        self.save_config()

    def on_language_changed(self, row, pspec):
        self.on_config_changed(); self.update_translation(); GLib.idle_add(self.build_ui)

if __name__ == "__main__":
    app = TrashGuardApp()
    app.run(sys.argv)