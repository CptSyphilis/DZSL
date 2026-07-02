CSS = """
window { background: #090d12; font-family: "Oswald", sans-serif; }
button {
    background: linear-gradient(110deg, rgba(110,231,240,0.07), rgba(124,108,255,0.11), rgba(255,122,209,0.06));
    border: 1px solid rgba(177,140,255,0.50);
    border-radius: 4px;
    color: #d9eef7;
    font-weight: 700;
    letter-spacing: 1px;
    padding: 6px 12px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.36);
}
button:hover {
    background: linear-gradient(110deg, rgba(110,231,240,0.15), rgba(124,108,255,0.19), rgba(255,122,209,0.12));
    border-color: rgba(255,122,209,0.72);
    color: #ffffff;
}
button:disabled { opacity: 0.42; box-shadow: none; }

/* Sidebar */
.sidebar { background: #0f141b; border-right: 1px solid #1c242e; min-width: 200px; }
.nav-section { color: #465563; font-size: 10px; letter-spacing: 2px; font-weight: 700;
               padding: 16px 16px 4px; font-family: monospace; }
.nav-btn { border-radius: 3px; padding: 9px 14px; margin: 2px 8px; color: #71828f; font-size: 13px;
           border: 1px solid rgba(124,108,255,0.16);
           background: linear-gradient(to right, rgba(110,231,240,0.025), rgba(124,108,255,0.045), rgba(255,122,209,0.02)); }
.nav-btn:hover { background: linear-gradient(to right, rgba(110,231,240,0.09), rgba(124,108,255,0.12), rgba(255,122,209,0.07));
                 border-color: rgba(177,140,255,0.48); color: #d9eef7; }
.nav-btn.active { background: linear-gradient(to right, rgba(110,231,240,0.08), rgba(124,108,255,0.09), rgba(255,122,209,0.05));
                  color: #b9e2f2; border-color: rgba(255,122,209,0.48); border-left: 2px solid rgba(177,140,255,0.78); }

/* Header */
.app-header { background: #090d12; border-bottom: 1px solid #1c242e; padding: 12px 20px; }
.app-title { font-size: 22px; font-weight: 400; letter-spacing: 2px;
             font-family: "Black Ops One", sans-serif; text-shadow: 0 0 10px rgba(177,140,255,0.20); }
.app-sub   { color: #34414d; font-size: 10px; letter-spacing: 2px; font-family: monospace; }
.header-link { background: linear-gradient(to right, rgba(110,231,240,0.03), rgba(124,108,255,0.06), rgba(255,122,209,0.03));
               border: 1px solid rgba(124,108,255,0.22); border-radius: 3px; color: #78b8ee;
               font-size: 11px; letter-spacing: 1px; padding: 4px 8px; margin: 0; min-height: 0; }
.header-link:hover { background: linear-gradient(to right, rgba(110,231,240,0.10), rgba(124,108,255,0.14), rgba(255,122,209,0.08));
                     border-color: rgba(255,122,209,0.58); color: #e4f6ff; }
.header-link.active { color: #9a87c4;
                      border-color: rgba(177,140,255,0.52);
                      background: linear-gradient(to right, rgba(110,231,240,0.07), rgba(124,108,255,0.12), rgba(255,122,209,0.07)); }
.header-link-dl { color: #8ec9e6; font-weight: 700; }
.header-back-btn { background: linear-gradient(to right, rgba(110,231,240,0.03), rgba(124,108,255,0.06), rgba(255,122,209,0.03));
                    border: 1px solid rgba(124,108,255,0.22); border-radius: 3px; color: #6aa8ff;
                    padding: 4px 6px; margin: 0; min-height: 0; }
.header-back-btn:hover { background: linear-gradient(to right, rgba(110,231,240,0.10), rgba(124,108,255,0.14), rgba(255,122,209,0.08));
                         border-color: rgba(255,122,209,0.58); color: #d9eef7; }

/* Welcome screen */
.welcome-scrim {
    background: linear-gradient(to bottom,
        rgba(8,10,12,0.30) 0%,
        rgba(8,10,12,0.45) 45%,
        rgba(8,10,12,0.82) 100%);
}
.welcome-bg-fallback { background: #0b0f14; }
.welcome-title { font-size: 72px; font-weight: 400; letter-spacing: 2px;
                 font-family: "Black Ops One", sans-serif;
                 text-shadow: 0 0 18px rgba(124,108,255,0.22), 0 2px 12px rgba(0,0,0,0.9); }
.welcome-sub { color: #83bfc5; font-size: 14px; font-weight: 600; letter-spacing: 3px;
               font-family: "Oswald", sans-serif;
               text-shadow: 0 1px 6px rgba(0,0,0,0.9); }
.welcome-primary { background: linear-gradient(110deg, rgba(110,231,240,0.09), rgba(124,108,255,0.11), rgba(255,122,209,0.07));
                   border: 1px solid rgba(177,140,255,0.58); border-radius: 4px;
                   color: #d9eef7; font-size: 14px; font-weight: 700; padding: 12px 48px; letter-spacing: 2px;
                   box-shadow: 0 4px 16px rgba(0,0,0,0.6); }
.welcome-primary:hover { background: linear-gradient(110deg, rgba(110,231,240,0.16), rgba(124,108,255,0.18), rgba(255,122,209,0.12));
                         border-color: rgba(255,122,209,0.70); color: #fff; }
.welcome-secondary { background: linear-gradient(110deg, rgba(10,24,29,0.78), rgba(25,20,45,0.80), rgba(37,17,36,0.70));
                     border: 1px solid rgba(177,140,255,0.40); border-radius: 4px;
                     color: #e9f0f5; font-size: 12px; padding: 8px 24px;
                     box-shadow: 0 2px 10px rgba(0,0,0,0.5); }
.welcome-secondary:hover { background: linear-gradient(110deg, rgba(110,231,240,0.14), rgba(124,108,255,0.18), rgba(255,122,209,0.11));
                           color: #fff; border-color: rgba(255,122,209,0.70); }

/* Toolbar */
.toolbar { background: #0f141b; border-bottom: 1px solid #1c242e; padding: 6px 12px; }
.toolbar-btn { background: linear-gradient(to right, rgba(110,231,240,0.04), rgba(124,108,255,0.08), rgba(255,122,209,0.04));
               border: 1px solid rgba(124,108,255,0.36); border-radius: 3px;
               color: #9aabb8; font-size: 11px; padding: 5px 10px; }
.toolbar-btn:hover { background: linear-gradient(to right, rgba(110,231,240,0.12), rgba(124,108,255,0.16), rgba(255,122,209,0.09));
                     color: #e4f6ff; border-color: rgba(255,122,209,0.62); }
.toolbar-btn.accent { background: linear-gradient(to right, rgba(110,231,240,0.09), rgba(124,108,255,0.14), rgba(255,122,209,0.08));
                      border-color: rgba(177,140,255,0.62); color: #d9eef7; }
.toolbar-btn.accent:hover { background: linear-gradient(to right, rgba(110,231,240,0.10), rgba(124,108,255,0.14), rgba(255,122,209,0.08)); }

/* Filter bar */
.filter-row { background: #0f141b; border-bottom: 1px solid #17202a; padding: 6px 12px; }
.filter-label { color: #465563; font-size: 10px; letter-spacing: 1px; font-family: monospace; margin-bottom: 2px; }
.search-box { background: #141b23; border: 1px solid #26323e; border-radius: 3px;
              color: #c4d0d9; font-size: 12px; padding: 5px 10px; min-width: 140px; }
.search-box:focus { border-color: #8ec9e6; }
.filter-check { color: #586773; font-size: 11px; }
.filter-check:checked { color: #8ec9e6; }

/* Server rows */
.server-row { background: #0f141b; border-bottom: 1px solid #141b23; padding: 10px 16px; }
.server-row:hover { background: linear-gradient(to right, rgba(124,108,255,0.07), rgba(255,122,209,0.03));
                    box-shadow: inset 2px 0 rgba(177,140,255,0.55); }
.srv-name { color: #e9f0f5; font-size: 13px; font-weight: 600; }
.srv-detail { color: #465563; font-size: 11px; }
.srv-players { color: #8ec9e6; font-size: 12px; font-weight: 700; font-family: monospace; }
.ping-good { color: #4a8a4a; font-size: 11px; font-family: monospace; }
.ping-ok   { color: #8a7a3a; font-size: 11px; font-family: monospace; }
.ping-bad  { color: #8a3a3a; font-size: 11px; font-family: monospace; }

/* Tags */
.tag { font-size: 9px; padding: 1px 5px; border-radius: 2px; font-weight: 700; letter-spacing: 1px; }
.tag-mod  { background: rgba(177,140,255,0.05); color: #9a87c4; border: 1px solid rgba(177,140,255,0.28); }
.tag-van  { background: #0d0d1a; color: #4a6a8a; }
.tag-1pp  { background: #1a0d0d; color: #8a4a4a; }
.tag-pass { background: #1a1a0d; color: #8a8a4a; }
.tag-gold { background: rgba(216,173,104,0.12); color: #f0cf91; border: 1px solid rgba(216,173,104,0.48); }

/* Buttons */
.btn-connect, .btn-success, .btn-info-active, .btn-steam {
    background: linear-gradient(110deg, rgba(110,231,240,0.09), rgba(124,108,255,0.14), rgba(255,122,209,0.08));
    border: 1px solid rgba(177,140,255,0.58);
    border-radius: 4px;
    color: #d9eef7;
    font-weight: 700;
    font-size: 12px;
    letter-spacing: 1px;
    padding: 7px 18px;
}
.btn-connect:hover, .btn-success:hover, .btn-info-active:hover, .btn-steam:hover {
    background: linear-gradient(110deg, rgba(110,231,240,0.17), rgba(124,108,255,0.22), rgba(255,122,209,0.14));
    border-color: rgba(255,122,209,0.74);
    color: #ffffff;
}
.btn-ghost {
    background: linear-gradient(110deg, rgba(110,231,240,0.025), rgba(124,108,255,0.055), rgba(255,122,209,0.025));
    border: 1px solid rgba(124,108,255,0.34);
    border-radius: 4px;
    color: #8797a4;
    font-size: 11px;
    padding: 5px 10px;
}
.btn-ghost:hover {
    background: linear-gradient(110deg, rgba(110,231,240,0.11), rgba(124,108,255,0.15), rgba(255,122,209,0.09));
    border-color: rgba(255,122,209,0.62);
    color: #d9eef7;
}
.btn-danger {
    background: linear-gradient(110deg, rgba(110,231,240,0.025), rgba(124,108,255,0.045), rgba(184,55,91,0.09));
    border: 1px solid rgba(210,76,113,0.48);
    border-radius: 4px;
    color: #d68ba1;
    font-size: 11px;
    padding: 5px 10px;
}
.btn-danger:hover {
    background: linear-gradient(110deg, rgba(124,108,255,0.08), rgba(184,55,91,0.20), rgba(255,90,137,0.15));
    border-color: rgba(255,110,151,0.76);
    color: #ffdbe5;
}

/* Status bar */
.statusbar { background: #0b0f14; border-top: 1px solid #17202a; padding: 6px 16px; min-height: 32px; }
.status-txt { color: #465563; font-size: 11px; font-family: monospace; }
.statusbar-sep { background: #1c242e; margin: 0 6px; min-width: 1px; }
.statusbar-dl { padding-left: 8px; }
.status-dl-speed { color: #6aa8ff; font-size: 11px; font-family: monospace; font-weight: 700; }
.status-dl-pct { color: #8ec9e6; font-size: 11px; font-family: monospace; font-weight: 700; }
.statusbar-dl-bar { min-height: 6px; }
.statusbar-dl-bar trough { background: #17202a; border-radius: 2px; min-height: 6px; }
.statusbar-dl-bar progress { background: linear-gradient(to right, rgba(110,231,240,0.72), rgba(106,168,255,0.72), rgba(124,108,255,0.72), rgba(177,140,255,0.72), rgba(255,122,209,0.72));
                             border-radius: 2px; min-height: 6px; box-shadow: 0 0 8px rgba(177,140,255,0.24); }
.statusbar-dl-arrow { background: linear-gradient(to right, rgba(110,231,240,0.03), rgba(124,108,255,0.06), rgba(255,122,209,0.03));
                       border: 1px solid rgba(124,108,255,0.24); color: #6aa8ff; font-size: 10px;
                       padding: 2px 6px; min-height: 0; min-width: 0; }
.statusbar-dl-arrow:hover { border-color: rgba(255,122,209,0.58); color: #d9eef7; }

/* Download toast popover */
popover.dl-toast { background: transparent; }
popover.dl-toast > contents {
    background: #0f141b;
    border: 1px solid #1c242e;
    border-radius: 6px;
    padding: 0;
    box-shadow: 0 4px 16px rgba(0,0,0,0.5);
}
.dl-toast-eyebrow { color: #6aa8ff; font-size: 10px; letter-spacing: 2px; font-weight: 700;
                     font-family: monospace; }
.dl-toast-sep { background: #1c242e; min-height: 1px; }
.dl-toast-name { color: #8ec9e6; font-size: 13px; font-weight: 700; font-family: monospace; }
.dl-toast-pct { color: #8ec9e6; font-size: 12px; font-weight: 700; font-family: monospace; }
.dl-toast-bar { min-height: 5px; }
.dl-toast-bar trough { background: #17202a; border-radius: 2px; min-height: 5px; }
.dl-toast-bar progress { background: linear-gradient(to right, rgba(110,231,240,0.72), rgba(106,168,255,0.72), rgba(124,108,255,0.72), rgba(177,140,255,0.72), rgba(255,122,209,0.72));
                         border-radius: 2px; min-height: 5px; }
.dl-toast-meta { color: #586773; font-size: 10px; font-family: monospace; }
.dl-toast-speed { color: #6aa8ff; font-size: 11px; font-weight: 700; font-family: monospace; }
.dl-toast-hint { color: #465563; font-size: 10px; font-family: monospace; }
.dl-toast-queue-title { color: #465563; font-size: 9px; letter-spacing: 2px;
                        font-family: monospace; font-weight: 700; }
.dl-queue-row { padding: 4px 2px; border-bottom: 1px solid #141b23; }
.dl-queue-state { min-width: 12px; font-size: 10px; font-family: monospace; }
.dl-queue-queued { color: #34414d; }
.dl-queue-active { color: #6aa8ff; }
.dl-queue-done { color: #4a8a4a; }
.dl-queue-failed { color: #a44747; }
.dl-queue-name { color: #7d8b97; font-size: 10px; font-family: monospace; }
.dl-queue-status { color: #586773; font-size: 10px; font-family: monospace; }

/* Settings cards */
.settings-card { background: #0f141b; border: 1px solid #1c242e; border-radius: 6px; }
.settings-card-header { background: #0b0f14; border-bottom: 1px solid #17202a;
                        border-radius: 6px 6px 0 0; padding: 10px 16px; }
.settings-card-title { color: #9a87c4; font-size: 10px; letter-spacing: 2px; font-weight: 700;
                       font-family: monospace; }
.settings-card-body { padding: 16px 16px; }
.settings-field-label { color: #52616d; font-size: 10px; letter-spacing: 1px; font-family: monospace; }
.settings-note { color: #34414d; font-size: 10px; font-family: monospace; }
.settings-check { color: #677684; font-size: 12px; }
.settings-check:checked { color: #e9f0f5; }
.settings-input { background: #121820; border: 1px solid #29333d; border-radius: 3px;
                  color: #c4d0d9; font-size: 12px; padding: 6px 10px; }
.settings-input:focus { border-color: #6aa8ff; }

/* Mods */
.mods-overview { background: #0f141b; border-bottom: 1px solid #1c242e; padding: 14px 18px; }
.mods-overview-title { color: #9a87c4; font-size: 12px; font-weight: 800; letter-spacing: 2px;
                       font-family: monospace; }
.mods-overview-subtitle { color: #7d8b97; font-size: 11px; }
.mods-metric { min-width: 74px; padding: 2px 12px; border-left: 1px solid #29333d; }
.mods-metric-value { color: #e9f0f5; font-size: 17px; font-weight: 700; font-family: monospace; }
.mods-metric-label { color: #6f7e8a; font-size: 8px; font-weight: 700; letter-spacing: 1px;
                     font-family: monospace; }
.mods-metric-attention { color: #b85b5b; }
.mods-metric-update { color: #8ec9e6; }
.mods-toolbar { padding: 10px 14px; background: #0f141b; }
.mod-row { background: #0f141b; border-bottom: 1px solid #1c242e; padding: 9px 16px; }
.mod-row:hover { background: linear-gradient(to right, rgba(124,108,255,0.06), rgba(255,122,209,0.025)); }
.mod-name { color: #e9f0f5; font-size: 13px; font-weight: 650; }
.mod-id   { color: #7d8b97; font-size: 10px; font-family: monospace; }
.mod-dl-pct { color: #6aa8ff; font-size: 10px; font-family: monospace; }
.mod-record { padding: 0; }
.mod-record.selected { background: linear-gradient(to right, rgba(110,231,240,0.05), rgba(124,108,255,0.07), rgba(255,122,209,0.03));
                       border-left: 3px solid rgba(177,140,255,0.60); }
.mod-record.marked { background: linear-gradient(to right, rgba(124,108,255,0.08), rgba(255,122,209,0.04));
                     box-shadow: inset 3px 0 rgba(255,122,209,0.58); }
.mod-record-main { padding: 10px 16px; }
.mod-status { font-size: 12px; font-family: monospace; }
.mod-status-good { color: #62a66b; }
.mod-status-warn { color: #c39a4b; }
.mod-status-bad  { color: #b85b5b; }
.mod-status-update { color: #8ec9e6; border-color: #334b6b; background: #111b2b; }
.mod-state-pill { border-radius: 10px; padding: 3px 8px; margin: 0 6px;
                  background: #17202a; border: 1px solid #29333d;
                  font-size: 8px; font-weight: 800; letter-spacing: 1px; font-family: monospace; }
.mod-action-menu { background: linear-gradient(to right, rgba(110,231,240,0.025), rgba(124,108,255,0.055), rgba(255,122,209,0.025));
                   border: 1px solid rgba(124,108,255,0.28); color: #7d8b97;
                   border-radius: 3px; padding: 3px; min-width: 28px; min-height: 28px; }
.mod-action-menu:hover { background: linear-gradient(to right, rgba(110,231,240,0.10), rgba(124,108,255,0.14), rgba(255,122,209,0.08));
                         border-color: rgba(255,122,209,0.58); color: #d9eef7; }
.mod-select-check { margin-right: 2px; }
.mod-selection-bar { background: #101827; border-top: 1px solid #293d59;
                     border-bottom: 1px solid #293d59; padding: 8px 14px; }
.mod-selection-count { color: #8ec9e6; font-size: 11px; font-weight: 700;
                       letter-spacing: 1px; font-family: monospace; }
.mod-chevron { color: #465563; font-size: 18px; min-width: 18px; }
.mod-details { background: #0b0f14; border-top: 1px solid #1c242e; padding: 16px 46px 18px; }
.mod-details-grid { padding-bottom: 4px; }
.mod-detail-cell { min-height: 42px; }
.mod-dependencies { border-top: 1px solid #1c242e; padding-top: 10px; }
.mod-detail-key { color: #8ec9e6; font-size: 9px; letter-spacing: 1px;
                  font-family: monospace; font-weight: 700; }
.mod-detail-value { color: #9aabb8; font-size: 11px; font-family: monospace; }
.mods-empty { padding: 72px 24px; }
.mods-empty-title { color: #9aabb8; font-size: 16px; font-weight: 650; }
.mods-empty-detail { color: #586773; font-size: 11px; }
.mod-section-header { color: #7d8b97; background: #0b0f14; border-bottom: 1px solid #1c242e;
                      padding: 7px 16px; font-size: 9px; font-weight: 800;
                      letter-spacing: 1.5px; font-family: monospace; }
.mod-section-update { color: #8ec9e6; background: #101827; border-bottom-color: #293d59; }
.creator-toolbar { padding: 10px 14px; background: #0f141b; }
.creator-record { background: #0f141b; border-bottom: 1px solid #1c242e; }
.creator-record:hover { background: #141b23; }
.creator-record.expanded { background: #121b24; border-left: 3px solid #8ec9e6; }
.creator-record-main { padding: 11px 16px; }
.creator-monogram { min-width: 36px; min-height: 36px; border-radius: 18px;
                    background: #111b2b; border: 1px solid #334b6b; color: #8ec9e6;
                    font-size: 14px; font-weight: 800; font-family: monospace; }
.creator-name { color: #e9f0f5; font-size: 13px; font-weight: 650; }
.creator-meta { color: #7d8b97; font-size: 10px; font-family: monospace; }
.creator-chevron { color: #64727e; font-size: 18px; min-width: 18px; }
.creator-details { background: #0b0f14; border-top: 1px solid #1c242e; padding: 14px 64px 18px; }
.creator-mod-shelf { padding-top: 4px; }
.creator-mod-chip { background: #141b23; border: 1px solid #29333d; border-radius: 3px;
                    color: #aab8c3; font-size: 10px; padding: 6px 10px; }
.creator-mod-chip:hover { color: #8ec9e6; border-color: #334b6b; background: #111b2b; }

/* Empty state */
.empty { color: #2c3945; font-size: 14px; font-style: italic; }

/* Sub-tabs */
.subtab { border-radius: 3px 3px 0 0; padding: 8px 16px; color: #647582; font-size: 12px;
          border: 1px solid rgba(124,108,255,0.18); border-bottom: 2px solid transparent;
          background: linear-gradient(to right, rgba(110,231,240,0.02), rgba(124,108,255,0.04), rgba(255,122,209,0.02)); }
.subtab:hover { color: #d9eef7; border-color: rgba(177,140,255,0.44);
                background: linear-gradient(to right, rgba(110,231,240,0.08), rgba(124,108,255,0.11), rgba(255,122,209,0.06)); }
.subtab.active { color: #9a87c4; border-bottom: 2px solid rgba(255,122,209,0.60);
                 background: linear-gradient(to bottom, transparent, rgba(124,108,255,0.06)); }

/* Filter panel */
.filter-panel { background: #090d12; border-right: 1px solid #1c242e; padding: 12px 10px; min-width: 200px; }

/* Table */
.col-header { background: #0b0f14; border-bottom: 2px solid #1c242e; padding: 0; }
.col-btn { background: linear-gradient(to right, rgba(110,231,240,0.015), rgba(124,108,255,0.035), rgba(255,122,209,0.015));
           border: 1px solid rgba(124,108,255,0.12); color: #52616d; font-size: 10px;
           letter-spacing: 1px; font-family: monospace; padding: 8px 6px; border-radius: 2px; }
.col-btn:hover { background: linear-gradient(to right, rgba(110,231,240,0.08), rgba(124,108,255,0.11), rgba(255,122,209,0.06));
                 border-color: rgba(177,140,255,0.42); color: #d9eef7; }
.col-label { color: #26323e; font-size: 10px; letter-spacing: 1px; font-family: monospace; padding: 8px 6px; }
.table-row { background: #0f141b; border-bottom: 1px solid #121820; padding: 8px 4px; }
.table-row.gold-server { background: linear-gradient(to right, rgba(216,173,104,0.07), rgba(15,20,27,0.35)); }
.table-row:hover { background: linear-gradient(to right, rgba(124,108,255,0.06), rgba(255,122,209,0.025)); }
.table-row.selected {
    background: linear-gradient(to right, rgba(110,231,240,0.06), rgba(124,108,255,0.09), rgba(255,122,209,0.04));
    border-left: 4px solid rgba(177,140,255,0.62);
}
/* Fav star */
.fav-star { background: linear-gradient(to right, rgba(110,231,240,0.025), rgba(124,108,255,0.06), rgba(255,122,209,0.07));
            border: 1px solid rgba(255,122,209,0.32); color: #c985b0; font-size: 16px; padding: 0 8px; }
.fav-star:hover { border-color: rgba(255,122,209,0.70); color: #fff; }
.fav-star-empty { background: linear-gradient(to right, rgba(110,231,240,0.02), rgba(124,108,255,0.045), rgba(255,122,209,0.02));
                  border: 1px solid rgba(124,108,255,0.20); color: #52616d; font-size: 16px; padding: 0 8px; }
.fav-star-empty:hover { border-color: rgba(255,122,209,0.58); color: #d9eef7; }
/* Context menu */
.context-btn { background: linear-gradient(to right, rgba(110,231,240,0.04), rgba(124,108,255,0.08), rgba(255,122,209,0.04));
               border: 1px solid rgba(124,108,255,0.32); border-radius: 3px; color: #aab8c3;
               font-size: 12px; padding: 6px 16px; }
.context-btn:hover { background: linear-gradient(to right, rgba(110,231,240,0.12), rgba(124,108,255,0.16), rgba(255,122,209,0.09));
                     border-color: rgba(255,122,209,0.62); color: #d9eef7; }

/* Gold server listing */
.gold-details { background: rgba(216,173,104,0.05); border: 1px solid rgba(216,173,104,0.28);
                border-radius: 5px; padding: 12px 14px; margin-right: 18px; }
.gold-details-title { color: #d8ad68; font-family: monospace; font-size: 10px;
                      font-weight: 800; letter-spacing: 2px; }
.gold-description { color: #aab8c3; font-size: 12px; }
.listing-banner { border-radius: 4px; background: #0b0f14; }
.gold-link { background: linear-gradient(to right, rgba(216,173,104,0.08), rgba(124,108,255,0.09), rgba(255,122,209,0.05));
             border: 1px solid rgba(216,173,104,0.48); border-radius: 4px;
             color: #f0cf91; font-size: 10px; font-weight: 700; letter-spacing: 1px; padding: 5px 10px; }
.gold-link:hover { background: linear-gradient(to right, rgba(216,173,104,0.16), rgba(124,108,255,0.17), rgba(255,122,209,0.11));
                   border-color: #d8ad68; color: #fff0c9; }

"""
