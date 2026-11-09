#!/system/bin/sh
# Lifecycle management for the supplied Sony APK; not an audio-processing meter.
SONY_PACKAGE=com.sonyericsson.soundenhancement
SONY_RECEIVER=$SONY_PACKAGE/.AudioEffectControlReceiver
SONY_PANEL=$SONY_PACKAGE/.SoundEnhancementRedirector
SEFX_RUNTIME_VERSION=v2.0.0-rc.2
SEFX_STATE_DIR=${SEFX_STATE_DIR:-/data/adb/sony-audio-manager}
SEFX_PROC_DIR=${SEFX_PROC_DIR:-/proc}
SEFX_LOCK_HELD=0
SEFX_WATCH_HELD=0
umask 077

sefx_now() { date +%s; }
sefx_tick() {
    { read -r tick_value _tick_unused < "$SEFX_PROC_DIR/uptime"; } 2>/dev/null || tick_value=
    tick_value=${tick_value%%.*}
    case "$tick_value" in ''|*[!0-9]*) sefx_now ;; *) printf '%s\n' "$tick_value" ;; esac
}
sefx_android_path() {
    if [ -n "${SEFX_ANDROID_BIN:-}" ]; then printf '%s/%s\n' "$SEFX_ANDROID_BIN" "$1"
    elif [ -x "/system/bin/$1" ]; then printf '/system/bin/%s\n' "$1"
    else command -v "$1"
    fi
}
sefx_android() { android_cmd=$(sefx_android_path "$1") || return 127; shift; "$android_cmd" "$@" 7>&- 8>&- 9>&-; }
sefx_android_timeout() { android_limit=$1; shift; android_cmd=$(sefx_android_path "$1") || return 127; shift; sefx_timeout "$android_limit" "$android_cmd" "$@"; }
sefx_write() {
    [ ! -L "$2" ] && [ ! -d "$2" ] && mv -f "$1" "$2"
}
sefx_ready() {
    if [ -f "$MODDIR/update" ]; then sefx_error 'Upgrade staged: reboot normally before using the module.'; return 6; fi
    if [ -f "$MODDIR/disable" ] || [ -f "$MODDIR/remove" ]; then sefx_error 'Module disabled/pending removal; reboot after enabling.'; return 3; fi
}
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
    for state_file in config events.log events.previous.log attached.tsv context refreshed_at detected.tsv last-am.txt diagnostics.txt attach.flock watch.flock watch.pid watch.token heartbeat daemon.flock daemon.pid daemon.token daemon.log last-poll.txt; do
        if [ -L "$SEFX_STATE_DIR/$state_file" ] || [ -d "$SEFX_STATE_DIR/$state_file" ]; then
            printf 'Refusing unsafe state file: %s\n' "$state_file" >&2; return 3
        fi
    done
    SEFX_RUN=$(mktemp -d "$SEFX_STATE_DIR/run.XXXXXXXX") || return 3
    if [ ! -f "$SEFX_STATE_DIR/config" ] && [ "$SEFX_STATE_DIR" != "$MODDIR/.sefx" ] && [ -f "$MODDIR/.sefx/config" ] && [ ! -L "$MODDIR/.sefx/config" ]; then
        cp "$MODDIR/.sefx/config" "$SEFX_RUN/config" && sefx_write "$SEFX_RUN/config" "$SEFX_STATE_DIR/config" || return 3
    fi
    SEFX_AUTO=1; SEFX_INTERVAL=5; SEFX_IDLE_INTERVAL=10; SEFX_REFRESH=60
    sefx_config
}
sefx_config() {
    # Configuration is data and is never sourced as shell code.
    [ -f "$SEFX_STATE_DIR/config" ] || return 0
    while IFS='=' read -r cfg_key cfg_value || [ -n "$cfg_key$cfg_value" ]; do
        case "$cfg_value" in ''|*[!0-9]*) continue ;; esac
        [ "${#cfg_value}" -le 3 ] || continue
        case "$cfg_value" in 0|[1-9]|[1-9][0-9]|[1-9][0-9][0-9]) ;; *) continue ;; esac
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
    if command -v timeout >/dev/null 2>&1; then timeout -s KILL "$sefx_limit" "$@" 7>&- 8>&- 9>&-
    elif [ -x /data/adb/magisk/busybox ]; then /data/adb/magisk/busybox timeout -s KILL "$sefx_limit" "$@" 7>&- 8>&- 9>&-
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
    sefx_lock=$SEFX_STATE_DIR/attach.flock
    [ ! -L "$sefx_lock" ] || return 1
    exec 9>"$sefx_lock" || return 1
    flock -n 9 || { exec 9>&-; return 1; }
    SEFX_LOCK_HELD=1
}
sefx_release_lock() {
    if [ "$SEFX_LOCK_HELD" = 1 ]; then
        flock -u 9
        exec 9>&-
        SEFX_LOCK_HELD=0
    fi
}
sefx_cleanup() {
    sefx_release_lock
    if [ "$SEFX_WATCH_HELD" = 1 ]; then
        rm -f "$SEFX_STATE_DIR/watch.pid" "$SEFX_STATE_DIR/watch.token" "$SEFX_STATE_DIR/heartbeat"
        flock -u 8
        exec 8>&-
    fi
    if [ -n "$SEFX_RUN" ] && [ -d "$SEFX_RUN" ] && [ ! -L "$SEFX_RUN" ]; then
        rm -f "$SEFX_RUN"/*
        rmdir "$SEFX_RUN" 2>/dev/null || true
    fi
}
sefx_current_user() {
    SEFX_USER=$(sefx_android_timeout 6 cmd activity get-current-user 2>/dev/null)
    case "$SEFX_USER" in ''|*[!0-9]*) sefx_error 'Cannot identify the foreground Android user.'; return 3 ;; esac
    [ "${#SEFX_USER}" -le 5 ] && [ "$SEFX_USER" -le 21474 ] || return 3
}
sefx_collect() {
    sefx_current_user || return $?
    if ! sefx_android_timeout 8 dumpsys audio > "$SEFX_RUN/audio.txt" 2> "$SEFX_RUN/audio.err"; then
        sefx_error 'Audio dump failed/timed out; preserving previous state.'; return 3
    fi
    if ! grep -Eq '^[[:space:]]*players:' "$SEFX_RUN/audio.txt"; then
        sefx_error 'Unknown/empty audio dump: no sessions will be guessed or closed.'; return 3
    fi
    if ! sefx_android_timeout 8 cmd package list packages -U --user "$SEFX_USER" > "$SEFX_RUN/packages.txt" 2> "$SEFX_RUN/packages.err"; then
        sefx_error 'Could not read package ownership.'; return 3
    fi
    grep -q '^package:.* uid:[0-9]' "$SEFX_RUN/packages.txt" || { sefx_error 'Unsupported package ownership output.'; return 3; }
    sefx_android_timeout 6 ps -A -o PID,NAME > "$SEFX_RUN/processes.txt" 2>/dev/null || : > "$SEFX_RUN/processes.txt"
    : > "$SEFX_RUN/unresolved" || return 3
    if ! awk -v user="$SEFX_USER" -v sony="$SONY_PACKAGE" -v meta="$SEFX_RUN/unresolved" -f "$MODDIR/sefx/sessions.awk" \
        "$SEFX_RUN/packages.txt" "$SEFX_RUN/processes.txt" "$SEFX_RUN/audio.txt" > "$SEFX_RUN/parsed.tsv"; then
        sefx_error 'Session parser failed.'; return 3
    fi
    LC_ALL=C sort -u "$SEFX_RUN/parsed.tsv" > "$SEFX_RUN/current.tsv" || return 3
    if [ -s "$SEFX_RUN/unresolved" ]; then
        printf 'Active media has an unresolved session/owner; preserving previous attachments. No global-session fallback is guessed.\n'
        return 4
    fi
}
sefx_valid_record() {
    printf '%s\n' "$rec_pkg" | grep -Eq '^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$' || return 1
    for rec_num in "$rec_uid" "$rec_pid" "$rec_sid" "$rec_type"; do
        case "$rec_num" in ''|*[!0-9]*) return 1 ;; esac
        [ "${#rec_num}" -le 10 ] && [ "$rec_num" -le 2147483647 ] || return 1
        case "$rec_num" in 0|[1-9]*) ;; *) return 1 ;; esac
    done
    [ "${#rec_device}" -le 255 ] || return 1
    printf '%s\n' "$rec_device" | grep -Eq '^[0-9]+(\+[0-9]+)*$' || return 1
    [ "$rec_uid" -gt 0 ] && [ "$rec_pid" -gt 0 ] && [ "$rec_sid" -gt 0 ] && [ "$rec_type" -le 3 ]
}
sefx_intent() {
    intent_action=$1
    sefx_valid_record || { sefx_error 'Invalid cached session rejected.'; return 3; }
    intent_user=$((rec_uid/100000))
    if ! sefx_android_timeout 8 cmd activity broadcast --user "$intent_user" --include-stopped-packages \
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
    sefx_ready || return $?
    sefx_acquire_lock || { sefx_error 'Another refresh is running; retry shortly.'; return 5; }
    sefx_collect; sync_result=$?
    if [ "$sync_result" != 0 ]; then sefx_release_lock; return "$sync_result"; fi
    if ! awk -v p="package:$SONY_PACKAGE" '$1==p {found=1} END {exit !found}' "$SEFX_RUN/packages.txt"; then
        sefx_error 'Sony app not installed for this user; check module mounts and reboot.'; sefx_release_lock; return 3
    fi
    sync_old=$SEFX_STATE_DIR/attached.tsv
    [ -f "$sync_old" ] || { : > "$SEFX_RUN/empty" && sefx_write "$SEFX_RUN/empty" "$sync_old"; } || { sefx_release_lock; return 3; }
    sync_route=$(awk '/^[[:space:]]*mMainType=|^[[:space:]]*mBluetoothName=/' "$SEFX_RUN/audio.txt" | cksum)
    sync_boot=$(cat "$SEFX_PROC_DIR/sys/kernel/random/boot_id" 2>/dev/null)
    sync_audio=$(sefx_android pidof audioserver 2>/dev/null)
    sync_sony=$(sefx_android pidof "$SONY_PACKAGE" 2>/dev/null)
    sync_context="user=$SEFX_USER audio=$sync_audio sony=$sync_sony route=$sync_route boot=$sync_boot"
    sync_before=$(cat "$SEFX_STATE_DIR/context" 2>/dev/null)
    sync_stamp=$(sefx_tick); sync_last=$(cat "$SEFX_STATE_DIR/refreshed_at" 2>/dev/null)
    case "$sync_last" in ''|*[!0-9]*) sync_last=0 ;; esac
    [ "${#sync_last}" -le 10 ] || sync_last=0
    case "$sync_last" in 0|[1-9]*) ;; *) sync_last=0 ;; esac
    sync_force=0
    if [ "$sync_mode" != auto ] || [ "$sync_context" != "$sync_before" ] || [ "$sync_stamp" -lt "$sync_last" ] || [ "$((sync_stamp-sync_last))" -ge "$SEFX_REFRESH" ]; then sync_force=1; fi
    sync_result=0; sync_sent=0
    : > "$SEFX_RUN/closed-packages.txt"
    : > "$SEFX_RUN/failed-packages.txt"
    : > "$SEFX_RUN/attached.next"
    while IFS='|' read -r rec_pkg rec_uid rec_pid rec_sid rec_type rec_device; do
        [ -n "$rec_pkg" ] || continue
        sefx_valid_record || continue
        [ "$((rec_uid/100000))" = "$SEFX_USER" ] || continue
        sync_old_row="$rec_pkg|$rec_uid|$rec_pid|$rec_sid|$rec_type|$rec_device"
        if [ "$sync_mode" = repair ] || [ "$sync_context" != "$sync_before" ] || ! grep -Fxq "$sync_old_row" "$SEFX_RUN/current.tsv"; then
            if ! grep -Fxq "$rec_pkg" "$SEFX_RUN/closed-packages.txt" && ! grep -Fxq "$rec_pkg" "$SEFX_RUN/failed-packages.txt"; then
                if sefx_intent CLOSE; then printf '%s\n' "$rec_pkg" >> "$SEFX_RUN/closed-packages.txt"
                else sync_result=3; printf '%s\n' "$rec_pkg" >> "$SEFX_RUN/failed-packages.txt"
                fi
            fi
            if grep -Fxq "$rec_pkg" "$SEFX_RUN/failed-packages.txt"; then printf '%s\n' "$sync_old_row" >> "$SEFX_RUN/attached.next"; fi
        fi
    done < "$sync_old"
    while IFS='|' read -r rec_pkg rec_uid rec_pid rec_sid rec_type rec_device; do
        [ -n "$rec_pkg" ] || continue
        sync_row="$rec_pkg|$rec_uid|$rec_pid|$rec_sid|$rec_type|$rec_device"
        if grep -Fxq "$rec_pkg" "$SEFX_RUN/failed-packages.txt"; then continue; fi
        if [ "$sync_mode" = repair ] && ! grep -Fxq "$rec_pkg" "$SEFX_RUN/closed-packages.txt"; then
            if sefx_intent CLOSE; then printf '%s\n' "$rec_pkg" >> "$SEFX_RUN/closed-packages.txt"
            else sync_result=3; printf '%s\n' "$rec_pkg" >> "$SEFX_RUN/failed-packages.txt"; printf '%s\n' "$sync_row" >> "$SEFX_RUN/attached.next"; continue
            fi
        fi
        # Sony CLOSE resets by package: every surviving session must reopen.
        if [ "$sync_force" = 0 ] && ! grep -Fxq "$rec_pkg" "$SEFX_RUN/closed-packages.txt" && grep -Fxq "$sync_row" "$sync_old"; then
            printf '%s\n' "$sync_row" >> "$SEFX_RUN/attached.next"
        elif sefx_intent OPEN; then
            printf '%s\n' "$sync_row" >> "$SEFX_RUN/attached.next"; sync_sent=$((sync_sent+1))
        else sync_result=3
        fi
    done < "$SEFX_RUN/current.tsv"
    if ! sefx_write "$SEFX_RUN/attached.next" "$sync_old"; then
        sefx_error 'Cannot commit attachment state.'; sefx_release_lock; return 3
    fi
    # Preserve pre-dispatch context: restarts during delivery stay observable.
    if [ "$sync_result" = 0 ]; then printf '%s\n' "$sync_context" > "$SEFX_RUN/context"
    else printf 'recovery_pending\n' > "$SEFX_RUN/context"
    fi
    sefx_write "$SEFX_RUN/context" "$SEFX_STATE_DIR/context" || sync_result=3
    if [ "$sync_force" = 1 ] && [ "$sync_result" = 0 ]; then
        printf '%s\n' "$sync_stamp" > "$SEFX_RUN/refreshed_at"
        sefx_write "$SEFX_RUN/refreshed_at" "$SEFX_STATE_DIR/refreshed_at" || sync_result=3
    fi
    [ ! -f "$SEFX_RUN/am.txt" ] || { cp -f "$SEFX_RUN/am.txt" "$SEFX_RUN/last-am.txt" && sefx_write "$SEFX_RUN/last-am.txt" "$SEFX_STATE_DIR/last-am.txt"; } || sync_result=3
    cp -f "$SEFX_RUN/current.tsv" "$SEFX_RUN/detected.tsv" && sefx_write "$SEFX_RUN/detected.tsv" "$SEFX_STATE_DIR/detected.tsv" || sync_result=3
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
    if ! sefx_android_timeout 8 cmd activity start-activity --user "$((rec_uid/100000))" -n "$SONY_PANEL" \
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
    SEFX_WATCH_PID=$(cat "$SEFX_STATE_DIR/watch.pid" 2>/dev/null)
    case "$SEFX_WATCH_PID" in ''|*[!0-9]*) return 1 ;; esac
    [ "${#SEFX_WATCH_PID}" -le 10 ] && [ "$SEFX_WATCH_PID" -gt 0 ] || return 1
    kill -0 "$SEFX_WATCH_PID" 2>/dev/null || return 1
    watch_token=$(sefx_process_token "$SEFX_WATCH_PID")
    [ -n "$watch_token" ] && [ "$(cat "$SEFX_STATE_DIR/watch.token" 2>/dev/null)" = "$watch_token" ] || return 1
    [ -r "$SEFX_PROC_DIR/$SEFX_WATCH_PID/cmdline" ] || return 1
    watch_cmd=$(tr '\000' ' ' < "$SEFX_PROC_DIR/$SEFX_WATCH_PID/cmdline")
    case "$watch_cmd" in *"$MODDIR/system/bin/sefx watch"*|*"/system/bin/sefx watch"*) return 0 ;; *) return 1 ;; esac
}
sefx_daemon_pid() {
    daemon_pid=$(cat "$SEFX_STATE_DIR/daemon.pid" 2>/dev/null)
    case "$daemon_pid" in ''|*[!0-9]*) return 1 ;; esac
    [ "${#daemon_pid}" -le 10 ] && [ "$daemon_pid" -gt 0 ] || return 1
    kill -0 "$daemon_pid" 2>/dev/null || return 1
    daemon_token=$(sefx_process_token "$daemon_pid")
    [ -n "$daemon_token" ] && [ "$(cat "$SEFX_STATE_DIR/daemon.token" 2>/dev/null)" = "$daemon_token" ] || return 1
    daemon_cmd=$(tr '\000' ' ' < "$SEFX_PROC_DIR/$daemon_pid/cmdline" 2>/dev/null)
    case "$daemon_cmd" in *"$MODDIR/system/bin/sefx daemon"*|*"/system/bin/sefx daemon"*) return 0 ;; *) return 1 ;; esac
}
sefx_start_watch() {
    sefx_config
    [ "$SEFX_AUTO" = 1 ] || { printf 'Auto reconnect OFF.\n'; return 0; }
    sefx_ready || return $?
    sefx_daemon_pid && { printf 'Auto reconnect supervisor running (PID %s).\n' "$daemon_pid"; return 0; }
    [ ! -f "$SEFX_STATE_DIR/daemon.log" ] || [ "$(wc -c < "$SEFX_STATE_DIR/daemon.log")" -le 65536 ] || : > "$SEFX_STATE_DIR/daemon.log"
    nohup sh "$MODDIR/system/bin/sefx" daemon >>"$SEFX_STATE_DIR/daemon.log" 2>&1 < /dev/null 8>&- 9>&- &
    printf 'Auto reconnect requested; active poll %ss. Use sefx status to confirm startup.\n' "$SEFX_INTERVAL"
}
sefx_watch() {
    sefx_ready || return $?
    sefx_config; [ "$SEFX_AUTO" = 1 ] || return 0
    exec 8>"$SEFX_STATE_DIR/watch.flock" || return 3
    flock -n 8 || { exec 8>&-; return 5; }
    SEFX_WATCH_HELD=1
    printf '%s\n' "$$" > "$SEFX_STATE_DIR/watch.pid"
    sefx_process_token "$$" > "$SEFX_STATE_DIR/watch.token" || true
    sefx_log 'watcher started'
    while [ -d "$MODDIR" ] && [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ] && [ ! -f "$MODDIR/update" ]; do
        sefx_config; [ "$SEFX_AUTO" = 1 ] || break
        if sefx_sync auto > "$SEFX_RUN/watch.txt" 2>&1; then watch_delay=$SEFX_INTERVAL
        else
            watch_delay=$SEFX_IDLE_INTERVAL
            head -c 16384 "$SEFX_RUN/watch.txt" > "$SEFX_RUN/last-poll.txt"
            sefx_write "$SEFX_RUN/last-poll.txt" "$SEFX_STATE_DIR/last-poll.txt" || return 3
        fi
        printf '%s\n' "$(sefx_tick)" > "$SEFX_RUN/heartbeat"
        sefx_write "$SEFX_RUN/heartbeat" "$SEFX_STATE_DIR/heartbeat" || return 3
        # No wake lock: Android Doze may delay polling.
        sleep "$watch_delay"
    done
    sefx_log 'watcher stopped'
}
sefx_daemon() {
    sefx_ready || return $?
    exec 7>"$SEFX_STATE_DIR/daemon.flock" || return 3
    flock -n 7 || { exec 7>&-; return 5; }
    printf '%s\n' "$$" > "$SEFX_STATE_DIR/daemon.pid"
    sefx_process_token "$$" > "$SEFX_STATE_DIR/daemon.token" || true
    sefx_log 'supervisor started'
    while [ -d "$MODDIR" ] && [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ] && [ ! -f "$MODDIR/update" ]; do
        sefx_config; [ "$SEFX_AUTO" = 1 ] || break
        # The child must not retain the supervisor lock after its parent's death.
        (exec 7>&-; exec sh "$MODDIR/system/bin/sefx" watch) > "$SEFX_RUN/worker.log" 2>&1 &
        daemon_child=$!
        wait "$daemon_child"; daemon_result=$?; daemon_child=
        sefx_log "watcher exited status=$daemon_result"
        sefx_config; [ "$SEFX_AUTO" = 1 ] || break
        sleep 5
    done
    rm -f "$SEFX_STATE_DIR/daemon.pid" "$SEFX_STATE_DIR/daemon.token"
    flock -u 7; exec 7>&-
    sefx_log 'supervisor stopped'
}
sefx_auto() {
    case "$1" in on) auto_value=1 ;; off) auto_value=0 ;; *) sefx_error 'Use: sefx auto on|off'; return 2 ;; esac
    printf 'auto=%s\ninterval=%s\nidle_interval=%s\nrefresh_interval=%s\n' "$auto_value" "$SEFX_INTERVAL" "$SEFX_IDLE_INTERVAL" "$SEFX_REFRESH" > "$SEFX_RUN/config"
    sefx_write "$SEFX_RUN/config" "$SEFX_STATE_DIR/config" || { sefx_error 'Cannot save auto reconnect preference.'; return 3; }
    if [ "$auto_value" = 1 ]; then sefx_start_watch
    else printf 'Auto reconnect OFF; watcher exits after its current bounded poll/sleep.\n'
    fi
}
sefx_status() {
    printf 'Runtime: %s\nDisplayed module metadata:\n' "$SEFX_RUNTIME_VERSION"
    cat "$MODDIR/module.prop"
    [ ! -f "$MODDIR/update" ] || printf '\nUPGRADE STAGED: reboot required.\n'
    printf '\nSELinux: '; sefx_android getenforce 2>/dev/null || true
    if sefx_daemon_pid; then printf 'Supervisor: running, PID %s\n' "$daemon_pid"; else printf 'Supervisor: not running\n'; fi
    if sefx_watch_pid; then printf 'Watcher: running, PID %s\n' "$SEFX_WATCH_PID"; else printf 'Watcher: not running\n'; fi
    if [ -f "$SEFX_STATE_DIR/heartbeat" ]; then printf 'Last poll uptime: '; cat "$SEFX_STATE_DIR/heartbeat"; fi
    printf 'Auto=%s, active=%ss, idle=%ss, refresh=%ss\n' "$SEFX_AUTO" "$SEFX_INTERVAL" "$SEFX_IDLE_INTERVAL" "$SEFX_REFRESH"
    printf '\nLast successfully requested sessions (not processing verification):\n'
    cat "$SEFX_STATE_DIR/attached.tsv" 2>/dev/null || true
    printf '\nLive detection:\n'; sefx_collect || return $?
    cat "$SEFX_RUN/current.tsv"
}
sefx_report_section() {
    report_heading=$1; shift
    printf '\n--- %s ---\n' "$report_heading"
    rm -f "$SEFX_RUN/report-status"
    (sefx_android_timeout 8 "$@"; printf '%s\n' "$?" > "$SEFX_RUN/report-status") 2>&1 | head -c 65536
    printf '\n[exit=%s; section limit=65536 bytes]\n' "$(cat "$SEFX_RUN/report-status" 2>/dev/null)"
}
sefx_diagnostics() {
    report_file=$SEFX_RUN/report.txt
    {
        printf 'SONY AUDIO DIAGNOSTICS - review before sharing\n'; date; sefx_status
        printf '\n--- EVENTS ---\n'; tail -n 120 "$SEFX_STATE_DIR/events.log" 2>/dev/null
        printf '\n--- LAST ANDROID INTENT ---\n'; cat "$SEFX_STATE_DIR/last-am.txt" 2>/dev/null
        sefx_report_section 'SONY PACKAGE' dumpsys package "$SONY_PACKAGE"
        sefx_report_section 'APP OPS' appops get --user "$SEFX_USER" "$SONY_PACKAGE"
        sefx_report_section 'OTHER EFFECT PANELS' cmd package query-activities --brief -a android.media.action.DISPLAY_AUDIO_EFFECT_CONTROL_PANEL
        printf '\n--- BOOT INITIALIZATION ---\n'; tail -n 80 "$MODDIR/.sefx/boot.log" 2>/dev/null
        printf '\n--- SUPERVISOR OUTPUT ---\n'; tail -c 16384 "$SEFX_STATE_DIR/daemon.log" 2>/dev/null
        printf '\n--- LAST UNSUCCESSFUL/IDLE POLL ---\n'; cat "$SEFX_STATE_DIR/last-poll.txt" 2>/dev/null
        sefx_report_section AUDIO dumpsys audio
        sefx_report_section 'AUDIO FLINGER' dumpsys media.audio_flinger
        sefx_report_section 'MEDIA SESSIONS' dumpsys media_session
        sefx_report_section 'RECENT LOGCAT' logcat -d -t 250
    } > "$report_file" 2>&1
    head -c 1048576 "$report_file" > "$SEFX_RUN/diagnostics.txt" && sefx_write "$SEFX_RUN/diagnostics.txt" "$SEFX_STATE_DIR/diagnostics.txt" || return 3
    chmod 0600 "$SEFX_STATE_DIR/diagnostics.txt"
    printf 'Report: %s/diagnostics.txt\n' "$SEFX_STATE_DIR"
    if [ "$1" = export ]; then
        sefx_current_user || return $?
        report_dir=/storage/emulated/$SEFX_USER/Download
        [ -d "$report_dir" ] || { sefx_error 'Downloads unavailable; private report remains saved.'; return 3; }
        report_target=$report_dir/SonyAudio-diagnostics-$(date +%Y%m%d-%H%M%S).txt
        cp "$SEFX_STATE_DIR/diagnostics.txt" "$report_target" || return 3
        chmod 0644 "$report_target" || return 3
        printf 'Exported: %s\n' "$report_target"
    fi
}
