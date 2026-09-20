"""Research queue, gates, agent separation and Telegram reporting."""
import unittest

from agentops.config import Settings
from agentops.controller import Controller
from agentops.research import assert_not_decision_core, structural_review_gate
from agentops.research_contracts import ResearchKind, parse_research_report
from agentops.store import Store
from agentops.team import TEAM
from tests.fakes import REPO, Clock, FakeCursor, FakeGitHub, FakeTelegram, backlog, update


def strategy_report(research_id='R001'):
    return {
        'research_id': research_id,
        'status': 'COMPLETE',
        'question': 'Define mean-reversion assumptions for GBPJPY M15',
        'citations': [{
            'citation_id': 'c1',
            'publisher': 'Bank of England',
            'title': 'Monetary Policy Report',
            'url': 'https://www.bankofengland.co.uk/monetary-policy-report',
            'retrieved_at': '2026-09-20T00:00:00Z',
            'published_at': '2026-08-01',
        }],
        'findings': [{
            'claim': 'Strategy definitions must state entry, exit and invalidation.',
            'evidence_citation_ids': ['c1'],
            'confidence': 'MEDIUM',
            'limitations': 'No live performance claimed',
        }],
        'hypotheses': ['Spread widening reduces net expectancy'],
        'assumptions': ['M15 bars are causal'],
        'parameter_ranges': {'lookback': '10-40 bars'},
        'proposed_tests': ['Chronological walk-forward on development split only'],
        'unknowns': ['Exact cost regime'],
        'summary': 'Bounded strategy research note; UNTESTED.',
    }


def blocked_report(research_id='R001'):
    return {
        'research_id': research_id,
        'status': 'BLOCKED',
        'question': 'Need ONS CPI vintage history',
        'citations': [],
        'findings': [],
        'missing_dependency': 'ONS CPI point-in-time vintage API access unavailable',
        'summary': 'Cannot proceed without source access',
    }


class ResearchQueueTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Settings(
            REPO, 'fake-gh', 'fake-cursor', '1:fake', 42, frozenset({42}),
            state_path=':memory:', allow_runs=True,
            spend_limit_confirmed=True, protection_confirmed=True,
            autonomous_default=False, auto_merge_safe=False,
        )
        self.db = Store(':memory:')
        self.gh, self.cu, self.tg = FakeGitHub(), FakeCursor(), FakeTelegram()
        self.clock = Clock()
        self.c = Controller(
            self.cfg, self.db, self.gh, self.cu, self.tg, backlog(), clock=self.clock,
        )

    def test_arman_is_separate_from_decision_core(self):
        assert_not_decision_core()
        self.assertEqual(TEAM['core'].name_en, 'Arman')
        from pathlib import Path
        import agentops.controller as controller_mod
        text = Path(controller_mod.__file__).read_text(encoding='utf-8')
        self.assertNotIn('trading_lab.contracts.decide', text)
        self.assertNotIn('from trading_lab.contracts import decide', text)

    def test_request_assigns_parsa_for_strategy(self):
        task = self.c.request_research('STRATEGY', 'Study GBPJPY mean reversion definitions')
        self.assertEqual(task['id'], 'R001')
        self.assertEqual(task['owner_role'], 'quant')
        self.assertEqual(task['state'], 'PENDING')
        self.assertEqual(self.db.research('R001')['kind'], 'STRATEGY')

    def test_research_command_lists_owner_status_blockers(self):
        self.c.request_research('DATA', 'Validate bar timestamp semantics')
        self.c.handle(update('/research'))
        self.c.flush()
        text = self.tg.sent[-1][1]
        self.assertIn('R001', text)
        self.assertIn(TEAM['data'].name_fa, text)
        self.assertIn('PENDING', text)

    def test_research_request_command_queues_without_unpause_when_paused(self):
        self.c.handle(update('/research request FUNDAMENTAL BoE calendar timing and revisions'))
        self.c.flush()
        task = self.db.research('R001')
        self.assertEqual(task['owner_role'], 'fundamental')
        self.assertEqual(task['state'], 'PENDING')
        self.assertEqual(self.cu.created, [])
        self.assertTrue(self.db.get('paused'))

    def test_blocked_report_keeps_exact_dependency(self):
        self.c.request_research('FUNDAMENTAL', 'Need ONS CPI vintages for point-in-time tests')
        self.c.submit_research_report('R001', blocked_report())
        task = self.db.research('R001')
        self.assertEqual(task['state'], 'BLOCKED')
        self.assertIn('ONS CPI point-in-time', task['blocker'])
        self.c.handle(update('/research', uid=2))
        self.c.flush()
        self.assertIn('ONS CPI', self.tg.sent[-1][1])

    def test_complete_report_passes_gate_and_creates_artifact(self):
        self.c.request_research('STRATEGY', 'Define mean-reversion assumptions')
        task = self.c.submit_research_report('R001', strategy_report())
        self.assertEqual(task['state'], 'APPROVED')
        self.assertTrue(task['artifact_id'].startswith('A-R001-'))
        artifacts = self.c.approved_artifacts_for()
        self.assertEqual(len(artifacts), 1)

    def test_fabrication_marker_is_rejected(self):
        payload = strategy_report()
        payload['citations'][0]['url'] = 'https://example.com/fake'
        self.c.request_research('STRATEGY', 'Define mean-reversion assumptions')
        task = self.c.submit_research_report('R001', payload)
        self.assertEqual(task['state'], 'REJECTED')
        self.assertIn('fabrication', task['blocker'].lower())

    def test_kian_prompt_consumes_approved_artifact(self):
        self.c.request_research('STRATEGY', 'Define mean-reversion assumptions', linked_dev_task='T001')
        self.c.submit_research_report('R001', strategy_report())
        text = self.c.prompt(self.db.task('T001'), 'dev')
        self.assertIn('Approved research artifacts', text)
        self.assertIn('A-R001-', text)
        self.assertIn('Parsa', text)

    def test_negar_prompt_checks_research_evidence(self):
        self.c.request_research('STRATEGY', 'Define mean-reversion assumptions', linked_dev_task='T001')
        self.c.submit_research_report('R001', strategy_report())
        text = self.c.prompt({'id': 'T001', 'pr': 7, 'head_sha': 'a' * 40}, 'qa')
        self.assertIn('approved research artifacts', text.lower())
        self.assertIn('R001', text)
        self.assertIn('c1', text)

    def test_dev_waits_for_required_research(self):
        items = backlog()
        items[0]['requires_research'] = ['STRATEGY']
        db = Store(':memory:')
        c = Controller(self.cfg, db, self.gh, self.cu, self.tg, items, clock=self.clock)
        c.handle(update('/resume'))
        c.tick()
        self.assertEqual(db.task('T001')['state'], 'PENDING')
        research = db.research_tasks()
        self.assertEqual(len(research), 1)
        self.assertEqual(research[0]['kind'], 'STRATEGY')
        self.assertEqual(research[0]['linked_dev_task'], 'T001')
        # Research launch consumes the coding slot path but is a research worker.
        self.assertTrue(self.cu.created)
        self.assertIn('Parsa', self.cu.created[0]['prompt'])
        self.assertIn('independent RESEARCH worker', self.cu.created[0]['prompt'])
        self.assertEqual(db.task('T001')['state'], 'PENDING')

    def test_research_launch_uses_research_worker_not_coding_profile(self):
        self.c.handle(update('/resume'))
        task = self.c.request_research('DATA', 'Coverage and look-ahead audit for bars')
        self.c.launch_research(task)
        self.assertEqual(self.db.research('R001')['state'], 'RUNNING')
        self.assertIn('Saman', self.cu.created[-1]['prompt'])
        self.assertIn('look-ahead', self.cu.created[-1]['prompt'])
        with self.assertRaises(ValueError):
            self.c.launch(self.db.task('T001'), 'data')

    def test_raha_reports_research_progress(self):
        self.c.request_research('STRATEGY', 'Define mean-reversion assumptions')
        self.c.submit_research_report('R001', strategy_report())
        self.c.flush()
        joined = '\n'.join(msg[1] for msg in self.tg.sent)
        self.assertIn(TEAM['support'].name_fa, joined)
        self.assertIn('RESEARCH_APPROVED', joined)
        self.assertIn(TEAM['quant'].name_fa, joined)

    def test_team_command_shows_live_research_status(self):
        self.c.request_research('STRATEGY', 'Define mean-reversion assumptions')
        self.c.handle(update('/team', uid=2))
        self.c.flush()
        text = self.tg.sent[-1][1]
        self.assertIn('PENDING:R001', text)
        self.assertIn(TEAM['quant'].name_fa, text)

    def test_structural_gate_requires_data_coverage(self):
        report = parse_research_report(
            {
                'status': 'COMPLETE',
                'question': 'Coverage check',
                'citations': [{
                    'citation_id': 'd1',
                    'publisher': 'Internal archive note',
                    'title': 'No vendor connected yet',
                    'retrieved_at': '2026-09-20T00:00:00Z',
                }],
                'findings': [{
                    'claim': 'Provider history not downloaded in this offline receipt',
                    'evidence_citation_ids': ['d1'],
                    'confidence': 'HIGH',
                }],
                'coverage_notes': '',
                'look_ahead_risks': [],
                'summary': 'Incomplete data research',
            },
            research_id='R009',
            kind=ResearchKind.DATA,
            owner_role='data',
        )
        gate = structural_review_gate(report)
        self.assertEqual(gate['verdict'], 'REJECT')


if __name__ == '__main__':
    unittest.main()
