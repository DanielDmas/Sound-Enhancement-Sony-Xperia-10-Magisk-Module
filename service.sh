#!/system/bin/sh
# One boot initialization, followed by a non-recursive session watcher.
MODDIR=${0%/*}
[ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ] && [ ! -f "$MODDIR/update" ] || exit 0
umask 077
[ ! -L "$MODDIR/.sefx" ] && [ ! -L "$MODDIR/.sefx/boot.log" ] && [ ! -L "$MODDIR/.sefx/boot.previous.log" ] || exit 3
mkdir -p "$MODDIR/.sefx" && chmod 0700 "$MODDIR/.sefx" || exit 3
if [ -f "$MODDIR/.sefx/boot.log" ] && [ "$(wc -c < "$MODDIR/.sefx/boot.log")" -gt 65536 ]; then
    mv -f "$MODDIR/.sefx/boot.log" "$MODDIR/.sefx/boot.previous.log" || exit 3
fi
exec >> "$MODDIR/.sefx/boot.log" 2>&1
printf 'Sony audio boot initialization\n'
. "$MODDIR/sefx/lib.sh"
trap sefx_cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
sefx_init || exit $?
sefx_ready || exit $?

# Retain the Sony capability properties used by the previously working build.
# These are capability flags, not an attempt to overwrite the user's EQ preset.
resetprop -n ro.audio.ignore_effects false
resetprop -n ro.sony.global.effect true
resetprop -n ro.semc.product.model I4113
resetprop -n ro.semc.ms_type_id PM-1181-BV
resetprop -n ro.semc.version.fs GENERIC
resetprop -n ro.semc.product.name "Xperia 10"
resetprop -n ro.semc.product.device I41
resetprop -n audio.sony.effect.use.proxy true
resetprop -n vendor.audio.sony.effect.use.proxy true
resetprop -n vendor.audio.sony.effect.custom.sp_bundle 0x122
resetprop -n vendor.audio.sony.effect.custom.caplus_hs 0x298
resetprop -n vendor.audio.sony.effect.custom.caplus_sp 0x2B8
resetprop -n ro.somc.dseehx.supported true
resetprop -n persist.sony.effect.ahc true
resetprop -n persist.sony.mono_speaker false
resetprop -n persist.sony.effect.dolby_atmos false
resetprop -n persist.sony.enable.dolby_auto_mode true
resetprop -n persist.sony.effect.clear_audio_plus true
resetprop -n vendor.audio.use.sw.alac.decoder true

# Preserve the upstream Sony hardware-effect device alias when required.
if [ ! -e /dev/sony_hweffect_params ] && [ -c /dev/msm_hweffects ]; then
    alias_numbers=$(stat -c '%t %T' /dev/msm_hweffects | {
        read -r alias_major alias_minor
        printf '%d %d\n' "0x$alias_major" "0x$alias_minor"
    })
    if [ -n "$alias_numbers" ]; then
        # Two decimal numbers from stat/printf, never user-provided shell code.
        set -- $alias_numbers
        mknod /dev/sony_hweffect_params c "$1" "$2" && {
            chmod 0660 /dev/sony_hweffect_params
            chown 1000:1005 /dev/sony_hweffect_params
            # The target ROM defines this type and grants its audio HAL access.
            # A generic device label should not require broader device access.
            chcon u:object_r:audio_hweffect_device:s0 /dev/sony_hweffect_params || printf 'Hardware effect node label failed; inspect policy diagnostics.\n'
        }
    fi
fi

# Upstream restarts audio at boot so the newly mounted configs are loaded.
# Keep one audioserver restart here; never periodically kill Sony or the HAL.
if pidof audioserver >/dev/null 2>&1; then killall audioserver; fi

boot_attempt=0
until [ "$(getprop sys.boot_completed)" = 1 ]; do
    [ "$boot_attempt" -lt 180 ] || { printf 'Boot readiness timed out.\n'; exit 1; }
    [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ] || exit 0
    sleep 2; boot_attempt=$((boot_attempt+1))
done

# RECORD_AUDIO is a real runtime permission. Do not use the invalid grant-all
# command, change the user's Magisk denylist, or clear application settings.
sefx_current_user || exit 1
boot_user=$SEFX_USER
sefx_android_timeout 8 pm grant --user "$boot_user" com.sonyericsson.soundenhancement android.permission.RECORD_AUDIO || printf 'RECORD_AUDIO grant failed; inspect package permissions.\n'
sefx_android_timeout 8 appops set --user "$boot_user" com.sonyericsson.soundenhancement SYSTEM_ALERT_WINDOW allow || printf 'Background/overlay app-op rejected.\n'
sefx_android_timeout 8 appops set --user "$boot_user" com.sonyericsson.soundenhancement RUN_IN_BACKGROUND allow || printf 'Background/overlay app-op rejected.\n'
sefx_android_timeout 8 appops set --user "$boot_user" com.sonyericsson.soundenhancement RUN_ANY_IN_BACKGROUND allow || printf 'Background/overlay app-op rejected.\n'
sefx_cleanup
exec sh "$MODDIR/system/bin/sefx" daemon
