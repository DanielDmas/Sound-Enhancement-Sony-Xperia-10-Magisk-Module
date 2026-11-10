# Sony Sound Enhancement for Xperia XZ1 Compact

## Latest test build: RC5 for G8441 / Android 12L

**[Download the RC5 installer artifact](https://github.com/DanielDmas/Sound-Enhancement-Sony-Xperia-10-Magisk-Module/actions/runs/42801361959/artifacts/13756966135)**

Target: European/international **Xperia XZ1 Compact G8441 (lilac), Flamefire
LineageOS 19.1 / Android 12L API 32, Magisk**.

RC5 checks native Sony engine evidence independently of successful broadcast
delivery. Repeated missing/failed engine observations request CLOSE/OPEN
repair with startup grace, increasing cooldowns and a three-attempt budget.
Disabled effects, suspension, competing ownership and unknown diagnostics
suppress automatic takeover. A stable profile selection matches Sony's
one-holder-per-package behavior and shared global engine.

The RC4 Android command transport fix is retained. Presets and persistent
preferences are retained; all 55 protected Sony/Dolby APK/JAR/ELF files remain
unchanged. No ROM reinstall, factory reset or DRM keys are needed for this
module upgrade.

## Install over the existing module

1. Download the artifact above. Extract GitHub's **outer archive once**.
2. In **Magisk > Modules > Install from storage**, select the inner
   **SoundEnhancement-v2.0.0-rc.5-lilac-12L.zip**, keeping it packed. Keep the
   earlier installer for rollback; install this as an update.
3. After a successful installation, **restart Android normally**.
4. Start Music without opening Magisk. Compare flat EQ with a strong manual
   cut at moderate volume, initially with other EQs, ClearAudio+ and DSEE HX
   off. Then test your automatic modes and outputs individually.
5. Action remains a manual repair option. Its log must say
   **Runtime: v2.0.0-rc.5**.

GitHub's **Code > Download ZIP** is source. The artifact contains the installer
and its SHA-256 file. The installer SHA-256 is:

```text
df5bbc7224f46173e98416ea551f9cb8121bcbe50a194221572a6785e13f2365
```

## Instructions, diagnostics and validation

- **[RC5 installation, recovery rules and troubleshooting](https://github.com/DanielDmas/Sound-Enhancement-Sony-Xperia-10-Magisk-Module/blob/f4a26c1762858746c9c7ded2c3abed84151d9f94/docs/RC5.md)**
- [Source-level findings that drove RC5](https://github.com/DanielDmas/Sound-Enhancement-Sony-Xperia-10-Magisk-Module/blob/f4a26c1762858746c9c7ded2c3abed84151d9f94/docs/POST-RC4-VERIFICATION.md)
- [Source and patch: PR #4](https://github.com/DanielDmas/Sound-Enhancement-Sony-Xperia-10-Magisk-Module/pull/4), commit **f4a26c1**
- [Extended CI: 251 tests, including 39 using official Magisk 31.1 BusyBox, no skips](https://github.com/DanielDmas/Sound-Enhancement-Sony-Xperia-10-Magisk-Module/actions/runs/42801361713)
- [Build CI and installer artifact](https://github.com/DanielDmas/Sound-Enhancement-Sony-Xperia-10-Magisk-Module/actions/runs/42801361959)

The checks include ShellCheck, pinned Yoshino/Flamefire configuration sources,
reproducible packaging and unchanged protected payloads. The downloaded GitHub
installer was compared byte for byte with the local build. Thirteen recovery
tests were also run from the unpacked final installer.

`adb shell "su -c 'sefx health'"` probes native engine presence and ownership
without repair or UI. A `ready` result is framework evidence, not an acoustic
measurement or proof that the physical output uses that chain. Inherited
global mode uses native session zero despite nonzero player intent IDs.
Players can also send their own broadcasts; PID ownership cannot distinguish
several Sony holders in the same process.

If controls stop affecting sound, keep music playing and run:

```sh
adb shell "su -c 'sefx report'"
adb shell "su -c 'sefx refresh'"
adb shell "su -c 'sefx report'"
```

Save both reports from Downloads and note whether refresh alone restored EQ.
Reports include app/playback details; review them before sharing. Nothing is
uploaded automatically.

**Physical/acoustic acceptance of RC5 remains pending.** The tests execute
shell behavior and controlled Android fixtures, not the phone's Binder/SELinux,
ARM DSP libraries or audio HAL. Screen-off power use, route changes and actual
audible recovery still need testing on the target phone.

The runtime source lives on **audit/rc4-binder-transport-20261109**; `main`
provides this download page while the candidate awaits phone acceptance.
[Earlier RC4 installer](https://github.com/DanielDmas/Sound-Enhancement-Sony-Xperia-10-Magisk-Module/actions/runs/42718445400/artifacts/13718892713)
remains available for rollback/comparison. RC3 is superseded.

Sony/Dolby retain their rights in the supplied proprietary files.
