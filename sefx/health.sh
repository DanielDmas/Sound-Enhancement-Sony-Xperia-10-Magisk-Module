#!/system/bin/sh
# Evidence-guided repair. No native engine is called "audibly working" here.
sefx_engine_probe() {
    engine_mode=$(sefx_android getprop ro.sony.global.effect 2>/dev/null)
    case "$engine_mode" in
        true) engine_sessions=0 ;;
        false) engine_sessions=$(awk -F'|' '{print $4}' "$SEFX_RUN/current.tsv" | sort -u | tr '\n' ',') ;;
        *) printf 'unknown|Sony native mode property unavailable\n'; return ;;
    esac
    engine_pids=$(sefx_android pidof "$SONY_PACKAGE" 2>/dev/null)
    case "$engine_pids" in ''|*[!0-9\ ]*) printf 'unknown|Sony process identity unavailable\n'; return ;; esac
    # Bound both command time and stored output. Overflow or failure is unknown,
    # never evidence that the effect is missing.
    rm -f "$SEFX_RUN/engine-exit"
    (sefx_android_timeout 6 dumpsys media.audio_flinger 2>"$SEFX_RUN/engine.err"; printf '%s\n' "$?" > "$SEFX_RUN/engine-exit") | head -c 1048576 > "$SEFX_RUN/engine.txt"
    if [ "$(cat "$SEFX_RUN/engine-exit" 2>/dev/null)" != 0 ] || [ "$(wc -c < "$SEFX_RUN/engine.txt")" -ge 1048576 ]; then
        printf 'unknown|AudioFlinger capture failed or exceeded the size limit\n'; return
    fi
    awk -v pids="$engine_pids" -v sessions="$engine_sessions" -f "$MODDIR/sefx/engine.awk" "$SEFX_RUN/engine.txt"
}
sefx_engine_evidence() {
    sefx_engine_probe > "$SEFX_RUN/engine-result"
    IFS='|' read -r ENGINE_STATE ENGINE_DETAIL < "$SEFX_RUN/engine-result"
    case "$ENGINE_STATE" in ready|missing|failed|conflict|disabled|suspended|unknown) ;; *) ENGINE_STATE=unknown; ENGINE_DETAIL='Engine parser failed' ;; esac
    printf '%s|%s\n' "$ENGINE_STATE" "$ENGINE_DETAIL" > "$SEFX_RUN/engine-health.next"
    sefx_write "$SEFX_RUN/engine-health.next" "$SEFX_STATE_DIR/engine-health.txt" || return 3
}
sefx_health_decide() {
    # Returned to the sourcing manager through HEALTH_REPAIR.
    # shellcheck disable=SC2034
    HEALTH_REPAIR=0
    health_context=$1; health_before=$2; health_now=$3
    # Cached data is numeric data only. The context includes user, route, PIDs
    # and boot identity. Never carry an old failure into a changed context.
    health_key=$(printf '%s' "$health_context" | cksum | awk '{print $1}')
    health_last=0; health_bad=0; health_attempts=0; health_next=0; health_oldkey=0
    if [ -f "$SEFX_STATE_DIR/engine-recovery" ]; then
        IFS='|' read -r health_last health_bad health_attempts health_next health_oldkey < "$SEFX_STATE_DIR/engine-recovery"
    fi
    for health_number in "$health_last" "$health_bad" "$health_attempts" "$health_next" "$health_oldkey"; do
        case "$health_number" in ''|*[!0-9]*) health_oldkey=invalid ;; esac
        [ "${#health_number}" -le 10 ] || health_oldkey=invalid
        case "$health_number" in 0|[1-9]*) ;; *) health_oldkey=invalid ;; esac
    done
    if [ "$health_oldkey" != "$health_key" ] || [ "$health_context" != "$health_before" ]; then
        health_last=$health_now; health_bad=0; health_attempts=0; health_next=0
    elif [ "$health_now" -lt "$health_last" ]; then
        health_last=$health_now; health_bad=0; health_next=0
    elif [ "$((health_now-health_last))" -ge 15 ]; then
        health_last=$health_now
        sefx_engine_evidence || return 3
        sefx_log "engine=$ENGINE_STATE $ENGINE_DETAIL"
        case "$ENGINE_STATE" in
            ready) health_bad=0; health_attempts=0; health_next=0 ;;
            missing|failed)
                health_bad=$((health_bad+1)); [ "$health_bad" -le 2 ] || health_bad=2
                if [ "$health_bad" -ge 2 ] && [ "$health_attempts" -lt 3 ] && [ "$health_now" -ge "$health_next" ]; then
                    # shellcheck disable=SC2034
                    HEALTH_REPAIR=1; health_attempts=$((health_attempts+1)); health_bad=0
                    health_wait=$((60*health_attempts)); health_next=$((health_now+health_wait))
                    sefx_log "engine repair requested attempt=$health_attempts; next eligible in ${health_wait}s"
                fi ;;
            *) health_bad=0 ;; # Never treat unavailable evidence or user OFF as failure.
        esac
    fi
    printf '%s|%s|%s|%s|%s\n' "$health_last" "$health_bad" "$health_attempts" "$health_next" "$health_key" > "$SEFX_RUN/engine-recovery.next"
    sefx_write "$SEFX_RUN/engine-recovery.next" "$SEFX_STATE_DIR/engine-recovery"
}
sefx_health() {
    sefx_ready || return $?
    sefx_acquire_lock || return 5
    sefx_collect; health_result=$?
    if [ "$health_result" = 0 ]; then
        sefx_engine_evidence; health_result=$?
        printf 'Native evidence: %s. %s\n' "$ENGINE_STATE" "$ENGINE_DETAIL"
    fi
    sefx_release_lock
    return "$health_result"
}
