import base64, hashlib, importlib.util, pathlib, unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('report_inspector',ROOT/'tools/inspect_audio_report.py')
report=importlib.util.module_from_spec(spec);spec.loader.exec_module(report)

def snapshot(data,path='/vendor/etc/audio_effects.xml',kind='active',original=None,digest=None):
    name=base64.b64encode(path.encode()).decode()
    h=digest or hashlib.sha256(data).hexdigest()
    return f'CONFIG_SNAPSHOT v1 {kind} {name} {h} {len(data) if original is None else original} {len(data)}\n'.encode()+base64.b64encode(data)+b'\nEND_CONFIG_SNAPSHOT\n'

class ReportAnalysis(unittest.TestCase):
    def test_well_formed_snapshot_has_no_acoustic_claim(self):
        r=report.inspect_report(snapshot(b'<audio_effects_conf><libraries/><effects/></audio_effects_conf>'))
        self.assertEqual(r['configuration_errors'],0);self.assertFalse(r['hardware_processing_verified'])

    def test_malformed_xml_is_identified(self):
        r=report.inspect_report(snapshot(b'<audio_effects_conf><libraries></audio_effects_conf>'))
        self.assertGreater(r['configuration_errors'],0)

    def test_unresolved_effect_library_is_identified(self):
        r=report.xml_check(b'<audio_effects_conf><libraries/><effects><effect name="eq" library="missing"/></effects></audio_effects_conf>')
        self.assertTrue(any('Missing library' in x for x in r['errors']))

    def test_duplicate_effect_names_are_rejected(self):
        r=report.xml_check(b'<audio_effects_conf><effects><effect name="eq"/><effect name="eq"/></effects></audio_effects_conf>')
        self.assertIn('Duplicate effect: eq',r['errors'])

    def test_missing_effect_attributes_are_not_treated_as_valid(self):
        r=report.xml_check(b'<audio_effects_conf><libraries/><effects><effect name="eq"/></effects></audio_effects_conf>')
        self.assertIn('Missing library attribute for eq',r['errors']);self.assertIn('Missing/invalid UUID for eq',r['errors'])

    def test_missing_required_sections_are_not_treated_as_valid(self):
        r=report.xml_check(b'<audio_effects_conf/>')
        self.assertIn('Expected one libraries section',r['errors']);self.assertIn('Expected one effects section',r['errors'])

    def test_missing_sony_proxy_in_module_is_identified(self):
        r=report.inspect_report(snapshot(b'<audio_effects_conf><effects/></audio_effects_conf>',kind='module'))
        self.assertGreater(r['configuration_errors'],0)

    def test_undefined_apply_is_identified(self):
        r=report.xml_check(b'<audio_effects_conf><effects/><postprocess><stream><apply effect="missing"/></stream></postprocess></audio_effects_conf>')
        self.assertTrue(any('Unresolved apply' in x for x in r['errors']))

    def test_bad_policy_route_is_identified(self):
        r=report.xml_check(b'<audioPolicyConfiguration><module name="primary"><mixPorts><mixPort name="known"/></mixPorts><routes><route sink="known" sources="missing"/></routes></module></audioPolicyConfiguration>')
        self.assertIn('Unknown route endpoint: missing',r['errors'])

    def test_truncation_is_not_reported_as_valid_xml(self):
        r=report.inspect_report(snapshot(b'<root/>',original=100))
        self.assertIn('Truncated snapshot; validation skipped',r['configurations'][0]['errors'])

    def test_integrity_mismatch_is_not_parsed(self):
        r=report.inspect_report(snapshot(b'<root/>',digest='0'*64))
        self.assertFalse(r['configurations']);self.assertTrue(r['issues'])

    def test_report_paths_are_labels_and_never_opened(self):
        r=report.inspect_report(snapshot(b'<root/>',path='/etc/this-path-is-not-opened.xml'))
        self.assertEqual(r['configurations'][0]['path'],'/etc/this-path-is-not-opened.xml')

    def test_dtd_entities_are_refused_including_utf16(self):
        text='<!DOCTYPE x [<!ENTITY e "payload">]><x>&e;</x>'
        for data in [text.encode(),text.encode('utf-16')]:
            with self.subTest(data=data[:10]):self.assertTrue(report.xml_check(data)['errors'])

    def test_incomplete_capture_and_report_limit_are_explicit(self):
        self.assertTrue(report.inspect_report(b'CONFIG_SNAPSHOT v1 bad\n')['issues'])
        with self.assertRaises(ValueError):report.inspect_report(b'x'*(report.MAX_REPORT+1))

    def test_legacy_conf_comments_and_quoted_braces(self):
        self.assertFalse(report.conf_check(b'root {\nvalue "brace } inside string" # ignored }\n}\n')['errors'])
        self.assertTrue(report.conf_check(b'root { value x')['errors'])

    def test_recovery_backup_and_staged_upgrade_are_reported(self):
        r=report.inspect_report(b'CONFIG_RECOVERY path\nUPGRADE STAGED: reboot required.\n')
        self.assertTrue(any('backup' in x for x in r['issues']));self.assertTrue(any('reboot' in x for x in r['issues']))
