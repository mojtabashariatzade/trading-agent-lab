"""Named roles with independent research workers and fail-closed coding launches."""
from dataclasses import FrozenInstanceError
from pathlib import Path
import unittest
from unittest.mock import patch

from agentops.config import Settings
from agentops.controller import Controller
from agentops.store import Store
from agentops.team import (
    CLOUD_WORKER_ROLES, RESEARCH_ROLES, RESEARCH_WORKER_ROLES, TEAM,
    research_instructions, research_worker_profile, team_report, worker_identity,
    worker_profile,
)
from tests.fakes import (
    HEAD, REPO, Clock, FakeCursor, FakeGitHub, FakeTelegram, backlog, update,
)


class NamedTeamTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Settings(
            REPO, 'fake-gh', 'fake-cursor', '1:fake', 42, frozenset({42}),
            state_path=':memory:', allow_runs=True,
            spend_limit_confirmed=True, protection_confirmed=True,
            autonomous_default=False, auto_merge_safe=False,
        )
        self.db = Store(':memory:')
        self.gh, self.cu, self.tg = FakeGitHub(), FakeCursor(), FakeTelegram()
        self.c = Controller(
            self.cfg, self.db, self.gh, self.cu, self.tg, backlog(), clock=Clock(),
        )

    def test_eight_unique_profiles(self):
        self.assertEqual(len(TEAM), 8)
        self.assertEqual(len({p.name_fa for p in TEAM.values()}), 8)
        self.assertEqual(len({p.name_en for p in TEAM.values()}), 8)
        for key, profile in TEAM.items():
            self.assertEqual(profile.role_id, key)

    def test_registry_is_read_only(self):
        with self.assertRaises(TypeError):
            TEAM['dev'] = TEAM['qa']
        with self.assertRaises(FrozenInstanceError):
            TEAM['dev'].name_en = 'Different'

    def test_every_role_document_exists(self):
        root = Path(__file__).resolve().parents[1]
        for profile in TEAM.values():
            text = (root / profile.instructions).read_text(encoding='utf-8')
            self.assertIn(profile.name_en, text)

    def test_only_developer_and_qa_are_coding_workers(self):
        self.assertEqual(CLOUD_WORKER_ROLES, frozenset({'dev', 'qa'}))
        for role in CLOUD_WORKER_ROLES:
            self.assertEqual(worker_profile(role), TEAM[role])
        for role in set(TEAM) - CLOUD_WORKER_ROLES:
            with self.assertRaises(ValueError):
                worker_profile(role)

    def test_research_workers_are_first_class(self):
        self.assertEqual(set(RESEARCH_ROLES), {'quant', 'fundamental', 'data'})
        self.assertEqual(RESEARCH_WORKER_ROLES, frozenset(RESEARCH_ROLES))
        for role in RESEARCH_ROLES:
            self.assertEqual(TEAM[role].runtime_mode, 'research_worker_after_setup')
            self.assertEqual(research_worker_profile(role), TEAM[role])
        with self.assertRaises(ValueError):
            research_worker_profile('dev')

    def test_research_instruction_points_to_artifacts(self):
        text = research_instructions()
        for role in RESEARCH_ROLES:
            self.assertIn(TEAM[role].name_en, text)
            self.assertIn(TEAM[role].instructions, text)
        self.assertIn('approved research artifacts', text)
        self.assertIn('Do not invent', text)

    def test_unknown_worker_identity_rejected(self):
        with self.assertRaises(ValueError):
            worker_identity('unregistered')

    def test_roster_lines_are_rtl_and_fit_telegram(self):
        text = team_report({'core': 'PAUSED', 'dev': 'IDLE'})
        self.assertLess(len(text), 4096)
        for line in text.splitlines():
            self.assertTrue(line.startswith('\u200f'))
        for profile in TEAM.values():
            self.assertIn(profile.name_fa, text)
        self.assertIn('PAUSED', text)

    def test_owner_team_command_does_not_launch_or_unpause(self):
        self.c.handle(update('/team'))
        self.c.flush()
        self.assertEqual(self.cu.created, [])
        self.assertTrue(self.db.get('paused'))
        self.assertTrue(self.tg.sent)
        self.assertIn(TEAM['fundamental'].name_fa, self.tg.sent[0][1])
        self.assertEqual(self.db.launch_count(self.c.day()), 0)

    def test_unauthorized_team_command_is_not_answered(self):
        self.c.handle(update('/team', owner=999))
        self.c.flush()
        self.assertEqual(self.tg.sent, [])
        self.assertEqual(self.cu.created, [])

    def test_developer_prompt_has_kian_and_research_artifact_rules(self):
        text = self.c.prompt(self.db.task('T001'), 'dev')
        self.assertIn('Kian', text)
        self.assertIn(TEAM['dev'].name_fa, text)
        self.assertIn('stable role ID: dev', text)
        self.assertIn('agents/FUNDAMENTAL.md', text)
        self.assertIn('approved research artifacts', text)

    def test_qa_prompt_is_named_and_remains_independent(self):
        text = self.c.prompt({'id': 'T001', 'pr': 7, 'head_sha': HEAD}, 'qa')
        self.assertIn('Negar', text)
        self.assertIn(TEAM['qa'].name_fa, text)
        self.assertIn('Do not modify files', text)
        self.assertIn('you cannot approve a merge', text)
        self.assertIn('research', text.lower())
        self.assertNotIn('Implement only this task', text)

    def test_cloud_title_uses_name_without_changing_role_id(self):
        with patch.object(self.cu, 'create', wraps=self.cu.create) as create:
            self.c.handle(update('/resume'))
            self.c.tick()
            self.assertTrue(create.call_args.args[1].startswith('Kian | DEV T001'))
        self.assertEqual(self.db.task('T001')['role'], 'dev')

    def test_event_is_signed_by_raha_and_identifies_actual_worker(self):
        self.c.handle(update('/resume'))
        self.c.tick()
        self.c.flush()
        text = '\n'.join(item[1] for item in self.tg.sent)
        self.assertIn(TEAM['support'].name_fa, text)
        self.assertIn(TEAM['dev'].name_fa, text)

    def test_controller_event_identifies_arman(self):
        self.c.event(self.db.task('T001'), 'CHECK', 'Local test event')
        self.c.flush()
        self.assertIn(TEAM['core'].name_fa, self.tg.sent[0][1])

    def test_status_report_has_raha_signature(self):
        self.assertIn(TEAM['support'].name_fa, self.c.report())

    def test_research_roles_cannot_use_coding_launch(self):
        for role in RESEARCH_ROLES:
            with self.assertRaises(ValueError):
                self.c.launch(self.db.task('T001'), role)
        self.assertEqual(self.cu.created, [])
        self.assertEqual(self.db.launch_count(self.c.day()), 0)
        self.assertEqual(self.db.task('T001')['state'], 'PENDING')

    def test_names_do_not_change_backlog_or_phase_gate(self):
        original_digest = self.db.get('backlog_digest')
        self.c.handle(update('/team'))
        Controller(self.cfg, self.db, self.gh, self.cu, self.tg, backlog(), clock=Clock())
        self.assertEqual(self.db.get('backlog_digest'), original_digest)
        self.assertEqual(self.db.task('T002')['phase'], 2)
        self.assertEqual(self.db.task('T002')['state'], 'PENDING')


if __name__ == '__main__':
    unittest.main()
