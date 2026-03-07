import sys, os, gi, subprocess, shutil, json, gettext
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gio
from engine import TrashEngine
from config import ConfigManager

# --- LOKALISIERUNG ---
# Verweist auf das lokale Verzeichnis im Projektordner
LOCALE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'locale')

def setup_language(lang_code):
    try:
        lang = gettext.translation('trashguard', localedir=LOCALE_DIR, languages=[lang_code], fallback=True)
        return lang.gettext
    except:
        return lambda s: s

class TrashGuardApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="com.oluja.trashguard", 
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )
        self.connect("activate", self.on_activate)
        self.engine = TrashEngine()
        self.config = ConfigManager()
        self.win = None
        self.timer_id = None
        self.is_loading = True
        
        # Reduzierte Sprach-Map
        self.lang_map = ["de", "en", "hr"]
        self.update_translation()

    def update_translation(self):
        code = self.config.settings.get("language_code", "de")
        self.translate = setup_language(code)

    def get_drive_info(self):
        return shutil.disk_usage("/")

    def create_help_btn(self, msg_id):
        btn = Gtk.Button.new_from_icon_name("help-about-symbolic")
        btn.add_css_class("flat")
        btn.set_valign(Gtk.Align.CENTER)
        popover = Gtk.Popover()
        label = Gtk.Label()
        label.set_margin_start(10); label.set_margin_end(10)
        label.set_margin_top(10); label.set_margin_bottom(10)
        popover.set_child(label)
        def on_clicked(b):
            label.set_label(self.translate(msg_id))
            popover.popup()
        btn.connect("clicked", on_clicked)
        popover.set_parent(btn)
        return btn

    def on_activate(self, app):
        self.show_main_window()
        if self.config.settings.get("service_enabled", False):
            self.restart_check_timer()

    def show_main_window(self):
        if self.win:
            self.win.present()
            return

        self.win = Adw.ApplicationWindow(application=self)
        self.win.set_title("TrashGuard")
        self.win.set_default_size(480, 600)
        
        # Warn-Dialog beim Schließen, falls Schutz aus ist
        self.win.connect("close-request", self.on_window_close_request)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.win.set_content(main_box)
        
        header = Adw.HeaderBar()
        about_btn = Gtk.Button.new_from_icon_name("dialog-information-symbolic")
        about_btn.add_css_class("flat")
        about_btn.connect("clicked", self.show_about_dialog)
        header.pack_start(about_btn)
        main_box.append(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        content.set_margin_top(20); content.set_margin_bottom(20)
        content.set_margin_start(20); content.set_margin_end(20)
        main_box.append(content)

        self.space_label = Gtk.Label()
        self.space_label.add_css_class("title-2")
        content.append(self.space_label)

        # Sprachauswahl (nur de, en, hr)
        lang_list = Gtk.ListBox(); lang_list.add_css_class("boxed-list")
        self.lang_row = Adw.ActionRow()
        langs = ["Deutsch", "English", "Hrvatski / Srpski"]
        self.lang_drop = Gtk.DropDown.new_from_strings(langs)
        
        current_code = self.config.settings.get("language_code", "de")
        if current_code in self.lang_map:
            self.lang_drop.set_selected(self.lang_map.index(current_code))
        
        self.lang_drop.connect("notify::selected", self.on_lang_changed)
        self.lang_row.add_suffix(self.lang_drop)
        lang_list.append(self.lang_row)
        content.append(lang_list)

        # Schutz-Schalter
        status_card = Gtk.Frame()
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        status_box.set_margin_top(12); status_box.set_margin_bottom(12)
        status_box.set_margin_start(12); status_box.set_margin_end(12)
        status_card.set_child(status_box)
        self.daemon_label = Gtk.Label(xalign=0, hexpand=True)
        self.master_switch = Gtk.Switch()
        self.master_switch.set_active(self.config.settings.get("service_enabled", False))
        self.master_switch.connect("state-set", self.on_master_toggle)
        status_box.append(self.daemon_label)
        status_box.append(self.create_help_btn("Aktiviert den Schutz."))
        status_box.append(self.master_switch)
        content.append(status_card)

        # Modus-Auswahl
        self.mode_switch = Gtk.CheckButton()
        self.mode_switch.set_active(self.config.settings.get("use_percentage", False))
        self.mode_switch.connect("toggled", self.on_mode_toggled)
        content.append(self.mode_switch)

        # Limits (mit 50% Hard-Limit Synchronisation)
        limit_list = Gtk.ListBox(); limit_list.add_css_class("boxed-list")
        self.gb_spin = Gtk.SpinButton.new_with_range(0.1, 1.0, 0.1)
        self.gb_spin.set_value(self.config.settings.get("fixed_gb_val", 2.0))
        self.gb_spin.connect("value-changed", self.on_gb_spin_changed)
        self.gb_row = Adw.ActionRow()
        self.gb_row.add_suffix(self.create_help_btn("Limit in GB (max 50% vom freien Speicher)."))
        self.gb_row.add_suffix(self.gb_spin)
        
        self.pct_label_info = Gtk.Label()
        self.pct_row = Adw.ActionRow()
        self.pct_row.add_suffix(self.create_help_btn("Limit in % (max 50% vom freien Speicher)."))
        self.pct_row.add_suffix(self.pct_label_info)
        limit_list.append(self.gb_row); limit_list.append(self.pct_row)
        content.append(limit_list)

        self.pct_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 50, 1)
        self.pct_scale.set_value(self.config.settings.get("percent_val", 10))
        self.pct_scale.connect("value-changed", self.on_pct_scroll)
        self.pct_scale_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.pct_scale_box.set_margin_start(15); self.pct_scale_box.set_margin_end(15)
        self.pct_scale_box.append(self.pct_scale)
        content.append(self.pct_scale_box)

        # Intervall
        int_list = Gtk.ListBox(); int_list.add_css_class("boxed-list")
        self.int_drop = Gtk.DropDown.new_from_strings(["30 Min", "1 Std", "24 Std", "7 Tage"])
        self.int_drop.set_selected(self.config.settings.get("interval_idx", 1))
        self.int_drop.connect("notify::selected", self.on_generic_change)
        self.int_row = Adw.ActionRow()
        self.int_row.add_suffix(self.create_help_btn("Häufigkeit der Papierkorb-Prüfung."))
        self.int_row.add_suffix(self.int_drop)
        int_list.append(self.int_row); content.append(int_list)

        # Log & Footer
        footer_list = Gtk.ListBox(); footer_list.add_css_class("boxed-list")
        self.log_row = Adw.ActionRow()
        log_btn = Gtk.Button.new_from_icon_name("document-open-symbolic")
        log_btn.connect("clicked", lambda x: self.launch_file("trashguard.log"))
        self.log_row.add_suffix(self.create_help_btn("Ereignis-Protokoll öffnen."))
        self.log_row.add_suffix(log_btn)
        footer_list.append(self.log_row)
        content.append(footer_list)

        self.is_loading = False
        self.refresh_ui_labels()
        self.win.present()

    def on_window_close_request(self, window):
        if not self.master_switch.get_active():
            t = self.translate
            dialog = Adw.MessageDialog(
                transient_for=self.win,
                heading=t("Schutz deaktiviert!"),
                body=t("Der Papierkorb-Schutz ist aktuell ausgeschaltet. Möchtest du das Programm wirklich beenden?"),
            )
            dialog.add_response("cancel", t("Abbrechen"))
            dialog.add_response("close", t("Beenden"))
            dialog.set_response_appearance("close", Adw.ResponseAppearance.DESTRUCTIVE)
            def on_response(d, response_id):
                if response_id == "close": self.quit()
            dialog.connect("response", on_response)
            dialog.present()
            return True
        return False

    def refresh_ui_labels(self):
        t = self.translate
        _, _, free = self.get_drive_info()
        free_gb = free / (2**30)
        self.space_label.set_label(f"{t('Verfügbar')}: {int(free_gb)} GB")
        max_allowed_gb = free_gb * 0.5
        self.gb_spin.set_range(0.1, max(0.2, max_allowed_gb))
        self.lang_row.set_title(t("Sprache"))
        self.daemon_label.set_label(t("Papierkorb-Dämon aktiv"))
        self.mode_switch.set_label(t("Prozent-Modus nutzen"))
        self.gb_row.set_title(t("Festplatten-Limit (GB)"))
        self.pct_row.set_title(t("Festplatten-Limit (%)"))
        self.int_row.set_title(t("Prüf-Intervall"))
        self.log_row.set_title(t("Ereignis-Log öffnen"))
        self.update_pct_label()
        self.update_ui_visibility()

    def update_pct_label(self):
        _, _, free = self.get_drive_info()
        pct = self.pct_scale.get_value()
        gb_equiv = (free * pct / 100) / (2**30)
        self.pct_label_info.set_label(f"{int(pct)}% (ca. {gb_equiv:.1f} GB)")

    def on_gb_spin_changed(self, spin):
        if self.is_loading: return
        _, _, free = self.get_drive_info()
        free_gb = free / (2**30)
        if free_gb > 0:
            new_pct = (spin.get_value() / free_gb) * 100
            self.pct_scale.set_value(min(max(new_pct, 1), 50))
        self.save_settings()

    def on_pct_scroll(self, scale):
        if self.is_loading: return
        _, _, free = self.get_drive_info()
        pct = scale.get_value()
        new_gb = (free * pct / 100) / (2**30)
        self.gb_spin.set_value(round(new_gb, 2))
        self.update_pct_label()
        self.save_settings()

    def on_mode_toggled(self, check):
        self.update_ui_visibility()
        if not self.is_loading: self.save_settings()

    def update_ui_visibility(self):
        use_pct = self.mode_switch.get_active()
        self.pct_scale_box.set_visible(use_pct)
        self.pct_row.set_sensitive(use_pct)
        self.gb_row.set_sensitive(not use_pct)

    def on_lang_changed(self, widget, pspec):
        if self.is_loading: return
        self.config.settings["language_code"] = self.lang_map[widget.get_selected()]
        self.save_settings(); self.update_translation(); self.refresh_ui_labels()

    def on_master_toggle(self, sw, state):
        if not self.is_loading: self.save_settings(); self.restart_check_timer()
        return False

    def on_generic_change(self, *args):
        if not self.is_loading: self.save_settings(); self.restart_check_timer()

    def save_settings(self):
        if self.is_loading: return
        data = {
            "service_enabled": self.master_switch.get_active(),
            "interval_idx": self.int_drop.get_selected(),
            "fixed_gb_val": round(self.gb_spin.get_value(), 2),
            "percent_val": int(self.pct_scale.get_value()),
            "use_percentage": self.mode_switch.get_active(),
            "language_code": self.config.settings.get("language_code", "de")
        }
        self.config.settings.update(data)
        path = os.path.expanduser("~/.config/trashguard/config.json")
        with open(path, "w") as f:
            json.dump(data, f, indent=4)

    def restart_check_timer(self):
        if self.timer_id: GLib.source_remove(self.timer_id)
        if self.master_switch.get_active():
            intervals = [1800, 3600, 86400, 604800]
            self.timer_id = GLib.timeout_add_seconds(intervals[self.int_drop.get_selected()], self.run_logic)

    def run_logic(self):
        self.refresh_ui_labels()
        self.engine.enforce_limit(self.config.settings)
        return True

    def show_about_dialog(self, btn):
        dialog = Adw.AboutWindow(
            transient_for=self.win,
            application_name="TrashGuard",
            developer_name="Mario Dejanović",
            version="2.9.4",
            issue_url="mailto:mario@dejanovic.at",
            copyright=f"{self.translate('Erstellt von')} Mario Dejanović",
            license_type=Gtk.License.GPL_3_0
        )
        dialog.present()

    def launch_file(self, filename):
        path = os.path.expanduser(f"~/.config/trashguard/{filename}")
        if os.path.exists(path): subprocess.Popen(["cosmic-edit", path])

if __name__ == "__main__":
    app = TrashGuardApp()
    try: app.run(sys.argv)
    except KeyboardInterrupt: pass