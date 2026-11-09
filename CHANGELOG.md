# Changelog

## v2.0.0-rc.1

- Target G8441/lilac Android 12L / API 32 with Magisk and the existing 32-bit Sony audio HAL path.
- Replace one-shot fragile session discovery with exact live playback/UID/PID matching and correct AudioEffect enums.
- Target Sony's exported receiver and redirector explicitly, including real session and player extras.
- Add automatic session/route/server/process reconnection, bounded polling and periodic renewal without opening UI in the background.
- Handle Sony's package-scoped CLOSE semantics; serialize concurrent operations and recover stale locks.
- Add refresh, status, auto toggle, player selection and private/exportable diagnostics.
- Remove periodic process kills, recursive monitoring and helper SELinux-permissive fallback.
- Preserve app settings on module-name changes and avoid automatic uninstallation/removal of other apps/modules.
- Add reproducible packaging, binary-identity checks, regression tests and CI artifacts.

This is a hardware-unverified candidate. It fixes verified script defects; audible operation on the Xperia still requires device-side validation.
