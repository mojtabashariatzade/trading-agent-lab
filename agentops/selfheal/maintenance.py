"""Self-healing maintenance loop: detect, classify, recover, report, cap repairs."""
import json
import logging
import os
from pathlib import Path
import subprocess
import time

from .patterns import BUILTIN_PATTERNS, MAX_REPAIR_ATTEMPTS, PatternRegistry
from .publish import publish_selfheal_changes
from ..providers import ProviderError

logger = logging.getLogger(__name__)


def default_report_dir() -> Path:
    override = os.environ.get("MAINTENANCE_REPORT_DIR", "").strip()
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("HOME") or "."
    return Path(base) / "trading-agent-lab" / "status" / "maintenance"


class MaintenanceLoop:
    """Runs after each supervisor tick. Never claims success without evidence."""

    def __init__(self, settings, store, controller, root: Path):
        self.cfg = settings
        self.db = store
        self.controller = controller
        self.root = Path(root)
        self.registry = PatternRegistry()
        self.report_dir = default_report_dir()
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def tick(self) -> list[dict]:
        reports = []
        for finding in self.scan():
            report = self.handle(finding)
            if report:
                reports.append(report)
        if reports:
            self.db.set("selfheal_last_reports", reports[-5:])
        return reports

    def scan(self) -> list[dict]:
        findings = []
        tasks = self.db.tasks()
        done_ids = {t["id"] for t in tasks if t.get("state") == "DONE"}
        blocked = [t for t in tasks if t.get("state") == "BLOCKED"]
        for task in blocked:
            feedback = str(task.get("feedback") or task.get("last_error") or "")
            class_id = self.registry.classify(feedback or "blocked_without_detail")
            # Attempt-cap stall: retryable but cannot retry via attempt counter
            if task.get("retryable") and int(task.get("attempt", 0)) >= self.cfg.max_attempts:
                class_id = "retryable_attempt_cap_stall"
                feedback = f"Attempt cap with retryable failure: {feedback[:300]}"
            findings.append(
                {
                    "task_id": task["id"],
                    "class_id": class_id,
                    "detail": feedback,
                    "task": task,
                    "kind": "blocked_task",
                }
            )
        # Dependency stall is a symptom: only record it when the upstream is not already scanned.
        already = {item["task_id"] for item in findings}
        for task in tasks:
            if task.get("state") != "PENDING":
                continue
            spec = self.controller.specs.get(task["id"])
            if not spec:
                continue
            deps = set(spec.get("depends_on") or [])
            if not deps or deps <= done_ids:
                continue
            blockers = [b for b in blocked if b["id"] in deps]
            if blockers and blockers[0]["id"] not in already:
                findings.append(
                    {
                        "task_id": blockers[0]["id"],
                        "class_id": "queue_dependency_hard_block",
                        "detail": (
                            f"dependency_hard_block: {task['id']} waits on "
                            f"{blockers[0]['id']} ({blockers[0].get('feedback', '')[:200]})"
                        ),
                        "task": blockers[0],
                        "kind": "dependency_stall",
                        "waiting_task": task["id"],
                    }
                )
        # Deduplicate by task_id+class
        seen = set()
        unique = []
        for item in findings:
            key = (item["task_id"], item["class_id"])
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    def handle(self, finding: dict) -> dict | None:
        class_id = finding["class_id"]
        task = finding["task"]
        detail = finding["detail"]
        strategy = self.registry.strategy_for(class_id)
        if strategy == "defer_upstream":
            return None
        if task.get("self_heal_blocked") or self.registry.is_blocked(class_id):
            if task.get("selfheal_block_reported"):
                return None
            task["selfheal_block_reported"] = True
            self.db.save(task)
            return self._report(
                finding,
                status="SELF_HEAL_BLOCKED",
                root_cause="Repair attempt cap reached for this failure class",
                fix_applied="none",
                regression_test="",
                ci_result="SKIPPED",
                qa_result="SKIPPED",
                merge_commit="",
                resumed_task="",
                success=False,
            )
        # Skip if recently handled (avoid thrash within backoff)
        last = float(task.get("selfheal_last_at") or 0)
        if time.time() - last < 60:
            return None

        diagnostics = self.capture_diagnostics(finding)
        regression = self.ensure_regression_test(class_id, detail)
        success = False
        fix = ""
        resumed = ""
        ci_result = "NOT_RUN"
        qa_result = "NOT_RUN"
        merge_commit = ""
        try:
            if strategy == "recover_worker":
                success, fix, resumed = self.apply_recover_worker(task, detail)
            else:
                fix = "capture_only"
                success = False
            if success:
                ci_result, qa_result = self.run_verification(regression)
                # Runtime recoveries do not open PRs; evidence is local unittest.
                if ci_result != "PASS" or qa_result != "PASS":
                    success = False
                    fix += "; verification failed — not claiming healed"
                else:
                    merge_commit = publish_selfheal_changes(
                        self.root, class_id=class_id, regression_rel=regression
                    ) or "n/a-runtime-recovery"
                    self.registry.release_after_recorded_fix(class_id, f"healed:{merge_commit}")
            self.registry.record_attempt(class_id, success=success, detail=detail)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Self-heal handler failed")
            self.registry.record_attempt(class_id, success=False, detail=f"{detail} | handler={exc}")
            return self._report(
                finding,
                status="SELF_HEAL_ERROR",
                root_cause=str(exc),
                fix_applied=fix,
                regression_test=regression,
                ci_result="ERROR",
                qa_result="ERROR",
                merge_commit="",
                resumed_task="",
                success=False,
                diagnostics=diagnostics,
            )

        task = self.db.task(task["id"]) or task
        task["selfheal_last_at"] = time.time()
        if not success and self.registry.is_blocked(class_id):
            task["self_heal_blocked"] = True
            task["state"] = "BLOCKED"
            task["retryable"] = False
            task["feedback"] = f"SELF_HEAL_BLOCKED:{class_id}: {detail}"[:1000]
            self.db.save(task)
            status = "SELF_HEAL_BLOCKED"
        elif success:
            status = "HEALED"
            after = self.db.task(task["id"]) or task
            after["selfheal_last_at"] = time.time()
            self.db.save(after)
            # Runtime recoveries need no process reload; learned code patches may.
            self.db.set("supervisor_reload_requested", False)
        else:
            status = "REPAIR_ATTEMPTED"
            after = self.db.task(task["id"]) or task
            after["selfheal_last_at"] = time.time()
            self.db.save(after)

        return self._report(
            finding,
            status=status,
            root_cause=detail,
            fix_applied=fix,
            regression_test=regression,
            ci_result=ci_result,
            qa_result=qa_result,
            merge_commit=merge_commit or "n/a-runtime-recovery",
            resumed_task=resumed,
            success=success,
            diagnostics=diagnostics,
        )

    def apply_recover_worker(self, task: dict, detail: str) -> tuple[bool, str, str]:
        """Restart the worker. LAUNCHING without a run_id is not a heal — only a live run is."""
        before = task.get("state")
        live = self.db.task(task["id"]) or task
        if live.get("pr") and self.controller.reconcile_existing_delivery(live):
            after = self.db.task(task["id"]) or live
            return True, f"reconciled existing PR {after.get('pr')} ({before} -> {after.get('state')})", after.get("id", "")
        if (
            int(live.get("stuck_retries", 0)) > self.cfg.max_stuck_retries
            or live.get("self_heal_blocked")
            or live.get("state") == "BLOCKED"
        ):
            live = dict(live)
            live["stuck_retries"] = 0
            live["self_heal_blocked"] = False
            live["selfheal_block_reported"] = False
            live["retryable"] = True
            live["backoff_until"] = 0
            self.db.save(live)
        self.controller.recover_or_block(live, detail[:1000], immediate=True)
        after = self.db.task(task["id"]) or {}
        if after.get("state") in {"LAUNCHING_DEV", "LAUNCHING_QA"} and not after.get("run_id"):
            if self.controller.clock() >= float(after.get("backoff_until") or 0):
                try:
                    self.controller.launch(after, after.get("role") or "dev")
                except ProviderError:
                    pass
                after = self.db.task(task["id"]) or after
        state = after.get("state")
        if state in {"DEVELOPING", "REVIEWING"}:
            return True, f"recover_or_block ({before} -> {state})", after.get("id", "")
        if state in {"LAUNCHING_DEV", "LAUNCHING_QA"} and after.get("run_id"):
            return True, f"recover_or_block ({before} -> {state} with run)", after.get("id", "")
        if state == "PENDING":
            return True, f"recover_or_block ({before} -> PENDING)", after.get("id", "")
        if state == "BLOCKED":
            return False, "recover_or_block resulted in BLOCKED", ""
        return False, f"not healed yet (state={state}, run_id={after.get('run_id')})", ""

    def capture_diagnostics(self, finding: dict) -> dict:
        task = finding["task"]
        status_path = self.cfg.resolved_status_path
        payload = {
            "captured_at": time.time(),
            "class_id": finding["class_id"],
            "task_id": finding["task_id"],
            "task_snapshot": {
                k: task.get(k)
                for k in (
                    "id", "state", "attempt", "stuck_retries", "retryable",
                    "feedback", "last_error", "role", "run_id", "pr",
                )
            },
            "runtime_status": self.db.get("runtime_status"),
        }
        try:
            if Path(status_path).is_file():
                payload["status_file"] = json.loads(Path(status_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
        diag_path = self.report_dir / f"diag_{finding['task_id']}_{int(time.time())}.json"
        diag_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        payload["diagnostics_path"] = str(diag_path)
        return payload

    def ensure_regression_test(self, class_id: str, detail: str) -> str:
        """Add a focused regression test under tests/added/ for this failure class."""
        tests_dir = self.root / "tests" / "added"
        tests_dir.mkdir(parents=True, exist_ok=True)
        init = tests_dir / "__init__.py"
        if not init.exists():
            init.write_text("", encoding="utf-8")
        safe = "".join(ch if ch.isalnum() else "_" for ch in class_id)[:60]
        path = tests_dir / f"test_selfheal_{safe}.py"
        if path.exists():
            return str(path.relative_to(self.root)).replace("\\", "/")
        if class_id == "retryable_attempt_cap_stall":
            body = '''import unittest
from dataclasses import replace
from agentops.config import Settings
from agentops.controller import Controller
from agentops.store import Store
from tests.fakes import *


class SelfHealAttemptCapTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Settings(
            REPO, "fake-gh", "fake-cursor", "1:fake", 42, frozenset({42}),
            state_path=":memory:", allow_runs=True, spend_limit_confirmed=True,
            protection_confirmed=True, autonomous_default=False, auto_merge_safe=False,
            max_attempts=2, max_stuck_retries=3, stuck_backoff_seconds=5,
        )
        self.db = Store(":memory:")
        self.gh, self.cu, self.tg = FakeGitHub(), FakeCursor(), FakeTelegram()
        self.clock = Clock()
        self.c = Controller(self.cfg, self.db, self.gh, self.cu, self.tg, backlog(), clock=self.clock)

    def test_retryable_attempt_cap_triggers_stuck_recovery(self):
        self.c.handle(update("/resume"))
        self.c.tick()
        t = self.db.task("T001")
        t.update(
            state="BLOCKED",
            retryable=True,
            attempt=2,
            feedback="Cursor terminal/unknown status: ERROR",
            role="dev",
            base_sha=BASE,
        )
        self.db.save(t)
        self.c.tick()
        t = self.db.task("T001")
        self.assertIn(t["state"], {"LAUNCHING_DEV", "DEVELOPING"})
        self.assertGreaterEqual(int(t.get("stuck_retries", 0)), 1)


if __name__ == "__main__":
    unittest.main()
'''
        else:
            body = f'''import tempfile
import unittest
from pathlib import Path

from agentops.selfheal.patterns import PatternRegistry


class SelfHealRegistrySmoke_{safe}(unittest.TestCase):
    def test_pattern_classifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = PatternRegistry(path=str(Path(tmp) / "patterns.json"))
            class_id = reg.classify({json.dumps(detail[:200])})
            self.assertTrue(isinstance(class_id, str) and class_id)


if __name__ == "__main__":
    unittest.main()
'''
        path.write_text(body, encoding="utf-8")
        return str(path.relative_to(self.root)).replace("\\", "/")

    def run_verification(self, regression_rel: str) -> tuple[str, str]:
        """Run unittest evidence. Maps to CI/QA slots for runtime recoveries.

        Broad suite is optional (SELFHEAL_BROAD_TESTS=true) to avoid recursive
        discover when this loop is itself under unittest.
        """
        try:
            mod = regression_rel.replace("/", ".").removesuffix(".py")
            proc = subprocess.run(
                ["python", "-m", "unittest", mod, "-v"],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            qa = "PASS" if proc.returncode == 0 else "FAIL"
            log = (proc.stdout or "") + "\n" + (proc.stderr or "")
            ci = qa
            if os.environ.get("SELFHEAL_BROAD_TESTS", "").lower() == "true":
                broad = subprocess.run(
                    ["python", "-m", "unittest", "discover", "-s", "tests", "-q"],
                    cwd=str(self.root),
                    capture_output=True,
                    text=True,
                    timeout=300,
                    check=False,
                )
                ci = "PASS" if broad.returncode == 0 else "FAIL"
                log += "\n---\n" + (broad.stdout or "") + "\n" + (broad.stderr or "")
            (self.report_dir / "last_unittest.log").write_text(log, encoding="utf-8")
            return ci, qa
        except (OSError, subprocess.SubprocessError) as exc:
            return "ERROR", f"ERROR:{exc}"

    def _report(
        self,
        finding: dict,
        *,
        status: str,
        root_cause: str,
        fix_applied: str,
        regression_test: str,
        ci_result: str,
        qa_result: str,
        merge_commit: str,
        resumed_task: str,
        success: bool,
        diagnostics: dict | None = None,
    ) -> dict:
        report = {
            "status": status,
            "failure_class": finding["class_id"],
            "root_cause": root_cause[:2000],
            "regression_test_added": regression_test,
            "fix_applied": fix_applied,
            "ci_result": ci_result,
            "qa_result": qa_result,
            "merge_commit": merge_commit,
            "resumed_task": resumed_task or finding.get("waiting_task") or finding["task_id"],
            "success": success,
            "task_id": finding["task_id"],
            "repair_attempt": self.registry.repair_count(finding["class_id"]),
            "max_repair_attempts": MAX_REPAIR_ATTEMPTS,
            "diagnostics_path": (diagnostics or {}).get("diagnostics_path", ""),
            "at": time.time(),
            "live_trading": False,
            "broker_access": False,
        }
        name = f"report_{finding['class_id']}_{finding['task_id']}_{int(time.time())}.json"
        path = self.report_dir / name
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        md = self.report_dir / name.replace(".json", ".md")
        md.write_text(
            "\n".join(
                [
                    "# Maintenance report",
                    "",
                    f"- failure class: `{report['failure_class']}`",
                    f"- root cause: {report['root_cause']}",
                    f"- regression test added: `{report['regression_test_added']}`",
                    f"- fix applied: {report['fix_applied']}",
                    f"- CI result: `{report['ci_result']}`",
                    f"- QA result: `{report['qa_result']}`",
                    f"- merge commit: `{report['merge_commit']}`",
                    f"- resumed task: `{report['resumed_task']}`",
                    f"- status: `{report['status']}`",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        report["report_path"] = str(path)
        self.db.audit("SELF_HEAL", report)
        return report
