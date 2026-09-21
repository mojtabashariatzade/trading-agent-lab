from dataclasses import dataclass
import os
import re

from .runtime_status import default_config_path, default_status_path


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
    auto_merge_safe: bool = True
    autonomous_default: bool = True
    telegram_optional: bool = False
    status_path: str = ""
    config_path: str = ""
    heartbeat_seconds: int = 300
    stuck_timeout_seconds: int = 300
    max_stuck_retries: int = 3
    stuck_backoff_seconds: int = 15
    supervisor_restart_enabled: bool = False
    max_daily_launches: int = 12
    max_attempts: int = 2
    max_phase: int = 1
    max_run_seconds: int = 5400
    approval_seconds: int = 86400
    poll_seconds: int = 30
    orchestration_backend: str = "maf_durable"
    dts_endpoint: str = "http://localhost:8080"
    dts_task_hub: str = "default"
    durable_checkpoint_dir: str = ""

    def __post_init__(self):
        backend = (self.orchestration_backend or "maf_durable").strip().lower()
        if backend not in {"legacy", "maf_durable"}:
            raise ValueError("ORCHESTRATION_BACKEND must be 'legacy' or 'maf_durable'")
        object.__setattr__(self, "orchestration_backend", backend)
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.repo):
            raise ValueError("GITHUB_REPOSITORY must be owner/repository")
        if not self.telegram_optional:
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
        if not 60 <= self.heartbeat_seconds <= 3600:
            raise ValueError("Heartbeat interval must be between 60 and 3600 seconds")
        if not 60 <= self.stuck_timeout_seconds <= 3600:
            raise ValueError("Stuck timeout must be between 60 and 3600 seconds")
        if not 1 <= self.max_stuck_retries <= 3:
            raise ValueError("Stuck retries must be in [1,3]")
        if not 5 <= self.stuck_backoff_seconds <= 300:
            raise ValueError("Stuck backoff must be between 5 and 300 seconds")
        if not re.fullmatch(r"[A-Za-z0-9_./-]+", self.branch):
            raise ValueError("Invalid branch name")

    @property
    def repo_url(self):
        return f"https://github.com/{self.repo}"

    @property
    def resolved_status_path(self) -> str:
        return self.status_path or default_status_path()

    @property
    def resolved_config_path(self) -> str:
        return self.config_path or default_config_path()

    @classmethod
    def from_env(cls):
        def flag(name, default="false"):
            return os.environ.get(name, default).lower() == "true"

        agent_runtime = os.environ.get("AGENT_RUNTIME", "cloud").strip().lower() or "cloud"
        telegram_optional = flag("TELEGRAM_OPTIONAL") or agent_runtime == "local"
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        if telegram_optional and not token:
            token = "0:localoptionaldisabled"
        owners_raw = os.environ.get("TELEGRAM_OWNER_IDS", "").strip()
        if telegram_optional and not owners_raw:
            owner_ids = frozenset({1})
        else:
            owner_ids = frozenset(int(s.strip()) for s in owners_raw.split(",") if s.strip())
        chat_raw = os.environ.get("TELEGRAM_CONTROL_CHAT_ID", "").strip()
        if telegram_optional and not chat_raw:
            control_chat = 1
        else:
            control_chat = int(chat_raw)
        cursor_key = os.environ.get("CURSOR_API_KEY", "").strip()
        if agent_runtime == "local" and not cursor_key:
            cursor_key = "local"

        return cls(
            repo=os.environ["GITHUB_REPOSITORY"],
            github_token=os.environ["GITHUB_TOKEN"],
            cursor_key=cursor_key,
            telegram_token=token,
            control_chat=control_chat,
            owner_ids=owner_ids,
            report_chat=int(os.environ["TELEGRAM_REPORT_CHAT_ID"]) if os.environ.get("TELEGRAM_REPORT_CHAT_ID") else None,
            branch=os.environ.get("DEFAULT_BRANCH", "main"),
            model=os.environ.get("CURSOR_MODEL", ""),
            state_path=os.environ.get("STATE_PATH", "/state/team.sqlite3"),
            allow_runs=flag("ALLOW_AGENT_RUNS"),
            spend_limit_confirmed=flag("SPEND_LIMIT_CONFIRMED"),
            protection_confirmed=flag("REPOSITORY_PROTECTION_CONFIRMED"),
            allow_public_repo=flag("ALLOW_PUBLIC_REPO"),
            agent_runtime=agent_runtime,
            auto_merge_safe=flag("AUTO_MERGE_SAFE", "true"),
            autonomous_default=flag("AUTONOMOUS_DEFAULT", "true"),
            telegram_optional=telegram_optional,
            status_path=os.environ.get("RUNTIME_STATUS_PATH", "").strip(),
            config_path=os.environ.get("RUNTIME_CONFIG_PATH", "").strip(),
            heartbeat_seconds=int(os.environ.get("HEARTBEAT_SECONDS", "300")),
            stuck_timeout_seconds=int(os.environ.get("STUCK_TIMEOUT_SECONDS", "300")),
            max_stuck_retries=int(os.environ.get("MAX_STUCK_RETRIES", "3")),
            stuck_backoff_seconds=int(os.environ.get("STUCK_BACKOFF_SECONDS", "15")),
            supervisor_restart_enabled=flag("SUPERVISOR_RESTART_ENABLED"),
            max_daily_launches=int(os.environ.get("MAX_DAILY_LAUNCHES", "12")),
            max_attempts=int(os.environ.get("MAX_ATTEMPTS", "2")),
            max_run_seconds=int(os.environ.get("MAX_RUN_SECONDS", "5400")),
            poll_seconds=int(os.environ.get("POLL_SECONDS", "30")),
            orchestration_backend=os.environ.get("ORCHESTRATION_BACKEND", "maf_durable").strip().lower()
            or "maf_durable",
            dts_endpoint=os.environ.get("DTS_ENDPOINT", "http://localhost:8080").strip()
            or "http://localhost:8080",
            dts_task_hub=os.environ.get("DTS_TASK_HUB", "default").strip() or "default",
            durable_checkpoint_dir=os.environ.get("DURABLE_CHECKPOINT_DIR", "").strip(),
        )
