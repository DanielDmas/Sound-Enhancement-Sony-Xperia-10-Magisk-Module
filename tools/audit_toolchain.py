#!/usr/bin/env python3
"""Fetch hash-pinned official tools for CI; never ship them in the phone module."""
import hashlib,io,json,os,pathlib,subprocess,tarfile,urllib.request,zipfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'audit-tools'
SOURCES={
 'magisk':('https://github.com/topjohnwu/Magisk/releases/download/v31.1/Magisk-v31.1.apk','89cefac0a318afa39fb3880c45c87b036c05bc1ebf02a7a715b7f8d7c26ac6e7'),
 'shellcheck':('https://github.com/koalaman/shellcheck/releases/download/v0.11.0/shellcheck-v0.11.0.linux.x86_64.tar.xz','8c3be12b05d5c177a04c29e3c78ce89ac86f1595681cab149b65b97c4e227198'),
}
def download(name):
 url,want=SOURCES[name]
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'sony-audio-audit'}),timeout=60) as response:data=response.read(30000000)
 if hashlib.sha256(data).hexdigest()!=want:raise ValueError('Download integrity failure: '+name)
 return data
def main():
 OUT.mkdir(exist_ok=True)
 with zipfile.ZipFile(io.BytesIO(download('magisk'))) as z:
  names=[n for n in z.namelist() if 'x86_64' in n and 'busybox' in n]
  if len(names)!=1:raise ValueError('Expected one x86_64 Magisk BusyBox: '+repr(names))
  (OUT/'busybox').write_bytes(z.read(names[0]))
 with tarfile.open(fileobj=io.BytesIO(download('shellcheck')),mode='r:xz') as t:
  m=t.getmember('shellcheck-v0.11.0/shellcheck')
  if not m.isfile():raise ValueError('Invalid ShellCheck archive')
  (OUT/'shellcheck').write_bytes(t.extractfile(m).read())
 for n in ['busybox','shellcheck']:(OUT/n).chmod(0o755)
 meta={'sources':SOURCES,'hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file()}}
 (OUT/'sources.json').write_text(json.dumps(meta,indent=2)+'\n')
 for args in [[str(OUT/'shellcheck'),'--version'],[str(OUT/'busybox'),'sh','-c','id; command -v timeout; command -v awk; command -v flock']]:
  r=subprocess.run(args,capture_output=True,text=True,timeout=15);print(r.stdout+r.stderr)
  if r.returncode:raise SystemExit(r.returncode)
 files=sorted(n for n in json.loads((ROOT/'tools/module_files.json').read_text()) if n.endswith('.sh') or n in ['system/bin/sefx','META-INF/com/google/android/update-binary'])
 r=subprocess.run([str(OUT/'shellcheck'),'-s','sh','-f','json',*files],cwd=ROOT,capture_output=True,text=True,timeout=30)
 (OUT/'shellcheck-baseline.json').write_text(r.stdout)
 print('ShellCheck baseline diagnostics:',len(json.loads(r.stdout or '[]')))
if __name__=='__main__':main()
