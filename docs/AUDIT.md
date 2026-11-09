# RC2 engineering audit and gap map

**Current fix:** [RC4 command transport regression, old-version comparison and installation](RC4.md). RC3 failed package ownership on the target phone; its previous fixture passes missed the Binder FD boundary.

RC3 follow-up: [changes, new verification and current remaining gates](RC3.md). The sections below preserve the RC2 assessment.

Date: 9 November 2026. Target: Xperia XZ1 Compact G8441/lilac, Flamefire
LineageOS 19.1 / Android 12L API 32, Magisk. Runtime tests pin Magisk 31.1.
Other ROMs, architectures and Magisk versions are not qualified by this audit.

## Result and scope

RC2 repairs lifecycle, configuration-generation and packaging failures around
the existing Sony port. It remains an **unvalidated phone candidate**, not a
production release or a guarantee of audible processing. The RC1 reference
download and current phone test remain unchanged.

Reviewed the candidate's 119-file baseline: installer, early/late boot,
intents, player parsing, locks, state, logs, recovery, packaging, tests,
SELinux rules, payload inventory and documentation. Upstream baseline:
925950e80b66db58703f408ea1ba4811811bbacb. Fifty-five supplied APK/JAR/ELF
containers are independently hash-protected and remain byte-identical.
Hashes establish identity, not freedom from defects. Sony DSP source is not
available here; the supplied binaries were not rebuilt.

## Method and verification boundary

1. Establish source identity and run the original 79 tests.
2. Review unsuccessful paths, not only successful discovery/delivery.
3. Add regressions before fixes: the first 19 new failure tests failed on RC1.
   Independently reproduce duplicate/empty XML proxy definitions.
4. Exercise official Magisk BusyBox standalone mode with real file operations,
   kernel locks, timers and process death; keep Android Binder commands as
   controlled fixtures.
5. Add boot, config rollback, malformed input, permission and packaging checks.
6. Compare design with primary Android, Magisk and Linux documentation.
7. Run the final source through GitHub CI; keep physical acceptance separate.

The last completed local run passed 131 tests. Additional tests and recovered
source require the final CI result, linked from the draft PR. The local
workspace became unavailable during final verification; its last run was not
silently treated as a pass. GitHub CI is the authoritative verification of the
published source.

Dedicated runtime tests use the x86_64 BusyBox executable extracted from the
official Magisk 31.1 APK. That checks the actual shell/app­let implementation,
not ARM execution, Android's kernel/SELinux, Binder services or the audio HAL.
A successful Android broadcast is not proof that audio samples are processed.

## Repair map

H = likely loss of processing, damaged generated files/artifacts or unsafe
state handling. M = recovery, diagnosis or maintainability. Findings are code
and fixture evidence, not all established causes of the reported phone symptom.

| ID | Priority | Gap | Repair/evidence |
| --- | --- | --- | --- |
| R01 | H | Action with no playback returned before starting recovery | Request supervisor even when no usable player exists; regression. |
| R02 | H | Panel failure prevented recovery startup | Preserve panel error and still start recovery; regression. |
| R03 | H | Failed CLOSE was forgotten | Retain failed rows, block OPEN for that package, retry; changed, stopped and unchanged-session repair tests. |
| R04 | H | Stale PID/mkdir lock takeover race | Kernel flock removes the stale-directory deletion phase; concurrent/crash tests. |
| R05 | H | A child could retain a lock after manager death | Close manager lock descriptors in Android command children; actual-BusyBox SIGKILL regression. |
| R06 | H | Killed watcher stayed dead until Action/reboot | Singleton supervisor restarts its worker after a bounded delay; SIGKILL/restart test. Supervisor itself is not immortal. |
| R07 | H | Truncated dump could look idle and close good attachments | Require players header and recognized record fields; preserve state on malformed/truncated input. |
| R08 | M | Session zero/missing/ambiguous ownership looked idle | Report active-but-unresolved media, retain prior state, never invent global session zero. |
| R09 | H | Oversized numbers could reach Android integer extras | Bound session, UID and PID; validate package grammar and device record structure. |
| R10 | M | Final config line without newline ignored | Read final data line; regression. |
| R11 | M | Huge/octal-like values could break arithmetic | Canonical decimal config, bounded values, sanitized cached renewal time; regressions. |
| R12 | M | Wall-clock correction could suppress renewal | Use uptime on Android and detect future cached timestamps; regressions. |
| R13 | H | Restart during delivery could be hidden by post-delivery PID cache | Save observed pre-dispatch context. Cold Sony startup may cause one extra rebuild. |
| R14 | M | Preferences lived in replaced module directory | Private /data/adb/sony-audio-manager state; migrate old config once; migration test. |
| R15 | M | Magisk displayed staged metadata before new scripts were active | Distinguish runtime from metadata, guard update flag, require reboot. Cannot retrofit old v1 Action. |
| R16 | H | State-file symlinks could be followed | Reject unsafe state-file types before use; unrelated-file preservation test. Already-root adversaries are outside this threat model. |
| R17 | H | Failed state replacement could be reported successful | Checked same-filesystem replacement and explicit failure status; I/O-error regression. |
| R18 | M | One noisy dump could hide later diagnostic evidence | Per-section caps/exit markers, bounded report, supervisor and last unsuccessful poll output. |
| R19 | M | Startup/permission failures poorly visible | Runtime/supervisor/watcher status, heartbeat, explicit grant errors; boot tests. |
| R20 | M | Boot log unbounded or linked | Rotation and type checks; boot tests. |
| R21 | M | Early boot reset private-state permissions | Exclude old .sefx state, use persistent state outside payload, remove unnecessary userdata remount. |
| R22 | H | Dormant 32-bit file could pass HAL check | Check ELF class of running audio HAL/effect services; five positive/negative tests. Necessary compatibility evidence, not full ABI qualification. |
| R23 | M | Optional pseudo partition reached mknod without device numbers | Validate block major/minor first; stop changing block-device RW flag; no-side-effect test. |
| R24 | H | Repeated XML patch left empty Sony proxies | Remove prior Sony proxy block; verify repeatability and unrelated effect/proxy preservation. |
| R25 | H | Copy/patch failure could destroy generated configs | Private staging, required Sony proxy, backups, checked commit and ordinary-failure rollback; transaction tests. ROM originals are read only. |
| R26 | H | ZIP builder destroyed previous download before verification | Write/flush/CRC-check temporary archive before replacement; injected write failure preserves previous bytes. |
| R27 | H | Builder could overwrite source/follow output symlink | Restrict repository output to dist; reject symlinks/non-ZIP output; tests. |
| R28 | M | Broad packaging prefixes silently accepted new files | Explicit payload allowlist plus independent protected-binary manifest. |
| R29 | M | Runtime/metadata version drift | Build-time version consistency check. |
| R30 | H | PATH mocks failed to model standalone applet selection | Explicit Android command paths; actual-BusyBox ownership, locks, death/recovery and config tests. |

## Open gaps and release gates

These remain open; fixtures cannot close them. RC2 remains a draft candidate.

| ID | Priority | Gap | Evidence/next step |
| --- | --- | --- | --- |
| G01 | Blocking | No RC2 physical/acoustic acceptance | Complete the phone matrix below and capture failure before recovery actions. |
| G02 | High | Closed-source Sony engine can fail or lose control internally | Correlate delivery, AudioFlinger chain/control ownership, logs and listening. Shell fixes cannot prove or repair every DSP defect. |
| G03 | High | Some media may expose no usable nonzero session | Capture real target records; qualify AudioFlinger/privileged-callback fallback. Vendor global session zero can be meaningful; its rejection here does not prove engine failure. |
| G04 | High | Inherited SELinux rules are broad and include unrelated vendor/Dolby allowances | Audit actual process domains, labels and justified access before reducing rules. No new global permissive fallback. Policy reduction is not complete. |
| G05 | High | Legacy XML/conf transformer is not a general parser/schema validator | Host tests parse generated fixtures. Qualify the actual ROM files/schema and replace the transformer before promising arbitrary-format support. Staging handles known command failures, not every semantically wrong config. |
| G06 | High | Installer/mount/SELinux behavior cannot be exercised fully on desktop | Exact-ROM install/upgrade/reboot; inspect mounts, loaded libraries, enforcing-mode denials and early-boot duration. |
| G07 | Medium | Polling/Doze/power management adds latency | Measure cold start, screen-off recovery and battery. Defaults: 5s active, 10s idle/error, 60s renewal, no wake lock. No instantaneous guarantee. |
| G08 | Medium | Killed/stopped supervisor has no independent parent watchdog | Boot starts it; Action/auto-on can restart it. Qualify whether the ROM actually kills it before adding another watchdog. |
| G09 | Medium | Multi-user/work-profile support partly modeled | UID/user routing tested; real per-user permissions, package visibility and SELinux require a phone. |
| G10 | Medium | Competing EQ/direct/exclusive output may bypass this path | Test EQs individually and each route. Exclusive USB/bit-perfect output is not promised. |
| G11 | Medium | Legacy installer has dead branches and lint debt | Fixed focused defaults remain; progressively remove unused Dolby/recovery/vendor paths with target evidence. Lint messages are not automatically reproduced bugs. |
| G12 | Medium | Power loss/full filesystem during multi-file config commit | Checked per-file replacement/rollback covers ordinary failures, not a journaled transaction spanning every config and Android intent. Keep known-good module. |
| G13 | Low | First migration from RC1 can use install-time config snapshot | Avoid changing reconnect preferences between staging the upgrade and reboot. Later RC2 upgrades use persistent preferences. |

## Alternative approaches

| Approach | Benefit | Decision |
| --- | --- | --- |
| Privileged AudioPlaybackCallback helper | Event-driven updates; potentially lower polling cost/latency | Promising follow-up, not a drop-in ordinary app: normal callbacks redact identity/session data, and relevant access is hidden/system API. Requires a build, permission/lifecycle design and ROM qualification. |
| Player-sent OPEN/CLOSE intents alone | Native integration, less background work | Useful, insufficient if a player omits them or Sony loses state. Explicit repair remains useful. |
| Repeated Sony/audioserver kills or SELinux toggling | May mask lost state temporarily | Rejected for routine recovery: disruptive and not causal diagnosis. Inherited single boot audioserver restart remains pending ROM qualification. |
| Force global session zero | Could match some vendor implementations | Not selected without target evidence; global insert use is deprecated and may target the wrong chain. |
| ROM-integrated vendor effect service | Better init, ownership, policy and schema control | Strongest long-term integration if maintaining the ROM/licensed components is feasible; larger scope than this module. |

## Reproduce engineering checks

    python3 -m unittest discover -s tests -v
    python3 tools/audit_toolchain.py
    sudo env SEFX_BUSYBOX="$PWD/audit-tools/busybox" python3 -m unittest discover -s tests -v
    audit-tools/shellcheck -s busybox -S warning action.sh service.sh system/bin/sefx sefx/lib.sh sefx/configure.sh copy.sh uninstall.sh
    python3 tools/build_module.py

The ordinary suite skips native tests when the pinned tool/root is unavailable.
The extended CI job supplies both. Maintained scripts are gated on ShellCheck
warnings. An exported legacy baseline is not a claim that the whole inherited
installer has been rewritten or made lint-clean. Tool downloads are SHA-256
pinned. Install only the inner module ZIP from the Actions artifact.

## Phone acceptance matrix

Record runtime version, exact ROM build, Magisk version, route, player, time
since boot and screen-lock state. Use a strong manual EQ cut at moderate volume
with ClearAudio+/DSEE initially disabled, then test those features individually.

| Test | Expected evidence |
| --- | --- |
| Upgrade, normal reboot | Successful install, Runtime RC2, no pending flag, supervisor/watcher visible. |
| Start Eleven after boot without Magisk | Audible EQ within awake polling opportunity; no app switching needed. |
| Music before Action | Correct package/session, matching panel extras, audible response. |
| Pause/resume, seek/skip, album/player restart | Correct new/surviving session lifecycle, no stuck control. |
| Speaker, wired insertion/removal, Bluetooth reconnect | Route rebuild and separate audible verification on every route. |
| Screen off 15 minutes, resume | Measured Doze/recovery latency and power behavior. |
| Multiple players/other EQ | Establish actual effect ownership; delivery alone is insufficient. |
| Second boot/reinstall/upgrade | One Sony proxy, preserved preferences/presets, no accumulating definitions. |
| Disable/re-enable, auto off/on | Flags/preferences respected, reboot applies mounts, no repeated server kills. |
| Failure before any app switching | Save sefx report first, then sefx refresh and record audible outcome. |

## Primary references

- [Magisk guide: BusyBox, modules, boot phases](https://topjohnwu.github.io/Magisk/guides.html)
- [Magisk 31.1 installer: staging and immediate metadata copy](https://github.com/topjohnwu/Magisk/blob/v31.1/scripts/util_functions.sh)
- [AudioEffect lifecycle, ownership and session-zero deprecation](https://developer.android.com/reference/android/media/audiofx/AudioEffect)
- [AudioPlaybackCallback](https://developer.android.com/reference/android/media/AudioManager.AudioPlaybackCallback)
- [AOSP anonymized playback data and system session access](https://android.googlesource.com/platform/frameworks/base/+/48b83a0025d2/media/java/android/media/AudioPlaybackConfiguration.java)
- [Linux flock: inherited descriptors and lock lifetime](https://man7.org/linux/man-pages/man2/flock.2.html)
- [AOSP audio effect integration](https://source.android.com/docs/core/audio/audio-effects)
- [SELinux least privilege and component scope](https://source.android.com/docs/security/features/selinux/customize)
- [Device-policy labels and overbroad allowances](https://source.android.com/docs/security/features/selinux/device-policy)

No source-count target or finite test suite proves that every possible bug has
been caught. This map keeps verified repairs and remaining evidence explicit.
