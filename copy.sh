#!/system/bin/sh
# Read ROM configuration into a private staging tree. Called by configure.sh.
MODPATH=${MODPATH:-${0%/*}}
MODSYSTEM=${MODSYSTEM:-/system}
copy_audio_configs() {
    copy_list=$MODPATH/.source-configs
    : > "$copy_list" || return 1
    for copy_partition in system odm my_product vendor; do
        copy_root=${SEFX_AUDIO_ROOT:-}/$copy_partition
        [ -d "$copy_root" ] || continue
        find "$copy_root" -type f \( -name '*audio*effects*.conf' -o -name '*audio*effects*.xml' -o -name '*policy*.conf' -o -name '*policy*.xml' \) \
            ! -name '*policy*volume*.xml' ! -name '*audio*effects*spatializer*.xml' ! -name '*audio*effects*haptic*.xml' >> "$copy_list" || return 1
    done
    [ -s "$copy_list" ] || { echo 'No ROM audio configuration files found.' >&2; return 1; }
    while IFS= read -r copy_source; do
        copy_relative=${copy_source#"${SEFX_AUDIO_ROOT:-}"}
        case "$copy_relative" in
            /system/*) copy_target=$MODPATH$copy_relative ;;
            /vendor/*) copy_target=$MODPATH$MODSYSTEM$copy_relative ;;
            /odm/*|/my_product/*) copy_target=$MODPATH/system$copy_relative ;;
            *) return 1 ;;
        esac
        mkdir -p "${copy_target%/*}" && cp -p "$copy_source" "$copy_target" || return 1
    done < "$copy_list"
    rm -f "$copy_list"
}
copy_audio_configs
