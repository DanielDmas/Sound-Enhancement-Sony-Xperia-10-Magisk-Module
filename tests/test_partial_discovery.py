"""An unresolved player must not block unrelated, identifiable playback."""
from test_sessions import AndroidFixture, PLAYER, SONY, record

OTHER='com.other.player'

class PartialDiscovery(AndroidFixture):
    def setUp(self):
        super().setUp()
        self.android['packages']+=f'package:{OTHER} uid:10124\n'
        self.android['processes']+=f'3456 {OTHER}\n';self.save()

    def test_unknown_session_in_other_player_does_not_block_music(self):
        self.android['audio']+=record(uid=10124,pid=3456,sid=0,piid=11);self.save()
        self.runfx('sync');self.assertEqual(len(self.broadcasts('OPEN')),1)
        self.assertIn(PLAYER,self.broadcasts('OPEN')[0])

    def test_preserves_only_uncertain_owner_while_repairing_known_player(self):
        self.android['audio']+=record(uid=10124,pid=3456,sid=88,piid=11);self.save();self.runfx('sync')
        self.android['audio']='players:\n'+record(sid=78)+record(uid=10124,pid=3456,sid=0,piid=11)
        self.save();self.clearcalls();self.runfx('sync')
        self.assertEqual(len(self.broadcasts('CLOSE')),1);self.assertIn(PLAYER,self.broadcasts('CLOSE')[0])
        self.assertEqual(len(self.broadcasts('OPEN')),1);self.assertIn('78',self.broadcasts('OPEN')[0])
        self.assertIn(OTHER,(self.state/'attached.tsv').read_text())

    def test_recovery_from_unresolved_state_renews_same_session(self):
        self.runfx('sync');self.android['audio']='players:\n'+record(sid=0);self.save()
        self.runfx('sync',expected=4)
        self.android['audio']='players:\n'+record();self.save();self.clearcalls();self.runfx('sync')
        self.assertEqual(len(self.broadcasts('OPEN')),1)

    def test_partial_discovery_does_not_spam_stable_known_player(self):
        self.android['audio']+=record(uid=10124,pid=3456,sid=0,piid=11);self.save()
        self.runfx('sync');self.clearcalls();self.runfx('sync');self.assertFalse(self.broadcasts())

    def test_device_order_is_canonical_and_does_not_rebuild(self):
        self.android['audio']='players:\n'+record(device=8)+record(device=2,piid=11);self.save();self.runfx('sync')
        self.android['audio']='players:\n'+record(device=2,piid=11)+record(device=8);self.save()
        self.clearcalls();self.runfx('sync');self.assertFalse(self.broadcasts())

    def test_duplicate_session_pid_choice_is_deterministic(self):
        self.android['processes']+=f'3457 {PLAYER}:playback\n'
        self.android['audio']='players:\n'+record(pid=3457)+record(piid=11);self.save();self.runfx('sync')
        self.android['audio']='players:\n'+record(piid=11)+record(pid=3457);self.save()
        self.clearcalls();self.runfx('sync');self.assertFalse(self.broadcasts())

    def test_sony_internal_zero_session_does_not_block_player(self):
        self.android['processes']+=f'4567 {SONY}\n'
        self.android['audio']+=record(uid=10077,pid=4567,sid=0,piid=12);self.save()
        self.runfx('sync');self.assertEqual(len(self.broadcasts('OPEN')),1)

    def test_partial_tracks_for_same_uid_do_not_duplicate_cached_rows(self):
        self.runfx('sync');self.android['audio']+=record(sid=0,piid=11);self.save()
        self.runfx('sync');rows=(self.state/'attached.tsv').read_text().splitlines()
        self.assertEqual(len(rows),1)
