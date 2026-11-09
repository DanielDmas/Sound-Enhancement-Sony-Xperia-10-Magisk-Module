# Investigation and validation

## Evidence available

The original local `v1.2.4-manual.1` ZIP was installed on a G8441/lilac. Its supplied install log records Magisk 31.1 / 31100 and Android API 32; audible operation was reported initially, followed by intermittent loss of effect despite a working panel. No diagnostic snapshot from that failure has been supplied, and no physical Xperia is connected to this development environment.

Base source: `925950e80b66db58703f408ea1ba4811811bbacb`. The fork's original tree was compared with the saved upstream files. The Sony APK/JAR/native binaries remain byte-identical; their SHA-256 values are in `tools/payload_manifest.json`.

## Confirmed defects and implementation decisions

1. **Wrong content enums.** Upstream sefx maps music to 2 and movie to 3. Android AudioEffect defines music=0, movie=1, game=2, voice=3. These differ from AudioAttributes and must be translated.
2. **Wrong-session discovery.** A text search for a PID can also match another PID, an unrelated field or historical player events. Reading all sessions/content tokens into separate lists loses the relationship between the two. The new parser accepts complete, anchored, current playback records and resolves exact UID/PID ownership.
3. **No package passed to UI.** Upstream starts the control-panel action without extras. Read-only inspection of the supplied Sony APK's manifest and DEX confirms that SoundEnhancementRedirector.onCreate reads EXTRA_PACKAGE_NAME and otherwise falls back to getCallingPackage. An am/cmd launch has no player Activity caller. The same player/session/type is now supplied to both receiver and redirector.
4. **No lifecycle repair.** The previous Action performs one attachment attempt. Its service recursively polls audio-server PIDs and kills Sony after a restart, without recreating sessions. The replacement uses a loop and automatic attachment/rebuild, retaining only one audio-server reload at boot.
5. **Sony closes by package.** The supplied SoundEnhancementService.handleCloseAudioEffect reads the package and calls resetAudioSession(package); it does not read the session ID there. Closing one departed session therefore invalidates other sessions from the same package. The manager closes each affected package once and reopens all surviving detected sessions for it.
6. **False success and hangs.** Shell exit 0 can accompany an Android Error/SecurityException; dump/intent calls can fail. The manager checks output and status, uses bounded calls and preserves previous state after collection failure. Acknowledged delivery is deliberately not called processing verification.
7. **Upgrade data loss.** The upstream installer's module-name-change cleanup executes uninstall.sh, which deletes Sony app data. That path and implicit data-app uninstallation are removed; the supplied APK stays unchanged. Automatic deletion of unrelated boot modules is removed too.
8. **Runtime tools.** Magisk executes boot scripts with BusyBox standalone applets. The CLI explicitly selects that runtime even from ADB, but invokes Android's ps by absolute path for the Android-specific NAME column. Direct cmd activity calls avoid the extra am shell wrapper under timeouts.

The original helper's SELinux-off fallback is not retained. This does not certify every unchanged upstream policy rule as minimal; SELinux policy and proprietary payload compatibility need device-side observation before a broader redesign.

## Primary sources checked

- [Android AudioEffect API](https://developer.android.com/reference/android/media/audiofx/AudioEffect): session intents, required package/session values and content enums.
- [Android 12L AudioEffect source](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-12.1.0_r1/media/java/android/media/audiofx/AudioEffect.java).
- [Android 12L AudioPlaybackConfiguration source](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-12.1.0_r1/media/java/android/media/AudioPlaybackConfiguration.java): exact current-record fields.
- [Android 12L PlaybackActivityMonitor](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-12.1.0_r1/services/core/java/com/android/server/audio/PlaybackActivityMonitor.java): current players and separate historical event log.
- [Android 12L AudioService](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-12.1.0_r1/services/core/java/com/android/server/audio/AudioService.java): global mMainType/mBluetoothName route fields, used even when track deviceId stays zero.
- [Android 12L am wrapper](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-12.1.0_r1/cmds/am/am): cmd activity delegation.
- [Magisk developer guide](https://topjohnwu.github.io/Magisk/guides.html): BusyBox standalone, module Action and nonblocking service scripts.
- [Sony XZ1 Compact guide, printed p.55](https://www.sony.com/electronics/support/res/manuals/V171/V1711079M.pdf): manual EQ requires ClearAudio+/DSEE HX off and does not change voice calls. Stock behavior is a test control, not proof of this port.

## What automated tests establish

The suite executes the real shell entry point with Android command fakes. It tests content translation, exact ownership, stopped/historical/invalid sessions, multi-session/package lifecycle, server/process/route changes, concurrent operations, lock recovery, failures that return exit 0, a genuinely hung command killed by timeout, no UI from background polling, configuration/permission handling and bounded logs. Packaging tests verify protected binary identities, deterministic output, installable root layout and script syntax.

These tests do not execute the Sony DSP libraries, Android Binder/SELinux or physical audio outputs. They do not establish audibility, native effect control ownership, Bluetooth offload behavior, battery impact or Doze timing on the actual phone.

## Device validation still required

- Install over the working-ROM setup without resetting Data; verify presets survive.
- Compare flat/strong manual EQ during real playback on a known working route, with automatic modes off.
- Restart the player, change output, pause/resume and reboot; verify reconnection and watcher state.
- Test wired and Bluetooth separately, plus any USB/direct path actually used.
- If silent, capture `sefx report` during the failure and inspect AudioFlinger/logcat for native load, control-owner, permission or bypass problems.
- Observe CPU/battery behavior over normal use before calling this a stable release.

There is no claim that it always works on every player/route, or that missing Sony DRM keys are restored. The release is labelled rc.1 because hardware validation remains outstanding.
