#!/system/bin/sh
# Magisk removes the module directory/mounts. Preserve Sony app data and presets.
# The watcher sees the remove flag and exits; reboot completes removal.
MODDIR=${0%/*}
if [ -d "$MODDIR/.sefx" ] && [ ! -L "$MODDIR/.sefx" ]; then
    printf 'auto=0\n' > "$MODDIR/.sefx/config"
fi
printf 'Sony audio module removal requested. Reboot to remove its mounts.\n'
