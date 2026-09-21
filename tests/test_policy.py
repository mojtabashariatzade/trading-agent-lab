import unittest
from agentops.policy import approval_required_reasons, validate_changes


class PolicyTests(unittest.TestCase):
    def test_allows_scoped_add(self):
        self.assertTrue(validate_changes([{'filename': 'trading_lab/data/a.py', 'status': 'added'}], ['trading_lab/data/'])[0])

    def test_hard_blocks_out_of_scope_even_if_github(self):
        self.assertFalse(validate_changes([{'filename': '.github/workflows/ci.yml', 'status': 'modified'}], ['trading_lab/'])[0])

    def test_protected_in_scope_passes_validate_but_needs_approval(self):
        files = [{'filename': 'agentops/policy.py', 'status': 'modified'}]
        self.assertTrue(validate_changes(files, ['agentops/'])[0])
        self.assertTrue(any('protected' in r for r in approval_required_reasons(files)))

    def test_safe_agentops_controller_does_not_require_approval(self):
        files = [{'filename': 'agentops/controller.py', 'status': 'modified'}]
        self.assertTrue(validate_changes(files, ['agentops/'])[0])
        self.assertEqual(approval_required_reasons(files), [])

    def test_selfheal_prefix_does_not_require_approval(self):
        files = [{'filename': 'agentops/selfheal/maintenance.py', 'status': 'modified'}]
        self.assertTrue(validate_changes(files, ['agentops/selfheal/'])[0])
        self.assertEqual(approval_required_reasons(files), [])

    def test_tests_under_test_prefix_need_approval(self):
        files = [{'filename': 'tests/test_policy.py', 'status': 'modified'}]
        self.assertTrue(validate_changes(files, ['tests/'])[0])
        self.assertTrue(approval_required_reasons(files))

    def test_deletion_needs_approval_not_hard_block(self):
        files = [{'filename': 'trading_lab/data/a.py', 'status': 'removed'}]
        self.assertTrue(validate_changes(files, ['trading_lab/data/'])[0])
        self.assertTrue(any('destructive' in r for r in approval_required_reasons(files)))

    def test_rename_needs_approval(self):
        files = [{'filename': 'trading_lab/data/a.py', 'status': 'renamed'}]
        self.assertTrue(validate_changes(files, ['trading_lab/data/'])[0])
        self.assertTrue(approval_required_reasons(files))

    def test_path_escape_blocked(self):
        self.assertFalse(validate_changes([{'filename': 'trading_lab/data/../../agentops/a.py', 'status': 'added'}], ['trading_lab/data/'])[0])

    def test_outside_scope_blocked(self):
        self.assertFalse(validate_changes([{'filename': 'trading_lab/other/a.py', 'status': 'added'}], ['trading_lab/data/'])[0])

    def test_empty_blocked(self):
        self.assertFalse(validate_changes([], ['trading_lab/'])[0])

    def test_secret_like_hard_blocked(self):
        self.assertFalse(validate_changes([{'filename': 'trading_lab/data/.env', 'status': 'added'}], ['trading_lab/data/'])[0])

    def test_live_trading_marker_needs_approval(self):
        files = [{'filename': 'trading_lab/data/live_trading_hook.py', 'status': 'added'}]
        self.assertTrue(validate_changes(files, ['trading_lab/data/'])[0])
        self.assertTrue(any('live_trading' in r for r in approval_required_reasons(files)))
