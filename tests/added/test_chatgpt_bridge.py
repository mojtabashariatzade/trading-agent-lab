import unittest

from agentops.config import Settings
from agentops.controller import Controller
from agentops.store import Store
from tests.fakes import FakeCursor, FakeGitHub, FakeTelegram, REPO, backlog, update


class BridgeGitHub(FakeGitHub):
    def __init__(self):
        super().__init__()
        self.bridge_comments = []

    def comment_issue(self, number, body):
        row = {"id": len(self.bridge_comments) + 100, "body": body}
        self.bridge_comments.append(row)
        return row

    def issue_comments(self, number):
        return list(self.bridge_comments)


class ChatGPTBridgeTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Settings(
            REPO,
            "fake-gh",
            "local",
            "1:fake",
            42,
            frozenset({42}),
            state_path=":memory:",
            allow_runs=True,
            spend_limit_confirmed=True,
            protection_confirmed=True,
            allow_public_repo=True,
            agent_runtime="local",
            chatgpt_bridge_issue=27,
        )
        self.db = Store(":memory:")
        self.gh = BridgeGitHub()
        self.tg = FakeTelegram()
        self.controller = Controller(
            self.cfg, self.db, self.gh, FakeCursor(), self.tg, backlog()
        )

    def test_free_form_owner_message_enters_public_mailbox(self):
        self.controller.handle(update("الان وضعیت پروژه چیه؟", uid=10))
        self.assertEqual(len(self.gh.bridge_comments), 1)
        body = self.gh.bridge_comments[0]["body"]
        self.assertIn("chatgpt-bridge:inbound update_id=10", body)
        self.assertIn("وضعیت پروژه", body)
        self.controller.flush()
        self.assertTrue(any("ChatGPT Supervisor" in row[1] for row in self.tg.sent))

    def test_outbound_mailbox_reply_is_relayed_once(self):
        self.gh.bridge_comments.append(
            {
                "id": 501,
                "body": "<!-- chatgpt-bridge:outbound reply_to=10 -->\nپروژه در حال اجراست.",
            }
        )
        self.controller.poll_chatgpt_bridge()
        self.controller.flush()
        sent = [row[1] for row in self.tg.sent if "پروژه در حال اجراست" in row[1]]
        self.assertEqual(len(sent), 1)
        self.controller.poll_chatgpt_bridge()
        self.controller.flush()
        sent = [row[1] for row in self.tg.sent if "پروژه در حال اجراست" in row[1]]
        self.assertEqual(len(sent), 1)

    def test_obvious_secret_is_not_posted_to_public_issue(self):
        self.controller.handle(update("GITHUB_TOKEN=ghp_secretvalue", uid=11))
        self.assertEqual(self.gh.bridge_comments, [])
        self.controller.flush()
        self.assertTrue(any("حساس" in row[1] for row in self.tg.sent))


if __name__ == "__main__":
    unittest.main()
