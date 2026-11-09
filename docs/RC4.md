# RC4: fix the Android command transport regression

Target: Xperia XZ1 Compact G8441/lilac, Flamefire LineageOS 19.1 / Android
12L API 32, Magisk. Version v2.0.0-rc.4, versionCode 20004. This is a module
upgrade; no ROM flash, wipe or DRM-key backup is needed for this upgrade.

## What the phone evidence establishes

The supplied RC3 installation log reaches Done on lilac/API32/Magisk31.1.
The subsequent Action log explicitly reports Runtime v2.0.0-rc.3 and fails
at package ownership discovery. This is a runtime failure, not old code
waiting for the first reboot. The log did not contain the command's stderr,
so it cannot establish the exact on-device SELinux denial or exit code.

## Comparison with the two supplied older installers

| Version | Command output and state | Relevant difference |
| --- | --- | --- |
| v1.2.4-manual.1 | One-shot am commands print to the caller | The manual command did not redirect its standard outputs to persistent private state files. |
| v2.0.0-rc.1 | Captures discovery and intent output in module-local .sefx | The module tree's label is covered by an inherited system_server/system_file write grant. |
| RC2/RC3 | Captures the same output in /data/adb/sony-audio-manager | State moved outside the labelled module tree, but the Android commands still inherited regular output/error file descriptors. That was a missed compatibility boundary. |
| RC4 | Keeps private persistent state; relays Android stdout and stderr separately | Binder sees pipes and null stdin; the root shell alone opens private files. No additional SELinux grant is needed by this approach. |

All **55 protected APK/JAR/ELF files** match both uploaded installers byte for
byte. RC3's policy reduction removed ordinary untrusted-app subjects; it did
not remove the existing system_server/system_file grant. RC4 does not restore
unrelated untrusted-app grants or make SELinux permissive.

The transport change is consistent with the observed failure and AOSP's
implementation. The old RC3 code also reproduces the exact package ownership
failure with the stricter FD-boundary fixture; RC4 passes it. This is not a
claim that a host fixture reproduces Android SELinux or confirms this phone's
actual file labels. Raw errors are now retained to resolve any remaining
device-specific failure instead of guessing.

## Repairs

- Apply one bounded pipe transport to package/user discovery, Sony OPEN/CLOSE
  broadcasts, panel launch, boot pm/appops calls and diagnostic commands.
- Keep stdout and stderr separate; warnings do not contaminate package/UID
  data. Preserve the command's actual exit status, including partial-output
  failures, instead of accepting the final cat process's successful exit.
- Close manager lock descriptors before spawning transport processes.
- Close the saved stdout pipe FD3 in every timeout helper too. BusyBox's
  detached timer otherwise retains it after standard I/O is redirected to
  null, delaying EOF until the timer checks whether its parent exited. The
  first extended CI run caught this delay and two related timing errors;
  RC4's final wrapper corrects it and adds direct helper/timing regressions.
- Bound pipe readers as well as the Android command. A service or descendant
  retaining a pipe after the command exits cannot leave the reader hanging
  indefinitely. The drain deadline is command timeout plus two seconds.
- Initialize the boot command transport before any Android helper, then
  clean up its invocation directory before starting the supervisor.
- Include a bounded raw error in Magisk Action. Save up to 8 KiB in private
  /data/adb/sony-audio-manager/last-command.txt and include it in reports.
- Reject failed foreground-user commands even when stdout contains a number;
  preserve prior attachments when discovery fails.

## Install over RC3

1. Save your old module ZIP. Download **SoundEnhancement-v2.0.0-rc.4-lilac-12L.zip**.
   A GitHub Actions download is an outer wrapper: extract that wrapper once
   and keep the inner installer ZIP packed. Code > Download ZIP is source.
2. Open **Magisk > Modules > Install from storage** and select the installer.
   It has the same SoundEnhancement module ID. Do not remove the old module
   first or clear Sony's app data.
3. After a successful installation, **restart Android normally**. Magisk can
   display new metadata before new runtime files become active; do not test
   Action before the reboot.
4. Play music in Lineage's Music app. Press the module's **Action**. Its log
   must say **Runtime: v2.0.0-rc.4**, then identify the player/session and open
   Sony settings without the package ownership error.
5. Turn other EQs, ClearAudio+ and DSEE HX off temporarily; compare flat EQ
   with a strong manual cut at moderate volume. Then test your usual effects
   and speaker/wired/Bluetooth routes separately. Background reconnection
   still uses polling; new playback need not attach instantaneously.

## If anything still fails

If Action reports an error, save its complete log in Magisk and send it. RC4
includes the underlying command error and exit code. No ADB is required for
that first diagnostic. Include which player and speaker/wired/Bluetooth route
you were using; do not reset the phone.

If the panel opens but settings have no audible effect, capture evidence
**while the failure is happening, before recovery or switching apps**:

```sh
adb shell su -c "sefx report"
```

The command prints a SonyAudio-diagnostics timestamped file in the phone's
Downloads. Review it before sharing: it contains package/playback details,
configurations and recent logs. Nothing is uploaded automatically.

If Downloads export fails, save the private report to your computer:

```sh
adb shell su -c "sefx doctor"
adb shell su -c "cat /data/adb/sony-audio-manager/diagnostics.txt" > SonyAudio-diagnostics.txt
```

After capture, `adb shell su -c "sefx recover"` repairs known sessions and opens
settings. It retains Sony app data and presets. To disable the module, switch
it off in Magisk and restart. Keep your earlier ZIP for rollback.

## Verification boundary and primary implementation references

The regression suite now rejects root-private regular-file standard FDs at
mock Binder entry points, validates the Android package command's syntax, and
exercises the relays with real POSIX and official Magisk31.1 BusyBox shells.
It covers command failures, separate stderr, partial output, lock inheritance,
file-backed Action logs, boot permissions, and a descendant retaining a pipe.
The extended workflow also checks ShellCheck, pinned target configuration
sources, unchanged proprietary payload hashes and deterministic packaging.

These checks do not execute the ARM Sony engine, Android Binder/SELinux or
the physical audio HAL. RC4's audible on-device acceptance is still pending.
Delivery, a running watcher and a visible enabled switch are not DSP proof.

- [Android 12L package shell implementation: -U and --user](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-12.1.0_r1/services/core/java/com/android/server/pm/PackageManagerShellCommand.java)
- [LineageOS 19.1 cmd implementation: passes stdin/stdout/stderr to IBinder::shellCommand and returns the service result](https://github.com/LineageOS/android_frameworks_native/blob/lineage-19.1/cmds/cmd/cmd.cpp)
- [Linux SELinux Binder transfer checks: descriptor use and access to the underlying file](https://github.com/torvalds/linux/blob/v4.4/security/selinux/hooks.c)
- [Magisk module and BusyBox standalone documentation](https://topjohnwu.github.io/Magisk/guides.html)
- [BusyBox 1.36 timeout timer process](https://github.com/mirror/busybox/blob/1_36_stable/coreutils/timeout.c) and [daemon descriptor handling](https://github.com/mirror/busybox/blob/1_36_stable/libbb/vfork_daemon_rexec.c)
