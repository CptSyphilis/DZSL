import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gdk, Adw

from ui.helpers import (
    normalize_map_name,
    format_server_time,
    filter_server_mods,
    transient_window,
    format_server_subtitle,
    server_tags,
)


def _row(label, value):
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    box.set_margin_top(4)
    box.set_margin_bottom(4)
    lbl = Gtk.Label(label=label)
    lbl.add_css_class("settings-label")
    lbl.set_halign(Gtk.Align.START)
    lbl.set_size_request(120, -1)
    val = Gtk.Label(label=value or "—")
    val.set_halign(Gtk.Align.START)
    val.set_hexpand(True)
    val.set_wrap(True)
    val.set_selectable(True)
    box.append(lbl)
    box.append(val)
    return box


def _copy_address(parent, ip, port):
    text = f"{ip}:{port}"
    Gdk.Display.get_default().get_clipboard().set(
        Gdk.ContentProvider.new_for_value(text)
    )
    win = transient_window(parent)
    if win:
        d = Adw.MessageDialog(transient_for=win)
        d.set_heading("Copied")
        d.set_body(text)
        d.add_response("ok", "OK")
        d.connect("response", lambda dialog, _: dialog.destroy())
        d.present()


def show_server_properties(parent, server):
    parent_win = transient_window(parent)
    if not parent_win:
        return

    ip = server.get("ip") or server.get("endpoint", {}).get("ip", "")
    port = server.get("port") or server.get("gamePort") or server.get("endpoint", {}).get("port", 2302)
    query_port = server.get("queryPort") or server.get("endpoint", {}).get("queryPort", "")
    map_name = normalize_map_name(server.get("map") or server.get("worldName") or "")
    mods = filter_server_mods(server.get("mods") or [])
    players = server.get("players", 0)
    max_players = server.get("maxPlayers", server.get("maxplayers", 0))
    version = server.get("version", "")
    ping = server.get("ping")
    tags = ", ".join(server_tags(server)) or "—"

    d = Adw.Dialog()
    d.set_title(server.get("name", "Server Properties"))

    toolbar = Adw.ToolbarView()
    header = Adw.HeaderBar()
    title = Gtk.Label(label=server.get("name", "Server Properties"))
    title.add_css_class("title")
    header.set_title_widget(title)
    close = Gtk.Button(icon_name="window-close-symbolic")
    close.connect("clicked", lambda _: d.close())
    header.pack_end(close)
    toolbar.add_top_bar(header)

    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_vexpand(True)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    outer.set_margin_top(12)
    outer.set_margin_bottom(12)
    outer.set_margin_start(16)
    outer.set_margin_end(16)

    for label, value in [
        ("Address", format_server_subtitle(server)),
        ("Query Port", str(query_port) if query_port else "—"),
        ("Map", map_name or "—"),
        ("Players", f"{players}/{max_players}" if max_players else str(players)),
        ("Ping", f"{ping} ms" if ping else "—"),
        ("Time", format_server_time(server)),
        ("Version", version or "—"),
        ("Tags", tags),
        ("Mods", str(len(mods)) if mods else "0"),
        ("Password", "Yes" if server.get("password") or server.get("hasPassword") else "No"),
        ("BattlEye", "Yes" if server.get("battlEye", server.get("battleye", True)) else "No"),
    ]:
        outer.append(_row(label, str(value)))

    if mods:
        mod_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        mod_box.set_margin_top(8)
        mod_lbl = Gtk.Label(label="Mod list")
        mod_lbl.add_css_class("settings-title")
        mod_lbl.set_halign(Gtk.Align.START)
        mod_box.append(mod_lbl)
        for m in mods[:30]:
            name = m.get("name") or m.get("steamWorkshopId") or m.get("id") or "?"
            mid = m.get("steamWorkshopId") or m.get("id") or ""
            mod_box.append(_row("", f"{name} ({mid})" if mid else name))
        if len(mods) > 30:
            mod_box.append(_row("", f"… and {len(mods) - 30} more"))
        outer.append(mod_box)

    scroll.set_child(outer)
    toolbar.set_content(scroll)

    btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    btn_box.set_margin_top(8)
    btn_box.set_margin_bottom(8)
    btn_box.set_margin_start(16)
    btn_box.set_margin_end(16)
    btn_box.set_halign(Gtk.Align.END)

    copy_btn = Gtk.Button(label="Copy IP:Port")
    copy_btn.add_css_class("btn-ghost")
    copy_btn.connect("clicked", lambda _: _copy_address(parent, ip, port))
    btn_box.append(copy_btn)

    close_btn = Gtk.Button(label="Close")
    close_btn.add_css_class("btn-connect")
    close_btn.connect("clicked", lambda _: d.close())
    btn_box.append(close_btn)

    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    root.append(toolbar)
    root.append(btn_box)
    d.set_child(root)
    d.present(parent_win)