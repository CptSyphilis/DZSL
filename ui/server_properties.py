import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gdk, Adw

from ui.helpers import (
    normalize_map_name,
    format_server_time,
    filter_server_mods,
    transient_window,
    server_tags,
    server_key,
)


def _field(label, value):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    lbl = Gtk.Label(label=label)
    lbl.add_css_class("settings-label")
    lbl.set_halign(Gtk.Align.START)
    val = Gtk.Label(label=value or "—")
    val.add_css_class("srv-detail")
    val.set_halign(Gtk.Align.START)
    val.set_wrap(True)
    val.set_selectable(True)
    box.append(lbl)
    box.append(val)
    return box


def _section(title, rows):
    group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    group.add_css_class("settings-group")

    heading = Gtk.Label(label=title)
    heading.add_css_class("settings-title")
    heading.set_halign(Gtk.Align.START)
    group.append(heading)

    for label, value in rows:
        group.append(_field(label, value))

    return group


def show_server_properties(parent, server):
    parent_win = transient_window(parent)
    if not parent_win:
        return

    ip, port = server_key(server)
    address = f"{ip}:{port}" if ip else "—"
    query_port = server.get("queryPort") or server.get("endpoint", {}).get("queryPort", "")
    map_name = normalize_map_name(server.get("map") or server.get("worldName") or "")
    mods = filter_server_mods(server.get("mods") or [])
    players = server.get("players", 0)
    max_players = server.get("maxPlayers", server.get("maxplayers", 0))
    version = server.get("version", "")
    ping = server.get("ping")
    tags = ", ".join(server_tags(server)) or "—"
    has_password = server.get("password") or server.get("hasPassword")
    battleye = server.get("battlEye", server.get("battleye", True))

    win = Adw.Window()
    win.set_transient_for(parent_win)
    win.set_modal(True)
    win.set_title("Server Properties")
    win.set_default_size(460, 520)

    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

    header = Adw.HeaderBar()
    title = Gtk.Label(label=server.get("name", "Server Properties"))
    title.set_ellipsize(3)
    title.set_max_width_chars(40)
    header.set_title_widget(title)
    root.append(header)

    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_vexpand(True)

    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    body.set_margin_top(12)
    body.set_margin_bottom(12)
    body.set_margin_start(16)
    body.set_margin_end(16)

    body.append(_section("Connection", [
        ("Address", address),
        ("Query Port", str(query_port) if query_port else "—"),
    ]))

    body.append(_section("Server", [
        ("Map", map_name or "—"),
        ("Players", f"{players}/{max_players}" if max_players else str(players)),
        ("Ping", f"{ping} ms" if ping is not None else "—"),
        ("Time", format_server_time(server)),
        ("Version", version or "—"),
        ("Tags", tags),
    ]))

    body.append(_section("Security", [
        ("Password", "Yes" if has_password else "No"),
        ("BattlEye", "Yes" if battleye else "No"),
    ]))

    if mods:
        mod_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        mod_group.add_css_class("settings-group")
        mod_heading = Gtk.Label(label=f"Mods ({len(mods)})")
        mod_heading.add_css_class("settings-title")
        mod_heading.set_halign(Gtk.Align.START)
        mod_group.append(mod_heading)

        mod_scroll = Gtk.ScrolledWindow()
        mod_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        max_h = 220
        min_h = min(min(len(mods), 8) * 28, max_h)
        mod_scroll.set_min_content_height(min_h)
        mod_scroll.set_max_content_height(max_h)

        mod_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        for m in mods[:40]:
            name = m.get("name") or m.get("steamWorkshopId") or m.get("id") or "?"
            mid = m.get("steamWorkshopId") or m.get("id") or ""
            line = Gtk.Label(label=f"{name}  ({mid})" if mid else name)
            line.add_css_class("mod-id")
            line.set_halign(Gtk.Align.START)
            line.set_wrap(True)
            line.set_selectable(True)
            mod_list.append(line)
        if len(mods) > 40:
            more = Gtk.Label(label=f"… and {len(mods) - 40} more")
            more.add_css_class("status-txt")
            more.set_halign(Gtk.Align.START)
            mod_list.append(more)

        mod_scroll.set_child(mod_list)
        mod_group.append(mod_scroll)
        body.append(mod_group)

    scroll.set_child(body)
    root.append(scroll)

    btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    btn_row.set_margin_top(8)
    btn_row.set_margin_bottom(12)
    btn_row.set_margin_start(16)
    btn_row.set_margin_end(16)
    btn_row.set_halign(Gtk.Align.END)

    copy_btn = Gtk.Button(label="Copy IP:Port")
    copy_btn.add_css_class("btn-ghost")

    def copy_address(_):
        if not ip:
            return
        Gdk.Display.get_default().get_clipboard().set(
            Gdk.ContentProvider.new_for_value(address)
        )

    copy_btn.connect("clicked", copy_address)
    btn_row.append(copy_btn)

    close_btn = Gtk.Button(label="Close")
    close_btn.add_css_class("btn-connect")
    close_btn.connect("clicked", lambda _: win.close())
    btn_row.append(close_btn)

    root.append(btn_row)
    win.set_content(root)
    win.present()