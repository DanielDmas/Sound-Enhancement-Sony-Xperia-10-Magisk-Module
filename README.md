# Sony Sound Enhancement for Xperia XZ1 Compact

## Latest test build: RC4 for G8441 / Android 12L

**[Download the RC4 installer artifact](https://github.com/DanielDmas/Sound-Enhancement-Sony-Xperia-10-Magisk-Module/actions/runs/42718445400/artifacts/13718892713)**

Target: European/international **Xperia XZ1 Compact G8441 (lilac), Flamefire
LineageOS 19.1 / Android 12L API 32, Magisk**. This is a Magisk module upgrade,
not a ROM. It does not support Android 15/16 or restore lost DRM keys.

RC4 repairs the private-file Android command transport regression in RC2/RC3
that can cause **Could not read package ownership**, and exposes the underlying
Android errors in Action logs and reports. It keeps the persistent state and
presets. All 55 protected Sony/Dolby APK/JAR/ELF files match the two supplied
older installers; the proprietary audio engine was not rebuilt.

## Install over the existing module

1. Download the artifact above. Extract GitHub's **outer archive once**.
2. In **Magisk > Modules > Install from storage**, select the inner
   **SoundEnhancement-v2.0.0-rc.4-lilac-12L.zip**, keeping it packed. Do not
   uninstall the old module first. Keep your earlier ZIP for rollback.
3. After a successful installation, **restart Android normally**. No TWRP,
   ROM reflash, factory reset or additional boot-image patch is needed.
4. Play music and press the module's **Action**. Check that its log says
   **Runtime: v2.0.0-rc.4**. Test flat EQ versus a strong manual cut with other
   EQs, ClearAudio+ and DSEE HX temporarily off, at moderate volume.

GitHub's **Code > Download ZIP** is source, not an installable module. The
artifact also contains the installer's SHA-256 file. Its installer SHA-256 is:

```text
1d17b51067ea35a6871da3bcfa01724b226ca7b7b154529760a0f24d8c2c1ad7
```

## Instructions, diagnostics and validation

- **[RC4 changes, older-version comparison, installation and troubleshooting](https://github.com/DanielDmas/Sound-Enhancement-Sony-Xperia-10-Magisk-Module/blob/audit/rc4-binder-transport-20261109/docs/RC4.md)**
- [Full commands and recovery manual](https://github.com/DanielDmas/Sound-Enhancement-Sony-Xperia-10-Magisk-Module/blob/audit/rc4-binder-transport-20261109/README.md)
- [Source and patch: PR #4](https://github.com/DanielDmas/Sound-Enhancement-Sony-Xperia-10-Magisk-Module/pull/4), commit **f29e714**
- [Extended CI: 202 tests, including 26 using official Magisk31.1 BusyBox, no skips](https://github.com/DanielDmas/Sound-Enhancement-Sony-Xperia-10-Magisk-Module/actions/runs/42718445257)
- [Build CI and installer artifact](https://github.com/DanielDmas/Sound-Enhancement-Sony-Xperia-10-Magisk-Module/actions/runs/42718445400)

The extended checks also pass ShellCheck and two patch passes against pinned
Yoshino/Flamefire configuration sources. The downloaded GitHub installer was
compared byte for byte with the locally tested build.

**Physical/acoustic acceptance of RC4 remains pending.** Shell fixtures model
the Binder descriptor boundary; they do not execute Android's Binder/SELinux,
ARM libraries or this phone's audio HAL. An enabled switch or delivered
broadcast alone does not prove processing.

If Action fails, tap its save icon and share the complete log; RC4 includes
raw command errors and exit codes. If settings open but have no audible effect,
capture `adb shell su -c "sefx report"` while the failure is happening, before
pressing Action or switching apps. The command prints the report's Downloads
path. Review it before sharing; nothing is uploaded automatically.

The runtime source lives on **audit/rc4-binder-transport-20261109**; `main`
retains the upstream runtime while this candidate awaits phone acceptance.
Use the installer above for RC4. [RC1 reference build](https://github.com/DanielDmas/Sound-Enhancement-Sony-Xperia-10-Magisk-Module/actions/runs/42572917815)
remains available for comparison. RC3 has a reported runtime failure and is
superseded by RC4.

Sony/Dolby retain their rights in the supplied proprietary files. Script fixes
and automated checks are not a guarantee of every stock Sony feature on every
player or output route.
