#!/system/bin/sh
MODDIR=${0%/*}
printf 'Sony Audio Session Manager\nKeep music playing. Repairing known profiles, then opening settings.\n\n'
exec sh "$MODDIR/system/bin/sefx" recover
