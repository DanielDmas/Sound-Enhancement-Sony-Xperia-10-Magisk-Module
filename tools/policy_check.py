#!/usr/bin/env python3
"""Check this module's explicit allow rules against its reviewed RC2 baseline.

This does not compile Android policy or assert that a grant is needed on a
phone. It rejects broadening and retains all non-untrusted-subject grants.
"""
import hashlib
import itertools
import json
from pathlib import Path
import re

UNTRUSTED={'untrusted_app','untrusted_app_29','untrusted_app_27'}

def grants(text):
    result=set()
    for line in text.splitlines():
        code=line.split('#',1)[0].strip()
        if not code:continue
        tokens=re.findall(r'\{[^}]*\}|[^\s{}]+',code)
        if len(tokens)!=5 or tokens[0]!='allow':raise ValueError('Unsupported policy statement: '+code)
        fields=[x.strip('{} ').split() for x in tokens[1:]]
        if any(not field for field in fields):raise ValueError('Empty policy set')
        if any(not re.fullmatch(r'[A-Za-z0-9_-]+',item) for field in fields for item in field):raise ValueError('Non-explicit policy token')
        result.update(itertools.product(*fields))
    return result

def fingerprint(items):
    return hashlib.sha256(json.dumps(sorted(items),separators=(',',':')).encode()).hexdigest()

def check(text,baseline):
    current=grants(text)
    untrusted={x for x in current if x[0] in UNTRUSTED}
    trusted=current-untrusted
    if untrusted:raise ValueError('Ordinary app subjects must not receive module-specific grants')
    if fingerprint(trusted)!=baseline['non_untrusted_grants_sha256']:
        raise ValueError('Policy changed outside the reviewed untrusted-subject reduction')
    return {'explicit_grants':len(current),'ordinary_app_subject_grants':0,
            'removed_grants':baseline['total_grants']-len(current),
            'non_untrusted_grants_unchanged':True}

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    print(json.dumps(check((root/'sepolicy.rule').read_text(),json.loads((root/'tools/policy_baseline.json').read_text())),indent=2))
