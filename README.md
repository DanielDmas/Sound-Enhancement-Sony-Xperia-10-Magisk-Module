# Sony Sound Enhancement: Android 12L session manager

## RC4 candidate for G8441 / LineageOS 19.1 (Android 12L)

**[RC4 fixes, installation and troubleshooting](docs/RC4.md)** | [Full audit/gap map](docs/AUDIT.md).

This branch builds `SoundEnhancement-v2.0.0-rc.4-lilac-12L.zip`, an unvalidated
phone candidate with the Android command transport regression fix and actionable failure diagnostics.

[Open RC4 build runs](https://github.com/DanielDmas/Sound-Enhancement-Sony-Xperia-10-Magisk-Module/actions/workflows/ci.yml?query=branch%3Aaudit%2Frc4-binder-transport-20261109).
Select a successful run, open **Artifacts**, download
**SoundEnhancement-v2.0.0-rc.4-lilac-12L**, and extract the outer archive once.
Install the **inner module ZIP** in Magisk and retain its checksum file.
GitHub's **Code > Download ZIP** is source, not an installer.

The saved [RC1 reference build](https://github.com/DanielDmas/Sound-Enhancement-Sony-Xperia-10-Magisk-Module/actions/runs/42572917815)
remains available as an earlier reference. Its artifact is named `SoundEnhancement-v2.0.0-rc.1-lilac-12L`.

This fork repairs the activation/lifecycle scripts around Rei Ryuki's Xperia 10 Sony audio port. The installable candidate is **v2.0.0-rc.4**, for **Sony Xperia XZ1 Compact G8441 / lilac, Android 12L / API 32, Magisk**. Its Sony apps, framework JARs and native libraries are unchanged. This is a root module, not a ROM or a DRM-key restore.

The previous local manual-launch version worked initially on a G8441, then sometimes opened controls without changing the sound. This fork fixes script defects that can cause incorrect or lost session attachment. No physical Xperia is connected for acoustic verification of the repaired build; automated tests and a successful Android intent are not proof of audible DSP processing.

## Install over the existing manual-launch module

1. Keep your old `SoundEnhancement-v1.2.4-manual-launch.zip` and the clean `boot.img` from your current ROM as a rollback kit.
2. Download the built **`SoundEnhancement-v2.0.0-rc.4-lilac-12L.zip`** and its SHA-256 file. Do not install GitHub's generic source-code ZIP. GitHub Actions also creates a wrapper artifact ZIP; extract that wrapper once and install the module ZIP inside it.
3. In **Magisk > Modules > Install from storage**, choose the new module ZIP. The ID stays `SoundEnhancement`, so this updates the existing module. Do not remove the old module first or wipe the phone. Check for a successful installation and then restart Android normally.
4. Play music through normal Android audio output. Open **Magisk > Modules > Sony Sound Enhancement - Session Manager > Action** if recovery is needed. RC4 repairs known current profiles, names the player/session and opens Sony's panel.
5. For the listening check, switch **ClearAudio+ and DSEE HX off**, if present, and compare flat EQ with a strong manual bass/treble cut at moderate volume. Turn off the player's own EQ during this test. Then try your usual wired/Bluetooth route separately.

You do not need TWRP, another ROM flash, another Magisk boot-image patch, Tasker, AML or Dolby for this upgrade. The focused installer refuses an incompatible model/API or missing 32-bit support instead of producing a knowingly nonworking partial installation. It ignores old shared-storage `optionals.prop` settings, preserves Sony app data on upgrade and does not remove unrelated modules.

## What changed

RC4 fixes the private-file command transport regression present in RC2/RC3: Android Binder commands now receive anonymous pipes for both output streams and null input. Command and relay timeouts remain bounded, actual exit codes are preserved, and failures include Android's raw error in Action and reports. It retains private persistent state without adding SELinux grants. See [the comparison with the uploaded older versions](docs/RC4.md).

- Correct Android **AudioEffect** content types: music 0, movie 1, game 2, voice 3. AudioAttributes uses different numeric values; they are explicitly translated.
- Find **current started playback** directly in Android's audio records, match package ownership by exact UID/PID, reject stale log entries and invalid/global session IDs. A media-session notification is no longer required.
- Send explicit intents to the actual exported Sony receiver, include stopped packages, and pass the same package/session/content type to Sony's redirector. Its bytecode confirms that it reads the package extra.
- Start a root-side watcher after boot: new sessions, route changes, audio-server/Sony-process restarts, and periodic renewal trigger reconnection. It does not need Magisk's UI to stay open.
- Account for a Sony-specific lifecycle quirk: CLOSE resets a whole package. Reopen surviving sessions for that package rather than accidentally leaving them disconnected.
- Serialize manual/background refreshes with kernel locks, bound Android commands with timeouts, distinguish Android error text from real delivery, rotate logs and provide diagnostics. Use Magisk's BusyBox explicitly; use Android's own `ps` for its NAME column.
- Remove the old recursive audio-server monitor and its unrecovered Sony process kills. A single audio-server restart remains at boot to load mounted audio configurations, as in the previous setup.
- Stop the installer's module-name-change cleanup and implicit data-app uninstall. Keep presets; no automatic SELinux-permissive fallback or global audio-server restart during routine refreshes.

## Automatic reconnection and limits

Auto reconnect is on by default. The watcher polls every **5 seconds during detected playback**, every **10 seconds when idle/erroring**, and renews requests after **60 seconds**. It rebuilds affected sessions after detected route/server/process changes. It holds no wake lock: Android sleep/Doze can delay polling, and reattachment is not instantaneous. Preferences are retained in `/data/adb/sony-audio-manager/config` with private permissions. This series migrates old module-local `.sefx/config` once. A supervisor restarts a crashed watcher; boot, Action or `sefx auto on` can start the supervisor.

The Sony port can still be limited by the ROM's audio HAL, exclusive/direct/bit-perfect output, another app owning the effects, or Sony's proprietary implementation. A visible control, received broadcast, DSEE capability string or running watcher does not prove the samples are being processed. This build targets the known Android 12L setup, not arbitrary LineageOS 22/23 installations. Lost DRM keys are not restored.

## Useful commands

Use an authorized ADB connection, for example `adb shell su -c 'sefx status'`. On Windows Command Prompt use double quotes around a multiword command, or open `adb shell`, run `su`, then enter the command.

| Command | Purpose |
| --- | --- |
| `sefx` | Reattach active media and open Sony's panel. Attach and open; Magisk Action additionally performs repair. |
| `sefx open org.example.player` | Open settings for one specific active player when several are playing. |
| `sefx recover` | Repair known current profiles and open Sony settings. Magisk Action uses this. |
| `sefx attach` | Reattach without opening the UI. |
| `sefx refresh` | Close/reopen managed active sessions, retaining presets and app data. |
| `sefx status` | Show watcher state, detected players and last successful delivery requests. |
| `sefx auto off` / `sefx auto on` | Stop/restart automatic reconnection. Off takes effect after the current bounded poll/sleep. |
| `sefx doctor` | Save a private report in /data/adb/sony-audio-manager. |
| `sefx report` | Generate a report and copy it to this user's Downloads. Review it before sharing. |

## If settings still make no audible difference

1. Keep music playing and capture `sefx report` before changing apps or pressing Action. Then press Action for repair and compare the result; opening the UI alone does not prove processing.
2. Switch ClearAudio+ / DSEE HX off for the manual-EQ test. Disable the player's own EQ and use normal Android output; exclusive USB/direct output may bypass system effects. Test wired first, then Bluetooth separately.
3. Run `adb shell su -c "sefx refresh"` and test again. This rebuilds the detected sessions without deleting your settings or rebooting the phone.
4. Run `adb shell su -c "sefx status"`. If needed, enable the watcher with `adb shell su -c "sefx auto on"`.
5. While the failure is happening, run `adb shell su -c "sefx report"`. The output names a `SonyAudio-diagnostics-YYYYMMDD-HHMMSS.txt` file in Downloads. It includes audio/session state, AudioFlinger, Sony package/app-ops information, recent logs and the last Android intent result. Logs may contain app names and playback details; nothing is uploaded automatically.

An incompatible output path or failure inside the proprietary effect engine needs evidence from this report and a listening check. Reinstalling Android or formatting Data is not an appropriate first response to an inactive EQ.

## Roll back

If Android boots, disable the module in Magisk and restart. To restore the previous implementation, install the saved v1.2.4 manual-launch ZIP and restart; note that its upstream installer can clear data on a name change, so record presets first.

If Android bootloops and recovery can access Data, create `/data/adb/modules/SoundEnhancement/disable`, then reboot. If Data is inaccessible but fastboot works, restore only the clean `boot.img` from the **exact current ROM** to stop Magisk loading modules. Never flash another ROM's boot image or relock the bootloader with a custom system.

## Build and verification

With Python 3 and a POSIX shell:

```sh
python3 -m unittest discover -s tests -v
python3 tools/build_module.py
```

The builder creates `dist/SoundEnhancement-v2.0.0-rc.4-lilac-12L.zip` and its `.zip.sha256` file. It verifies 55 protected upstream APK/JAR/ELF files, shell syntax, ZIP CRCs and deterministic packaging. No Android SDK, Java compiler or Tasker is needed because the supplied proprietary binaries are reused, not rebuilt. The extended CI also runs actual Magisk BusyBox integration, the policy reduction invariant and pinned Yoshino/Flamefire configuration checks. It does not emulate the hardware DSP. GitHub Actions runs tests and saves the candidate artifact.

See [docs/AUDIT.md](docs/AUDIT.md) for the RC2 repair/gap map, alternatives, primary references and phone acceptance matrix. [docs/INVESTIGATION.md](docs/INVESTIGATION.md) retains the RC1 investigation. Upstream scripts are MIT-licensed; Sony/Dolby retain their rights in the supplied apps/libraries. Do not interpret the scripts' license as a license to proprietary payload source code.
