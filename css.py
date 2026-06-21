CSS = """
window { background: #0d0d0d; }

/* Sidebar */
.sidebar { background: #111; border-right: 1px solid #1c1c1c; min-width: 200px; }
.nav-section { color: #3a3a3a; font-size: 10px; letter-spacing: 2px; font-weight: 700;
               padding: 16px 16px 4px; font-family: monospace; }
.nav-btn { border-radius: 0; padding: 10px 16px; color: #555; font-size: 13px;
           border: none; background: transparent; }
.nav-btn:hover { background: #181818; color: #aaa; }
.nav-btn.active { background: #1a1a1a; color: #d4b483; border-left: 2px solid #d4b483; }

/* Header */
.app-header { background: #0d0d0d; border-bottom: 1px solid #1c1c1c; padding: 12px 20px; }
.app-title { color: #d4b483; font-size: 22px; font-weight: 900; letter-spacing: 3px; font-family: monospace; }
.app-sub   { color: #333; font-size: 10px; letter-spacing: 2px; font-family: monospace; }

/* Toolbar */
.toolbar { background: #111; border-bottom: 1px solid #1c1c1c; padding: 6px 12px; }
.toolbar-btn { background: #1a1a1a; border: 1px solid #252525; border-radius: 3px;
               color: #666; font-size: 11px; padding: 5px 10px; }
.toolbar-btn:hover { background: #222; color: #aaa; border-color: #333; }
.toolbar-btn.accent { background: #1e1409; border-color: #3a2a10; color: #d4b483; }
.toolbar-btn.accent:hover { background: #2a1e0d; }

/* Filter bar */
.filter-row { background: #0f0f0f; border-bottom: 1px solid #1a1a1a; padding: 6px 12px; }
.filter-label { color: #444; font-size: 10px; letter-spacing: 1px; font-family: monospace; margin-bottom: 2px; }
.search-box { background: #161616; border: 1px solid #222; border-radius: 3px;
              color: #bbb; font-size: 12px; padding: 5px 10px; min-width: 140px; }
.search-box:focus { border-color: #d4b483; }
.filter-check { color: #555; font-size: 11px; }
.filter-check:checked { color: #d4b483; }

/* Server rows */
.server-row { background: #111; border-bottom: 1px solid #161616; padding: 10px 16px; }
.server-row:hover { background: #161616; }
.srv-name { color: #ccc; font-size: 13px; font-weight: 600; }
.srv-detail { color: #444; font-size: 11px; }
.srv-players { color: #d4b483; font-size: 12px; font-weight: 700; font-family: monospace; }
.ping-good { color: #4a8a4a; font-size: 11px; font-family: monospace; }
.ping-ok   { color: #8a7a3a; font-size: 11px; font-family: monospace; }
.ping-bad  { color: #8a3a3a; font-size: 11px; font-family: monospace; }

/* Tags */
.tag { font-size: 9px; padding: 1px 5px; border-radius: 2px; font-weight: 700; letter-spacing: 1px; }
.tag-mod  { background: #0d1a0d; color: #4a8a4a; }
.tag-van  { background: #0d0d1a; color: #4a6a8a; }
.tag-1pp  { background: #1a0d0d; color: #8a4a4a; }
.tag-pass { background: #1a1a0d; color: #8a8a4a; }

/* Buttons */
.btn-connect { background: #8a1a1a; color: #fff; font-weight: 700; font-size: 12px;
               letter-spacing: 1px; border-radius: 2px; padding: 7px 18px; border: none; }
.btn-connect:hover { background: #aa2020; }
.btn-ghost { background: transparent; border: 1px solid #252525; border-radius: 2px;
             color: #555; font-size: 11px; padding: 5px 10px; }
.btn-ghost:hover { border-color: #d4b483; color: #d4b483; }
.btn-info-active { background: transparent; border: 1px solid #fff; border-radius: 2px;
                    color: #fff; font-size: 11px; padding: 5px 10px; }
.btn-info-active:hover { background: #1a1a1a; border-color: #d4b483; color: #d4b483; }
.btn-steam { background: #1b2838; border: 1px solid #2a475e; border-radius: 2px;
             color: #c7d5e0; font-size: 11px; padding: 5px 10px; }
.btn-steam:hover { background: #2a3f56; }
.btn-danger { background: transparent; border: 1px solid #3a1a1a; border-radius: 2px;
              color: #8a3a3a; font-size: 11px; padding: 5px 10px; }
.btn-danger:hover { background: #1a0d0d; }

/* Status bar */
.statusbar { background: #080808; border-top: 1px solid #161616; padding: 3px 12px; }
.status-txt { color: #333; font-size: 10px; font-family: monospace; }

/* Settings */
.settings-group { background: #111; border: 1px solid #1c1c1c; border-radius: 4px;
                  padding: 16px; margin: 8px 16px; }
.settings-label { color: #555; font-size: 10px; letter-spacing: 1px; font-family: monospace; margin-bottom: 4px; }
.settings-input { background: #161616; border: 1px solid #222; border-radius: 3px;
                  color: #bbb; font-size: 12px; padding: 6px 10px; }
.settings-input:focus { border-color: #d4b483; }
.settings-title { color: #d4b483; font-size: 11px; letter-spacing: 2px; font-weight: 700;
                  font-family: monospace; padding: 16px 16px 8px; }

/* Mods */
.mod-row { background: #111; border-bottom: 1px solid #161616; padding: 8px 16px; }
.mod-row:hover { background: #161616; }
.mod-name { color: #ccc; font-size: 12px; font-weight: 600; }
.mod-id   { color: #333; font-size: 10px; font-family: monospace; }

/* Empty state */
.empty { color: #2a2a2a; font-size: 14px; font-style: italic; }

/* Sub-tabs */
.subtab { border-radius: 0; padding: 8px 16px; color: #444; font-size: 12px;
          border: none; background: transparent; border-bottom: 2px solid transparent; }
.subtab:hover { color: #888; }
.subtab.active { color: #d4b483; border-bottom: 2px solid #d4b483; background: transparent; }

/* Filter panel */
.filter-panel { background: #0d0d0d; border-right: 1px solid #1c1c1c; padding: 12px 10px; min-width: 200px; }

/* Table */
.col-header { background: #0a0a0a; border-bottom: 2px solid #1c1c1c; padding: 0; }
.col-btn { background: transparent; border: none; color: #333; font-size: 10px;
           letter-spacing: 1px; font-family: monospace; padding: 8px 6px; border-radius: 0; }
.col-btn:hover { background: #141414; color: #d4b483; }
.col-label { color: #222; font-size: 10px; letter-spacing: 1px; font-family: monospace; padding: 8px 6px; }
.table-row { background: #0f0f0f; border-bottom: 1px solid #141414; padding: 8px 4px; }
.table-row:hover { background: #141414; }
.table-row.selected {
    background: #1a1f2e;
    border-left: 4px solid #d4b483;
}
.table-row.selected {
    background: #1a1f2e;
    border-left: 4px solid #d4b483;
}
/* Fav star */
.fav-star { background: transparent; border: none; color: #d4b483; font-size: 16px; padding: 0 8px; }
.fav-star:hover { color: #fff; }
.fav-star-empty { background: transparent; border: none; color: #2a2a2a; font-size: 16px; padding: 0 8px; }
.fav-star-empty:hover { color: #d4b483; }
/* Context menu */
.context-btn { background: #161616; border: none; border-radius: 2px; color: #aaa;
               font-size: 12px; padding: 6px 16px; }
.context-btn:hover { background: #1e1e1e; color: #d4b483; }

"""
