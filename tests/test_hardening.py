"""Failure-oriented regressions for issues found by the RC1 audit."""
import fcntl, importlib.util, os, pathlib, subprocess, tempfile, time, unittest
from unittest import mock
from test_sessions import AndroidFixture, record, PLAYER, SONY, REPO

class Recovery(AndroidFixture):
    def test_newer_lineage_android_api_is_refused_before_intents(self):
        self.android['props']={'ro.build.version.sdk':'35'};self.save()
        r=self.runfx('attach',expected=3);self.assertIn('API 32',r.stderr);self.assertFalse(self.broadcasts())

    def test_wrong_device_is_refused_before_intents(self):
        self.android['props']={'ro.product.device':'poplar'};self.save()
        self.runfx('attach',expected=3);self.assertFalse(self.broadcasts())
    def test_recover_rebuilds_profile_and_opens_panel_without_changing_config(self):
        self.runfx('sync');self.clearcalls();before=(self.state/'config').read_bytes()
        self.runfx('recover')
        self.assertEqual(len(self.broadcasts('CLOSE')),1);self.assertEqual(len(self.broadcasts('OPEN')),1)
        self.assertTrue(any(x[1]=='start-activity' for x in self.calls('am')))
        self.assertEqual((self.state/'config').read_bytes(),before)
    def wait_for_launch(self):
        for _ in range(50):
            if self.calls('nohup'):return
            time.sleep(0.01)
        self.fail('Watcher startup was never requested')

    def test_open_without_playback_still_requests_watcher(self):
        self.config('auto=1\n');self.android['audio']='players:\n';self.save()
        self.runfx('open',expected=4);self.wait_for_launch()

    def test_open_panel_failure_still_requests_watcher(self):
        self.config('auto=1\n');self.android['panel_fail']=True;self.save()
        self.runfx('open',expected=3);self.wait_for_launch()

    def test_failed_close_is_retried_before_new_session_open(self):
        self.runfx('sync');self.android.update(audio='players:\n'+record(sid=88),close_fail=True)
        self.save();self.clearcalls();self.runfx('sync',expected=3)
        self.assertFalse(self.broadcasts('OPEN'))
        self.android['close_fail']=False;self.save();self.clearcalls();self.runfx('sync')
        self.assertEqual(len(self.broadcasts('CLOSE')),1);self.assertEqual(len(self.broadcasts('OPEN')),1)
        self.clearcalls();self.runfx('sync');self.assertFalse(self.broadcasts())

    def test_failed_close_of_stopped_player_is_not_forgotten(self):
        self.runfx('sync');self.android.update(audio='players:\n',close_fail=True)
        self.save();self.runfx('sync',expected=3)
        self.android['close_fail']=False;self.save();self.clearcalls();self.runfx('sync',expected=4)
        self.assertEqual(len(self.broadcasts('CLOSE')),1)

    def test_failed_close_during_repair_retries_even_when_session_is_unchanged(self):
        self.runfx('sync');self.android['close_fail']=True;self.save();self.runfx('refresh',expected=3)
        self.android['close_fail']=False;self.save();self.clearcalls();self.runfx('sync')
        self.assertEqual(len(self.broadcasts('CLOSE')),1);self.assertEqual(len(self.broadcasts('OPEN')),1)

    def test_future_renewal_timestamp_does_not_block_repair(self):
        self.runfx('sync');(self.state/'refreshed_at').write_text('9999999999\n')
        self.clearcalls();self.runfx('sync');self.assertEqual(len(self.broadcasts('OPEN')),1)

    def test_partial_header_does_not_close_working_sessions(self):
        self.runfx('sync');old=(self.state/'attached.tsv').read_text()
        self.android['audio']='PlaybackActivityMonitor dump time: truncated\n';self.save()
        self.clearcalls();self.runfx('sync',expected=3)
        self.assertEqual((self.state/'attached.tsv').read_text(),old);self.assertFalse(self.broadcasts())

    def test_unknown_player_record_does_not_close_working_sessions(self):
        self.runfx('sync');old=(self.state/'attached.tsv').read_text()
        self.android['audio']='players:\n  AudioPlaybackConfiguration piid:10 unrecognised-format\n';self.save()
        self.clearcalls();self.runfx('sync',expected=3)
        self.assertEqual((self.state/'attached.tsv').read_text(),old);self.assertFalse(self.broadcasts())

    def test_zero_session_is_reported_as_unresolved(self):
        self.android['audio']='players:\n'+record(sid=0);self.save()
        result=self.runfx('attach',expected=4)
        self.assertIn('unresolved',result.stdout.lower());self.assertFalse(self.broadcasts())

    def test_truncated_active_attributes_do_not_close_working_sessions(self):
        self.runfx('sync');self.android['audio']='players:\n    AudioPlaybackConfiguration piid:10 u/pid:10123/2345 state:started\n';self.save()
        self.clearcalls();self.runfx('sync',expected=3);self.assertFalse(self.broadcasts())

    def test_configuration_final_line_without_newline_is_read(self):
        self.config('auto=0\ninterval=17')
        self.assertIn('active=17s',self.runfx('status').stdout)

    def test_preferences_migrate_once_and_survive_module_replacement(self):
        self.config('auto=0\ninterval=17\n')
        persistent=self.root/'persistent';self.env['SEFX_STATE_DIR']=str(persistent)
        self.assertIn('active=17s',self.runfx('status').stdout)
        self.config('auto=0\ninterval=29\n')
        self.assertIn('active=17s',self.runfx('status').stdout)
        self.assertEqual(persistent.stat().st_mode&0o777,0o700)

    def test_corrupt_octal_renewal_timestamp_does_not_kill_manager(self):
        self.runfx('sync');(self.state/'refreshed_at').write_text('008\n')
        self.clearcalls();self.runfx('sync');self.assertEqual(len(self.broadcasts('OPEN')),1)

    def test_oversized_numeric_configuration_uses_safe_default(self):
        self.config('auto=0\ninterval='+'9'*300+'\n')
        r=self.runfx('status');self.assertIn('active=5s',r.stdout);self.assertNotIn('Illegal number',r.stderr)

    def test_integer_overflow_session_is_never_dispatched(self):
        self.android['audio']='players:\n'+record(sid='9'*30);self.save()
        self.runfx('attach',expected=4);self.assertFalse(self.broadcasts())

    def test_state_file_symlinks_cannot_overwrite_other_files(self):
        target=self.root/'unrelated';target.write_text('keep');(self.state/'events.log').symlink_to(target)
        self.runfx('attach',expected=3);self.assertEqual(target.read_text(),'keep')

    def test_pending_upgrade_requires_reboot_and_makes_no_changes(self):
        (self.module/'update').touch();r=self.runfx('attach',expected=6)
        self.assertIn('reboot',r.stderr.lower());self.assertFalse(self.broadcasts())

    def test_status_distinguishes_runtime_version_from_displayed_metadata(self):
        (self.module/'module.prop').write_text('name=New metadata\nversion=v99\n')
        r=self.runfx('status');self.assertIn('Runtime:',r.stdout);self.assertIn('v99',r.stdout)

    def test_failed_state_commit_is_reported(self):
        (self.state/'attached.tsv').mkdir();self.runfx('attach',expected=3)

    def test_kernel_lock_exclusion_and_crash_release(self):
        with (self.state/'attach.flock').open('w') as fd:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.runfx('attach',expected=5);self.assertFalse(self.broadcasts())
        self.runfx('attach')

class AtomicPackage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('atomic_builder',REPO/'tools/build_module.py')
        cls.builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.builder)

    def test_failed_archive_write_preserves_previous_download(self):
        (REPO/'dist').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=REPO/'dist') as directory:
            out=pathlib.Path(directory)/'module.zip';out.write_bytes(b'previous verified file')
            with mock.patch.object(self.builder.zipfile.ZipFile,'writestr',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):self.builder.build(out)
            self.assertEqual(out.read_bytes(),b'previous verified file')

    def test_cannot_overwrite_a_packaged_source_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);(root/'module.prop').write_text('original')
            with mock.patch.object(self.builder,'inputs',return_value={'module.prop':b'id=x\nversion=v1\n'}),mock.patch.object(self.builder,'validate_payload',return_value=0):
                with self.assertRaises(ValueError):self.builder.build(root/'module.prop',root)
            self.assertEqual((root/'module.prop').read_text(),'original')

    def test_output_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target=pathlib.Path(directory)/'keep';target.write_text('original')
            out=pathlib.Path(directory)/'module.zip';out.symlink_to(target)
            with self.assertRaises(ValueError):self.builder.build(out)
            self.assertEqual(target.read_text(),'original')
