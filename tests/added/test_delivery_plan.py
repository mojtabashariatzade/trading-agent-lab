"""Planning tests only: no network, agents, billing or trading."""
import copy
from datetime import date
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('daily_preview', ROOT / 'scripts/plan_day.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DailyPlanTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads((ROOT / 'planning/delivery_plan.json').read_text())
        self.state = json.loads((ROOT / 'planning/delivery_state.json').read_text())

    def done(self, ident):
        self.state['records'][ident] = {'state':'DONE','completed_at':'2026-09-22T08:00:00Z','evidence':['fixture-only:test-receipt']}

    def test_full_thirty_day_schedule(self):
        module.validate(self.plan, self.state)
        self.assertEqual(len(self.plan['days']), 30)
        self.assertEqual(self.plan['days'][-1]['date'], '2026-10-21')

    def test_day_one_selects_existing_work(self):
        report = module.preview(self.plan, self.state, date(2026,9,22))
        self.assertEqual(report['selected'], {'product':'G01','research':'R01'})
        self.assertIn('NO_WORKER_STARTED', report['mode'])

    def test_unfinished_work_carries_over_not_reset(self):
        report = module.preview(self.plan, self.state, date(2026,9,25))
        self.assertEqual(report['selected']['product'], 'G01')
        self.assertIn('G01', report['overdue_original_targets'])

    def test_blocked_source_allows_independent_research(self):
        self.state['records']['R01']={
            'state':'BLOCKED',
            'blocker':'Provider archive permissions unresolved',
            'blocker_owner':'Data provider administrator',
            'unblock_condition':'Grant archive permissions for bounded historical sample',
            'blocked_by':['ISSUE-37-ACCESS'],
        }
        report = module.preview(self.plan, self.state, date(2026,9,25))
        self.assertEqual(report['selected']['research'], 'R03')

    def test_completion_unblocks_dependency(self):
        self.done('G01')
        report = module.preview(self.plan, self.state, date(2026,9,24))
        self.assertEqual(report['selected']['product'], 'G02')

    def test_blocked_record_requires_owner_dependency_and_unblock_condition(self):
        self.state['records']['R01']={'state':'BLOCKED','blocker':'Waiting on source'}
        with self.assertRaises(ValueError):
            module.validate(self.plan,self.state)

    def test_preview_is_deterministic_and_does_not_mutate_inputs(self):
        before = copy.deepcopy((self.plan,self.state))
        first = module.preview(self.plan, self.state, date(2026,9,24))
        self.assertEqual(first,module.preview(self.plan, self.state,date(2026,9,24)))
        self.assertEqual(before,(self.plan,self.state))

    def test_done_without_evidence_is_rejected(self):
        self.state['records']['G01']={'state':'DONE'}
        with self.assertRaises(ValueError): module.validate(self.plan,self.state)

    def test_unknown_dependency_is_rejected(self):
        self.plan['tasks'][0]['depends_on']=['UNKNOWN']
        with self.assertRaises(ValueError): module.validate(self.plan,self.state)

    def test_cycle_is_rejected(self):
        self.plan['tasks'][0]['depends_on']=['G02']
        with self.assertRaises(ValueError): module.validate(self.plan,self.state)

    def test_active_work_requires_actual_executor(self):
        self.state['records']['G01']={'state':'WORKING'}
        with self.assertRaises(ValueError): module.validate(self.plan,self.state)

    def test_unplanned_p1_requests_safe_interrupt_not_worker_cancellation(self):
        self.done('G01')
        self.done('G02')
        self.done('G03')
        self.state['records']['G05']={'state':'WORKING','executor':'fixture-worker','started_at':'2026-09-29T08:00:00Z'}
        task=copy.deepcopy(self.plan['tasks'][0])
        task.update(id='INC001',planned_start='2026-09-29',planned_finish='2026-09-29',unplanned=True,depends_on=[])
        self.plan['tasks'].append(task)
        report=module.preview(self.plan,self.state,date(2026,9,29))
        self.assertEqual(report['selected']['product'],'G05')
        self.assertIn('INC001',report['interrupt_at_safe_checkpoint'])

    def test_wip_violation_is_rejected(self):
        for ident in ('G01','G02'):
            self.state['records'][ident]={'state':'WORKING','executor':'fixture','started_at':'2026-09-22T08:00:00Z'}
        with self.assertRaises(ValueError): module.validate(self.plan,self.state)

    def test_snapshot_age_is_visible(self):
        self.assertTrue(module.preview(self.plan,self.state,date(2026,9,23))['state_is_stale'])

    def test_wrong_plan_state_is_rejected(self):
        self.state['plan_id']='other'
        with self.assertRaises(ValueError): module.validate(self.plan,self.state)

    def test_cancelled_dependency_does_not_mean_done(self):
        self.state['records']['G01']={'state':'CANCELLED'}
        report=module.preview(self.plan,self.state,date(2026,9,24))
        self.assertIn('G02',[b['id'] for b in report['blocked']])

    def test_invalid_date_and_naive_work_time_rejected(self):
        self.state['records']['G01']={'state':'WORKING','executor':'fixture','started_at':'2026-09-22T08:00:00'}
        with self.assertRaises(ValueError): module.validate(self.plan,self.state)

    def test_completion_evidence_cannot_be_a_single_unchecked_string(self):
        self.done('G01')
        self.state['records']['G01']['evidence']='not-a-reference-list'
        with self.assertRaises(ValueError): module.validate(self.plan,self.state)

    def test_future_completion_cannot_unlock_past_work(self):
        self.done('G01')
        self.state['records']['G01']['completed_at']='2026-10-01T08:00:00Z'
        with self.assertRaises(ValueError): module.preview(self.plan,self.state,date(2026,9,24))

    def test_daily_row_wrong_lane_is_rejected(self):
        self.plan['days'][0]['research']='G01'
        with self.assertRaises(ValueError): module.validate(self.plan,self.state)

    def test_preview_reports_queue_policy_references(self):
        report = module.preview(self.plan, self.state, date(2026, 9, 22))
        self.assertEqual(report['queue_policy_issue_refs'], [52, 57])

if __name__=='__main__': unittest.main()
