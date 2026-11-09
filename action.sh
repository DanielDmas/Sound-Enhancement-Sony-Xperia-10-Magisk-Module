#!/system/bin/sh
MODDIR=${0%/*}
printf 'Sony Audio Session Manager\nKeep music playing while opening this panel.\n\n'
exec sh "$MODDIR/system/bin/sefx" open
