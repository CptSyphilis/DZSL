# Changelog

## 0.9.0 — Release candidate

### Added

- Gold server listings with pinned placement, badges, banners, descriptions, and Discord links
- Bundled DZSL typography, galaxy branding, and consistent button styling
- Native and Flatpak DayZ Client launch arguments with required server mods
- Steam Workshop verification, repair, update, unsubscribe, and visible download progress
- Automated release metadata checks and CI coverage for Python 3.10, 3.12, and 3.13

### Fixed

- Missing-mod installs now ask Steam to subscribe and install Workshop content
- Long-running Workshop downloads no longer fail only because one hour elapsed
- Unsubscribe failures preserve local mod files
- Updates preserve the selected Steam library and existing user configuration
- Gold listing requests include headers accepted by the public API
