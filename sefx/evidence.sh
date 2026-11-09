#!/system/bin/sh
# On-demand evidence only. Nothing is uploaded, relabelled or repaired here.
sefx_snapshot_file() {
    evidence_kind=$1; evidence_path=$2
    if [ "$evidence_count" -ge 24 ]; then evidence_omitted=1; return 0; fi
    [ -f "$evidence_path" ] && [ ! -L "$evidence_path" ] || return 0
    evidence_real=$(readlink -f "$evidence_path") || return 0
    evidence_key=$evidence_kind:$evidence_real
    grep -Fxq "$evidence_key" "$SEFX_RUN/evidence-seen" && return 0
    printf '%s\n' "$evidence_key" >> "$SEFX_RUN/evidence-seen"
    evidence_size=$(stat -c %s "$evidence_path" 2>/dev/null)
    case "$evidence_size" in ''|*[!0-9]*) return 0 ;; esac
    sefx_timeout 4 head -c 65536 "$evidence_path" > "$SEFX_RUN/config-snapshot" || return 0
    evidence_included=$(wc -c < "$SEFX_RUN/config-snapshot" | tr -d ' ')
    evidence_hash=$(sha256sum "$SEFX_RUN/config-snapshot");evidence_hash=${evidence_hash%% *}
    evidence_name=$(printf '%s' "$evidence_path" | base64 | tr -d '\n')
    printf 'CONFIG_SNAPSHOT v1 %s %s %s %s %s\n' "$evidence_kind" "$evidence_name" "$evidence_hash" "$evidence_size" "$evidence_included"
    base64 "$SEFX_RUN/config-snapshot"
    printf '\nEND_CONFIG_SNAPSHOT\n'
    evidence_count=$((evidence_count+1))
}
sefx_configuration_evidence() {
    printf '\n--- CONFIGURATION SNAPSHOTS ---\n'
    evidence_count=0; evidence_omitted=0; : > "$SEFX_RUN/evidence-seen"
    for evidence_kind in module active; do
        if [ "$evidence_kind" = module ]; then
            evidence_root=$MODDIR/system; evidence_subdirs='/etc /vendor/etc /odm/etc /my_product/etc'
        else
            evidence_root=${SEFX_SYSTEM_ROOT:-}; evidence_subdirs='/system/etc /vendor/etc /odm/etc /my_product/etc'
        fi
        : > "$SEFX_RUN/evidence-paths"
        for evidence_subdir in $evidence_subdirs; do
            evidence_dir=$evidence_root$evidence_subdir
            [ -d "$evidence_dir" ] || continue
            find "$evidence_dir" -maxdepth 3 -type f \( -name '*audio*effects*.xml' -o -name '*audio*effects*.conf' -o -name '*policy*.xml' -o -name '*policy*.conf' \) \
                ! -name '*policy*volume*.xml' ! -name '*effects*spatializer*.xml' ! -name '*effects*haptic*.xml' >> "$SEFX_RUN/evidence-paths" 2>/dev/null
        done
        while IFS= read -r evidence_path; do sefx_snapshot_file "$evidence_kind" "$evidence_path"; done < "$SEFX_RUN/evidence-paths"
    done
    [ "$evidence_omitted" = 0 ] || printf 'CONFIG_SNAPSHOT_LIMIT_REACHED\n'
    find "$MODDIR" -mindepth 1 -maxdepth 1 -type d -name '.config.*' > "$SEFX_RUN/recovery-paths" 2>/dev/null
    while IFS= read -r evidence_path; do
        printf 'CONFIG_RECOVERY %s\n' "$(printf '%s' "$evidence_path" | base64 | tr -d '\n')"
    done < "$SEFX_RUN/recovery-paths"
}
sefx_policy_evidence() {
    printf '\n--- SONY PROCESS SECURITY CONTEXTS ---\n'
    sefx_android_timeout 6 ps -AZ > "$SEFX_RUN/security-processes" 2>&1
    grep -E '(^LABEL|soundenhancement|audioutil|audioserver|android.hardware.audio)' "$SEFX_RUN/security-processes" | head -c 16384
    printf '\n--- HARDWARE EFFECT NODE LABELS ---\n'
    ls -lZ /dev/sony_hweffect_params /dev/msm_hweffects 2>&1 | head -c 8192
    printf '\n--- RECENT AUDIO/POLICY ERRORS ---\n'
    sefx_android_timeout 8 logcat -b all -d -t 2000 2>&1 | tail -c 262144 > "$SEFX_RUN/policy-logcat"
    grep -Ei 'avc: *denied|soundenhancement|sonyeffect|libsony|hweffect' "$SEFX_RUN/policy-logcat" | tail -c 32768
    printf '\n--- MODULE POLICY ---\n'; head -c 16384 "$MODDIR/sepolicy.rule" 2>/dev/null
}
