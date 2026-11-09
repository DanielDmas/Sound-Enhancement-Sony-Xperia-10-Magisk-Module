"""Exercise real shell config edits and parse output structurally."""
import fcntl, os, pathlib, shutil, subprocess, tempfile, unittest, xml.etree.ElementTree as ET
ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE='''<?xml version="1.0" encoding="UTF-8"?>
<audio_effects_conf version="2.0" xmlns="http://schemas.android.com/audio/audio_effects_conf/v2_0">
    <libraries>
        <library name="bundle" path="libbundlewrapper.so"/>
    </libraries>
    <effects>
        <effect name="equalizer" library="bundle" uuid="ce772f20-847d-11df-bb17-0002a5d5c51b"/>
    </effects>
</audio_effects_conf>
'''
class ConfigGeneration(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
        self.config=self.root/'system/vendor/etc/audio_effects.xml';self.config.parent.mkdir(parents=True);self.config.write_text(BASE)
        library=self.root/'system/vendor/lib/soundfx/libsonysweffect.so';library.parent.mkdir(parents=True);library.touch()
        self.script=self.root/'.aml.sh';self.script.write_text((ROOT/'aml.sh').read_text().replace('#hsound_enhancement','sound_enhancement'))
        (self.root/'sefx').mkdir();shutil.copyfile(ROOT/'sefx/proxy.awk',self.root/'sefx/proxy.awk')
    def tearDown(self):self.tmp.cleanup()
    def patch(self):
        r=subprocess.run(['sh',str(self.script)],env={**os.environ,'MODPATH':str(self.root),'MODSYSTEM':'/system'},text=True,capture_output=True,timeout=15,cwd=self.root)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr);return ET.parse(self.config).getroot()
    @staticmethod
    def elements(root,tag):return [x for x in root.iter() if x.tag.split('}')[-1]==tag]
    def test_proxy_and_unrelated_effect_are_preserved(self):
        root=self.patch();proxies=self.elements(root,'effectProxy')
        self.assertEqual(len(proxies),1);self.assertEqual(proxies[0].attrib['name'],'sonyeffect')
        self.assertTrue(any(x.attrib.get('name')=='equalizer' for x in self.elements(root,'effect')))
        self.assertEqual(len(self.elements(proxies[0],'libsw')),1);self.assertEqual(len(self.elements(proxies[0],'libhw')),1)
    def test_repeated_patching_does_not_leave_empty_or_duplicate_proxies(self):
        self.patch();root=self.patch();proxies=self.elements(root,'effectProxy')
        self.assertEqual(len(proxies),1);self.assertEqual(proxies[0].attrib['name'],'sonyeffect')
        self.assertEqual(len(self.elements(root,'postprocess')),1)
    def test_does_not_remove_an_unrelated_proxy(self):
        text=BASE.replace('    </effects>','''        <effectProxy name="other" library="bundle" uuid="other-uuid">
            <libsw library="bundle" uuid="sw-other"/>
        </effectProxy>
    </effects>''')
        self.config.write_text(text);self.patch();root=self.patch()
        self.assertEqual(sorted(x.attrib['name'] for x in self.elements(root,'effectProxy')),['other','sonyeffect'])
    def test_policy_has_one_alac_profile_after_repeated_patching(self):
        policy=self.config.with_name('audio_policy_configuration.xml')
        policy.write_text('''<audioPolicyConfiguration>
<mixPort name="compressed" flags="AUDIO_OUTPUT_FLAG_COMPRESS_OFFLOAD">
    <profile name="" format="AUDIO_FORMAT_MP3"/>
</mixPort>
</audioPolicyConfiguration>
''')
        self.patch();self.patch();root=ET.parse(policy).getroot()
        self.assertEqual(len([x for x in root.iter('profile') if x.attrib.get('format')=='AUDIO_FORMAT_ALAC']),1)
        self.assertNotIn('COMPRESS_OFFLOAD',policy.read_text())

class ConfigTransaction(unittest.TestCase):
    shell=['sh']
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
        self.module=self.root/'module';self.module.mkdir();(self.module/'sefx').mkdir()
        for name in ['copy.sh','sefx/configure.sh','sefx/proxy.awk']:shutil.copyfile(ROOT/name,self.module/name)
        (self.module/'.aml.sh').write_text((ROOT/'aml.sh').read_text().replace('#hsound_enhancement','sound_enhancement'))
        lib=self.module/'system/vendor/lib/soundfx/libsonysweffect.so';lib.parent.mkdir(parents=True);lib.touch()
        self.original=self.root/'rom/vendor/etc/audio_effects.xml';self.original.parent.mkdir(parents=True);self.original.write_text(BASE)
        self.target=self.module/'system/vendor/etc/audio_effects.xml';self.target.parent.mkdir(parents=True);self.target.write_text('previous working config')
        self.env={**os.environ,'MODPATH':str(self.module),'SEFX_AUDIO_ROOT':str(self.root/'rom')}
    def tearDown(self):self.tmp.cleanup()
    def configure(self,expected=0):
        r=subprocess.run([*self.shell,str(self.module/'sefx/configure.sh')],env=self.env,text=True,capture_output=True,timeout=20)
        self.assertEqual(r.returncode,expected,r.stdout+r.stderr)
        self.assertFalse([p for p in self.module.glob('.config.*') if p.is_dir()]);return r
    def test_success_commits_valid_output_without_touching_rom(self):
        self.configure();root=ET.parse(self.target).getroot();self.assertEqual(self.original.read_text(),BASE)
        self.assertEqual(len(ConfigGeneration.elements(root,'effectProxy')),1)
    def test_concurrent_configuration_does_not_touch_live_files(self):
        with (self.module/'.config.flock').open('w') as fd:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);self.configure(expected=5)
        self.assertEqual(self.target.read_text(),'previous working config')
    def test_generation_error_preserves_all_previous_files(self):
        (self.module/'.aml.sh').write_text('exit 1\n');self.configure(expected=1)
        self.assertEqual(self.target.read_text(),'previous working config')
    def test_missing_sources_preserve_previous_files(self):
        self.original.unlink();self.configure(expected=1);self.assertEqual(self.target.read_text(),'previous working config')
    def test_missing_proxy_is_not_accepted_as_a_successful_patch(self):
        (self.module/'.aml.sh').write_text('exit 0\n');self.configure(expected=1);self.assertEqual(self.target.read_text(),'previous working config')
    def test_second_boot_does_not_accumulate_proxy_definitions(self):
        self.configure();first=self.target.read_bytes();self.configure();self.assertEqual(self.target.read_bytes(),first)
    def test_rollback_restores_previous_file_after_commit_error(self):
        bindir=self.root/'bin';bindir.mkdir()
        fake=bindir/'mv';fake.write_text('#!/bin/sh\ncase "$*" in *audio_effects.xml.next*) exit 1 ;; esac\nexec /usr/bin/mv "$@"\n');fake.chmod(0o755)
        self.env['PATH']=str(bindir)+os.pathsep+self.env['PATH']
        self.configure(expected=1);self.assertEqual(self.target.read_text(),'previous working config')

    def test_failed_restore_keeps_backup_for_recovery(self):
        bindir=self.root/'bin';bindir.mkdir()
        fake=bindir/'mv';fake.write_text('#!/bin/sh\ncase "$*" in *audio_effects.xml.next*) /usr/bin/mv "$@"; exit 1 ;; */backup/*) exit 1 ;; esac\nexec /usr/bin/mv "$@"\n');fake.chmod(0o755)
        self.env['PATH']=str(bindir)+os.pathsep+self.env['PATH']
        r=subprocess.run([*self.shell,str(self.module/'sefx/configure.sh')],env=self.env,text=True,capture_output=True,timeout=20)
        self.assertNotEqual(r.returncode,0)
        backups=list(self.module.glob('.config.*/backup/system/vendor/etc/audio_effects.xml'))
        self.assertEqual(len(backups),1,r.stderr);self.assertEqual(backups[0].read_text(),'previous working config')
        self.assertTrue(self.target.is_file())

@unittest.skipUnless(os.environ.get('SEFX_BUSYBOX'),'requires official Magisk BusyBox')
class BusyboxConfigTransaction(unittest.TestCase):
    shell=[os.environ.get('SEFX_BUSYBOX',''),'sh']
    def setUp(self):
        ConfigTransaction.setUp(self);self.env['ASH_STANDALONE']='1'
    tearDown=ConfigTransaction.tearDown
    configure=ConfigTransaction.configure
    test_success_commits_valid_output_without_touching_rom=ConfigTransaction.test_success_commits_valid_output_without_touching_rom
    test_generation_error_preserves_all_previous_files=ConfigTransaction.test_generation_error_preserves_all_previous_files
