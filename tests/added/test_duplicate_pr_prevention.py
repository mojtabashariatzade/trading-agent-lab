"""Duplicate PR prevention: restart/re-run must reuse an existing open delivery PR."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentops.config import Settings
from agentops.controller import Controller
from agentops.local_runtime import LocalCursor
from agentops.store import Store
from tests.fakes import *


class DuplicatePrPreventionTests(unittest.TestCase):
    def test_controller_binds_existing_open_pr_instead_of_relaunch(self):
        cfg = Settings(
            REPO, "fake-gh", "fake-cursor", "1:fake", 42, frozenset({42}),
            state_path=":memory:", allow_runs=True, spend_limit_confirmed=True,
            protection_confirmed=True, agent_runtime="local", auto_merge_safe=True,
        )
        db = Store(":memory:")
        gh, cu, tg = FakeGitHub(), FakeCursor(), FakeTelegram()
        gh.open_prs = [
            {
                "number": 42,
                "title": "feat(data): local Kian M15 bar helpers T001",
                "body": "[team:T001]\n",
                "head": {"ref": "local/kian-old", "sha": HEAD, "repo": {"full_name": REPO}},
            }
        ]
        gh.pull = {
            "number": 42, "state": "open", "draft": False, "merged": False,
            "head": {"sha": HEAD, "repo": {"full_name": REPO}},
            "base": {"ref": "main", "repo": {"full_name": REPO}},
        }
        ctl = Controller(cfg, db, gh, cu, tg, backlog(), clock=Clock())
        ctl.handle(update("/resume"))
        created_before = len(cu.created)
        bound = ctl.bind_existing_open_pr(db.task("T001"))
        self.assertTrue(bound)
        t = db.task("T001")
        self.assertEqual(t.get("pr"), 42)
        self.assertIn(t.get("state"), {"CI_WAIT", "LAUNCHING_QA", "REVIEWING"})
        self.assertEqual(len(cu.created), created_before)

    def test_local_cursor_reuses_open_pr_for_same_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cursor = LocalCursor(root, github_repo=REPO)
            calls = []

            def fake_gh(args, cwd=None):
                calls.append(list(args))
                if args[:2] == ["pr", "list"]:
                    return json.dumps([
                        {
                            "number": 99,
                            "url": f"https://github.com/{REPO}/pull/99",
                            "title": "feat(execution): local Kian research execution kernel stubs",
                            "headRefName": "local/kian-deadbeef",
                        }
                    ])
                if args[:2] == ["pr", "create"]:
                    raise AssertionError("must not create duplicate PR")
                return ""

            with patch.object(cursor, "_gh", side_effect=fake_gh):
                url = cursor._find_existing_pr(
                    branch="local/kian-deadbeef",
                    task_id="T002",
                    title="feat(execution): local Kian research execution kernel stubs",
                    cwd=root,
                )
            self.assertEqual(url, f"https://github.com/{REPO}/pull/99")
            self.assertTrue(any(c[:2] == ["pr", "list"] for c in calls))
            self.assertFalse(any(c[:2] == ["pr", "create"] for c in calls))


if __name__ == "__main__":
    unittest.main()
