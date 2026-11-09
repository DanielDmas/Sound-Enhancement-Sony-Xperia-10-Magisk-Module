# Changelog

## v2.0.0-rc.4

- Fix the RC2/RC3 private-state command transport regression: Android Binder commands receive separate stdout/stderr pipes and null stdin, never root-private file descriptors.
- Preserve command exit codes through the relays; bound the relays as well as the command so a retained Android-side pipe cannot hang the manager indefinitely.
- Close the saved stdout pipe in BusyBox timeout helpers so detached timers do not delay successful commands; cover the monitor boundary and native completion time explicitly.
- Apply the transport to discovery, broadcasts, panel launch, permissions/app-ops and diagnostic commands; initialize and clean up boot transport state.
- Print bounded underlying command errors in Magisk Action and retain a private last-command report across invocation cleanup.
- Reject failed foreground-user queries even when they printed a numeric value; retain error details.
- Tighten command fixtures to validate real package command syntax, reject private regular-file FDs, and check pipes, lock FDs, partial output, stderr separation and timeouts under POSIX and official Magisk BusyBox shells.
- Compare both user-supplied old installers: all 55 protected APK/JAR/ELF containers are unchanged. No extra SELinux grants or data resets.

This fixes demonstrated code/fixture failures. On-device audible acceptance of RC4 is still pending.

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
