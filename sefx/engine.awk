# Android 12L EffectBase/EffectModule::dump. Deliberately conservative:
# only exact Sony implementation UUIDs and complete framework records count.
# Output: evidence|explanation. This does not measure processed audio samples.
function finish(    ok) {
    if (!in_effect) return
    if (!summary || !uuid_seen || !status_seen || !clients_seen || handles != clients || broken) { uncertain=1; return }
    if (!sony || !(session in wanted)) return
    seen[session]=1
    if (enabled == "n") { disabled=1; return }
    if (suspended == "y") { suspended_any=1; return }
    if (status != 0) { failed=1; return }
    if (owner) good[session]=1
    else if (other_owner) conflict=1
    else uncertain=1
}
function reset() {
    sony=uuid_seen=summary=status_seen=clients_seen=handles=owner=other_owner=broken=0
    clients=0; session=-999; enabled=""; suspended=""; pending=""
}
BEGIN {
    n=split(sessions, ids, ","); for (i=1;i<=n;i++) if (ids[i] ~ /^[0-9]+$/) wanted[ids[i]+0]=1
    reset()
}
/Could not lock|[Tt]imed out|[Pp]ermission [Dd]enial|[Ff]ailed to dump/ { incomplete=1 }
/^[[:space:]]*Output thread / { output_seen=1 }
/^[[:space:]]*[0-9]+ Effect Chains[[:space:]]*$/ { chains_seen=1; declared_chains+=$1 }
/^[[:space:]]*[0-9]+ effects for session -?[0-9]+[[:space:]]*$/ { parsed_chains++; declared_effects+=$1 }
/^[[:space:]]*Effect ID [0-9]+:/ { finish(); reset(); in_effect=1; parsed_effects++; next }
/^[[:space:]]*Effect ID [0-9]+ HAL dump:/ { finish(); reset(); in_effect=0; next }
!in_effect { next }
/^[[:space:]]*Session State Registered Enabled Suspended:/ { pending="summary"; next }
pending=="summary" {
    if (NF==5 && $1 ~ /^[0-9]+$/ && $2 ~ /^[0-9]+$/ && $3 ~ /^[yn]$/ && $4 ~ /^[yn]$/ && $5 ~ /^[yn]$/) {
        session=$1+0; enabled=$4; suspended=$5; summary=1
    } else broken=1
    pending=""; next
}
/^[[:space:]]*- UUID:/ {
    uuid=tolower($3)
    uuid_seen=(uuid ~ /^[0-9a-f-]+$/ && length(uuid)==36)
    sony=(uuid=="af8da7e0-2ca1-11e3-b71d-0002a5d5c51b" || uuid=="50786e95-da76-4557-976b-7981bdf6feb9" || uuid=="f9ed8ae0-1b9c-11e4-8900-0002a5d5c51b")
    next
}
/^[[:space:]]*[0-9]+ Clients:/ { clients=$1+0; clients_seen=1; next }
/^[[:space:]]*Pid Priority Ctrl Locked client server/ { pending="handles"; next }
pending=="handles" && NF==6 && $1 ~ /^[0-9]+$/ && $2 ~ /^-?[0-9]+$/ && $3 ~ /^(yes|no)$/ && $4 ~ /^(yes|no)$/ && $5 ~ /^[0-9]+$/ && $6 ~ /^[0-9]+$/ {
    handles++
    if ($3=="yes") {
        if (index(" " pids " ", " " ($1+0) " ")) owner=1
        else other_owner=1
    }
    next
}
/^[[:space:]]*Status Engine:/ { pending="status"; next }
pending=="status" {
    if (NF==2 && $1 ~ /^-?[0-9]+$/ && $2 ~ /^(0x[0-9a-fA-F]+|\(nil\))$/) { status=$1+0; status_seen=1 }
    else broken=1
    pending=""; next
}
END {
    finish(); total=0; ready=0; absent=0
    for (sid in wanted) { total++; if (good[sid]) ready++; if (!seen[sid]) absent++ }
    if (incomplete || !output_seen || !chains_seen || declared_chains!=parsed_chains || declared_effects!=parsed_effects || !total || uncertain) print "unknown|Incomplete or unsupported AudioFlinger evidence; no automatic repair"
    else if (ready==total) print "ready|Sony engine present, enabled and controlled by Sony; audibility unverified"
    else if (conflict) print "conflict|Another process controls the Sony engine; automatic takeover suppressed"
    else if (disabled) print "disabled|Sony effect disabled; preserving the user's effect setting"
    else if (suspended_any) print "suspended|Framework suspended the effect; automatic takeover suppressed"
    else if (failed) print "failed|Sony native engine reports an initialization error"
    else if (absent) print "missing|Sony engine absent from expected native session(s)"
    else print "unknown|Sony control ownership could not be established"
}
