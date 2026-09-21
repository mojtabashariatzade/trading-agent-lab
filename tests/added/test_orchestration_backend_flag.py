"""Feature flag: default legacy; maf_durable selectable without breaking imports."""
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from agentops.config import Settings
from agentops.controller import Controller
from agentops.orchestration.factory import create_backend
from agentops.orchestration.legacy_backend import LegacyBackend
from agentops.selfheal import MaintenanceLoop
from agentops.store import Store
from tests.fakes import *


class OrchestrationBackendFlagTests(unittest.TestCase):
    def _settings(self, **kw):
        return Settings(
            REPO, "fake-gh", "fake-cursor", "1:fake", 42, frozenset({42}),
            state_path=":memory:", allow_runs=True, spend_limit_confirmed=True,
            protection_confirmed=True, agent_runtime="local", **kw,
        )

    def test_default_backend_is_maf_durable(self):
        self.assertEqual(self._settings().orchestration_backend, "maf_durable")

    def test_invalid_backend_rejected(self):
        with self.assertRaises(ValueError):
            replace(self._settings(), orchestration_backend="temporal")

    def test_factory_returns_maf_durable_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._settings(durable_checkpoint_dir=tmp)
            db = Store(":memory:")
            ctl = Controller(cfg, db, FakeGitHub(), FakeCursor(), FakeTelegram(), backlog())
            healer = MaintenanceLoop(cfg, db, ctl, Path("."))
            backend = create_backend(cfg, ctl, healer)
            self.assertEqual(backend.name, "maf_durable")

    def test_factory_returns_legacy_when_flagged(self):
        cfg = self._settings(orchestration_backend="legacy")
        db = Store(":memory:")
        ctl = Controller(cfg, db, FakeGitHub(), FakeCursor(), FakeTelegram(), backlog())
        healer = MaintenanceLoop(cfg, db, ctl, Path("."))
        backend = create_backend(cfg, ctl, healer)
        self.assertIsInstance(backend, LegacyBackend)
        self.assertEqual(backend.name, "legacy")

    def test_from_env_defaults_maf_durable(self):
        env = {
            "GITHUB_REPOSITORY": REPO,
            "GITHUB_TOKEN": "t",
            "CURSOR_API_KEY": "local",
            "TELEGRAM_BOT_TOKEN": "0:x",
            "TELEGRAM_CONTROL_CHAT_ID": "1",
            "TELEGRAM_OWNER_IDS": "1",
            "AGENT_RUNTIME": "local",
            "TELEGRAM_OPTIONAL": "true",
        }
        old = {k: os.environ.get(k) for k in list(env) + ["ORCHESTRATION_BACKEND"]}
        try:
            os.environ.update(env)
            os.environ.pop("ORCHESTRATION_BACKEND", None)
            s = Settings.from_env()
            self.assertEqual(s.orchestration_backend, "maf_durable")
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
