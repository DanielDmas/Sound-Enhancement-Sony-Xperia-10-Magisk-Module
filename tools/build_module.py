#!/usr/bin/env python3
"""Deterministic Magisk ZIP using the repository's supplied binary payloads."""
import argparse, hashlib, json, os, pathlib, stat, subprocess, tempfile, zipfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
PREFIXES=('META-INF/','system/','system_support/','system_dolby/','system_dolby_36dB/',
          'unused/','arm64-v8a/','armeabi-v7a/','x86/','x86_64/','sefx/','docs/')
ROOT_FILES={'module.prop','LICENSE','README.md','CHANGELOG.md','acdb.conf','audio.txt',
 'action.sh','aml.sh','cleaner.sh','copy.sh','customize.sh','function.sh','package.txt',
 'package-dolby.txt','post-fs-data.sh','sepolicy.rule','service.sh','system.prop',
 'uninstall.sh','update.sh','installer-defaults.prop'}

def inputs(root=ROOT):
    allowed=set(json.loads((root/'tools/module_files.json').read_text()))
    files={}
    for path in root.rglob('*'):
        if not path.is_file():continue
        name=path.relative_to(root).as_posix()
        if '__pycache__' in path.parts or name.startswith('system/priv-app/AudioSettings/'):continue
        if name in ROOT_FILES or name.startswith(PREFIXES):
            if name not in allowed:raise ValueError('Unlisted file in module payload: '+name)
            if path.is_symlink():raise ValueError('Symlink in module payload: '+name)
            files[name]=path.read_bytes()
    required={'module.prop','customize.sh','action.sh','service.sh','sefx/lib.sh',
              'sefx/sessions.awk','system/bin/sefx','META-INF/com/google/android/update-binary',
              'system/priv-app/SoundEnhancement/SoundEnhancement.apk'}
    if not required<=files.keys():raise ValueError('Missing required files: '+repr(required-files.keys()))
    return files

def validate_payload(files,root=ROOT):
    manifest=json.loads((root/'tools/payload_manifest.json').read_text())
    for name,want in manifest.items():
        if name not in files:raise ValueError('Missing protected upstream payload: '+name)
        got=hashlib.sha256(files[name]).hexdigest()
        if got!=want:raise ValueError('Protected upstream payload was modified: '+name)
        if name.endswith(('.apk','.jar')):
            import io
            with zipfile.ZipFile(io.BytesIO(files[name])) as archive:
                if archive.testzip():raise ValueError('Corrupt APK/JAR: '+name)
        if name.endswith('.so') and files[name][:4]!=b'\x7fELF':raise ValueError('Invalid ELF: '+name)
    for name,data in files.items():
        if name.endswith('.sh') or name=='system/bin/sefx':
            r=subprocess.run(['sh','-n'],input=data,capture_output=True)
            if r.returncode:raise ValueError('Shell syntax failure: '+name+' '+r.stderr.decode())
    return len(manifest)

def build(output,root=ROOT):
    output=pathlib.Path(output).absolute()
    if output.is_symlink():raise ValueError('Output must not be a symlink')
    if output.suffix!='.zip':raise ValueError('Output must have a .zip extension')
    resolved=output.resolve()
    if resolved.is_relative_to(root.resolve()) and not resolved.is_relative_to((root/'dist').resolve()):
        raise ValueError('Repository output must be inside dist, never a source file')
    output=resolved
    files=inputs(root);protected=validate_payload(files,root)
    prop=dict(line.split('=',1) for line in files['module.prop'].decode().splitlines() if '=' in line)
    if 'SEFX_RUNTIME_VERSION='+prop['version']+'\n' not in files['sefx/lib.sh'].decode():
        raise ValueError('Runtime and module metadata versions differ')
    info={'version':prop['version'],'id':prop['id'],'protected_payloads_verified':protected,
          'target':'G8441/lilac Android 12L API 32 with Magisk',
          'upstream_commit':'925950e80b66db58703f408ea1ba4811811bbacb',
          'hardware_tested':False,'notice':'Candidate; shell/fixture tests cannot prove audible processing.',
          'files_sha256':{p:hashlib.sha256(v).hexdigest() for p,v in sorted(files.items())}}
    files['BUILD_INFO.json']=(json.dumps(info,indent=2)+'\n').encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.build-',dir=output.parent) as temporary:
        candidate=pathlib.Path(temporary)/'candidate.zip'
        with candidate.open('w+b') as target:
            with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
                for name,data in sorted(files.items()):
                    entry=zipfile.ZipInfo(name,date_time=(2026,11,8,0,0,0))
                    mode=0o755 if name.endswith('.sh') or name in ['system/bin/sefx','META-INF/com/google/android/update-binary'] else 0o644
                    entry.create_system=3;entry.external_attr=(stat.S_IFREG|mode)<<16
                    entry.compress_type=zipfile.ZIP_DEFLATED
                    archive.writestr(entry,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
            target.flush();os.fsync(target.fileno())
        with zipfile.ZipFile(candidate) as archive:
            if archive.testzip():raise ValueError('ZIP CRC failure')
        digest=hashlib.sha256(candidate.read_bytes()).hexdigest()
        checksum=pathlib.Path(temporary)/'checksum'
        with checksum.open('w') as target:
            target.write(digest+'  '+output.name+'\n');target.flush();os.fsync(target.fileno())
        sidecar=output.with_suffix(output.suffix+'.sha256')
        if output.is_symlink() or sidecar.is_symlink():raise ValueError('Output changed to a symlink')
        os.replace(candidate,output)
        os.replace(checksum,sidecar)
    return {'path':str(output),'bytes':output.stat().st_size,'sha256':digest,'files':len(files),'protected_payloads_verified':protected,'hardware_tested':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(ROOT/'dist/SoundEnhancement-v2.0.0-rc.2-lilac-12L.zip'))
    print(json.dumps(build(parser.parse_args().output),indent=2))
