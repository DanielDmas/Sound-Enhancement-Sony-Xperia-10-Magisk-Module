#!/system/bin/sh
# Lifecycle management for the supplied Sony APK; not an audio-processing meter.
SONY_PACKAGE=com.sonyericsson.soundenhancement
SONY_RECEIVER=$SONY_PACKAGE/.AudioEffectControlReceiver
SONY_PANEL=$SONY_PACKAGE/.SoundEnhancementRedirector
SEFX_STATE_DIR=${SEFX_STATE_DIR:-$MODDIR/.sefx}
SEFX_PROC_DIR=${SEFX_PROC_DIR:-/proc}
SEFX_LOCK_HELD=0
SEFX_WATCH_HELD=0
umask 077

sefx_now() { date +%s; }
sefx_log() {
    [ -d "$SEFX_STATE_DIR" ] || return 0
    if [ -f "$SEFX_STATE_DIR/events.log" ]; then
        sefx_size=$(wc -c < "$SEFX_STATE_DIR/events.log")
        [ "$sefx_size" -le 65536 ] || mv -f "$SEFX_STATE_DIR/events.log" "$SEFX_STATE_DIR/events.previous.log"
    fi
    printf '%s %s\n' "$(sefx_now)" "$*" >> "$SEFX_STATE_DIR/events.log"
}
sefx_error() { printf 'ERROR: %s\n' "$*" >&2; sefx_log "ERROR $*"; }
sefx_init() {
    if [ "$(id -u)" != 0 ]; then printf 'Root required: use Magisk Action or su -c sefx.\n' >&2; return 1; fi
    [ ! -L "$SEFX_STATE_DIR" ] || { printf 'Refusing symlink state directory.\n' >&2; return 1; }
    mkdir -p "$SEFX_STATE_DIR" || return 1
    chmod 0700 "$SEFX_STATE_DIR" || return 1
    SEFX_RUN=$SEFX_STATE_DIR/run.$$
    [ ! -L "$SEFX_RUN" ] || return 1
    mkdir -p "$SEFX_RUN" || return 1
    SEFX_AUTO=1; SEFX_INTERVAL=5; SEFX_IDLE_INTERVAL=10; SEFX_REFRESH=60
    sefx_config
}
sefx_config() {
    # Configuration is data and is never sourced as shell code.
    [ -f "$SEFX_STATE_DIR/config" ] || return 0
    while IFS='=' read -r cfg_key cfg_value; do
        case "$cfg_value" in ''|*[!0-9]*) continue ;; esac
        case "$cfg_key" in
            auto) [ "$cfg_value" -le 1 ] && SEFX_AUTO=$cfg_value ;;
            interval) [ "$cfg_value" -ge 3 ] && [ "$cfg_value" -le 60 ] && SEFX_INTERVAL=$cfg_value ;;
            idle_interval) [ "$cfg_value" -ge 5 ] && [ "$cfg_value" -le 120 ] && SEFX_IDLE_INTERVAL=$cfg_value ;;
            refresh_interval) [ "$cfg_value" -ge 30 ] && [ "$cfg_value" -le 600 ] && SEFX_REFRESH=$cfg_value ;;
        esac
    done < "$SEFX_STATE_DIR/config"
    return 0
}
sefx_timeout() {
    sefx_limit=$1; shift
    if command -v timeout >/dev/null 2>&1; then timeout -s KILL "$sefx_limit" "$@"
    elif [ -x /data/adb/magisk/busybox ]; then /data/adb/magisk/busybox timeout -s KILL "$sefx_limit" "$@"
    else printf 'No timeout available; refusing an unbounded Android command.\n' >&2; return 127
    fi
}
sefx_process_token() {
    # PID alone is not identity: it may be reused or refer to a previous boot.
    token_pid=$1
    token_boot=$(cat "$SEFX_PROC_DIR/sys/kernel/random/boot_id" 2>/dev/null)
    token_start=$(sed 's/^[^(]*(.*) //' "$SEFX_PROC_DIR/$token_pid/stat" 2>/dev/null | awk '{print $20}')
    case "$token_start" in ''|*[!0-9]*) return 1 ;; esac
    case "$token_boot" in ''|*[!A-Za-z0-9-]*) return 1 ;; esac
    printf '%s:%s\n' "$token_boot" "$token_start"
}
sefx_lock_live() {
    lock_pid=$(cat "$1/pid" 2>/dev/null)
    case "$lock_pid" in ''|*[!0-9]*) return 1 ;; esac
    [ "$lock_pid" -ge 1 ] || return 1
    kill -0 "$lock_pid" 2>/dev/null || return 1
    lock_saved=$(cat "$1/token" 2>/dev/null)
    lock_actual=$(sefx_process_token "$lock_pid")
    if [ -n "$lock_saved" ] && [ -n "$lock_actual" ] && [ "$lock_saved" != "$lock_actual" ]; then return 1; fi
    return 0
}
sefx_acquire_lock() {
    sefx_lock=$SEFX_STATE_DIR/attach.lock
    [ ! -L "$sefx_lock" ] || return 1
    if ! mkdir "$sefx_lock" 2>/dev/null; then
        sefx_owner=$(cat "$sefx_lock/pid" 2>/dev/null)
        case "$sefx_owner" in
            ''|*[!0-9]*)
                # A just-created lock may not have its owner file yet.
                sefx_stamp=$(stat -c %Y "$sefx_lock" 2>/dev/null)
                case "$sefx_stamp" in ''|*[!0-9]*) return 1 ;; esac
                [ "$(( $(sefx_now)-sefx_stamp ))" -ge 30 ] || return 1 ;;
            *) sefx_lock_live "$sefx_lock" && return 1 ;;
        esac
        rm -f "$sefx_lock/pid"
        rm -f "$sefx_lock/token"
        rmdir "$sefx_lock" 2>/dev/null || return 1
        mkdir "$sefx_lock" 2>/dev/null || return 1
    fi
    printf '%s\n' "$$" > "$sefx_lock/pid"
    sefx_process_token "$$" > "$sefx_lock/token" || true
    SEFX_LOCK_HELD=1
}
sefx_release_lock() {
    if [ "$SEFX_LOCK_HELD" = 1 ]; then
        rm -f "$SEFX_STATE_DIR/attach.lock/pid"
        rm -f "$SEFX_STATE_DIR/attach.lock/token"
        rmdir "$SEFX_STATE_DIR/attach.lock" 2>/dev/null || true
        SEFX_LOCK_HELD=0
    fi
}
sefx_cleanup() {
    sefx_release_lock
    if [ "$SEFX_WATCH_HELD" = 1 ]; then
        rm -f "$SEFX_STATE_DIR/watch.lock/pid"
        rm -f "$SEFX_STATE_DIR/watch.lock/token"
        rmdir "$SEFX_STATE_DIR/watch.lock" 2>/dev/null || true
    fi
    if [ -n "$SEFX_RUN" ] && [ -d "$SEFX_RUN" ] && [ ! -L "$SEFX_RUN" ]; then
        rm -f "$SEFX_RUN"/*
        rmdir "$SEFX_RUN" 2>/dev/null || true
    fi
}
sefx_current_user() {
    SEFX_USER=$(sefx_timeout 6 cmd activity get-current-user 2>/dev/null)
    case "$SEFX_USER" in ''|*[!0-9]*) sefx_error 'Cannot identify the foreground Android user.'; return 3 ;; esac
}
sefx_collect() {
    sefx_current_user || return $?
    if ! sefx_timeout 8 dumpsys audio > "$SEFX_RUN/audio.txt" 2> "$SEFX_RUN/audio.err"; then
        sefx_error 'Audio dump failed/timed out; preserving previous state.'; return 3
    fi
    if ! grep -Eq 'PlaybackActivityMonitor|AudioPlaybackConfiguration|^[[:space:]]*players:' "$SEFX_RUN/audio.txt"; then
        sefx_error 'Unknown/empty audio dump: no sessions will be guessed or closed.'; return 3
    fi
    if ! sefx_timeout 8 cmd package list packages -U --user "$SEFX_USER" > "$SEFX_RUN/packages.txt" 2> "$SEFX_RUN/packages.err"; then
        sefx_error 'Could not read package ownership.'; return 3
    fi
    grep -q '^package:.* uid:[0-9]' "$SEFX_RUN/packages.txt" || { sefx_error 'Unsupported package ownership output.'; return 3; }
    # BusyBox ps does not support Android's NAME field. Bypass standalone applets.
    if [ -x /system/bin/ps ]; then sefx_ps=/system/bin/ps; else sefx_ps=ps; fi
    sefx_timeout 6 "$sefx_ps" -A -o PID,NAME > "$SEFX_RUN/processes.txt" 2>/dev/null || : > "$SEFX_RUN/processes.txt"
    if ! awk -v user="$SEFX_USER" -v sony="$SONY_PACKAGE" -f "$MODDIR/sefx/sessions.awk" \
        "$SEFX_RUN/packages.txt" "$SEFX_RUN/processes.txt" "$SEFX_RUN/audio.txt" > "$SEFX_RUN/parsed.tsv"; then
        sefx_error 'Session parser failed.'; return 3
    fi
    LC_ALL=C sort -u "$SEFX_RUN/parsed.tsv" > "$SEFX_RUN/current.tsv" || return 3
}
sefx_valid_record() {
    case "$rec_pkg" in ''|*[!A-Za-z0-9_.]*) return 1 ;; esac
    for rec_num in "$rec_uid" "$rec_pid" "$rec_sid" "$rec_type"; do
        case "$rec_num" in ''|*[!0-9]*) return 1 ;; esac
    done
    case "$rec_device" in ''|*[!0-9+]*) return 1 ;; esac
    [ "$rec_sid" -gt 0 ] && [ "$rec_type" -le 3 ]
}
sefx_intent() {
    intent_action=$1
    sefx_valid_record || { sefx_error 'Invalid cached session rejected.'; return 3; }
    intent_user=$((rec_uid/100000))
    if ! sefx_timeout 8 cmd activity broadcast --user "$intent_user" --include-stopped-packages \
        -n "$SONY_RECEIVER" -a "android.media.action.${intent_action}_AUDIO_EFFECT_CONTROL_SESSION" \
        --es android.media.extra.PACKAGE_NAME "$rec_pkg" \
        --ei android.media.extra.AUDIO_SESSION "$rec_sid" \
        --ei android.media.extra.CONTENT_TYPE "$rec_type" > "$SEFX_RUN/am.txt" 2>&1; then
        sefx_error "Sony $intent_action broadcast failed: $rec_pkg session=$rec_sid."; return 3
    fi
    if grep -Eiq 'error:|exception|permission denial|unable to resolve' "$SEFX_RUN/am.txt"; then
        sefx_error "Android rejected $intent_action; see last-am.txt."; return 3
    fi
    grep -q 'Broadcast completed:' "$SEFX_RUN/am.txt" || { sefx_error "Unconfirmed $intent_action broadcast."; return 3; }
    sefx_log "$intent_action user=$intent_user package=$rec_pkg session=$rec_sid type=$rec_type route=$rec_device"
}
sefx_sync() {
    sync_mode=$1
    if [ -f "$MODDIR/disable" ] || [ -f "$MODDIR/remove" ]; then sefx_error 'Module disabled/pending removal; reboot after enabling.'; return 3; fi
    sefx_acquire_lock || { sefx_error 'Another refresh is running; retry shortly.'; return 5; }
    sefx_collect; sync_result=$?
    if [ "$sync_result" != 0 ]; then sefx_release_lock; return "$sync_result"; fi
    if ! awk -v p="package:$SONY_PACKAGE" '$1==p {found=1} END {exit !found}' "$SEFX_RUN/packages.txt"; then
        sefx_error 'Sony app not installed for this user; check module mounts and reboot.'; sefx_release_lock; return 3
    fi
    sync_old=$SEFX_STATE_DIR/attached.tsv
    [ -f "$sync_old" ] || : > "$sync_old"
    # AudioService's global route changes even when a track still reports deviceId 0.
    sync_route=$(awk '/^[[:space:]]*mMainType=|^[[:space:]]*mBluetoothName=/' "$SEFX_RUN/audio.txt" | cksum)
    sync_boot=$(cat "$SEFX_PROC_DIR/sys/kernel/random/boot_id" 2>/dev/null)
    sync_context="user=$SEFX_USER audio=$(pidof audioserver 2>/dev/null) sony=$(pidof "$SONY_PACKAGE" 2>/dev/null) route=$sync_route boot=$sync_boot"
    sync_before=$(cat "$SEFX_STATE_DIR/context" 2>/dev/null)
    sync_stamp=$(sefx_now); sync_last=$(cat "$SEFX_STATE_DIR/refreshed_at" 2>/dev/null)
    case "$sync_last" in ''|*[!0-9]*) sync_last=0 ;; esac
    sync_force=0
    if [ "$sync_mode" != auto ] || [ "$sync_context" != "$sync_before" ] || [ "$((sync_stamp-sync_last))" -ge "$SEFX_REFRESH" ]; then sync_force=1; fi
    sync_result=0; sync_sent=0
    : > "$SEFX_RUN/closed-packages.txt"
    while IFS='|' read -r rec_pkg rec_uid rec_pid rec_sid rec_type rec_device; do
        [ -n "$rec_pkg" ] || continue
        sefx_valid_record || continue
        [ "$((rec_uid/100000))" = "$SEFX_USER" ] || continue
        sync_old_row="$rec_pkg|$rec_uid|$rec_pid|$rec_sid|$rec_type|$rec_device"
        if [ "$sync_mode" = repair ] || [ "$sync_context" != "$sync_before" ] || ! grep -Fxq "$sync_old_row" "$SEFX_RUN/current.tsv"; then
            if ! grep -Fxq "$rec_pkg" "$SEFX_RUN/closed-packages.txt"; then
                sefx_intent CLOSE || sync_result=3
                printf '%s\n' "$rec_pkg" >> "$SEFX_RUN/closed-packages.txt"
            fi
        fi
    done < "$sync_old"
    : > "$SEFX_RUN/attached.next"
    while IFS='|' read -r rec_pkg rec_uid rec_pid rec_sid rec_type rec_device; do
        [ -n "$rec_pkg" ] || continue
        sync_row="$rec_pkg|$rec_uid|$rec_pid|$rec_sid|$rec_type|$rec_device"
        if [ "$sync_mode" = repair ] && ! grep -Fxq "$rec_pkg" "$SEFX_RUN/closed-packages.txt"; then
            sefx_intent CLOSE || sync_result=3
            printf '%s\n' "$rec_pkg" >> "$SEFX_RUN/closed-packages.txt"
        fi
        # Sony's handleCloseAudioEffect resets by PACKAGE, not just by session ID.
        # Reopen every surviving session for that package after any CLOSE.
        if [ "$sync_force" = 0 ] && ! grep -Fxq "$rec_pkg" "$SEFX_RUN/closed-packages.txt" && grep -Fxq "$sync_row" "$sync_old"; then
            printf '%s\n' "$sync_row" >> "$SEFX_RUN/attached.next"
        elif sefx_intent OPEN; then
            printf '%s\n' "$sync_row" >> "$SEFX_RUN/attached.next"; sync_sent=$((sync_sent+1))
        else sync_result=3
        fi
    done < "$SEFX_RUN/current.tsv"
    mv -f "$SEFX_RUN/attached.next" "$sync_old"
    # Store PID after broadcasts, so starting Sony does not cause a feedback loop.
    printf 'user=%s audio=%s sony=%s route=%s boot=%s\n' "$SEFX_USER" "$(pidof audioserver 2>/dev/null)" "$(pidof "$SONY_PACKAGE" 2>/dev/null)" "$sync_route" "$sync_boot" > "$SEFX_STATE_DIR/context"
    if [ "$sync_force" = 1 ] && [ "$sync_result" = 0 ]; then printf '%s\n' "$sync_stamp" > "$SEFX_STATE_DIR/refreshed_at"; fi
    [ ! -f "$SEFX_RUN/am.txt" ] || cp -f "$SEFX_RUN/am.txt" "$SEFX_STATE_DIR/last-am.txt"
    cp -f "$SEFX_RUN/current.tsv" "$SEFX_STATE_DIR/detected.tsv"
    SEFX_COUNT=$(wc -l < "$sync_old" | tr -d ' ')
    printf 'Detected %s session(s); sent %s OPEN request(s).\n' "$(wc -l < "$SEFX_RUN/current.tsv" | tr -d ' ')" "$sync_sent"
    sefx_release_lock
    [ "$sync_result" = 0 ] || return "$sync_result"
    if [ "$SEFX_COUNT" = 0 ]; then
        [ "$sync_mode" = auto ] || printf 'Play music through normal Android audio output, then retry Action.\n'
        return 4
    fi
}
sefx_panel() {
    if [ -n "$1" ]; then
        awk -F'|' -v p="$1" '$1==p {print;exit}' "$SEFX_RUN/current.tsv" > "$SEFX_RUN/panel.tsv"
    else head -n 1 "$SEFX_RUN/current.tsv" > "$SEFX_RUN/panel.tsv"
    fi
    IFS='|' read -r rec_pkg rec_uid rec_pid rec_sid rec_type rec_device < "$SEFX_RUN/panel.tsv"
    sefx_valid_record || { sefx_error 'No usable session for the panel.'; return 4; }
    if ! sefx_timeout 8 cmd activity start-activity --user "$((rec_uid/100000))" -n "$SONY_PANEL" \
        -a android.media.action.DISPLAY_AUDIO_EFFECT_CONTROL_PANEL -c android.intent.category.DEFAULT \
        --es android.media.extra.PACKAGE_NAME "$rec_pkg" --ei android.media.extra.AUDIO_SESSION "$rec_sid" \
        --ei android.media.extra.CONTENT_TYPE "$rec_type" > "$SEFX_RUN/panel.txt" 2>&1; then
        sefx_error 'Sony panel launch failed.'; return 3
    fi
    if grep -Eiq 'error:|exception|permission denial|unable to resolve' "$SEFX_RUN/panel.txt"; then
        cat "$SEFX_RUN/panel.txt" >&2; sefx_error 'Android rejected the Sony panel.'; return 3
    fi
    printf 'Panel opened for %s, session %s.\n' "$rec_pkg" "$rec_sid"
    printf 'Delivery is not proof of processing: compare flat vs a strong manual EQ cut.\n'
}
sefx_watch_pid() {
    SEFX_WATCH_PID=$(cat "$SEFX_STATE_DIR/watch.lock/pid" 2>/dev/null)
    case "$SEFX_WATCH_PID" in ''|*[!0-9]*) return 1 ;; esac
    sefx_lock_live "$SEFX_STATE_DIR/watch.lock" || return 1
    [ -r "$SEFX_PROC_DIR/$SEFX_WATCH_PID/cmdline" ] || return 1
    watch_cmd=$(tr '\000' ' ' < "$SEFX_PROC_DIR/$SEFX_WATCH_PID/cmdline")
    case "$watch_cmd" in *"$MODDIR/system/bin/sefx watch"*|*"/system/bin/sefx watch"*) return 0 ;; *) return 1 ;; esac
}
sefx_start_watch() {
    sefx_config
    [ "$SEFX_AUTO" = 1 ] || { printf 'Auto reconnect OFF.\n'; return 0; }
    sefx_watch_pid && { printf 'Auto reconnect running (PID %s).\n' "$SEFX_WATCH_PID"; return 0; }
    nohup sh "$MODDIR/system/bin/sefx" watch >/dev/null 2>&1 < /dev/null &
    printf 'Auto reconnect requested; active poll %ss.\n' "$SEFX_INTERVAL"
}
sefx_watch() {
    sefx_config; [ "$SEFX_AUTO" = 1 ] || return 0
    [ ! -L "$SEFX_STATE_DIR/watch.lock" ] || return 5
    if ! mkdir "$SEFX_STATE_DIR/watch.lock" 2>/dev/null; then
        sefx_watch_pid && return 0
        watch_owner=$(cat "$SEFX_STATE_DIR/watch.lock/pid" 2>/dev/null)
        case "$watch_owner" in
            ''|*[!0-9]*)
                watch_stamp=$(stat -c %Y "$SEFX_STATE_DIR/watch.lock" 2>/dev/null)
                case "$watch_stamp" in ''|*[!0-9]*) return 5 ;; esac
                [ "$(( $(sefx_now)-watch_stamp ))" -ge 30 ] || return 5 ;;
        esac
        sefx_lock_live "$SEFX_STATE_DIR/watch.lock" && return 5
        rm -f "$SEFX_STATE_DIR/watch.lock/pid"
        rm -f "$SEFX_STATE_DIR/watch.lock/token"
        rmdir "$SEFX_STATE_DIR/watch.lock" 2>/dev/null || return 5
        mkdir "$SEFX_STATE_DIR/watch.lock" 2>/dev/null || return 5
    fi
    printf '%s\n' "$$" > "$SEFX_STATE_DIR/watch.lock/pid"; SEFX_WATCH_HELD=1
    sefx_process_token "$$" > "$SEFX_STATE_DIR/watch.lock/token" || true
    sefx_log 'watcher started'
    while [ -d "$MODDIR" ] && [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ]; do
        sefx_config; [ "$SEFX_AUTO" = 1 ] || break
        if sefx_sync auto > "$SEFX_RUN/watch.txt" 2>&1; then watch_delay=$SEFX_INTERVAL
        else watch_delay=$SEFX_IDLE_INTERVAL
        fi
        # No wake lock: Android Doze may delay this bounded polling loop.
        sleep "$watch_delay"
    done
    sefx_log 'watcher stopped'
}
sefx_auto() {
    case "$1" in on) auto_value=1 ;; off) auto_value=0 ;; *) sefx_error 'Use: sefx auto on|off'; return 2 ;; esac
    printf 'auto=%s\ninterval=%s\nidle_interval=%s\nrefresh_interval=%s\n' "$auto_value" "$SEFX_INTERVAL" "$SEFX_IDLE_INTERVAL" "$SEFX_REFRESH" > "$SEFX_RUN/config"
    mv -f "$SEFX_RUN/config" "$SEFX_STATE_DIR/config"
    if [ "$auto_value" = 1 ]; then sefx_start_watch
    else printf 'Auto reconnect OFF; watcher exits after its current bounded poll/sleep.\n'
    fi
}
sefx_status() {
    cat "$MODDIR/module.prop"
    printf '\nSELinux: '; getenforce 2>/dev/null || true
    if sefx_watch_pid; then printf 'Watcher: running, PID %s\n' "$SEFX_WATCH_PID"; else printf 'Watcher: not running\n'; fi
    printf 'Auto=%s, active=%ss, idle=%ss, refresh=%ss\n' "$SEFX_AUTO" "$SEFX_INTERVAL" "$SEFX_IDLE_INTERVAL" "$SEFX_REFRESH"
    printf '\nLast successfully requested sessions (not processing verification):\n'
    cat "$SEFX_STATE_DIR/attached.tsv" 2>/dev/null || true
    printf '\nLive detection:\n'; sefx_collect || return $?
    cat "$SEFX_RUN/current.tsv"
}
sefx_diagnostics() {
    report_file=$SEFX_RUN/report.txt
    {
        printf 'SONY AUDIO DIAGNOSTICS - review before sharing\n'; date; sefx_status
        printf '\n--- EVENTS ---\n'; tail -n 120 "$SEFX_STATE_DIR/events.log" 2>/dev/null
        printf '\n--- LAST ANDROID INTENT ---\n'; cat "$SEFX_STATE_DIR/last-am.txt" 2>/dev/null
        printf '\n--- SONY PACKAGE ---\n'; sefx_timeout 8 dumpsys package "$SONY_PACKAGE"
        printf '\n--- APP OPS ---\n'; sefx_timeout 8 appops get "$SONY_PACKAGE"
        printf '\n--- OTHER EFFECT PANELS ---\n'; sefx_timeout 8 cmd package query-activities --brief -a android.media.action.DISPLAY_AUDIO_EFFECT_CONTROL_PANEL
        printf '\n--- BOOT INITIALIZATION ---\n'; tail -n 80 "$MODDIR/.sefx/boot.log" 2>/dev/null
        printf '\n--- AUDIO ---\n'; sefx_timeout 8 dumpsys audio
        printf '\n--- AUDIO FLINGER ---\n'; sefx_timeout 8 dumpsys media.audio_flinger
        printf '\n--- MEDIA SESSIONS ---\n'; sefx_timeout 8 dumpsys media_session
        printf '\n--- RECENT LOGCAT ---\n'; sefx_timeout 8 logcat -d -t 250
    } > "$report_file" 2>&1
    head -c 1048576 "$report_file" > "$SEFX_STATE_DIR/diagnostics.txt"
    chmod 0600 "$SEFX_STATE_DIR/diagnostics.txt"
    printf 'Report: %s/diagnostics.txt\n' "$SEFX_STATE_DIR"
    if [ "$1" = export ]; then
        sefx_current_user || return $?
        report_dir=/storage/emulated/$SEFX_USER/Download
        [ -d "$report_dir" ] || { sefx_error 'Downloads unavailable; private report remains saved.'; return 3; }
        report_target=$report_dir/SonyAudio-diagnostics-$(date +%Y%m%d-%H%M%S).txt
        cp "$SEFX_STATE_DIR/diagnostics.txt" "$report_target" || return 3
        printf 'Exported: %s\n' "$report_target"
    fi
}
