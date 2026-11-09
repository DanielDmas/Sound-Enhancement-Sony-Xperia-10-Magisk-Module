#!/usr/bin/env python3
"""Patch pinned Yoshino/Flamefire source configs twice and check their structure.

Source snapshots are not a dump of the user's installed ROM. They qualify the
published source format; device acceptance still requires the real phone.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from inspect_audio_report import xml_check,local

ROOT=Path(__file__).resolve().parents[1]

def effects(data):
    root=ET.fromstring(data)
    return {x.get('name'):(local(x.tag),tuple(sorted(x.attrib.items())),tuple((local(c.tag),tuple(sorted(c.attrib.items()))) for c in x))
            for parent in root if local(parent.tag)=='effects' for x in parent if x.get('name')!='sonyeffect'}

def routes(data):
    return [(local(x.tag),tuple(sorted(x.attrib.items()))) for x in ET.fromstring(data).iter()
            if local(x.tag) in ('route','mixPort','devicePort')]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--fixture-dir',type=Path)
    args=parser.parse_args();source={}
    for item in json.loads((ROOT/'tools/upstream_fixtures.json').read_text()):
        if args.fixture_dir:data=(args.fixture_dir/item['name']).read_bytes()
        else:
            url='https://raw.githubusercontent.com/'+item['repository']+'/'+item['commit']+'/'+item['path']
            with urllib.request.urlopen(url,timeout=30) as response:data=response.read(65537)
        if hashlib.sha256(data).hexdigest()!=item['sha256']:raise ValueError('Source integrity failure: '+item['name'])
        before=xml_check(data,require_sony='effects' in item['name'])
        if before['errors']:raise ValueError('Invalid source fixture: '+repr(before))
        source[item['name']]=data
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary);(root/'system/vendor/etc').mkdir(parents=True);(root/'sefx').mkdir()
        lib=root/'system/vendor/lib/soundfx/libsonysweffect.so';lib.parent.mkdir(parents=True);lib.touch()
        shutil.copyfile(ROOT/'sefx/proxy.awk',root/'sefx/proxy.awk')
        script=root/'.aml.sh';script.write_text((ROOT/'aml.sh').read_text().replace('#hsound_enhancement','sound_enhancement'))
        for name,data in source.items():(root/'system/vendor/etc'/name).write_bytes(data)
        env={**os.environ,'MODPATH':str(root),'MODSYSTEM':'/system'}
        shell=[os.environ['SEFX_BUSYBOX'],'sh'] if os.environ.get('SEFX_BUSYBOX') else ['sh']
        if os.environ.get('SEFX_BUSYBOX'):env['ASH_STANDALONE']='1'
        first={}
        for iteration in range(2):
            subprocess.run([*shell,str(script)],env=env,cwd=root,check=True,capture_output=True,timeout=30)
            for name,data in source.items():
                patched=(root/'system/vendor/etc'/name).read_bytes()
                result=xml_check(patched,require_sony='effects' in name)
                if result['errors']:raise ValueError(name+': '+repr(result['errors']))
                if 'effects' in name:
                    if effects(data)!=effects(patched):raise ValueError('An unrelated effect definition changed')
                else:
                    # The inherited port intentionally excludes compressed-offload
                    # routes. Preserve every other route/endpoint exactly.
                    before=routes(data);after=routes(patched)
                    normalized=lambda rows:[(t,tuple((k,v) for k,v in a if k!='flags')) for t,a in rows]
                    expected=[]
                    for tag,attributes in before:
                        attributes=dict(attributes)
                        if tag=='route' and 'sources' in attributes:
                            attributes['sources']=','.join(v for v in attributes['sources'].split(',') if v!='compressed_offload')
                        expected.append((tag,tuple(sorted(attributes.items()))))
                    if normalized(expected)!=normalized(after):raise ValueError('An unrelated audio route/endpoint changed')
                if iteration and patched!=first[name]:raise ValueError('Repeated patch is not byte-idempotent: '+name)
                first[name]=patched
    print(json.dumps({'pinned_source_configs_checked':len(source),'patch_passes':2,'unrelated_effects_preserved':True,
                      'non_offload_routes_preserved':True,'hardware_processing_verified':False},indent=2))

if __name__=='__main__':main()
