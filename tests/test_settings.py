from dataclasses import replace
import unittest
from agentops.config import Settings
from tests.fakes import REPO


class SettingsTests(unittest.TestCase):
    def setUp(self): self.s=Settings(REPO,'a','b','1:c',42,frozenset({42}))
    def test_launch_is_off_by_default(self): self.assertFalse(self.s.allow_runs)
    def test_phase_escalation_not_an_environment_switch(self):
        with self.assertRaises(ValueError): replace(self.s,max_phase=2)
    def test_excessive_launch_cap_rejected(self):
        with self.assertRaises(ValueError): replace(self.s,max_daily_launches=1000)
    def test_unbounded_retries_rejected(self):
        with self.assertRaises(ValueError): replace(self.s,max_attempts=1000)
    def test_empty_owner_rejected(self):
        with self.assertRaises(ValueError): replace(self.s,owner_ids=frozenset())
    def test_repository_path_injection_rejected(self):
        with self.assertRaises(ValueError): replace(self.s,repo='x/y?token=abc')
