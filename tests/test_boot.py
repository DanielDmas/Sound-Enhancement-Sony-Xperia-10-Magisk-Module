import os, pathlib, shutil, subprocess, unittest
from test_sessions import AndroidFixture, REPO
class Boot(AndroidFixture):
    def test_unsupported_target_does_not_spoof_properties_or_restart_audio(self):
        self.android['props']={'ro.build.version.sdk':'35'};self.save();self.boot(expected=3)
        self.assertFalse(self.calls('killall'));self.assertFalse(self.calls('resetprop'));self.assertFalse(self.calls('pm'))
    def setUp(self):
        super().setUp();shutil.copyfile(REPO/'service.sh',self.module/'service.sh')
    def boot(self,expected=0):
        r=subprocess.run(['sh',str(self.module/'service.sh')],env=self.env,text=True,capture_output=True,timeout=15)
        self.assertEqual(r.returncode,expected,r.stdout+r.stderr);return r
    def test_boot_respects_auto_off_and_grants_only_target_permission(self):
        self.boot();self.assertFalse(self.broadcasts('OPEN'))
        self.assertEqual(self.calls('pm'),[['pm','grant','--user','0','com.sonyericsson.soundenhancement','android.permission.RECORD_AUDIO']])
        self.assertEqual(len(self.calls('killall')),1)
        boot_log=(self.state/'boot.log').read_text()
        self.assertNotIn('grant failed',boot_log);self.assertNotIn('app-op rejected',boot_log)
        self.assertEqual(len(self.calls('appops')),3)
    def test_boot_starts_supervisor_without_opening_panel(self):
        self.config('auto=1\n');self.android['stop_after']=1;self.save();self.boot()
        self.assertTrue(self.broadcasts('OPEN'));self.assertFalse(any(x[1]=='start-activity' for x in self.calls('am')))
        self.assertIn('supervisor started',(self.state/'events.log').read_text())
    def test_pending_update_does_not_restart_audio_or_grant_permissions(self):
        (self.module/'update').touch();self.boot();self.assertFalse(self.calls())
    def test_disabled_boot_is_noop(self):
        (self.module/'disable').touch();self.boot();self.assertFalse(self.calls())
    def test_boot_log_rotation_is_bounded(self):
        (self.state/'boot.log').write_text('x'*65537);self.boot()
        self.assertTrue((self.state/'boot.previous.log').exists());self.assertLess((self.state/'boot.log').stat().st_size,4096)
    def test_permission_failure_is_recorded(self):
        self.android['pm_fail']=True;self.save();self.boot()
        self.assertIn('RECORD_AUDIO grant failed',(self.state/'boot.log').read_text())
    def test_symlink_boot_log_is_refused(self):
        target=self.root/'keep';target.write_text('original');(self.state/'boot.log').symlink_to(target)
        self.boot(expected=3);self.assertEqual(target.read_text(),'original');self.assertFalse(self.calls())

BUSYBOX=os.environ.get('SEFX_BUSYBOX','')
@unittest.skipUnless(BUSYBOX and os.getuid()==0,'requires official Magisk BusyBox and root')
class MagiskBootTransport(AndroidFixture):
    def test_permissions_use_pipes_despite_regular_boot_log(self):
        shutil.copyfile(REPO/'service.sh',self.module/'service.sh')
        self.env.update(ASH_STANDALONE='1',SEFX_SHELL='magisk_busybox')
        result=subprocess.run([BUSYBOX,'sh',str(self.module/'service.sh')],env=self.env,
                              text=True,capture_output=True,timeout=15)
        log=(self.state/'boot.log').read_text()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr+log)
        self.assertEqual(len(self.calls('pm')),1);self.assertEqual(len(self.calls('appops')),3)
        self.assertNotIn('Failed transaction',log);self.assertNotIn('grant failed',log)
        self.assertNotIn('app-op rejected',log)
        self.assertFalse(list(self.state.glob('run.*')))
