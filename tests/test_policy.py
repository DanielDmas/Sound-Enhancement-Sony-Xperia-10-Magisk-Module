import importlib.util,json,pathlib,unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('policy_checker',ROOT/'tools/policy_check.py')
policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)

class PolicyReduction(unittest.TestCase):
    def setUp(self):
        self.text=(ROOT/'sepolicy.rule').read_text()
        self.baseline=json.loads((ROOT/'tools/policy_baseline.json').read_text())

    def test_policy_reduction_preserves_all_other_grants(self):
        r=policy.check(self.text,self.baseline)
        self.assertTrue(r['non_untrusted_grants_unchanged']);self.assertEqual(r['removed_grants'],171)

    def test_new_ordinary_app_grants_are_rejected(self):
        with self.assertRaises(ValueError):policy.check(self.text+'\nallow untrusted_app device chr_file write\n',self.baseline)

    def test_unrelated_policy_changes_are_rejected(self):
        with self.assertRaises(ValueError):policy.check(self.text+'\nallow new_domain device chr_file write\n',self.baseline)

    def test_wildcard_policy_is_not_accepted(self):
        with self.assertRaises(ValueError):policy.grants('allow * * * *')
