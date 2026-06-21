import threading
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib

class ModProgressDialog:
    SUBSCRIBE_END = 0.20
    DOWNLOAD_END = 0.92

    def __init__(self, parent, heading, mod_ids, names, on_cancel=None,
                 on_open_downloads=None):
        self._cancel = threading.Event()
        self._continue = threading.Event()
        self._closed = False
        self.on_cancel = on_cancel
        self.on_open_downloads = on_open_downloads
        self.mod_ids = list(mod_ids)

        self.win = Adw.Window()
        self.win.set_transient_for(parent)
        self.win.set_modal(True)
        self.win.set_title(heading)
        self.win.set_default_size(480, 420)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        root.set_margin_top(20)
        root.set_margin_bottom(20)
        root.set_margin_start(20)
        root.set_margin_end(20)

        title = Gtk.Label(label=heading)
        title.add_css_class("settings-title")
        title.set_halign(Gtk.Align.START)
        root.append(title)

        self.hint = Gtk.Label(label="")
        self.hint.add_css_class("status-txt")
        self.hint.set_halign(Gtk.Align.START)
        self.hint.set_wrap(True)
        self.hint.set_visible(False)
        root.append(self.hint)

        self.status = Gtk.Label(label="Preparing…")
        self.status.add_css_class("status-txt")
        self.status.set_halign(Gtk.Align.START)
        self.status.set_wrap(True)
        root.append(self.status)

        self.bar = Gtk.ProgressBar()
        self.bar.set_show_text(True)
        self.bar.set_fraction(0.0)
        self.bar.set_text("0%")
        root.append(self.bar)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.rows = {}
        for mid in mod_ids:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            mark = Gtk.Label(label="○")
            mark.set_width_chars(2)
            name = Gtk.Label(label=names.get(mid, mid))
            name.set_halign(Gtk.Align.START)
            name.set_hexpand(True)
            name.set_ellipsize(3)
            row.append(mark)
            row.append(name)
            self.rows[mid] = mark
            self.list_box.append(row)
        scroll.set_child(self.list_box)
        root.append(scroll)

        action_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        action_row.set_halign(Gtk.Align.START)
        action_row.set_margin_top(4)

        if on_open_downloads:
            dl_btn = Gtk.Button(label="Open Steam Downloads")
            dl_btn.add_css_class("btn-ghost")
            dl_btn.connect("clicked", lambda *_: on_open_downloads())
            action_row.append(dl_btn)

        self.next_btn = Gtk.Button(label="Next mod (subscribed)")
        self.next_btn.add_css_class("btn-ghost")
        self.next_btn.connect("clicked", self._on_next_mod)
        action_row.append(self.next_btn)

        root.append(action_row)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)
        btn_row.set_margin_top(4)

        self.stop_btn = Gtk.Button(label="Stop Download")
        self.stop_btn.add_css_class("btn-ghost")
        self.stop_btn.connect("clicked", self._on_stop)
        btn_row.append(self.stop_btn)

        close_btn = Gtk.Button(label="Close")
        close_btn.add_css_class("btn-ghost")
        close_btn.connect("clicked", self._on_close)
        btn_row.append(close_btn)

        root.append(btn_row)

        self.win.set_content(root)
        self.win.connect("close-request", self._on_close_request)
        self.win.present()

    def _run(self, fn):
        GLib.idle_add(fn)

    def is_cancelled(self):
        return self._cancel.is_set()

    def clear_continue(self):
        self._continue.clear()

    def continue_requested(self):
        return self._continue.is_set()

    def _on_next_mod(self, *_):
        self._continue.set()

    def set_action_prompt(self, text):
        self.set_phase(text, None)

    def request_cancel(self):
        if self._cancel.is_set():
            return
        self._cancel.set()
        self.set_phase("Stopping download…")
        self._run(lambda: self.stop_btn.set_sensitive(False))
        if self.on_cancel:
            self.on_cancel()

    def _on_stop(self, *_):
        self.request_cancel()

    def _on_close(self, *_):
        self.request_cancel()
        self.close()

    def _on_close_request(self, win):
        self.request_cancel()
        self._closed = True
        return False

    def set_hint(self, text):
        def update():
            if self._closed:
                return
            self.hint.set_text(text)
            self.hint.set_visible(bool(text))
        self._run(update)

    def set_phase(self, text, fraction=None):
        def update():
            if self._closed:
                return
            self.status.set_text(text)
            if fraction is None:
                self.bar.pulse()
            else:
                self.bar.set_fraction(min(max(fraction, 0.0), 1.0))
                self.bar.set_text(f"{int(fraction * 100)}%")
        self._run(update)

    def _download_fraction(self, done, total, subscribed=0):
        total = max(total, 1)
        downloaded_frac = done / total
        subscribed_only = max(0, subscribed - done) / total
        span = self.DOWNLOAD_END - self.SUBSCRIBE_END
        return self.SUBSCRIBE_END + span * (downloaded_frac + subscribed_only * 0.35)

    def set_subscribe_progress(self, done, total, subscribed=0):
        total = max(total, 1)
        opened_frac = (done / total) * self.SUBSCRIBE_END
        sub_frac = (subscribed / total) * self.SUBSCRIBE_END
        frac = max(opened_frac, sub_frac)
        msg = f"Subscribing via Steam… {done}/{total}"
        if subscribed:
            msg += f" — subscribed {subscribed}/{total}"
        self.set_phase(msg, frac)

    def set_download_progress(self, done, total, subscribed=0, elapsed=0):
        total = max(total, 1)
        done = min(max(done, 0), total)
        frac = self._download_fraction(done, total, subscribed)
        msg = f"Downloaded {done}/{total}"
        if subscribed > done:
            msg += f", subscribed {subscribed}/{total}"
        if done < total:
            if subscribed <= done and elapsed:
                msg += f" — waiting for Steam ({elapsed}s)"
            elif elapsed:
                msg += f" — waiting for Steam ({elapsed}s)"
        self.set_phase(msg, frac)

    def set_setup_progress(self, text):
        self.set_phase(text, 0.95)

    def mark_subscribed(self, mid):
        def update():
            if mid in self.rows:
                self.rows[mid].set_text("◐")
        self._run(update)

    def mark_installed(self, mid):
        def update():
            if mid in self.rows:
                self.rows[mid].set_text("✓")
        self._run(update)

    def close(self):
        if self._closed:
            return
        self._closed = True

        def update():
            self.win.close()
        self._run(update)
