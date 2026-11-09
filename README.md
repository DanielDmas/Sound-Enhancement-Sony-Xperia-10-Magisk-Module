# Sony Sound Enhancement for Xperia XZ1 Compact

## Latest test build: RC3 for G8441 / Android 12L

**[Download the verified RC3 build](https://github.com/DanielDmas/Sound-Enhancement-Sony-Xperia-10-Magisk-Module/actions/runs/42708340513/artifacts/13715231063)**

This candidate targets the European/international **Xperia XZ1 Compact G8441
(lilac), LineageOS 19.1 / Android 12L API 32**, with Magisk. It passed **179 CI
tests**, including **14 actual Magisk BusyBox tests**, and two passes against
pinned Yoshino/Flamefire configuration sources. Physical/acoustic validation
is still required.

Extract GitHub's outer artifact archive once and install the inner
**SoundEnhancement-v2.0.0-rc.3-lilac-12L.zip** through Magisk > Modules >
Install from storage. Then reboot normally. The module ID is unchanged, so
this upgrades the existing module without a ROM flash or factory reset.

[RC3 installation and troubleshooting](https://github.com/DanielDmas/Sound-Enhancement-Sony-Xperia-10-Magisk-Module/blob/audit/rc3-recovery-validation-20261109/docs/RC3.md)
| [RC3 source and changes (PR #3)](https://github.com/DanielDmas/Sound-Enhancement-Sony-Xperia-10-Magisk-Module/pull/3)

The RC3 source lives on **audit/rc3-recovery-validation-20261109**. Default
**Code > Download ZIP** is not the installable module. The older RC1 reference
below remains available.

---

## Download v2.0.0-rc.1 for Xperia XZ1 Compact / Android 12L

**[Open the verified GitHub download build](https://github.com/DanielDmas/Sound-Enhancement-Sony-Xperia-10-Magisk-Module/actions/runs/42572917815)**

1. Sign in to GitHub and open the link above.
2. In the run's **Artifacts** section, click **`SoundEnhancement-v2.0.0-rc.1-lilac-12L`**.
3. Extract GitHub's downloaded outer archive once. Inside are:
   - **`SoundEnhancement-v2.0.0-rc.1-lilac-12L.zip`** - install this ZIP in Magisk, keeping it packed.
   - **`SoundEnhancement-v2.0.0-rc.1-lilac-12L.zip.sha256`** - checksum for that module ZIP.

The outer GitHub artifact archive is a download container. Magisk needs the **inner module ZIP**. GitHub's **Code > Download ZIP** downloads source files and is not the installable module.

The linked build passed **79 tests**, verified **55 unchanged upstream binary containers**, and reproduced the locally tested module ZIP exactly. It targets **G8441/lilac, Android 12L / API 32, with Magisk**. It is a candidate awaiting real-phone audio validation.

GitHub lists this pinned artifact's expiry as **7 February 2027**. Save both inner files locally; [the Actions page](https://github.com/DanielDmas/Sound-Enhancement-Sony-Xperia-10-Magisk-Module/actions) lists other builds if the pinned artifact becomes unavailable. [GitHub's artifact download instructions](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts) explain the sign-in and Artifacts steps.

## Install the downloaded module

1. Keep the previous working module ZIP and your current ROM's clean `boot.img` as a rollback kit.
2. In **Magisk > Modules > Install from storage**, choose `SoundEnhancement-v2.0.0-rc.1-lilac-12L.zip` **over the existing module**, then restart Android normally.
3. Start music playback, then open **Magisk > Modules > Sony Sound Enhancement - Session Manager > Action**.
4. To check manual EQ, switch ClearAudio+ and DSEE HX off, if present, and compare flat EQ with a strong manual adjustment at moderate volume.

## Full manual, source and status

- **[Full installation, commands, troubleshooting and recovery manual](https://github.com/DanielDmas/Sound-Enhancement-Sony-Xperia-10-Magisk-Module/blob/fix/sony-session-manager-20261108/README.md)**
- **[Candidate source branch](https://github.com/DanielDmas/Sound-Enhancement-Sony-Xperia-10-Magisk-Module/tree/fix/sony-session-manager-20261108)**
- **[PR #1: implementation, tests and validation](https://github.com/DanielDmas/Sound-Enhancement-Sony-Xperia-10-Magisk-Module/pull/1)**

The runtime changes are in the candidate branch and PR #1 pending listening tests on the Xperia; `main` retains the upstream runtime implementation. Use the candidate branch when inspecting or building the repaired module. The download link above points to its verified build.

The Sony apps and native libraries are supplied by the upstream port and retain their original ownership. This module does not restore lost DRM keys, and successful automated tests do not prove that every player or output route processes audio correctly.
