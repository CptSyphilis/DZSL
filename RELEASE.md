# Release process

DZSL 0.9.0 is the release candidate for 1.0. Feature work stays frozen until the candidate passes the checks below.

## Automated gate

```bash
./bin/check-release.py
bash -n bin/*.sh
appstreamcli validate --no-net packaging/flatpak/com.dayzlinux.dzsl.metainfo.xml
desktop-file-validate packaging/flatpak/com.dayzlinux.dzsl.desktop
flatpak-builder --show-manifest packaging/flatpak/com.dayzlinux.dzsl.yml >/dev/null
python3 -m compileall -q dzsl tests
python3 -m unittest discover -s tests -v
python3 -m build
```

Every gate must pass in CI before tagging a release.

## Manual release-candidate checks

- Clean installation on a supported distribution
- Upgrade over an existing installation without losing settings, favorites, recent servers, or the selected Steam library
- Launch from the installed desktop entry, not the source checkout
- Browse, filter, favorite, and refresh servers with the Gold API available and unavailable
- Join a vanilla server
- Join a modded server with all mods installed
- Join a modded server with missing mods and wait for Steam to finish
- Cancel and retry a Workshop download
- Verify or repair an invalid Workshop mod
- Join password-protected and queued servers
- Test native Steam and Flatpak Steam
- Confirm the app closes or restores according to the saved setting after DayZ exits

## Publish 0.9.0

1. Confirm `main` is clean and CI is green.
2. Confirm the changelog and release metadata use `0.9.0`.
3. Tag the tested commit as `v0.9.0`.
4. Publish the source archive and release notes.
5. Keep 0.9.0 available for testing before promoting the same release line to 1.0.

## Promote to 1.0

Promote only after the manual matrix passes without a release-blocking defect. Update all version metadata to `1.0.0`, add the final changelog entry, rerun every gate, tag `v1.0.0`, and publish the tested artifacts.
