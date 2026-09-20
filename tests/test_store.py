import tempfile
from pathlib import Path
import unittest
from agentops.store import Store


class StoreTests(unittest.TestCase):
    def test_state_survives_restart(self):
        with tempfile.TemporaryDirectory() as d:
            p=str(Path(d)/'s.sqlite'); s=Store(p); s.save({'id':'T001','state':'REVIEWING'}); s.set('paused',True); s.db.close()
            s=Store(p); self.assertEqual(s.task('T001')['state'],'REVIEWING'); self.assertTrue(s.get('paused')); s.db.close()
    def test_launch_reservation_idempotent(self):
        s=Store(':memory:'); self.assertTrue(s.reserve('a','2026-09-20',1)); self.assertTrue(s.reserve('a','2026-09-20',1)); self.assertEqual(s.launch_count('2026-09-20'),1)
    def test_launch_cap(self):
        s=Store(':memory:'); s.reserve('a','2026-09-20',1); self.assertFalse(s.reserve('b','2026-09-20',1))
    def test_cap_resets_on_new_day(self):
        s=Store(':memory:'); s.reserve('a','2026-09-20',1); self.assertTrue(s.reserve('b','2026-09-21',1))
    def test_update_replay(self):
        s=Store(':memory:'); s.consume_update(50); s.consume_update(50); self.assertTrue(s.seen_update(50)); self.assertEqual(s.get('telegram_offset'),51)
    def test_outbox_dedup(self):
        s=Store(':memory:'); s.notify('event','x'); s.notify('event','x'); self.assertEqual(len(s.outbox()),1); s.delivered('event'); self.assertEqual(s.outbox(),[])
