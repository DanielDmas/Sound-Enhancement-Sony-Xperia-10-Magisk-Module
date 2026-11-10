# Source-level follow-up: what RC4 still cannot verify

Date: 10 November 2026. Target: G8441/lilac, Flamefire LineageOS 19.1,
Android 12L, Magisk 31.1. Reviewed runtime commit:
`f29e714b7900b22f8d7ecd00a2932324c52e84f5`.

This follow-up corrects two assumptions in the earlier audit. Repeated OPEN
delivery is not necessarily an effect rebuild. Also, although the manager
requires a nonzero player session in its intents, the inherited Sony APK
defaults to a native effect on global session zero. Those are different layers.
The older audit's statement that global mode was not selected is therefore
incomplete. These findings do not change the published RC4 installer or prove
the cause of the user's intermittent failure.

## Findings from the exact shipped binaries

Read-only DEX inspection used these files, unchanged from the supplied port:

- `system/priv-app/SoundEnhancement/SoundEnhancement.apk`:
  SHA-256 `46bd1409aabf7e3b832bf1413c0be20305cc88dc8fa72a3dbd10de6aa3867031`.
- `system/framework/sonyaudioeffect.jar`:
  SHA-256 `f16653c3f51f84480db0d8c73dd57d4a272a6c4014f60e96af83577f1625ee78`.

### 1. Periodic OPEN is weaker than repair

`AudioEffectSettings.updateAudioSession` looks up a holder by package.
When its session ID changes, it releases the old effect and creates a new
holder. When the ID is unchanged, it checks the existing effect's control
status; it does not unconditionally recreate the effect. The same-ID path
also skips creation if the holder's effect reference is null.

DEX instruction offsets in that method: the equality branch at code-unit 22
jumps to 46, bypassing release/removal/recreation at 24–42. The null-effect
branch at 53 jumps to 71. `hasControl()` at 55 can lead to an
`UnsupportedOperationException`. `AudioEffectServiceImpl.updateAudioSession`
has an exception path calling `createSessionHolder`; that helper delegates
to `createNewSessionHolder`, which returns an existing package holder instead
of rebuilding it. An Android broadcast exit status cannot expose this as a
reliable success/failure acknowledgment.

RC4's 60-second renewal sends OPEN. It therefore cannot guarantee recovery
of a broken same-ID object in an otherwise unchanged Sony process. The
existing `sefx refresh` / Action repair sends CLOSE then OPEN, requesting a
stronger rebuild. This is a confirmed recovery limitation, not a reproduced
on-phone failure. Blindly rebuilding every few seconds could interrupt audio
and contend with the player, so no such automatic change is made here.

### 2. The default native effect is global

`service.sh` sets `ro.sony.global.effect=true`, inherited from the working
port. In `AudioEffectManager.constructSonyAudioEffect`, the true branch sets
the constructor's session argument to zero (code-unit 21). With false, it
keeps the requested session. The priority argument is zero.
`SonyAudioEffect` in the supplied JAR forwards those arguments to Android's
`AudioEffect` constructor; it also contains a warning about global-output
attachment. The installer can change the property through the inherited
`stream.mode` option, so the actual installed property must be recorded.

Consequences: a detected player ID is not proof that an effect is attached
to that player's native session. Inspect the global chain as well. Multiple
Sony effect objects can also contend for the same underlying engine. Android's
framework explicitly arbitrates control between handles, including equal
priority handles. Do not change global/postprocess mode without a controlled
comparison on the actual vendor HAL.

### 3. Multiple sessions per package are not independent in Sony's app

`findSessionHolder` matches the package name, not package plus session ID.
Opening a different ID for the same package replaces its existing holder.
The manager can track several playback records, but that does not establish
independent native processing for all those IDs. Earlier multi-session tests
prove script dispatch behavior only. This is particularly relevant to players
with separate concurrent tracks; Eleven's next-track player explicitly reuses
the current session ID, which reduces this specific concern for normal music.

### 4. Do not apply the historical stopSelf patch blindly

An older upstream changelog describes removing `stopSelf()` to address DSEE
HX/Clear Phase toggle behavior. The shipped APK still has `stopSelf()` call
sites, including conditional paths after checking running sessions. Their
presence alone does not prove they are incorrect or that the old report
describes this build. Removing them would change foreground-service lifetime
and could waste power. Correlate a failure with service and effect-chain
state before changing proprietary bytecode.

## Cross-checks against Android and Lineage sources

- [Android AudioEffect documentation](https://developer.android.com/reference/android/media/audiofx/AudioEffect): an object can exist without owning its engine; global insert effects on session zero are deprecated.
- [Android 12L AudioEffect.java](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-12.1.0_r1/media/java/android/media/audiofx/AudioEffect.java): OPEN/CLOSE extras and content values; absence of CONTENT_TYPE defaults to music.
- [Lineage 19.1 AudioFlinger Effects.cpp](https://github.com/LineageOS/android_frameworks_av/blob/lineage-19.1/services/audioflinger/Effects.cpp): `EffectBase::addHandle` transfers control; `EffectHandle::command` rejects parameter-changing commands without control; `dumpToBuffer` reports client PID, priority and control state. The dump can distinguish an ownership problem from mere intent delivery.
- [Lineage 19.1 Eleven](https://github.com/LineageOS/android_packages_apps_Eleven/blob/lineage-19.1/src/org/lineageos/eleven/MusicPlaybackService.java): play sends OPEN, pause and destruction send CLOSE, and the next-track player reuses the current session. Player-sent events and the manager can both affect Sony's state. The source is a branch reference, not proof of the exact installed APK.
- [Lineage 19.1 AudioFX](https://github.com/LineageOS/android_packages_apps_AudioFX/blob/lineage-19.1/src/org/lineageos/audiofx/backends/AndroidEffects.java): creates its own effects. That is a reason to isolate EQs during testing, not proof it owns Sony's particular effect type. The module already attempts to hide stock AudioFX/MusicFX during installation.
- [Lineage 19.1 effect configuration](https://github.com/LineageOS/android_frameworks_av/blob/lineage-19.1/media/libeffects/data/audio_effects.xml): software and hardware implementations are paired through a proxy; an XML entry alone does not prove the selected route uses it.
- [AOSP device effects](https://source.android.com/docs/core/audio/audio-effects): automatic device attachment requires suitable vendor implementation, flags and HAL support. It is not a universally compatible replacement for this legacy port.
- [Magisk developer guide](https://topjohnwu.github.io/Magisk/guides.html): standalone BusyBox and absolute paths for Android tools remain consistent with the RC4 approach.
- [Flamefire build repository](https://github.com/Flamefire/lineageos_lilac): establishes the target build family; it does not qualify this third-party module.

Forum reports and old port changelogs are leads, not independent successful
tests of this RC4 binary on the user's exact ROM.

## Minimal evidence to separate the remaining causes

Keep one track and output route unchanged. With manual EQ, temporarily turn
ClearAudio+ and DSEE HX off. At the moment changes stop affecting sound,
before opening Magisk or switching apps, use authorized ADB:

```sh
adb shell "su -c 'sefx report'"
adb shell "su -c '/system/bin/getprop ro.sony.global.effect'"
adb shell "su -c 'sefx refresh'"
adb shell "su -c 'sefx report'"
```

Save the first report before the second capture and note which is before/after.
Each report command prints its destination in Downloads. Reports use timestamps
to the second; separate the captures if necessary to avoid a same-second name.
Record whether refresh alone restores audible EQ, without opening the panel.

Compare the AudioFlinger chains and controlling client PID, active player IDs,
Sony lifecycle/control warnings, route, loaded effect libraries, mounted
configuration and SELinux denials. In global mode, do not misclassify a chain
on session zero as missing just because the player's ID differs. A surviving
engine with the wrong controlling handle suggests ownership; a disappeared
engine suggests lifecycle/load failure; an existing enabled chain on an unused
output suggests routing. Each remains a hypothesis until correlated with the
before/after captures and audible result.

No runtime or binary patch is issued from this research alone. The verified
RC4 transport fix remains useful, but its successful tests do not establish
that all proprietary-engine recovery paths work.
