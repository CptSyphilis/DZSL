import threading
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

def _fmt_bytes(n):
    n = float(n or 0)
    if n < 1024:
        return f"{int(n)} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    if n < 1024 ** 3:
        return f"{n / 1024 ** 2:.1f} MB"
    return f"{n / 1024 ** 3:.2f} GB"

class ModProgressDialog:
    SUBSCRIBE_END = 0.20
    DOWNLOAD_END  = 0.92

    def __init__(self, mod_ids, names, on_cancel=None,
                 on_open_downloads=None):
        self._cancel   = threading.Event()
        self._continue = threading.Event()
        self._closed   = False
        self.on_cancel = on_cancel
        self.on_open_downloads = on_open_downloads
        self.mod_ids   = list(mod_ids)
        self.names     = names or {}
        self.total       = len(self.mod_ids)
        self.done_count  = 0
        self.current_mod_name  = ""
        self.current_fraction  = 0.0
        self.current_size_text = ""

        self.popover = Gtk.Popover()
        self.popover.add_css_class("dl-toast")
        self.popover.set_position(Gtk.PositionType.TOP)
        self.popover.set_has_arrow(False)
        self.popover.set_autohide(True)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        root.add_css_class("dl-toast-body")
        root.set_size_request(380, -1)
        root.set_margin_top(14)
        root.set_margin_bottom(12)
        root.set_margin_start(14)
        root.set_margin_end(14)

        eyebrow_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.eyebrow = Gtk.Label(label=f"DOWNLOADING · 0/{self.total}")
        self.eyebrow.add_css_class("dl-toast-eyebrow")
        self.eyebrow.set_halign(Gtk.Align.START)
        self.eyebrow.set_hexpand(True)
        eyebrow_row.append(self.eyebrow)
        root.append(eyebrow_row)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.add_css_class("dl-toast-sep")
        root.append(sep)

        name_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.name_lbl = Gtk.Label(label="Preparing…")
        self.name_lbl.add_css_class("dl-toast-name")
        self.name_lbl.set_halign(Gtk.Align.START)
        self.name_lbl.set_hexpand(True)
        self.name_lbl.set_ellipsize(3)
        name_row.append(self.name_lbl)
        self.pct_lbl = Gtk.Label(label="")
        self.pct_lbl.add_css_class("dl-toast-pct")
        name_row.append(self.pct_lbl)
        root.append(name_row)

        self.bar = Gtk.ProgressBar()
        self.bar.add_css_class("dl-toast-bar")
        self.bar.set_show_text(False)
        root.append(self.bar)

        meta_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.size_lbl = Gtk.Label(label="")
        self.size_lbl.add_css_class("dl-toast-meta")
        self.size_lbl.set_halign(Gtk.Align.START)
        self.size_lbl.set_hexpand(True)
        meta_row.append(self.size_lbl)
        self.speed_label = Gtk.Label(label="—")
        self.speed_label.add_css_class("dl-toast-speed")
        meta_row.append(self.speed_label)
        root.append(meta_row)

        self.hint = Gtk.Label(label="")
        self.hint.add_css_class("dl-toast-hint")
        self.hint.set_halign(Gtk.Align.START)
        self.hint.set_wrap(False)
        self.hint.set_ellipsize(3)
        self.hint.set_visible(False)
        root.append(self.hint)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        btn_row.set_halign(Gtk.Align.END)
        btn_row.set_spacing(6)
        btn_row.set_margin_top(2)

        if self.on_open_downloads:
            self.downloads_btn = Gtk.Button(label="Steam Downloads")
            self.downloads_btn.add_css_class("btn-ghost")
            self.downloads_btn.connect("clicked", lambda *_: self.on_open_downloads())
            btn_row.append(self.downloads_btn)

        self.next_btn = Gtk.Button(label="Continue")
        self.next_btn.add_css_class("btn-ghost")
        self.next_btn.connect("clicked", self._on_next_mod)
        btn_row.append(self.next_btn)

        self.stop_btn = Gtk.Button(label="Stop")
        self.stop_btn.add_css_class("btn-danger")
        self.stop_btn.connect("clicked", self._on_stop)
        btn_row.append(self.stop_btn)

        root.append(btn_row)

        self.popover.set_child(root)

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

    def set_speed(self, text):
        def update():
            if self._closed:
                return
            self.speed_label.set_text(text or "—")
        self._run(update)

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
            self.hint.set_text(text)
            self.hint.set_visible(bool(text))
            if fraction is not None:
                self.bar.set_fraction(min(max(fraction, 0.0), 1.0))
        self._run(update)

    def _download_fraction(self, done, total, subscribed=0):
        total = max(total, 1)
        downloaded_frac  = done / total
        subscribed_only  = max(0, subscribed - done) / total
        span = self.DOWNLOAD_END - self.SUBSCRIBE_END
        return self.SUBSCRIBE_END + span * (downloaded_frac + subscribed_only * 0.35)

    def set_subscribe_progress(self, done, total, subscribed=0):
        total = max(total, 1)
        opened_frac = (done / total) * self.SUBSCRIBE_END
        sub_frac    = (subscribed / total) * self.SUBSCRIBE_END
        frac = max(opened_frac, sub_frac)
        msg = f"Subscribing via Steam… {done}/{total}"
        if subscribed:
            msg += f" — subscribed {subscribed}/{total}"
        self.set_phase(msg, frac)

    def set_download_progress(self, done, total, subscribed=0, elapsed=0):
        total = max(total, 1)
        done  = min(max(done, 0), total)
        frac  = self._download_fraction(done, total, subscribed)
        msg   = f"Downloaded {done}/{total}"
        if subscribed > done:
            msg += f", subscribed {subscribed}/{total}"
        if done < total and elapsed:
            msg += f" — waiting for Steam ({elapsed}s)"
        self.set_phase(msg, frac)

    def set_setup_progress(self, text):
        self.set_phase(text, 0.95)

    def set_mod_progress(self, mid, fraction, bytes_done=None, total_bytes=None):
        fraction = max(0.0, min(1.0, fraction))
        self.current_fraction = fraction
        self.current_mod_name = self.names.get(mid, mid)
        if bytes_done is not None and total_bytes:
            self.current_size_text = f"{_fmt_bytes(bytes_done)} / {_fmt_bytes(total_bytes)}"
        else:
            self.current_size_text = ""
        def update():
            if self._closed:
                return
            self.name_lbl.set_text(self.current_mod_name)
            self.pct_lbl.set_text(f"{int(fraction * 100)}%")
            self.bar.set_fraction(fraction)
            self.size_lbl.set_text(self.current_size_text)
        self._run(update)

    def mark_subscribed(self, mid):
        self.set_hint(f"Subscribed: {self.names.get(mid, mid)}")

    def mark_installed(self, _mid):
        self.done_count += 1
        def update():
            self.eyebrow.set_text(f"DOWNLOADING · {self.done_count}/{self.total}")
        self._run(update)

    def close(self):
        if self._closed:
            return
        self._closed = True
        def update():
            self.popover.popdown()
            if self.popover.get_parent():
                self.popover.unparent()
        self._run(update)
