"""Regression coverage for Binder FD transfer, not an SELinux emulator."""
import json, os, stat, subprocess, time, unittest
from test_sessions import AndroidFixture, SONY, PLAYER

class TransportChecks:
    def test_private_state_files_do_not_cross_binder_boundary(self):
        self.runfx('recover')
        self.assertEqual(len(self.broadcasts('CLOSE')),1)
        self.assertEqual(len(self.broadcasts('OPEN')),1)
        self.assertTrue(any(x[1]=='start-activity' for x in self.calls('am')))

    def test_package_stderr_is_not_parsed_as_stdout(self):
        self.android['packages_stderr']='A harmless service warning'
        self.save();self.runfx('attach')
        self.assertEqual(len(self.broadcasts('OPEN')),1)

    def test_nonzero_package_exit_with_valid_partial_output_is_rejected(self):
        self.runfx('sync');before=(self.state/'attached.tsv').read_text()
        self.android.update(packages_fail=True,packages_partial=self.android['packages'],
                            packages_stderr='Failure calling service package: Failed transaction',packages_exit=42)
        self.save();self.clearcalls();result=self.runfx('recover',expected=3)
        self.assertIn('Failed transaction',result.stderr)
        self.assertIn('exit 42',result.stderr)
        self.assertEqual((self.state/'attached.tsv').read_text(),before)
        self.assertFalse(self.broadcasts())
        saved=(self.state/'last-command.txt').read_text()
        self.assertIn('Failed transaction',saved)
        self.assertLessEqual(len(saved.encode()),8192)
        self.assertEqual((self.state/'last-command.txt').stat().st_mode&0o777,0o600)
        self.runfx('doctor')
        self.assertIn('LAST FAILED ANDROID COMMAND',(self.state/'diagnostics.txt').read_text())

    def test_stderr_is_piped_even_when_action_output_is_a_file(self):
        output=self.root/'action.log'
        with output.open('w') as stream:
            result=subprocess.run(self.command('recover'),
                                  env=self.env,stdout=stream,stderr=stream,timeout=15)
        self.assertEqual(result.returncode,0,output.read_text())
        self.assertIn('Panel opened',output.read_text())

    def test_unsafe_failure_report_path_is_refused(self):
        target=self.root/'keep';target.write_text('original')
        (self.state/'last-command.txt').symlink_to(target)
        self.runfx('attach',expected=3)
        self.assertEqual(target.read_text(),'original');self.assertFalse(self.broadcasts())

    def test_current_user_warning_is_separate_from_numeric_output(self):
        self.android['user_stderr']='Service warning on stderr';self.save()
        self.runfx('recover');self.assertTrue(self.broadcasts('OPEN'))

    def test_nonzero_user_exit_is_not_accepted_even_with_numeric_stdout(self):
        self.android.update(user_exit=23,user_stderr='User service unavailable')
        self.save();result=self.runfx('recover',expected=3)
        self.assertIn('exit 23',result.stderr);self.assertIn('User service unavailable',result.stderr)
        self.assertFalse(self.broadcasts())

    def test_binder_receives_pipes_null_input_and_no_lock_fds(self):
        self.android['record_fds']=True;self.save();self.runfx('recover')
        calls=[json.loads(x) for x in (self.root/'fds.jsonl').read_text().splitlines()]
        binder=[fds for name,fds in calls if name in ['cmd','am','pm','appops']]
        self.assertGreaterEqual(len(binder),5)
        for fds in binder:
            self.assertEqual(fds['0'],stat.S_IFCHR)
            self.assertEqual(fds['1'],stat.S_IFIFO);self.assertEqual(fds['2'],stat.S_IFIFO)
            for fd in ['3','7','8','9']:self.assertIsNone(fds[fd])

    def test_reader_is_bounded_when_android_descendant_retains_pipe(self):
        self.android['dump_orphan_fds']=True;self.save();start=time.monotonic()
        self.runfx('attach',expected=3)
        self.assertLess(time.monotonic()-start,11.5)
        self.assertFalse(self.broadcasts())

    def test_failure_details_are_capped(self):
        self.android.update(packages_fail=True,packages_stderr='x'*20000)
        self.save();result=self.runfx('attach',expected=3)
        self.assertLess(len(result.stderr.encode()),2500)
        self.assertLessEqual((self.state/'last-command.txt').stat().st_size,8192)

class AndroidTransport(TransportChecks,AndroidFixture):pass

BUSYBOX=os.environ.get('SEFX_BUSYBOX','')
@unittest.skipUnless(BUSYBOX and os.getuid()==0,'requires official Magisk BusyBox and root')
class MagiskAndroidTransport(TransportChecks,AndroidFixture):
    def setUp(self):
        super().setUp();self.env.update(ASH_STANDALONE='1',SEFX_SHELL='magisk_busybox')
    def command(self,*args):return [BUSYBOX,'sh',str(self.module/'system/bin/sefx'),*args]
