from __future__ import annotations

from datetime import datetime, timedelta, timezone
import tempfile
import unittest

from trading_lab.data import (
    CollectionState,
    CollectionWindow,
    CollectorCheckpoint,
    LocalCheckpointStore,
)


class Issue37ResumableCollectorTests(unittest.TestCase):
    def test_window_requires_timezone_aware_bounds(self) -> None:
        start = datetime(2026, 1, 1, 0, 0, 0)
        end = datetime(2026, 1, 1, 1, 0, 0, tzinfo=timezone.utc)
        with self.assertRaises(ValueError):
            CollectionWindow(start_utc=start, end_utc=end)

    def test_checkpoint_roundtrip_and_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalCheckpointStore(tmp)
            start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
            end = start + timedelta(hours=4)
            now = start + timedelta(minutes=1)

            created = store.begin_or_resume(
                provider_id="dukascopy",
                instrument="GBPJPY",
                dataset_id="gbpjpy-m15",
                requested_window=CollectionWindow(start_utc=start, end_utc=end),
                now_utc=now,
            )
            self.assertEqual(created.state, CollectionState.PLANNED)
            self.assertEqual(created.next_start_utc, start)

            store.save(created)
            resumed = store.begin_or_resume(
                provider_id="dukascopy",
                instrument="GBPJPY",
                dataset_id="gbpjpy-m15",
                requested_window=CollectionWindow(start_utc=start, end_utc=end),
                now_utc=now + timedelta(minutes=5),
            )
            self.assertEqual(resumed, created)

    def test_mark_chunk_success_moves_state_and_completes_on_terminal_chunk(self) -> None:
        start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(hours=2)
        checkpoint = CollectorCheckpoint(
            provider_id="dukascopy",
            instrument="GBPJPY",
            dataset_id="gbpjpy-m15",
            requested_window=CollectionWindow(start_utc=start, end_utc=end),
            next_start_utc=start,
            state=CollectionState.PLANNED,
            updated_at_utc=start,
        )

        first = checkpoint.mark_chunk_success(
            chunk_end_utc=start + timedelta(hours=1),
            update_time_utc=start + timedelta(hours=1, minutes=1),
        )
        self.assertEqual(first.state, CollectionState.IN_PROGRESS)
        self.assertEqual(first.attempt_count, 1)
        self.assertIsNotNone(first.remaining)

        final = first.mark_chunk_success(
            chunk_end_utc=end,
            update_time_utc=end,
        )
        self.assertEqual(final.state, CollectionState.COMPLETE)
        self.assertTrue(final.is_complete)
        self.assertIsNone(final.remaining)

    def test_blocked_requires_reason_and_tracks_blocker(self) -> None:
        start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(hours=1)
        checkpoint = CollectorCheckpoint(
            provider_id="dukascopy",
            instrument="GBPJPY",
            dataset_id="gbpjpy-m15",
            requested_window=CollectionWindow(start_utc=start, end_utc=end),
            next_start_utc=start,
            state=CollectionState.PLANNED,
            updated_at_utc=start,
        )
        blocked = checkpoint.mark_blocked(
            reason="provider_terms_unverified",
            update_time_utc=start + timedelta(minutes=5),
        )
        self.assertEqual(blocked.state, CollectionState.BLOCKED)
        self.assertEqual(blocked.blocker_reason, "provider_terms_unverified")
        self.assertEqual(blocked.attempt_count, 1)


if __name__ == "__main__":
    unittest.main()
