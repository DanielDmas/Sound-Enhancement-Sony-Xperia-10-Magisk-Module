#!/system/bin/sh
# Stage all edits before touching generated copies; ROM originals are read only.
CFG_MODULE=${MODPATH:-${0%/sefx/configure.sh}}
umask 077
[ ! -L "$CFG_MODULE/.config.flock" ] && [ ! -d "$CFG_MODULE/.config.flock" ] || exit 1
exec 6>"$CFG_MODULE/.config.flock" || exit 1
flock -n 6 || { printf 'Another audio configuration transaction is running.\n' >&2; exit 5; }
CFG_WORK=$(mktemp -d "$CFG_MODULE/.config.XXXXXXXX") || exit 1
CFG_COMMIT=0; CFG_OK=0
cfg_cleanup() {
    trap '' INT TERM
    cfg_restore_failed=0
    if [ "$CFG_COMMIT" = 1 ] && [ "$CFG_OK" != 1 ]; then
        printf 'Configuration commit failed; restoring previous generated copies.\n' >&2
        while IFS= read -r cfg_relative; do
            rm -f "$CFG_MODULE/$cfg_relative.next"
            if ! grep -Fxq "$cfg_relative" "$CFG_WORK/old.list"; then
                rm -f "$CFG_MODULE/$cfg_relative" || cfg_restore_failed=1
            fi
        done < "$CFG_WORK/new.list"
        while IFS= read -r cfg_relative; do
            if [ "$CFG_WORK/backup/$cfg_relative" -ef "$CFG_MODULE/$cfg_relative" ]; then
                # Commit did not replace this inode; it is already the backup.
                rm -f "$CFG_WORK/backup/$cfg_relative"
                continue
            fi
            # Rename the preserved inode back. Do not first delete a still-good
            # live file, and do not allocate another full copy on a full disk.
            if ! mv -f "$CFG_WORK/backup/$cfg_relative" "$CFG_MODULE/$cfg_relative"; then
                cfg_restore_failed=1
                printf 'RESTORE FAILED: %s\n' "$cfg_relative" >&2
            fi
        done < "$CFG_WORK/old.list"
    fi
    if [ "$cfg_restore_failed" = 1 ]; then
        printf 'BACKUP RETAINED: %s\n' "$CFG_WORK" >&2
    else rm -rf "$CFG_WORK"
    fi
}
trap 'cfg_cleanup' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
mkdir -p "$CFG_WORK/candidate/sefx" "$CFG_WORK/backup" || exit 1
cp "$CFG_MODULE/sefx/proxy.awk" "$CFG_WORK/candidate/sefx/proxy.awk" || exit 1
MODPATH=$CFG_WORK/candidate MODSYSTEM=${MODSYSTEM:-/system} sh -e "$CFG_MODULE/copy.sh" 6>&- || exit 1
MODPATH=$CFG_WORK/candidate SEFX_PAYLOAD_ROOT=$CFG_MODULE sh -e "$CFG_MODULE/.aml.sh" 6>&- || exit 1
: > "$CFG_WORK/new.list"; : > "$CFG_WORK/old.list"
for cfg_tree in system vendor; do
    if [ -d "$CFG_WORK/candidate/$cfg_tree" ]; then
        find "$CFG_WORK/candidate/$cfg_tree" -type f | sed "s|^$CFG_WORK/candidate/||" >> "$CFG_WORK/new.list" || exit 1
    fi
    if [ -d "$CFG_MODULE/$cfg_tree" ]; then
        find "$CFG_MODULE/$cfg_tree" -type f \( -name '*audio*effects*.conf' -o -name '*audio*effects*.xml' -o -name '*policy*.conf' -o -name '*policy*.xml' \) | sed "s|^$CFG_MODULE/||" >> "$CFG_WORK/old.list" || exit 1
    fi
done
[ -s "$CFG_WORK/new.list" ] || exit 1
if ! find "$CFG_WORK/candidate" -type f \( -name '*audio*effects*.conf' -o -name '*audio*effects*.xml' \) -exec grep -l 'af8da7e0-2ca1-11e3-b71d-0002a5d5c51b' {} \; | grep -q .; then
    printf 'Generated audio configuration has no Sony proxy; preserving previous files.\n' >&2
    exit 1
fi
while IFS= read -r cfg_relative; do
    [ ! -L "$CFG_MODULE/$cfg_relative" ] || exit 1
    mkdir -p "$CFG_WORK/backup/${cfg_relative%/*}" || exit 1
    # A hard link preserves mode/context and consumes no duplicate file data.
    ln "$CFG_MODULE/$cfg_relative" "$CFG_WORK/backup/$cfg_relative" 2>/dev/null || cp -p "$CFG_MODULE/$cfg_relative" "$CFG_WORK/backup/$cfg_relative" || exit 1
done < "$CFG_WORK/old.list"
while IFS= read -r cfg_relative; do
    [ ! -L "$CFG_MODULE/$cfg_relative" ] && [ ! -e "$CFG_MODULE/$cfg_relative.next" ] && [ ! -L "$CFG_MODULE/$cfg_relative.next" ] || exit 1
done < "$CFG_WORK/new.list"
CFG_COMMIT=1
while IFS= read -r cfg_relative; do
    mkdir -p "$CFG_MODULE/${cfg_relative%/*}" && cp -p "$CFG_WORK/candidate/$cfg_relative" "$CFG_MODULE/$cfg_relative.next" && mv -f "$CFG_MODULE/$cfg_relative.next" "$CFG_MODULE/$cfg_relative" || exit 1
done < "$CFG_WORK/new.list"
while IFS= read -r cfg_relative; do
    grep -Fxq "$cfg_relative" "$CFG_WORK/new.list" || rm -f "$CFG_MODULE/$cfg_relative" || exit 1
done < "$CFG_WORK/old.list"
CFG_OK=1
printf 'Audio configuration staged and committed successfully.\n'
