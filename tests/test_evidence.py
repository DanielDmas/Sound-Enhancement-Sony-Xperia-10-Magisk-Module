from test_sessions import AndroidFixture
from test_report_analysis import report

class Evidence(AndroidFixture):
    def setUp(self):
        super().setUp()
        self.directory=self.module/'system/vendor/etc';self.directory.mkdir(parents=True)
        self.path=self.directory/'audio_effects.xml'
        self.data=b'<audio_effects_conf><libraries/><effects/></audio_effects_conf>\n'
        self.path.write_bytes(self.data)
        self.env['SEFX_SYSTEM_ROOT']=str(self.root/'rom')

    def inspect(self):
        self.runfx('doctor');data=(self.state/'diagnostics.txt').read_bytes()
        return data,report.inspect_report(data)

    def test_exact_configuration_bytes_and_hash_are_captured(self):
        data,result=self.inspect();entry=result['configurations'][0]
        self.assertEqual(entry['path'],str(self.path));self.assertEqual(entry['bytes'],len(self.data))
        self.assertEqual(entry['included'],len(self.data));self.assertEqual(self.path.read_bytes(),self.data)
        self.assertIn(b'HARDWARE EFFECT NODE LABELS',data);self.assertIn(b'SONY PROCESS SECURITY CONTEXTS',data)

    def test_missing_proxy_in_the_real_capture_is_flagged(self):
        _,result=self.inspect();self.assertGreater(result['configuration_errors'],0)
        self.assertFalse(result['hardware_processing_verified'])

    def test_active_system_config_is_captured_separately(self):
        active=self.root/'rom/system/etc/audio_effects.xml';active.parent.mkdir(parents=True);active.write_bytes(self.data)
        _,result=self.inspect();self.assertEqual({x['kind'] for x in result['configurations']},{'module','active'})

    def test_oversized_configuration_is_explicitly_truncated(self):
        self.path.write_bytes(self.data+b' '*70000)
        _,result=self.inspect();entry=result['configurations'][0]
        self.assertEqual(entry['included'],65536);self.assertIn('Truncated snapshot; validation skipped',entry['errors'])

    def test_failed_rollback_backup_is_reported_and_never_deleted(self):
        backup=self.module/'.config.recovery';backup.mkdir()
        _,result=self.inspect();self.assertTrue(any('backup' in x for x in result['issues']));self.assertTrue(backup.exists())

    def test_capture_limit_is_reported(self):
        for n in range(25):(self.directory/f'audio_policy_{n}.xml').write_bytes(b'<root/>')
        data,result=self.inspect();self.assertEqual(len(result['configurations']),24)
        self.assertIn(b'CONFIG_SNAPSHOT_LIMIT_REACHED',data)
        self.assertTrue(any('omitted' in x for x in result['issues']))
