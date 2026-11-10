# RC3: G8441/lilac on LineageOS 19.1 / Android 12L

**Superseded by [RC4](RC4.md).** RC3 failed package ownership discovery on
the target phone. Its host tests missed the private-file descriptor boundary
at Android Binder commands. Use RC4's installer and instructions for the fix.

This build is for the European/international Xperia XZ1 Compact G8441, device
codename lilac, Android 12L API 32. Magisk 31.1 is the runtime exercised in CI.
It is an installable test candidate. Android 9, Android 15/16 and other Xperia
models are outside its supported scope; the installer refuses incompatible
targets. Runtime commands and boot initialization now check the target too.

## Changes since RC2

- An unidentifiable player no longer blocks every other player's effects.
  Discovery keeps uncertainty by UID, preserves that owner's previous requests,
  and continues attaching identifiable playback. When a session becomes known
  again, its profile is renewed even when its numeric ID is unchanged.
- Sony's internal zero-session tracks are ignored before deciding that playback
  is unresolved. Duplicate tracks use a stable PID/device ordering, avoiding
  false reconnections when dump ordering changes.
- Magisk's Action button runs **recover**: close/reopen known current profiles,
  then open Sony settings. It preserves presets and reconnect preferences.
  Background polling still avoids routine audio-server kills.
- Configuration transactions are serialized. Rollback restores preserved
  inodes by rename, avoids deleting a good live file first, and retains its
  backup if restoration fails. It no longer deletes the only recovery copy.
- Reports include bounded, integrity-checked configuration snapshots, Sony/audio
  process security contexts, hardware-effect node labels and relevant policy
  errors. A read-only Python analyzer detects malformed XML, missing effect
  libraries, duplicate effects/proxies, unresolved apply references, invalid
  routes, incomplete snapshots and retained rollback backups.
- Module-specific SELinux grants with ordinary untrusted-app subjects were
  removed. The 171 removed entries are explicit source/target/class/permission
  combinations; they are not 171 demonstrated exploits. Every grant for other
  subjects remains unchanged, including the HAL's grants involving ordinary
  player apps. Build-time checks reject accidental broadening.
- A hardware-effect alias created by the module is labelled
  audio_hweffect_device, the type already defined by the target device policy.

## Target-specific source verification

The source fixture manifest pins two public configurations by commit and SHA-256:

| Input | Source |
| --- | --- |
| Vendor audio effects | whatawurst/android_vendor_sony_yoshino-common, commit 0fb1f35c79dfe0ed6de189a388431ff60d30213b |
| Flamefire audio policy | Flamefire/android_device_sony_yoshino-common, commit 71d95f043fdb2cfde9e72ffb6cc2af9121f50211 |

Both are parsed before and after two patch passes. Checks require a single
correct Sony proxy, resolved library references, unchanged unrelated effects,
stable repeated output and preserved non-offload routes/endpoints. These are
source snapshots, not an extraction from your installed ROM.

The vendor configuration already defines the same Sony proxy/software/hardware
UUIDs that this port uses. This is useful compatibility evidence; it does not
prove the engine is processing your music.

The inherited policy transformation deliberately excludes compressed-offload
routes. RC3 keeps this behavior. It does not promise exclusive/bit-perfect
output compatibility, identical power consumption to stock, or every stock
Sony feature on every output route.

The supplied APK is under system/priv-app and declares no shared system UID.
AOSP Android 12 application-context rules distinguish privileged apps from
ordinary untrusted apps; the pinned Flamefire vendor seapp file adds no Sony
Sound Enhancement override. Actual on-phone labels are now captured in reports.
Other broad inherited privileged/HAL allowances still need device evidence
before further reduction. SELinux remains enforcing; no permissive fallback
or automatic audit2allow policy is introduced.

## Install over the existing module

1. Save your current known-good module ZIP. Download the RC3 Actions artifact.
2. Extract GitHub's outer artifact archive once. Keep the inner
   SoundEnhancement-v2.0.0-rc.3-lilac-12L.zip packed.
3. In Magisk > Modules > Install from storage, select that inner ZIP.
   The module ID remains SoundEnhancement, so it is an upgrade.
4. After a successful installation, reboot Android normally. No ROM flash,
   TWRP operation, factory reset or another boot-image patch is required.
5. Play music. Test automatic reconnection first. If needed, Action now repairs
   known profiles and opens Sony's panel. Check that Runtime shows v2.0.0-rc.3.

For an audible comparison, temporarily disable ClearAudio+/DSEE and other EQs,
then compare flat EQ with a strong manual cut at moderate volume. Test speaker,
wired and Bluetooth separately, then qualify your usual enhancements individually.

## Capture a failure without hiding it

While music is playing and controls have no audible effect, capture a report
**before** pressing Action, changing apps or running refresh/recover:

    adb shell su -c "sefx report"

The command prints the report's Downloads path. Review the file before sharing;
it includes playback/app names, configuration contents and recent logs. It is
never uploaded automatically.

If Downloads export is unavailable, preserve the private report instead:

    adb shell su -c "sefx doctor"
    adb shell su -c "cat /data/adb/sony-audio-manager/diagnostics.txt" > SonyAudio-diagnostics.txt

The second command runs on your computer and saves the text there. After
capture, sefx recover repairs known profiles and opens settings. sefx refresh
repairs without opening the panel. Neither command clears Sony app data.

Optional desktop inspection, with Python 3 and this repository:

    python3 tools/inspect_audio_report.py SonyAudio-diagnostics.txt

The analyzer does not open paths from the report, execute content, expand DTD
entities or claim audible DSP verification. XML checks are structural and
targeted; legacy conf semantic checking is incomplete. Truncated/omitted
snapshots and XInclude targets remain explicit.

## Verification and remaining gates

The extended audit executes the unit/failure suite and real Magisk BusyBox
integration tests, checks maintained scripts with ShellCheck, verifies policy
invariants, and validates the pinned source configurations. Packaging verifies
the unchanged 55 proprietary binary containers, deterministic archives and CRCs.
The draft PR links the final CI run and the exact installer ZIP checksum.

Actual RC3 install/mount behavior, Sony DSP control, screen-off/Doze latency,
per-user behavior and every desired audio enhancement still need the phone.
The background supervisor is not an independent system init service. The
legacy transformer is not a general XML/schema engine. See AUDIT.md for the
full gap map; these limits are not erased by a green CI result.

## Sources

- [Pinned vendor effects configuration](https://github.com/whatawurst/android_vendor_sony_yoshino-common/blob/0fb1f35c79dfe0ed6de189a388431ff60d30213b/proprietary/vendor/etc/audio_effects.xml)
- [Pinned Flamefire audio policy](https://github.com/Flamefire/android_device_sony_yoshino-common/blob/71d95f043fdb2cfde9e72ffb6cc2af9121f50211/config/audio_policy/audio_policy_configuration.xml)
- [Target HAL SELinux policy](https://github.com/Flamefire/android_device_sony_yoshino-common/blob/71d95f043fdb2cfde9e72ffb6cc2af9121f50211/sepolicy/vendor/hal_audio_default.te)
- [Target vendor application-context rules](https://github.com/Flamefire/android_device_sony_yoshino-common/blob/71d95f043fdb2cfde9e72ffb6cc2af9121f50211/sepolicy/vendor/seapp_contexts)
- [AOSP Android 12 application contexts](https://android.googlesource.com/platform/system/sepolicy/+/refs/heads/android-s-qpr3-beta-1/private/seapp_contexts)
- [AOSP SELinux policy guidance](https://source.android.com/docs/security/features/selinux/device-policy)
- [Magisk developer guide](https://topjohnwu.github.io/Magisk/guides.html)
