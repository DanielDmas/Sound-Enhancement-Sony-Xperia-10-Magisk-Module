import fcntl, json, os, pathlib, shutil, subprocess, tempfile, time, unittest

REPO=pathlib.Path(__file__).resolve().parents[1]
SONY='com.sonyericsson.soundenhancement'
PLAYER='org.lineageos.eleven'

def record(uid=10123,pid=2345,sid=77,state='started',device=2,usage='USAGE_MEDIA',content='CONTENT_TYPE_MUSIC',piid=10):
    return f'    AudioPlaybackConfiguration piid:{piid} deviceId:{device} type:android.media.AudioTrack u/pid:{uid}/{pid} state:{state} attr: usage={usage} content={content} flags=0x0 tags= bundle=null sessionId:{sid}\n'

class AndroidFixture(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
        self.module=self.root/'module';self.module.mkdir()
        for p in ['system/bin/sefx','sefx/lib.sh','sefx/sessions.awk','module.prop']:
            q=self.module/p;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(REPO/p,q)
        self.bin=self.root/'bin';self.bin.mkdir()
        fake=self.root/'fake.py';shutil.copyfile(REPO/'tests/fake_android.py',fake);fake.chmod(0o755)
        for c in ['id','am','dumpsys','cmd','ps','pidof','getenforce','getprop','appops','logcat','nohup','sleep','resetprop','killall','pm']:
            (self.bin/c).symlink_to(fake)
        self.state=self.module/'.sefx';self.state.mkdir(mode=0o700)
        self.config('auto=0\n')
        self.android={'root':True,'user':0,'audio':'PlaybackActivityMonitor dump time: test\n  players:\n'+record(),
            'packages':f'package:{PLAYER} uid:10123\npackage:{SONY} uid:10077\n',
            'processes':f'PID NAME\n2345 {PLAYER}\n','pids':{'audioserver':'310',SONY:'780'}}
        self.save()
        self.env={**os.environ,'PATH':str(self.bin)+os.pathsep+os.environ['PATH'],
            'FAKE_ANDROID_ROOT':str(self.root),'SEFX_STATE_DIR':str(self.state),'SEFX_ANDROID_BIN':str(self.bin)}
    def tearDown(self):self.tmp.cleanup()
    def save(self):
        target=self.root/'android.json';tmp=self.root/'android.next';tmp.write_text(json.dumps(self.android));tmp.replace(target)
    def config(self,text):
        tmp=self.state/'config.next';tmp.write_text(text);tmp.replace(self.state/'config')
    def runfx(self,*args,expected=0):
        r=subprocess.run(['sh',str(self.module/'system/bin/sefx'),*args],env=self.env,text=True,capture_output=True,timeout=15)
        self.assertEqual(r.returncode,expected,r.stdout+r.stderr);return r
    def calls(self,kind=None):
        p=self.root/'calls.jsonl';xs=[json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []
        return [x for x in xs if kind is None or x[0]==kind]
    def broadcasts(self,action=None):
        xs=[x for x in self.calls('am') if len(x)>1 and x[1]=='broadcast']
        return [x for x in xs if action is None or f'android.media.action.{action}_AUDIO_EFFECT_CONTROL_SESSION' in x]
    def clearcalls(self):(self.root/'calls.jsonl').write_text('')
    def rows(self):
        r=self.runfx('status');return r.stdout

class Sessions(AndroidFixture):
    def test_music_enum_is_zero(self):
        self.runfx('attach');x=self.broadcasts('OPEN')[0];i=x.index('android.media.extra.CONTENT_TYPE');self.assertEqual(x[i+1],'0')
    def test_movie_enum_is_one(self):
        self.android['audio']='players:\n'+record(content='CONTENT_TYPE_MOVIE');self.save();self.runfx('attach')
        self.assertIn('1',self.broadcasts('OPEN')[0][-1:])
    def test_speech_enum_is_three(self):
        self.android['audio']='players:\n'+record(content='CONTENT_TYPE_SPEECH');self.save();self.runfx('attach');self.assertEqual(self.broadcasts('OPEN')[0][-1],'3')
    def test_game_enum_is_two(self):
        self.android['audio']='players:\n'+record(usage='USAGE_GAME');self.save();self.runfx('attach');self.assertEqual(self.broadcasts('OPEN')[0][-1],'2')
    def test_numeric_audio_attribute_enum_translation(self):
        for content,want in [('2','0'),('3','1'),('1','3'),('0','0')]:
            with self.subTest(content=content):
                self.android['audio']='players:\n'+record(usage='1',content=content);self.save();self.clearcalls();self.runfx('attach');self.assertEqual(self.broadcasts('OPEN')[0][-1],want)
    def test_panel_receives_actual_package_session_and_type(self):
        self.runfx('open');x=[x for x in self.calls('am') if x[1]=='start-activity'][0]
        for key,value in [('android.media.extra.PACKAGE_NAME',PLAYER),('android.media.extra.AUDIO_SESSION','77'),('android.media.extra.CONTENT_TYPE','0')]:self.assertEqual(x[x.index(key)+1],value)
        self.assertIn(SONY+'/.SoundEnhancementRedirector',x)
    def test_explicit_player_selection(self):
        self.android['packages']+='package:com.other.player uid:10124\n'
        self.android['processes']+='12345 com.other.player\n';self.android['audio']+=record(uid=10124,pid=12345,sid=88,piid=11)
        self.save();self.runfx('open',PLAYER);x=[x for x in self.calls('am') if x[1]=='start-activity'][0]
        self.assertEqual(x[x.index('android.media.extra.PACKAGE_NAME')+1],PLAYER);self.assertEqual(len(self.broadcasts('OPEN')),2)
    def test_inactive_selected_player_does_not_open_wrong_panel(self):
        self.runfx('open','com.not.playing',expected=4);self.assertFalse(any(x[1]=='start-activity' for x in self.calls('am')))
    def test_broadcast_explicit_target_and_stopped_flag(self):
        self.runfx('attach');x=self.broadcasts()[0];self.assertIn('--include-stopped-packages',x);self.assertIn(SONY+'/.AudioEffectControlReceiver',x)
    def test_does_not_need_media_session_notification(self):
        self.runfx('attach');self.assertEqual(len(self.broadcasts('OPEN')),1)
        self.assertFalse(any(x[:2]==['dumpsys','media_session'] for x in self.calls()))
    def test_paused_stopped_released_records_ignored(self):
        for state in ['paused','stopped','released','idle']:
            with self.subTest(state=state):
                self.android['audio']='players:\n'+record(state=state);self.save();self.clearcalls();self.runfx('attach',expected=4);self.assertFalse(self.broadcasts('OPEN'))
    def test_rejects_voice_calls_alarms_notifications(self):
        for usage in ['USAGE_VOICE_COMMUNICATION','USAGE_ALARM','USAGE_NOTIFICATION','USAGE_ASSISTANCE_SONIFICATION','2','4','5']:
            with self.subTest(usage=usage):
                self.android['audio']='players:\n'+record(usage=usage);self.save();self.clearcalls();self.runfx('attach',expected=4);self.assertFalse(self.broadcasts('OPEN'))
    def test_rejects_invalid_or_global_session(self):
        for sid in ['0','-1','bad','77;reboot']:
            with self.subTest(sid=sid):
                self.android['audio']='players:\n'+record(sid=sid);self.save();self.clearcalls();self.runfx('attach',expected=4);self.assertFalse(self.broadcasts('OPEN'))
    def test_ignores_timestamped_history(self):
        self.android['audio']='players:\n  player events:\n12:34:56 '+record().strip()+'\n';self.save();self.runfx('attach',expected=4);self.assertFalse(self.broadcasts('OPEN'))
    def test_exact_pid_prevents_substring_match(self):
        self.android['packages']+= 'package:com.other.player uid:10124\n'
        self.android['processes']+= '12345 com.other.player\n'
        self.android['audio']='players:\n'+record(uid=10124,pid=12345);self.save();self.runfx('attach');self.assertIn('com.other.player',self.broadcasts('OPEN')[0]);self.assertNotIn(PLAYER,self.broadcasts('OPEN')[0])
    def test_process_suffix_resolves_shared_uid(self):
        self.android['packages']+='package:com.shared.other uid:10123\n';self.android['processes']='PID NAME\n2345 '+PLAYER+':playback\n';self.save();self.runfx('attach');self.assertIn(PLAYER,self.broadcasts('OPEN')[0])
    def test_ambiguous_shared_uid_is_not_guessed(self):
        self.android['packages']+='package:com.shared.other uid:10123\n';self.android['processes']='PID NAME\n2345 unknown\n';self.save();self.runfx('attach',expected=4);self.assertFalse(self.broadcasts('OPEN'))
    def test_unknown_process_allowed_for_unique_uid(self):
        self.android['ps_fail']=True;self.save();self.runfx('attach');self.assertIn(PLAYER,self.broadcasts('OPEN')[0])
    def test_cross_user_sessions_rejected(self):
        self.android['audio']='players:\n'+record(uid=1010123);self.android['packages']+=f'package:{PLAYER} uid:1010123\n';self.save();self.runfx('attach',expected=4)
    def test_foreground_secondary_user_supported(self):
        self.android['user']=10;self.android['audio']='players:\n'+record(uid=1010123)
        self.android['packages']=f'package:{PLAYER} uid:1010123\npackage:{SONY} uid:1010077\n';self.save();self.runfx('attach');x=self.broadcasts('OPEN')[0];self.assertEqual(x[x.index('--user')+1],'10')
    def test_duplicate_track_session_opened_once(self):
        self.android['audio']+=record(piid=11);self.save();self.runfx('attach');self.assertEqual(len(self.broadcasts('OPEN')),1)
    def test_two_sessions_opened_individually(self):
        self.android['audio']+=record(sid=78,piid=11);self.save();self.runfx('attach');self.assertEqual(len(self.broadcasts('OPEN')),2)
    def test_stable_automatic_poll_does_not_spam(self):
        self.runfx('sync');self.clearcalls();self.runfx('sync');self.assertFalse(self.broadcasts())
    def test_new_session_closes_old_then_opens_new(self):
        self.runfx('sync');self.android['audio']='players:\n'+record(sid=88);self.save();self.clearcalls();self.runfx('sync');xs=self.broadcasts();self.assertIn('android.media.action.CLOSE_AUDIO_EFFECT_CONTROL_SESSION',xs[0]);self.assertEqual(xs[-1][xs[-1].index('android.media.extra.AUDIO_SESSION')+1],'88')
    def test_sony_package_scoped_close_reopens_surviving_session(self):
        self.android['audio']+=record(sid=78,piid=11);self.save();self.runfx('sync')
        self.android['audio']='players:\n'+record(sid=78,piid=11);self.save();self.clearcalls();self.runfx('sync')
        self.assertEqual(len(self.broadcasts('CLOSE')),1);self.assertEqual(len(self.broadcasts('OPEN')),1);self.assertIn('78',self.broadcasts('OPEN')[0])
    def test_route_change_rebuilds(self):
        self.runfx('sync');self.android['audio']='players:\n'+record(device=8);self.save();self.clearcalls();self.runfx('sync');self.assertEqual(len(self.broadcasts('CLOSE')),1);self.assertEqual(len(self.broadcasts('OPEN')),1)
    def test_audio_server_restart_rebuilds(self):
        self.runfx('sync');self.android['pids']['audioserver']='311';self.save();self.clearcalls();self.runfx('sync');self.assertEqual(len(self.broadcasts('CLOSE')),1);self.assertEqual(len(self.broadcasts('OPEN')),1)
    def test_global_route_change_with_same_track_device_rebuilds(self):
        self.android['audio']+='\nAudio routes:\n  mMainType=0x2\n  mBluetoothName=null\n'
        self.save();self.runfx('sync')
        self.android['audio']=self.android['audio'].replace('mBluetoothName=null','mBluetoothName=Headphones')
        self.save();self.clearcalls();self.runfx('sync');self.assertEqual(len(self.broadcasts('OPEN')),1);self.assertEqual(len(self.broadcasts('CLOSE')),1)
    def test_sony_process_restart_rebuilds(self):
        self.runfx('sync');self.android['pids'][SONY]='781';self.save();self.clearcalls();self.runfx('sync');self.assertEqual(len(self.broadcasts('OPEN')),1)
    def test_periodic_renewal(self):
        self.runfx('sync');(self.state/'refreshed_at').write_text('0\n');self.clearcalls();self.runfx('sync');self.assertEqual(len(self.broadcasts('OPEN')),1)
    def test_manual_refresh_preserves_config_and_reopens(self):
        config=(self.state/'config').read_text();self.runfx('refresh');self.assertEqual(len(self.broadcasts('CLOSE')),1);self.assertEqual(len(self.broadcasts('OPEN')),1);self.assertEqual((self.state/'config').read_text(),config)
    def test_stop_closes_owned_session(self):
        self.runfx('sync');self.android['audio']='players:\n';self.save();self.clearcalls();self.runfx('sync',expected=4);self.assertEqual(len(self.broadcasts('CLOSE')),1);self.assertFalse(self.broadcasts('OPEN'))
    def test_audio_dump_failure_preserves_state(self):
        self.runfx('sync');old=(self.state/'attached.tsv').read_text();self.android['dump_fail']=True;self.save();self.clearcalls();self.runfx('sync',expected=3);self.assertEqual((self.state/'attached.tsv').read_text(),old);self.assertFalse(self.broadcasts())
    def test_hung_android_command_is_killed_by_timeout(self):
        self.android['dump_hang']=True;self.save();start=time.monotonic();self.runfx('attach',expected=3);self.assertLess(time.monotonic()-start,11);self.assertFalse(self.broadcasts())
    def test_concurrent_refreshes_are_serialized(self):
        self.android['am_delay']=0.5;self.save()
        first=subprocess.Popen(['sh',str(self.module/'system/bin/sefx'),'attach'],env=self.env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            for _ in range(100):
                if self.broadcasts('OPEN'):break
                time.sleep(0.01)
            self.runfx('attach',expected=5)
            out,err=first.communicate(timeout=10);self.assertEqual(first.returncode,0,out+err);self.assertEqual(len(self.broadcasts('OPEN')),1)
        finally:
            if first.poll() is None:first.kill();first.wait()
    def test_unknown_dump_preserves_state(self):
        self.runfx('sync');old=(self.state/'attached.tsv').read_text();self.android['audio']='Error dumping service';self.save();self.clearcalls();self.runfx('sync',expected=3);self.assertEqual((self.state/'attached.tsv').read_text(),old)
    def test_packages_failure_preserves_state(self):
        self.runfx('sync');old=(self.state/'attached.tsv').read_text();self.android['packages_fail']=True;self.save();self.clearcalls();self.runfx('sync',expected=3);self.assertEqual((self.state/'attached.tsv').read_text(),old)
    def test_broadcast_failure_not_reported_as_attached(self):
        self.android['am_fail']=True;self.save();self.runfx('attach',expected=3);self.assertEqual((self.state/'attached.tsv').read_text(),'')
    def test_broadcast_nonzero_exit_is_failure(self):
        self.android.update(am_fail=True,am_exit=1);self.save();self.runfx('attach',expected=3)
    def test_unconfirmed_broadcast_is_failure(self):
        self.android['am_unconfirmed']=True;self.save();self.runfx('attach',expected=3)
    def test_failed_attach_is_retried_next_poll(self):
        self.android['am_fail']=True;self.save();self.runfx('sync',expected=3);self.android['am_fail']=False;self.save();self.clearcalls();self.runfx('sync');self.assertEqual(len(self.broadcasts('OPEN')),1)
    def test_panel_error_even_with_zero_exit_is_failure(self):
        self.android['panel_fail']=True;self.save();self.runfx('open',expected=3)
    def test_root_required(self):
        self.android['root']=False;self.save();self.runfx('attach',expected=1);self.assertFalse(self.broadcasts())
    def test_missing_sony_package_is_failure(self):
        self.android['packages']=f'package:{PLAYER} uid:10123\n';self.save();self.runfx('attach',expected=3)
    def test_disabled_module_does_not_attach(self):
        (self.module/'disable').touch();self.runfx('attach',expected=3);self.assertFalse(self.broadcasts())
    def test_pending_removal_does_not_attach(self):
        (self.module/'remove').touch();self.runfx('attach',expected=3);self.assertFalse(self.broadcasts())
    def test_live_lock_not_stolen(self):
        with (self.state/'attach.flock').open('w') as fd:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.runfx('attach',expected=5);self.assertFalse(self.broadcasts())

    def test_dead_lock_recovered(self):
        d=self.state/'attach.lock';d.mkdir();(d/'pid').write_text('2147483647');self.runfx('attach');self.assertTrue(d.exists())

    def fake_proc(self,boot='boot-A',start='900'):
        proc=self.root/'proc';(proc/'sys/kernel/random').mkdir(parents=True,exist_ok=True)
        (proc/'sys/kernel/random/boot_id').write_text(boot)
        p=proc/str(os.getpid());p.mkdir(exist_ok=True)
        (p/'stat').write_text(f'{os.getpid()} (a name with spaces) S '+' '.join(['0']*18)+f' {start} 0\n')
        self.env['SEFX_PROC_DIR']=str(proc);return proc
    def test_pid_reused_after_crash_does_not_block_refresh(self):
        self.fake_proc();d=self.state/'attach.lock';d.mkdir();(d/'pid').write_text(str(os.getpid()));(d/'token').write_text('old-boot:300')
        self.runfx('attach');self.assertTrue(d.exists())

    def test_stale_legacy_pid_metadata_does_not_override_kernel_lock(self):
        self.fake_proc();d=self.state/'attach.lock';d.mkdir();(d/'pid').write_text(str(os.getpid()));(d/'token').write_text('boot-A:900')
        self.runfx('attach');self.assertTrue(d.exists())

    def test_reboot_invalidates_attachment_cache_even_with_same_pids(self):
        proc=self.fake_proc();self.runfx('sync');self.clearcalls();(proc/'sys/kernel/random/boot_id').write_text('boot-B');self.runfx('sync');self.assertEqual(len(self.broadcasts('OPEN')),1)
    def test_unlocked_kernel_lock_file_is_not_mistaken_for_live_lock(self):
        (self.state/'attach.flock').touch();self.runfx('attach')

    def test_old_empty_lock_recovered(self):
        d=self.state/'attach.lock';d.mkdir();os.utime(d,(1,1));self.runfx('attach')
    def test_zero_pid_is_not_a_live_owner(self):
        d=self.state/'attach.lock';d.mkdir();(d/'pid').write_text('0');self.runfx('attach')
    def test_symlink_lock_refused(self):
        (self.state/'attach.flock').symlink_to(self.root);self.runfx('attach',expected=3)

    def test_config_does_not_execute_shell(self):
        sentinel=self.root/'injected';self.config(f'auto=0\ninterval=$(touch {sentinel})\nrefresh_interval=1\n')
        self.runfx('status');self.assertFalse(sentinel.exists())
    def test_private_state_and_report_modes(self):
        self.runfx('doctor');self.assertEqual(self.state.stat().st_mode&0o777,0o700);self.assertEqual((self.state/'diagnostics.txt').stat().st_mode&0o777,0o600)
    def test_diagnostics_contain_audio_engine_and_runtime_evidence(self):
        self.runfx('attach');self.runfx('doctor');s=(self.state/'diagnostics.txt').read_text()
        for v in ['AUDIO FLINGER','MEDIA SESSIONS','SELinux: Enforcing',PLAYER,'RECENT LOGCAT']:self.assertIn(v,s)
    def test_event_log_rotation_is_bounded(self):
        (self.state/'events.log').write_text('a'*65537);self.runfx('attach');self.assertTrue((self.state/'events.previous.log').exists());self.assertLess((self.state/'events.log').stat().st_size,1000)
    def test_auto_off_persists(self):
        self.runfx('auto','off');self.assertIn('auto=0',(self.state/'config').read_text())
    def test_auto_on_requests_watcher(self):
        self.runfx('auto','on');self.assertIn('auto=1',(self.state/'config').read_text())
    def test_watch_loop_exits_cleanly_without_recursion(self):
        self.config('auto=1\n');self.android['stop_after']=2;self.save();self.runfx('watch');self.assertFalse((self.state/'watch.lock').exists());self.assertEqual(len(self.broadcasts('OPEN')),1)
    def test_old_empty_watch_lock_recovered(self):
        self.config('auto=1\n');d=self.state/'watch.lock';d.mkdir();os.utime(d,(1,1));self.android['stop_after']=1;self.save();self.runfx('watch');self.assertFalse((self.state/'watch.pid').exists())

    def test_live_watch_kernel_lock_not_stolen(self):
        self.config('auto=1\n')
        with (self.state/'watch.flock').open('w') as fd:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);self.runfx('watch',expected=5)

    def test_watch_does_not_open_user_interface(self):
        self.config('auto=1\n');self.android['stop_after']=1;self.save();self.runfx('watch');self.assertFalse(any(x[1]=='start-activity' for x in self.calls('am')))
    def test_invalid_command(self):self.runfx('nonsense',expected=2)
    def test_invalid_auto_argument(self):self.runfx('auto','nonsense',expected=2)

if __name__=='__main__':unittest.main()
