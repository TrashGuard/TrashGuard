#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, os, gi, json, gettext, shutil, subprocess
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio

# --- KONFIGURATION ---
MY_NAME = "Mario Dejanović"
MY_EMAIL = "trashguard@alpenjodel.de"
LOG_FILE = os.path.expanduser("~/.config/trashguard/trashguard_log.txt")
CONFIG_FILE = os.path.expanduser("~/.config/trashguard/config.json")

# --- LOKALISIERUNG ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
LOCALE_DIR = os.path.join(BASE_DIR, 'locale')

class TrashGuardApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.oluja.trashguard")
        self.connect("activate", self.on_activate)
        self.settings_path = CONFIG_FILE
        self.load_settings()
        self.lang_map = ["de", "en", "hr"]
        self.update_translation()
        self.is_loading = True

    def get_free_space(self):
        total, used, free = shutil.disk_usage(os.path.expanduser("~"))
        return free / (1024**3)

    def load_settings(self):
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    self.settings = json.load(f)
            except:
                self.set_default_settings()
        else:
            self.set_default_settings()

    def set_default_settings(self):
        self.settings = {
            "service_enabled": False, "interval_idx": 1, 
            "fixed_gb_val": 2.0, "percent_val": 10, 
            "del_strategy_idx": 0, "language_code": "de"
        }

    def update_translation(self):
        lang_code = self.settings.get("language_code", "de")
        try:
            lang = gettext.translation('trashguard', localedir=LOCALE_DIR, languages=[lang_code])
            self.t = lang.gettext
        except Exception:
            self.t = lambda s: s

    def open_logfile(self, btn):
        for editor in ["cosmic-edit", "gnome-text-editor", "gedit", "mousepad", "xdg-open"]:
            if shutil.which(editor):
                subprocess.Popen([editor, LOG_FILE])
                return

    def create_help_btn(self, msg_id):
        btn = Gtk.Button.new_from_icon_name("help-info-symbolic")
        btn.add_css_class("flat")
        def on_clicked(b):
            popover = Gtk.Popover()
            label = Gtk.Label(label=self.t(msg_id), max_width_chars=35, wrap=True)
            label.set_margin_top(10); label.set_margin_bottom(10)
            label.set_margin_start(10); label.set_margin_end(10)
            popover.set_child(label)
            popover.set_parent(b)
            popover.popup()
        btn.connect("clicked", on_clicked)
        return btn

    def show_legal(self, btn):
        legal = Gtk.Window(transient_for=self.win, modal=True, resizable=False, title=self.t("legal_title"))
        legal.set_default_size(350, 250)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        box.set_margin_top(20); box.set_margin_bottom(20)
        box.set_margin_start(20); box.set_margin_end(20)
        label = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        label.set_markup(self.t("legal_text"))
        close_btn = Gtk.Button(label=self.t("btn_close"))
        close_btn.connect("clicked", lambda x: legal.destroy())
        box.append(label); box.append(close_btn)
        legal.set_child(box)
        legal.present()

    def show_about_custom(self, btn):
        about = Gtk.Window(transient_for=self.win, modal=True, resizable=False, title=self.t("info_title"))
        about.set_default_size(320, 500)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        box.set_margin_top(30); box.set_margin_bottom(30)
        box.set_margin_start(30); box.set_margin_end(30)
        img = Gtk.Image.new_from_icon_name("user-trash-full-symbolic")
        img.set_pixel_size(96)
        title = Gtk.Label(label="TrashGuard", css_classes=["title-1"])
        author = Gtk.Label(label=f"{MY_NAME}\nVersion 2.9.7", justify=Gtk.Justification.CENTER)
        legal_btn = Gtk.Button(label=self.t("legal_title"))
        legal_btn.connect("clicked", self.show_legal)
        bug_btn = Gtk.Button(label=self.t("btn_report"))
        bug_btn.connect("clicked", lambda x: subprocess.run(["xdg-open", f"mailto:{MY_EMAIL}"]))
        close_btn = Gtk.Button(label=self.t("btn_close"))
        close_btn.connect("clicked", lambda x: about.destroy())
        box.append(img); box.append(title); box.append(author); box.append(legal_btn); box.append(bug_btn); box.append(close_btn)
        about.set_child(box)
        about.present()

    def on_activate(self, app):
        self.win = Adw.ApplicationWindow(application=self, title="TrashGuard", default_width=450)
        
        # NEU: Warnmeldung beim Schließen, falls Service aus ist
        self.win.connect("close-request", self.on_close_request)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = Adw.HeaderBar()
        info_btn = Gtk.Button.new_from_icon_name("help-about-symbolic")
        info_btn.connect("clicked", self.show_about_custom)
        header.pack_start(info_btn)
        main_box.append(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(15); content.set_margin_bottom(15)
        content.set_margin_start(15); content.set_margin_end(15)

        self.free_label = Gtk.Label(xalign=0, css_classes=["caption"])
        content.append(self.free_label)

        # UI Reihen
        self.lang_row = Adw.ActionRow()
        self.lang_drop = Gtk.DropDown.new_from_strings(["Deutsch", "English", "Hrvatski"])
        self.lang_drop.connect("notify::selected", self.on_lang_changed)
        self.lang_row.add_suffix(self.lang_drop)
        self.lang_row.add_prefix(self.create_help_btn("help_lang"))

        self.daemon_row = Adw.ActionRow()
        self.daemon_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.daemon_switch.connect("notify::active", self.on_generic_change)
        self.daemon_row.add_suffix(self.daemon_switch)

        self.gb_row = Adw.ActionRow()
        self.gb_spin = Gtk.SpinButton.new_with_range(0.1, 100.0, 0.1)
        self.gb_spin.connect("value-changed", self.on_gb_changed)
        self.gb_row.add_suffix(self.gb_spin)
        self.gb_row.add_prefix(self.create_help_btn("help_gb"))

        self.pct_row = Adw.ActionRow()
        pct_box = Gtk.Box(spacing=10)
        self.pct_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 50, 1)
        self.pct_scale.set_hexpand(True)
        self.pct_scale.set_size_request(200, -1)
        self.pct_label = Gtk.Label()
        self.pct_scale.connect("value-changed", self.on_pct_changed)
        pct_box.append(self.pct_scale); pct_box.append(self.pct_label)
        self.pct_row.add_suffix(pct_box)
        self.pct_row.add_prefix(self.create_help_btn("help_pct"))

        self.int_row = Adw.ActionRow()
        self.int_drop = Gtk.DropDown.new_from_strings(["30 Min", "1 Std", "24 Std", "7 Tage"])
        self.int_drop.connect("notify::selected", self.on_generic_change)
        self.int_row.add_suffix(self.int_drop)
        self.int_row.add_prefix(self.create_help_btn("help_interval"))

        self.strat_row = Adw.ActionRow()
        self.strat_drop = Gtk.DropDown.new_from_strings(["Oldest", "Biggest", "Random"])
        self.strat_drop.connect("notify::selected", self.on_generic_change)
        self.strat_row.add_suffix(self.strat_drop)
        self.strat_row.add_prefix(self.create_help_btn("help_strat"))

        for r in [self.lang_row, self.daemon_row]:
            lb = Gtk.ListBox(css_classes=["boxed-list"], margin_bottom=5); lb.append(r); content.append(lb)
        
        lb_limits = Gtk.ListBox(css_classes=["boxed-list"], margin_bottom=5)
        lb_limits.append(self.gb_row); lb_limits.append(self.pct_row); content.append(lb_limits)

        lb_extra = Gtk.ListBox(css_classes=["boxed-list"], margin_bottom=5)
        lb_extra.append(self.int_row); lb_extra.append(self.strat_row); content.append(lb_extra)

        self.log_btn = Gtk.Button(css_classes=["suggested-action", "pill"])
        self.log_btn.connect("clicked", self.open_logfile)
        content.append(self.log_btn)

        main_box.append(content)
        self.win.set_content(main_box)
        self.is_loading = False
        self.load_ui_values()
        self.refresh_ui_labels()
        self.win.present()

    def on_close_request(self, window):
        # Wenn der Switch aus ist, zeige Warnung
        if not self.daemon_switch.get_active():
            dialog = Adw.MessageDialog(
                transient_for=self.win,
                heading=self.t("warn_title"),
                body=self.t("warn_body")
            )
            dialog.add_response("cancel", self.t("warn_cancel"))
            dialog.add_response("close", self.t("warn_confirm"))
            dialog.set_response_appearance("close", Adw.ResponseAppearance.DESTRUCTIVE)
            
            def on_response(d, response):
                if response == "close":
                    self.quit()
                d.destroy()
            
            dialog.connect("response", on_response)
            dialog.present()
            return True # Verhindert das sofortige Schließen
        return False

    def on_lang_changed(self, widget, pspec):
        if self.is_loading: return
        self.settings["language_code"] = self.lang_map[widget.get_selected()]
        self.update_translation()
        self.refresh_ui_labels()
        self.save_settings()

    def on_gb_changed(self, spin):
        if self.is_loading: return
        self.is_loading = True
        val_gb = spin.get_value()
        pct = (val_gb / self.get_free_space()) * 100
        val_pct = min(int(pct), 50)
        self.pct_scale.set_value(val_pct)
        self.pct_label.set_label(f"{val_pct} %")
        self.is_loading = False
        self.save_settings()

    def on_pct_changed(self, scale):
        val_pct = int(scale.get_value())
        self.pct_label.set_label(f"{val_pct} %")
        if self.is_loading: return
        self.is_loading = True
        new_gb = (val_pct / 100) * self.get_free_space()
        self.gb_spin.set_value(round(new_gb, 2))
        self.is_loading = False
        self.save_settings()

    def load_ui_values(self):
        self.is_loading = True
        s = self.settings
        self.lang_drop.set_selected(self.lang_map.index(s.get("language_code", "de")))
        self.daemon_switch.set_active(s.get("service_enabled", False))
        self.gb_spin.set_value(s.get("fixed_gb_val", 2.0))
        self.pct_scale.set_value(s.get("percent_val", 10))
        self.pct_label.set_label(f"{int(self.pct_scale.get_value())} %")
        self.int_drop.set_selected(s.get("interval_idx", 1))
        self.strat_drop.set_selected(s.get("del_strategy_idx", 0))
        self.is_loading = False

    def refresh_ui_labels(self):
        t = self.t
        self.free_label.set_label(f"{t('free_space')}: {self.get_free_space():.2f} GB")
        self.lang_row.set_title(t("lang_title"))
        self.daemon_row.set_title(t("daemon_title"))
        self.gb_row.set_title(t("limit_gb_title"))
        self.pct_row.set_title(t("limit_pct_title"))
        self.int_row.set_title(t("interval_title"))
        self.strat_row.set_title(t("strat_title"))
        self.log_btn.set_label(t("btn_log_title"))

    def on_generic_change(self, *args):
        if not self.is_loading: self.save_settings()

    def save_settings(self):
        self.settings.update({
            "service_enabled": self.daemon_switch.get_active(),
            "interval_idx": self.int_drop.get_selected(),
            "fixed_gb_val": round(self.gb_spin.get_value(), 2),
            "percent_val": int(self.pct_scale.get_value()),
            "del_strategy_idx": self.strat_drop.get_selected(),
            "language_code": self.settings.get("language_code", "de")
        })
        os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
        with open(self.settings_path, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    app = TrashGuardApp()
    app.run(sys.argv)