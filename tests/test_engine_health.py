"""Source-derived 12L dump grammar and recovery decisions, not DSP simulation."""
import os, pathlib, subprocess, unittest
from test_sessions import AndroidFixture, REPO, SONY, record

UUID='af8da7e0-2ca1-11e3-b71d-0002a5d5c51b'
HEADER='Output thread 0x1234, name AudioOut_D, tid 888, type 0 (MIXER):\n  1 Effect Chains\n'
def effect(session=0,pid=780,control='yes',enabled='y',suspended='n',status=0,uuid=UUID):
    # Literal labels and column order from lineage-19.1 Effects.cpp.
    return f'''    1 effects for session {session}
\tEffect ID 42:
\t\tSession State Registered Enabled Suspended:
\t\t{session:05d}   004   y          {enabled}       {suspended}
\t\tDescriptor:
\t\t- UUID: {uuid}
\t\t- TYPE: 00000000-0000-0000-0000-000000000000
\t\t- name: Sony
\t\t- implementor: Sony
\t\t1 Clients:
\t\t\t  Pid Priority Ctrl Locked client server
\t\t\t{pid}    0  {control}    yes  0  0
\t\tStatus Engine:
\t\t{status:03d}    0x123456
\tEffect ID 42 HAL dump:
'''

class EngineParser(unittest.TestCase):
    def parse(self,text,sessions='0',pids='780',awk='awk'):
        cmd=[awk,'-v','sessions='+sessions,'-v','pids='+pids,'-f',str(REPO/'sefx/engine.awk')]
        r=subprocess.run(cmd,input=text,text=True,capture_output=True,check=True)
        return r.stdout.split('|')[0]
    def test_native_global_engine_ready(self):self.assertEqual(self.parse(HEADER+effect()),'ready')
    def test_matching_player_engine(self):self.assertEqual(self.parse(HEADER+effect(session=77),'77'),'ready')
    def test_wrong_native_session_is_missing(self):self.assertEqual(self.parse(HEADER+effect(session=77)),'missing')
    def test_other_owner_is_conflict(self):self.assertEqual(self.parse(HEADER+effect(pid=781)),'conflict')
    def test_pid_substring_is_not_ownership(self):self.assertEqual(self.parse(HEADER+effect(pid=1780)),'conflict')
    def test_no_controlling_handle_is_unknown(self):self.assertEqual(self.parse(HEADER+effect(control='no')),'unknown')
    def test_user_disabled_is_not_failure(self):self.assertEqual(self.parse(HEADER+effect(enabled='n')),'disabled')
    def test_disabled_failed_engine_does_not_override_user_off(self):self.assertEqual(self.parse(HEADER+effect(enabled='n',status=-19)),'disabled')
    def test_framework_suspension_is_not_missing(self):self.assertEqual(self.parse(HEADER+effect(suspended='y')),'suspended')
    def test_failed_engine(self):self.assertEqual(self.parse(HEADER+effect(status=-19)),'failed')
    def test_empty_complete_chain_list(self):self.assertEqual(self.parse(HEADER.replace('1 Effect Chains','0 Effect Chains')),'missing')
    def test_library_uuid_listing_is_not_live_effect(self):self.assertEqual(self.parse(HEADER.replace('1 Effect Chains','0 Effect Chains')+UUID),'missing')
    def test_unknown_uuid_is_not_sony(self):self.assertEqual(self.parse(HEADER+effect(uuid='00000000-0000-0000-0000-000000000000')),'missing')
    def test_truncated_client_table_is_unknown(self):self.assertEqual(self.parse(HEADER+effect().replace('1 Clients','2 Clients')),'unknown')
    def test_truncated_engine_is_unknown(self):self.assertEqual(self.parse(HEADER+effect().split('Status Engine:')[0]),'unknown')
    def test_missing_chain_body_is_unknown(self):self.assertEqual(self.parse(HEADER),'unknown')
    def test_missing_effect_body_is_unknown(self):self.assertEqual(self.parse(HEADER+'1 effects for session 0\n'),'unknown')
    def test_broken_session_row_is_unknown(self):self.assertEqual(self.parse(HEADER+effect().replace('00000   004','broken row')),'unknown')
    def test_lock_failure_is_unknown(self):self.assertEqual(self.parse(HEADER+effect()+'Could not lock mutex:\n'),'unknown')
    def test_thread_lock_failure_is_unknown(self):self.assertEqual(self.parse(HEADER+effect()+'Thread may be deadlocked\n'),'unknown')
    def test_unsupported_format_is_unknown(self):self.assertEqual(self.parse('Sony enabled '+UUID),'unknown')
    def test_all_expected_sessions_required(self):self.assertEqual(self.parse(HEADER+effect(session=77),'77,78'),'missing')
    def test_hal_dump_cannot_supply_control_table(self):
        text=HEADER+effect().replace('780    0  yes','780    0  no')+'780    0 yes yes 0 0\n'
        self.assertEqual(self.parse(text),'unknown')

class EngineRecovery(AndroidFixture):
    def setUp(self):
        super().setUp();self.proc=self.root/'proc';self.proc.mkdir();self.env['SEFX_PROC_DIR']=str(self.proc)
        self.android['props']={'ro.sony.global.effect':'true'};self.android['flinger']=HEADER.replace('1 Effect Chains','0 Effect Chains')
        self.clock(100);self.save()
    def clock(self,n):(self.proc/'uptime').write_text(f'{n}.0 0.0\n')
    def poll(self,n):self.clock(n);return self.runfx('sync')
    def test_two_missing_observations_rebuild_without_ui(self):
        self.poll(100);self.clearcalls();self.poll(116);self.assertFalse(self.broadcasts())
        self.poll(132);self.assertEqual(len(self.broadcasts('CLOSE')),1);self.assertEqual(len(self.broadcasts('OPEN')),1)
        self.assertFalse(any(x[1]=='start-activity' for x in self.calls('am')))
    def test_ready_engine_does_not_rebuild(self):
        self.android['flinger']=HEADER+effect();self.save();self.poll(100);self.clearcalls();self.poll(116);self.poll(132)
        self.assertFalse(self.broadcasts());self.assertIn('ready|',(self.state/'engine-health.txt').read_text())
    def test_unknown_disabled_suspended_conflict_do_not_rebuild(self):
        for dump in ['Unsupported',HEADER+effect(enabled='n'),HEADER+effect(suspended='y'),HEADER+effect(pid=781)]:
            with self.subTest(dump=dump[:25]):
                (self.state/'engine-recovery').unlink(missing_ok=True);self.android['flinger']=dump;self.save()
                self.poll(100);self.clearcalls();self.poll(116);self.poll(132);self.assertFalse(self.broadcasts())
    def test_failed_dump_is_unknown(self):
        self.android['flinger_exit']=1;self.save();self.poll(100);self.clearcalls();self.poll(116);self.poll(132)
        self.assertFalse(self.broadcasts());self.assertIn('unknown|',(self.state/'engine-health.txt').read_text())
    def test_oversized_dump_is_unknown(self):
        self.android['flinger']=HEADER+'x'*1048576;self.save();self.poll(100);self.poll(116)
        self.assertIn('unknown|',(self.state/'engine-health.txt').read_text())
    def test_repair_budget_and_backoff(self):
        self.poll(100);self.poll(116);self.poll(132);self.clearcalls();self.poll(148);self.poll(164)
        self.assertFalse(self.broadcasts('CLOSE'));self.poll(196);self.assertEqual(len(self.broadcasts('CLOSE')),1)
        self.poll(212);self.poll(228);self.poll(316);self.clearcalls()
        self.poll(332);self.poll(348);self.poll(600);self.assertFalse(self.broadcasts('CLOSE'))
    def test_probe_does_not_repair_or_open_ui(self):
        self.runfx('health');self.assertFalse(self.broadcasts());self.assertIn('missing|',(self.state/'engine-health.txt').read_text())
    def test_manual_repair_resets_exhausted_budget(self):
        self.poll(100);cache=(self.state/'engine-recovery').read_text().split('|');cache[2]='3'
        (self.state/'engine-recovery').write_text('|'.join(cache));self.runfx('refresh')
        self.assertFalse((self.state/'engine-recovery').exists())
    def test_corrupt_recovery_cache_does_not_execute(self):
        self.poll(100);(self.state/'engine-recovery').write_text('$(reboot)|x|999999999999|0|0')
        self.poll(116);self.assertFalse(self.calls('reboot'))
    def test_representative_does_not_flip_when_new_id_sorts_first(self):
        self.poll(100);self.android['audio']+=record(sid=1,piid=20);self.save();self.clearcalls();self.poll(101)
        self.assertFalse(self.broadcasts());self.assertIn('|77|',(self.state/'attached.tsv').read_text())
    def test_global_mode_does_not_create_competing_package_holders(self):
        self.android['packages']+='package:com.other.player uid:10124\n'
        self.android['processes']+='3456 com.other.player\n'
        self.poll(100);self.android['audio']+=record(uid=10124,pid=3456,sid=88,piid=20);self.save()
        self.clearcalls();self.poll(101);self.assertFalse(self.broadcasts())
        self.runfx('open','com.other.player');self.assertEqual(len(self.broadcasts('CLOSE')),1)
        self.assertEqual(len(self.broadcasts('OPEN')),1)
        self.assertIn('com.other.player',self.broadcasts('OPEN')[0])
    def test_sony_mode_unknown_does_not_guess_global(self):
        self.android['props']={};self.save();r=self.runfx('health');self.assertIn('unknown',r.stdout)
    def test_health_state_symlink_refused(self):
        target=self.root/'keep';target.write_text('keep');(self.state/'engine-health.txt').symlink_to(target)
        self.runfx('health',expected=3);self.assertEqual(target.read_text(),'keep')

BUSYBOX=os.environ.get('SEFX_BUSYBOX','')
@unittest.skipUnless(BUSYBOX and os.getuid()==0,'requires official Magisk BusyBox and root')
class NativeEngineRecovery(EngineRecovery):
    def command(self,*args):
        self.env.update(ASH_STANDALONE='1',SEFX_SHELL='magisk_busybox')
        return [BUSYBOX,'sh',str(self.module/'system/bin/sefx'),*args]
