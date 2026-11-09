import hashlib,importlib.util,json,pathlib,subprocess,tempfile,unittest,zipfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('builder',ROOT/'tools/build_module.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

class Package(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT/'dist').mkdir(exist_ok=True)
        cls.tmp=tempfile.TemporaryDirectory(dir=ROOT/'dist');cls.out=pathlib.Path(cls.tmp.name)/'module.zip'
        cls.result=builder.build(cls.out)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_payloads_and_archive_are_valid(self):
        self.assertEqual(self.result['protected_payloads_verified'],55)
        with zipfile.ZipFile(self.out) as z:self.assertIsNone(z.testzip())
    def test_package_is_reproducible(self):
        second=builder.build(pathlib.Path(self.tmp.name)/'again.zip')
        self.assertEqual(self.result['sha256'],second['sha256'])
    def test_root_layout_is_installable(self):
        with zipfile.ZipFile(self.out) as z:
            for name in ['module.prop','customize.sh','action.sh','service.sh','sefx/lib.sh','sefx/sessions.awk','system/bin/sefx','installer-defaults.prop']:
                self.assertIn(name,z.namelist())
    def test_zip_excludes_unbuilt_launcher_and_development_files(self):
        with zipfile.ZipFile(self.out) as z:
            self.assertFalse(any(n.startswith(('system/priv-app/AudioSettings/','.git/','.github/','tests/','tools/','dist/','.sefx/')) for n in z.namelist()))
    def test_module_identity_is_an_upgrade_not_a_second_module(self):
        with zipfile.ZipFile(self.out) as z:
            self.assertIn('id=SoundEnhancement\n',z.read('module.prop').decode())
            self.assertIn('versionCode=20002\n',z.read('module.prop').decode())
    def test_critical_executables_have_executable_mode(self):
        with zipfile.ZipFile(self.out) as z:
            for name in ['system/bin/sefx','action.sh','service.sh','META-INF/com/google/android/update-binary']:
                self.assertEqual((z.getinfo(name).external_attr>>16)&0o777,0o755)
    def test_all_shell_files_pass_dash_and_bash_syntax(self):
        for name,data in builder.inputs().items():
            if name.endswith('.sh') or name=='system/bin/sefx':
                for shell in ['sh','bash']:
                    with self.subTest(file=name,shell=shell):
                        r=subprocess.run([shell,'-n'],input=data,capture_output=True)
                        self.assertEqual(r.returncode,0,r.stderr.decode())
    def test_binary_changes_are_rejected(self):
        files=builder.inputs();name='system/priv-app/SoundEnhancement/SoundEnhancement.apk';files[name]=files[name]+b'changed'
        with self.assertRaisesRegex(ValueError,'modified'):builder.validate_payload(files)
    def test_no_claim_of_physical_verification(self):
        with zipfile.ZipFile(self.out) as z:self.assertFalse(json.loads(z.read('BUILD_INFO.json'))['hardware_tested'])
    def test_background_manager_never_kills_audio_or_changes_selinux(self):
        s=(ROOT/'sefx/lib.sh').read_text()
        for text in ['killall','setenforce','/sys/fs/selinux/enforce','pm clear','pm uninstall','magisk --denylist rm']:self.assertNotIn(text,s)
    def test_name_change_no_longer_calls_upstream_destructive_cleanup(self):
        s=(ROOT/'customize.sh').read_text()
        self.assertNotIn('  cleanup\n',s);self.assertNotIn('pm uninstall $PKG',s)
        self.assertIn('OPTIONALS=$MODPATH/installer-defaults.prop',s)
    def test_installer_has_explicit_12l_lilac_guard(self):
        s=(ROOT/'customize.sh').read_text()
        self.assertIn('"$(getprop ro.product.device)" != lilac',s);self.assertIn('"$API" != 32',s)
        self.assertIn('No compatible running 32-bit audio HAL was found',s)

if __name__=='__main__':unittest.main()
