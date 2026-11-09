"""Real Magisk BusyBox shell/applets; Android Binder commands remain fixtures."""
import fcntl, os, pathlib, signal, subprocess, time, unittest
from test_sessions import AndroidFixture, PLAYER, SONY, record
BUSYBOX=os.environ.get('SEFX_BUSYBOX','')

@unittest.skipUnless(BUSYBOX and os.getuid()==0,'requires official Magisk BusyBox and root for integration')
class MagiskRuntime(AndroidFixture):
    def setUp(self):
        super().setUp();self.children=[]
        self.env.update(ASH_STANDALONE='1',SEFX_SHELL='magisk_busybox')
    def command(self,*args):return [BUSYBOX,'sh',str(self.module/'system/bin/sefx'),*args]
    def runfx(self,*args,expected=0):
        r=subprocess.run(self.command(*args),env=self.env,text=True,capture_output=True,timeout=20)
        self.assertEqual(r.returncode,expected,r.stdout+r.stderr);return r
    def spawn(self,*args):
        p=subprocess.Popen(self.command(*args),env=self.env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        self.children.append(p);return p
    def until(self,predicate,seconds=12):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            if predicate():return
            time.sleep(.05)
        self.fail('Timed out waiting for runtime state')
    def tearDown(self):
        self.config('auto=0\n')
        for p in self.children:
            # A killed parent may leave a sleeping child in this owned group.
            try:os.killpg(p.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            if p.poll() is None:
                try:p.wait(timeout=3)
                except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
        super().tearDown()
    def test_standalone_dispatches_real_session_and_android_ps(self):
        self.android['packages']+='package:com.shared.other uid:10123\n';self.save()
        self.runfx('attach');x=self.broadcasts('OPEN')[0]
        self.assertIn(PLAYER,x);self.assertEqual(x[x.index('android.media.extra.AUDIO_SESSION')+1],'77')
        self.assertTrue(self.calls('ps'));self.assertTrue(self.calls('pidof'))
    def test_partial_discovery_keeps_identifiable_music_working(self):
        self.android['packages']+='package:com.other.player uid:10124\n'
        self.android['processes']+='3456 com.other.player\n'
        self.android['audio']+=record(uid=10124,pid=3456,sid=0,piid=11);self.save()
        self.runfx('sync');self.assertEqual(len(self.broadcasts('OPEN')),1);self.assertIn(PLAYER,self.broadcasts('OPEN')[0])
    def test_evidence_capture_works_with_real_magisk_applets(self):
        p=self.module/'system/vendor/etc/audio_effects.xml';p.parent.mkdir(parents=True)
        p.write_text('<audio_effects_conf><libraries/><effects/></audio_effects_conf>\n')
        self.env['SEFX_SYSTEM_ROOT']=str(self.root/'rom');self.runfx('doctor')
        self.assertIn('CONFIG_SNAPSHOT v1 module',(self.state/'diagnostics.txt').read_text())
    def test_kernel_lock_is_respected_by_magisk_busybox(self):
        with (self.state/'attach.flock').open('w') as fd:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);self.runfx('attach',expected=5)
        self.runfx('attach');self.assertEqual(len(self.broadcasts('OPEN')),1)
    def test_sleep_child_does_not_keep_dead_watchers_lock(self):
        self.config('auto=1\ninterval=60\nidle_interval=120\n');p=self.spawn('watch')
        self.until(lambda:(self.state/'heartbeat').exists());time.sleep(.2)
        p.kill();p.wait(timeout=3)
        with (self.state/'watch.flock').open('w') as fd:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    def test_killed_refresh_releases_kernel_lock(self):
        self.android['am_delay']=2;self.save();p=self.spawn('attach')
        self.until(lambda:bool(self.broadcasts('OPEN')))
        os.killpg(p.pid,signal.SIGKILL);p.wait(timeout=3)
        self.android['am_delay']=0;self.save();self.runfx('attach')
    def test_reconnects_when_music_starts_after_watcher(self):
        self.config('auto=1\ninterval=3\nidle_interval=5\n');self.android['audio']='players:\n';self.save()
        p=self.spawn('watch');self.until(lambda:(self.state/'heartbeat').exists())
        self.android['audio']='players:\n'+record();self.save()
        self.until(lambda:bool(self.broadcasts('OPEN')))
        self.assertFalse(any(x[1]=='start-activity' for x in self.calls('am')))
        self.config('auto=0\n');p.wait(timeout=8);self.assertEqual(p.returncode,0)
    def test_reconnects_after_unresolved_session_becomes_valid(self):
        self.config('auto=1\ninterval=3\nidle_interval=5\n');self.android['audio']='players:\n'+record(sid=0);self.save()
        p=self.spawn('watch');self.until(lambda:(self.state/'heartbeat').exists())
        self.android['audio']='players:\n'+record();self.save()
        self.until(lambda:bool(self.broadcasts('OPEN')))
        self.assertFalse(any(x[1]=='start-activity' for x in self.calls('am')))
        self.config('auto=0\n');p.wait(timeout=8);self.assertEqual(p.returncode,0)
    def test_supervisor_restarts_killed_worker(self):
        self.config('auto=1\ninterval=3\nidle_interval=5\n');p=self.spawn('daemon')
        self.until(lambda:(self.state/'watch.pid').exists() and bool(self.broadcasts('OPEN')))
        first=int((self.state/'watch.pid').read_text());os.kill(first,signal.SIGKILL)
        self.until(lambda:(self.state/'watch.pid').exists() and (self.state/'watch.pid').read_text().strip()!=str(first),seconds=15)
        self.config('auto=0\n');p.wait(timeout=12);self.assertEqual(p.returncode,0)
        self.assertIn('watcher exited status=137',(self.state/'events.log').read_text())
    def test_duplicate_supervisor_is_rejected(self):
        self.config('auto=1\n')
        with (self.state/'daemon.flock').open('w') as fd:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);self.runfx('daemon',expected=5)
    def test_corrupted_dump_preserves_attachment_under_standalone(self):
        self.runfx('sync');before=(self.state/'attached.tsv').read_text()
        self.android['audio']='PlaybackActivityMonitor truncated';self.save();self.clearcalls()
        self.runfx('sync',expected=3);self.assertEqual((self.state/'attached.tsv').read_text(),before);self.assertFalse(self.broadcasts())
    def test_failed_close_is_retried_under_standalone(self):
        self.runfx('sync');self.android.update(close_fail=True,audio='players:\n'+record(sid=88));self.save()
        self.clearcalls();self.runfx('sync',expected=3);self.assertFalse(self.broadcasts('OPEN'))
        self.android['close_fail']=False;self.save();self.clearcalls();self.runfx('sync')
        self.assertEqual(len(self.broadcasts('CLOSE')),1);self.assertEqual(len(self.broadcasts('OPEN')),1)
