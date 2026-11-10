# RC5: native engine evidence and bounded automatic repair

Target: Sony Xperia XZ1 Compact G8441/lilac, Flamefire LineageOS 19.1,
Android 12L/API32, Magisk. Version `v2.0.0-rc.5`, versionCode `20005`.

## What changed

RC4's periodic OPEN cannot guarantee an existing same-session Sony effect is
recreated. RC5 checks AudioFlinger evidence after a stable startup grace:
Sony implementation UUID, expected native session, engine status, enabled and
suspended flags, and controlling client PID. The default inherited Sony mode
uses native session zero; the player's intent session is a different layer.
In postprocess mode the selected player sessions are checked instead.

Two missing/failed observations, at least 15 seconds apart in stable context,
request CLOSE/OPEN repair without opening the panel. Repairs have increasing
60/120/180-second cooldowns and a maximum of three attempts per context until
positive engine evidence, an explicit repair or a context change resets the
budget. The first automatic attempt normally needs roughly 30 seconds of
stable failure. Regular player attachment still uses the existing 5-second
awake polling opportunity. Doze can delay both.

Unknown, failed, oversized or unsupported diagnostic captures do not trigger
repair. An effect disabled by the user, framework suspension, or another
process controlling the Sony effect also suppresses automatic repair.
The manager does not force-enable effects, change audio mode, kill processes,
clear data or make SELinux permissive to recover playback.

Sony's APK has one holder per package. RC5 retains one stable active record per
package, and replaces it when it disappears. All detected records remain in
diagnostics. This avoids repeatedly replacing one package's holder while
pretending its concurrent sessions are independently supported. In global mode
it additionally retains one active package owner to avoid creating competing
holders through the manager. `sefx open PACKAGE`
explicitly selects another active player; otherwise the owner stays stable
until it stops. This is one global profile for the mixed output. In
postprocess mode one holder per active package is retained.

Players can also send OPEN/CLOSE broadcasts directly to Sony's APK. The manager
does not intercept those broadcasts or prove which Java holder owns an engine
when several holders belong to Sony's same process. Multiple-player behavior
therefore still needs device testing; PID ownership alone cannot resolve it.

## Install

1. Keep your previous module ZIP and record your presets.
2. Install `SoundEnhancement-v2.0.0-rc.5-lilac-12L.zip` through Magisk's
   Modules > Install from storage. The module ID stays `SoundEnhancement`.
   With GitHub Actions, extract the outer download once; install its inner ZIP.
3. Restart Android normally. No ROM reinstall, format or DRM keys are required
   for this module upgrade.
4. Start Music without opening Magisk. Test flat versus a strong manual EQ cut
   at moderate volume with ClearAudio+ and DSEE HX temporarily off. Then test
   the automatic modes and each output separately.

## Useful verification

```sh
adb shell "su -c 'sefx health'"
adb shell "su -c 'sefx status'"
adb shell "su -c 'sefx report'"
```

`health` performs a fresh native evidence probe and does not repair or open UI.
`ready` means that the captured framework record shows Sony's engine enabled
and Sony controlling it. It does not establish audible processing or correct
physical-output routing. `status` labels cached evidence as potentially stale.

If controls have no audible effect, capture a report first, then run
`adb shell "su -c 'sefx refresh'"`, and capture another report. Save both
Downloads files and note whether refresh alone restored EQ. After three failed
automatic repairs the manager stops escalating; Action/refresh resets the
budget. Do not reinstall Android to diagnose this symptom.

## Verification boundary

Automated tests use source-derived Android 12L dump layouts and command fakes,
including missing engines, disabled effects, control conflicts, corrupt state,
timeouts, unsupported/oversized dumps, grace periods, cooldown and exhaustion.
Actual Magisk BusyBox exercises the shell, pipelines and locks in CI. The 55
Sony/Dolby APK/JAR/ELF payloads remain hash-protected and unchanged.

The parser deliberately refuses to infer missing state from an unrecognized
dump. Sony's native DSP, actual ROM dump variations, acoustic operation,
power consumption and route behavior still require the target phone.
This version is a release candidate; it is not certified as perfect or
universally working. See [source-level findings](POST-RC4-VERIFICATION.md).
