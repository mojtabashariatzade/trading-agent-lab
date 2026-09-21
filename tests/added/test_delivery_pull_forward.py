"""An early finish must not create artificial calendar idle time."""
from datetime import date
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('daily_pull_forward', ROOT / 'scripts/plan_day.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PullForwardTests(unittest.TestCase):
    def test_finished_work_advances_ready_dependency_and_keeps_original_date(self):
        plan = json.loads((ROOT / 'planning/delivery_plan.json').read_text())
        state = json.loads((ROOT / 'planning/delivery_state.json').read_text())
        state['records']['G01'] = {
            'state': 'DONE', 'completed_at': '2026-09-22T08:00:00Z',
            'evidence': ['fixture-only:test-receipt'],
        }
        result = module.preview(plan, state, date(2026, 9, 22))
        self.assertEqual(result['selected']['product'], 'G02')
        self.assertIn('G02', result['pulled_forward'])
        task = next(t for t in plan['tasks'] if t['id'] == 'G02')
        self.assertEqual(task['planned_start'], '2026-09-24')
        self.assertEqual(result['mode'], 'READ_ONLY_PREVIEW_NO_WORKER_STARTED')


if __name__ == '__main__':
    unittest.main()
