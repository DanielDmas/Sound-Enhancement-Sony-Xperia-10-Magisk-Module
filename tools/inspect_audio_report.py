#!/usr/bin/env python3
"""Read-only checks of bounded configuration snapshots from sefx doctor/report.

Checks syntax/references, not acoustic processing. Never follows paths or expands
entities from a report. No report content is executed or extracted to disk.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

MAX_REPORT=4*1024*1024
MAX_CONFIG=65536
SONY='af8da7e0-2ca1-11e3-b71d-0002a5d5c51b'
SONY_SW='50786e95-da76-4557-976b-7981bdf6feb9'
SONY_HW='f9ed8ae0-1b9c-11e4-8900-0002a5d5c51b'

def local(tag):
    return tag.rsplit('}',1)[-1] if isinstance(tag,str) else ''

def xml_check(data,require_sony=False):
    errors=[];warnings=[]
    if len(data)>MAX_CONFIG:return {'errors':['Configuration exceeds analysis limit'],'warnings':[]}
    try:text=data.decode('utf-8-sig')
    except UnicodeError:return {'errors':['Unsupported XML encoding; only UTF-8 snapshots are analyzed'],'warnings':[]}
    if '\x00' in text:return {'errors':['Unsupported XML encoding/NUL content'],'warnings':[]}
    if re.search(r'<!\s*(?:DOCTYPE|ENTITY)\b',text,re.I):
        return {'errors':['DTD/entity declarations refused'],'warnings':[]}
    try:root=ET.fromstring(text)
    except (ET.ParseError,ValueError) as exc:return {'errors':['Malformed XML: '+str(exc)],'warnings':[]}
    name=local(root.tag)
    if name=='audio_effects_conf':
        libraries={};effects={};proxies=[]
        for parent in root:
            if local(parent.tag)=='libraries':
                for item in parent:
                    if local(item.tag)!='library':continue
                    key=item.get('name','')
                    if not key or not item.get('path'):errors.append('Library lacks name/path')
                    if key in libraries:errors.append('Duplicate library: '+key)
                    libraries[key]=item.get('path','')
            if local(parent.tag)=='effects':
                for item in parent:
                    if local(item.tag) not in ('effect','effectProxy'):continue
                    key=item.get('name','')
                    if not key:errors.append('Effect lacks name')
                    if key in effects:errors.append('Duplicate effect: '+key)
                    effects[key]=item
                    if local(item.tag)=='effectProxy':proxies.append(item)
        for key,item in effects.items():
            for node in [item,*item]:
                library=node.get('library')
                if library and library not in libraries:errors.append('Missing library '+library+' for '+key)
        for node in root.iter():
            if local(node.tag)=='apply' and node.get('effect') not in effects:
                errors.append('Unresolved apply effect: '+str(node.get('effect')))
        sony=[x for x in proxies if x.get('name')=='sonyeffect' or x.get('uuid')==SONY]
        if require_sony and len(sony)!=1:errors.append('Expected one Sony effectProxy; found '+str(len(sony)))
        for item in sony:
            if item.get('uuid')!=SONY or item.get('library')!='proxy':errors.append('Unexpected Sony proxy identity/library')
            sw=[x for x in item if local(x.tag)=='libsw'];hw=[x for x in item if local(x.tag)=='libhw']
            if len(sw)!=1 or sw[0].get('uuid')!=SONY_SW or sw[0].get('library')!='sonyeffect_sw':errors.append('Invalid Sony software proxy member')
            if len(hw)!=1 or hw[0].get('uuid')!=SONY_HW or hw[0].get('library')!='sonyeffect_hw':errors.append('Invalid Sony hardware proxy member')
        if not effects:warnings.append('No effect definitions in this configuration')
    elif name=='audioPolicyConfiguration':
        for module in (x for x in root.iter() if local(x.tag)=='module'):
            endpoints=[]
            for parent in module:
                if local(parent.tag) in ('mixPorts','devicePorts'):
                    endpoints.extend(x.get('name') if local(x.tag)=='mixPort' else x.get('tagName') for x in parent)
            known=set(endpoints)
            if len(known)!=len(endpoints):errors.append('Duplicate port in module '+module.get('name','?'))
            for route in (x for x in module.iter() if local(x.tag)=='route'):
                for endpoint in [route.get('sink',''),*route.get('sources','').split(',')]:
                    if endpoint.strip() not in known:errors.append('Unknown route endpoint: '+endpoint.strip())
        if any(local(x.tag)=='include' for x in root.iter()):warnings.append('XInclude targets require separate snapshots; no external files are read')
    else:warnings.append('XML parsed, but this configuration root has no semantic checker: '+name)
    return {'root':name,'errors':sorted(set(errors)),'warnings':sorted(set(warnings))}

def conf_check(data):
    text=data.decode('utf-8','replace');depth=0;quote=False;escape=False;comment=False
    for c in text:
        if comment:
            if c=='\n':comment=False
            continue
        if escape:escape=False;continue
        if quote:
            if c=='\\':escape=True
            elif c=='"':quote=False
            continue
        if c=='#':comment=True
        elif c=='"':quote=True
        elif c=='{':depth+=1
        elif c=='}':
            depth-=1
            if depth<0:break
    errors=['Unbalanced legacy conf braces/quotes'] if depth or quote else []
    return {'errors':errors,'warnings':['Legacy conf semantic validation is incomplete']}

def inspect_report(data):
    if len(data)>MAX_REPORT:raise ValueError('Report exceeds 4 MiB limit')
    text=data.decode('utf-8','replace');lines=text.splitlines();configs=[];issues=[];i=0
    while i<len(lines):
        if lines[i].startswith('CONFIG_SNAPSHOT v1 '):
            if len(configs)>=24:issues.append('Configuration snapshot count exceeds limit');break
            fields=lines[i].split();i+=1;chunks=[]
            while i<len(lines) and lines[i]!='END_CONFIG_SNAPSHOT':
                chunks.append(lines[i]);i+=1
            if len(fields)!=7 or i>=len(lines):issues.append('Incomplete configuration snapshot');continue
            _,_,kind,path64,digest,original,included=fields
            try:
                if kind not in ('module','active'):raise ValueError('unknown snapshot kind')
                path=base64.b64decode(path64,validate=True).decode('utf-8')
                expected=int(included);size=int(original)
                if not 0<=expected<=MAX_CONFIG or size<expected:raise ValueError('invalid snapshot sizes')
                raw=base64.b64decode(''.join(chunks),validate=True)
                if len(raw)!=expected or hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('snapshot integrity mismatch')
                entry={'kind':kind,'path':path,'bytes':size,'included':expected,'sha256':digest}
                if size!=expected:entry.update(errors=['Truncated snapshot; validation skipped'],warnings=[])
                elif path.endswith('.xml'):entry.update(xml_check(raw,require_sony=kind=='module' and 'effects' in Path(path).name))
                elif path.endswith('.conf'):entry.update(conf_check(raw))
                else:entry.update(errors=[],warnings=['Unsupported configuration file type'])
                configs.append(entry)
            except (ValueError,UnicodeError) as exc:issues.append('Invalid snapshot: '+str(exc))
        i+=1
    if not configs:issues.append('No complete configuration snapshots; collect an RC3 report')
    if 'CONFIG_SNAPSHOT_LIMIT_REACHED' in text:issues.append('Some configurations were omitted by the bounded capture')
    if 'CONFIG_RECOVERY ' in text:issues.append('A retained configuration rollback backup needs attention')
    if 'UPGRADE STAGED:' in text:issues.append('A module upgrade is staged; reboot before comparing versions')
    return {'hardware_processing_verified':False,'configuration_errors':sum(len(x['errors']) for x in configs),
            'issues':issues,'configurations':configs,
            'notice':'Configuration checks and engine-dump presence do not prove audible processing.'}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('report',type=Path)
    args=parser.parse_args()
    with args.report.open('rb') as stream:data=stream.read(MAX_REPORT+1)
    try:result=inspect_report(data)
    except ValueError as exc:parser.error(str(exc))
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 1 if result['configuration_errors'] or result['issues'] else 0

if __name__=='__main__':raise SystemExit(main())
