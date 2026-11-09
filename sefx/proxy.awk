# Remove only prior Sony proxy definitions before regenerating them.
# Scoped line-oriented transformer, not a general XML validator.
function attr(text,key, rest,q,end) {
    if(!match(text,key "[[:space:]]*=[[:space:]]*[\"\047]")) return ""
    rest=substr(text,RSTART+RLENGTH-1);q=substr(rest,1,1);rest=substr(rest,2)
    end=index(rest,q);return end?substr(rest,1,end-1):""
}
function sony(text, name,uuid) {
    name=attr(text,"name");uuid=attr(text,"uuid")
    return name=="sonyeffect" || uuid=="af8da7e0-2ca1-11e3-b71d-0002a5d5c51b" ||
        (name=="removed" && attr(text,"library")=="proxy" && uuid=="removed")
}
function finish() {
    if(!sony(buffer)) printf "%s",buffer
    buffer="";inside=0
}
{
    if(!inside && $0~/<effectProxy([[:space:]]|>)/ && $0!~/^[[:space:]]*<!--/) {
        if($0!~/^[[:space:]]*<effectProxy/) exit 3
        inside=1;buffer=$0 "\n"
        if($0~/<\/effectProxy[[:space:]]*>[[:space:]]*$/ || $0~/\/[[:space:]]*>[[:space:]]*$/) finish()
        next
    }
    if(inside) {
        buffer=buffer $0 "\n"
        if($0~/<\/effectProxy[[:space:]]*>[[:space:]]*$/) finish()
        next
    }
    if($0~/^[[:space:]]*<library[[:space:]]/) {
        name=attr($0,"name");path=attr($0,"path")
        if(name=="sonyeffect_sw" || name=="sonyeffect_hw" || path=="libsonysweffect.so" || path=="libsonypostprocbundle.so" || path=="libeffectproxy.so") {
            if($0!~/\/[[:space:]]*>[[:space:]]*$/) exit 3
            next
        }
    }
    print
}
END {if(inside) exit 3}
