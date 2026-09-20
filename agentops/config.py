from dataclasses import dataclass
import os
import re


@dataclass(frozen=True)
class Settings:
    repo: str
    github_token: str
    cursor_key: str
    telegram_token: str
    control_chat: int
    owner_ids: frozenset[int]
    report_chat: int | None = None
    branch: str = "main"
    model: str = ""
    state_path: str = "/state/team.sqlite3"
    allow_runs: bool = False
    spend_limit_confirmed: bool = False
    protection_confirmed: bool = False
    allow_public_repo: bool = False
    agent_runtime: str = "cloud"
    max_daily_launches: int = 4
    max_attempts: int = 2
    max_phase: int = 1
    max_run_seconds: int = 5400
    approval_seconds: int = 86400
    poll_seconds: int = 30

    def __post_init__(self):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.repo):
            raise ValueError("GITHUB_REPOSITORY must be owner/repository")
        if not self.owner_ids or any(i <= 0 for i in self.owner_ids):
            raise ValueError("At least one positive numeric Telegram owner ID is required")
        if self.control_chat == 0:
            raise ValueError("TELEGRAM_CONTROL_CHAT_ID is required")
        if not 1 <= self.max_daily_launches <= 20:
            raise ValueError("Daily launch count must be in [1,20]")
        if not 1 <= self.max_attempts <= 3:
            raise ValueError("Retry attempts must be in [1,3]")
        if self.max_phase != 1:
            raise ValueError("Starter authorizes phase 1 only; later phases need a reviewed release")
        if not 10 <= self.poll_seconds <= 300:
            raise ValueError("Poll interval must be between 10 and 300 seconds")
        if not 300 <= self.max_run_seconds <= 14400:
            raise ValueError("Run watchdog must be between 5 minutes and 4 hours")
        if not re.fullmatch(r"[A-Za-z0-9_./-]+", self.branch):
            raise ValueError("Invalid branch name")

    @property
    def repo_url(self):
        return f"https://github.com/{self.repo}"

    @classmethod
    def from_env(cls):
        def flag(name):
            return os.environ.get(name, "false").lower() == "true"
        return cls(
            repo=os.environ["GITHUB_REPOSITORY"],
            github_token=os.environ["GITHUB_TOKEN"],
            cursor_key=os.environ["CURSOR_API_KEY"],
            telegram_token=os.environ["TELEGRAM_BOT_TOKEN"],
            control_chat=int(os.environ["TELEGRAM_CONTROL_CHAT_ID"]),
            owner_ids=frozenset(int(s.strip()) for s in os.environ["TELEGRAM_OWNER_IDS"].split(",") if s.strip()),
            report_chat=int(os.environ["TELEGRAM_REPORT_CHAT_ID"]) if os.environ.get("TELEGRAM_REPORT_CHAT_ID") else None,
            branch=os.environ.get("DEFAULT_BRANCH", "main"),
            model=os.environ.get("CURSOR_MODEL", ""),
            state_path=os.environ.get("STATE_PATH", "/state/team.sqlite3"),
            allow_runs=flag("ALLOW_AGENT_RUNS"),
            spend_limit_confirmed=flag("SPEND_LIMIT_CONFIRMED"),
            protection_confirmed=flag("REPOSITORY_PROTECTION_CONFIRMED"),
            allow_public_repo=flag("ALLOW_PUBLIC_REPO"),
            agent_runtime=os.environ.get("AGENT_RUNTIME", "cloud").strip().lower() or "cloud",
            max_daily_launches=int(os.environ.get("MAX_DAILY_LAUNCHES", "4")),
            max_attempts=int(os.environ.get("MAX_ATTEMPTS", "2")),
            max_run_seconds=int(os.environ.get("MAX_RUN_SECONDS", "5400")),
            poll_seconds=int(os.environ.get("POLL_SECONDS", "30")),
        )
