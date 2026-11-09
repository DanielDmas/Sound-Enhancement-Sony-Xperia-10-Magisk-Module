# Parse current Android 12L records, not historical player events.
# Inputs: package-list, process-list, dumpsys audio. Output: pkg|uid|pid|session|type|devices.
FILENAME == ARGV[1] {
    pkg=""; uid=""
    for(i=1;i<=NF;i++) {
        if($i~/^package:/) {pkg=$i;sub(/^package:/,"",pkg)}
        if($i~/^uid:[0-9]+$/) {uid=$i;sub(/^uid:/,"",uid)}
    }
    if(pkg~/^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)+$/ && uid~/^[0-9]+$/) {
        owns[uid SUBSEP pkg]=1
        if(!seenpkg[uid SUBSEP pkg]++) {count[uid]++;only[uid]=pkg}
    }
    next
}
FILENAME == ARGV[2] {
    if($1~/^[0-9]+$/) {proc=$2;sub(/^.*\//,"",proc);sub(/:.*/,"",proc);process[$1]=proc}
    next
}
FILENAME == ARGV[3] {
    if($0!~/^[ \t]*(AudioPlaybackConfiguration[ \t]+)?piid:[0-9]+[ \t]/) next
    uid="";pid="";session="";state="";device="0";usage="";content=""
    for(i=1;i<=NF;i++) {
        token=$i
        if(token~/^u\/pid:[0-9]+\/[0-9]+$/) {
            sub(/^u\/pid:/,"",token);split(token,pair,"/");uid=pair[1];pid=pair[2]
        } else if(token~/^sessionId:/) {session=token;sub(/^sessionId:/,"",session)}
        else if(token~/^deviceId:/) {device=token;sub(/^deviceId:/,"",device)}
        else if(token~/^state:/) {state=token;sub(/^state:/,"",state)}
        else if(token~/^usage=/) {usage=token;sub(/^usage=/,"",usage)}
        else if(token~/^content=/) {content=token;sub(/^content=/,"",content)}
    }
    if(uid!~/^[0-9]+$/ || pid!~/^[0-9]+$/ || state=="") {bad=1;next}
    if(state!~/^(started|paused|stopped|released|idle|unknown|0|1|2|3|4|5)$/) {bad=1;next}
    if(state!="started" && state!="2") next
    if(usage=="" || content=="") {bad=1;next}
    if(int(uid/100000)!=user || uid%100000<10000) next
    if(usage!="USAGE_MEDIA" && usage!="1" && usage!="USAGE_GAME" && usage!="14") next
    pkg=process[pid]
    if(!(uid SUBSEP pkg in owns)) {if(count[uid]!=1) {unresolved++;unknown[uid]=1;next};pkg=only[uid]}
    if(pkg==sony || pkg=="com.sonymobile.audioutil") next
    if(length(uid)>10 || uid+0>2147483647 || length(pid)>10 || pid+0>2147483647 || pid+0<1 || session!~/^[1-9][0-9]*$/ || length(session)>10 || session+0>2147483647) {unresolved++;unknown[uid]=1;next}
    if(device!~/^[0-9]+$/ || length(device)>10 || device+0>2147483647) device="0"
    # AudioEffect uses different enum values from AudioAttributes.
    type=0
    if(usage=="USAGE_GAME" || usage=="14") type=2
    else if(content=="CONTENT_TYPE_MOVIE" || content=="3") type=1
    else if(content=="CONTENT_TYPE_SPEECH" || content=="1") type=3
    key=pkg SUBSEP session
    # Stable identity when several tracks share one app/session.
    if(!(key in rows) || pid+0<rowpid[key]+0) {rows[key]=pkg "|" uid "|" pid "|" session;rowpid[key]=pid}
    if(type>rowtype[key]+0) rowtype[key]=type
    if(!devices[key SUBSEP device]++) routes[key]=routes[key] (routes[key]!=""?"+":"") device
}
END {
    if(bad) exit 3
    if(unresolved && meta!="") print unresolved > meta
    if(uncertain!="") for(uid in unknown) print uid > uncertain
    for(key in rows) {
        n=split(routes[key],route,"+")
        for(i=2;i<=n;i++) {v=route[i];j=i-1;while(j>0 && route[j]+0>v+0) {route[j+1]=route[j];j--};route[j+1]=v}
        canonical=route[1];for(i=2;i<=n;i++) canonical=canonical "+" route[i]
        print rows[key] "|" (rowtype[key]+0) "|" canonical
    }
}
