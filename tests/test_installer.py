import os, pathlib, shutil, subprocess, tempfile, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class HalProbe(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
        self.bin=self.root/'bin';self.bin.mkdir();self.proc=self.root/'proc';self.proc.mkdir()
        ps=self.bin/'ps';ps.write_text('#!/bin/sh\ncat "$HAL_FIXTURE"\n');ps.chmod(0o755)
        self.rows=self.root/'ps.txt';self.rows.write_text('PID NAME\n')
        self.env={**os.environ,'SEFX_ANDROID_BIN':str(self.bin),'SEFX_PROC_DIR':str(self.proc),'HAL_FIXTURE':str(self.rows)}
    def tearDown(self):self.tmp.cleanup()
    def service(self,pid,name,elf_class):
        with self.rows.open('a') as out:out.write(f'{pid} {name}\n')
        d=self.proc/str(pid);d.mkdir();(d/'exe').write_bytes(b'\x7fELF'+bytes([elf_class])+b'\0'*20)
    def probe(self,expected):
        r=subprocess.run(['sh','-c','. "$1"; audio_hal_32bit','probe',str(ROOT/'function.sh')],env=self.env,capture_output=True,text=True,timeout=5)
        self.assertEqual(r.returncode,expected,r.stderr)
    def test_running_32_bit_audio_hal_is_accepted(self):
        self.service(500,'android.hardware.audio@2.0-service',1);self.probe(0)
    def test_running_64_bit_audio_hal_is_rejected(self):
        self.service(500,'android.hardware.audio@2.0-service',2);self.probe(1)
    def test_dormant_or_unrelated_32_bit_binary_is_not_enough(self):
        self.service(500,'com.music.player',1);self.probe(1)
    def test_effect_hal_service_name_is_supported(self):
        self.service(501,'/vendor/bin/hw/android.hardware.audio.effect@6.0-service',1);self.probe(0)
    def test_unreadable_or_non_elf_service_is_rejected(self):
        self.service(500,'android.hardware.audio@2.0-service',1);(self.proc/'500/exe').write_bytes(b'not an ELF');self.probe(1)
class Mirror(unittest.TestCase):
    def test_missing_block_device_does_not_attempt_mknod_or_mount(self):
        r=subprocess.run(['sh','-c','''. "$1"
get_device() { DEV=; }
mknod() { echo unexpected; return 99; }
mount() { echo unexpected; return 99; }
mount_mirror /optional /unused
''','probe',str(ROOT/'function.sh')],capture_output=True,text=True)
        self.assertEqual(r.returncode,1);self.assertNotIn('unexpected',r.stdout)
