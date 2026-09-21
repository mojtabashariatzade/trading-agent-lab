"""Documented HTTPS APIs only. No shell, arbitrary URLs, or code evaluation."""
import base64
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler


class ProviderError(RuntimeError):
    def __init__(self, provider, status=0):
        self.provider, self.status = provider, status
        # Never include request URL, auth headers, or response bodies (bot URL holds a secret).
        super().__init__(f"{provider}: HTTP {status or 'network/timeout'}")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Http:
    def __init__(self, base, headers, provider):
        self.base, self.headers, self.provider = base, headers, provider
        self.opener = build_opener(NoRedirect)

    def call(self, method, path, payload=None):
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("Only provider-relative paths are permitted")
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Accept": "application/json", "Content-Type": "application/json", "User-Agent": "trading-team-starter/0.1", **self.headers}
        try:
            with self.opener.open(Request(self.base + path, body, headers, method=method), timeout=45) as response:
                raw = response.read(4 * 1024 * 1024 + 1)
                if len(raw) > 4 * 1024 * 1024:
                    raise ProviderError(self.provider, 413)
                return json.loads(raw) if raw else None
        except HTTPError as exc:
            raise ProviderError(self.provider, exc.code) from None
        except (URLError, TimeoutError, OSError, json.JSONDecodeError):
            raise ProviderError(self.provider) from None


class Cursor:
    def __init__(self, key):
        auth = base64.b64encode((key + ":").encode()).decode()
        self.http = Http("https://api.cursor.com", {"Authorization": "Basic " + auth}, "Cursor")

    def create(self, agent_id, name, repo_url, ref, prompt, *, review=False, model=""):
        payload = {
            "agentId": agent_id,
            "name": name[:100],
            "prompt": {"text": prompt},
            "repos": [{"url": repo_url, "startingRef": ref}],
            "workOnCurrentBranch": False,
            "autoCreatePR": not review,
            "skipReviewerRequest": True,
            "mode": "agent",
        }
        if model:
            payload["model"] = {"id": model}
        try:
            response = self.http.call("POST", "/v1/agents", payload)
            return response["run"]["id"]
        except ProviderError as exc:
            if exc.status != 409:
                raise
            # v1 client-supplied agentId is an idempotency mechanism.
            return self.http.call("GET", f"/v1/agents/{quote(agent_id, safe='')}")["latestRunId"]

    def run(self, agent_id, run_id):
        return self.http.call("GET", f"/v1/agents/{quote(agent_id, safe='')}/runs/{quote(run_id, safe='')}")

    def cancel(self, agent_id, run_id):
        return self.http.call("POST", f"/v1/agents/{quote(agent_id, safe='')}/runs/{quote(run_id, safe='')}/cancel")


class GitHub:
    def __init__(self, repo, token):
        self.repo = repo
        self.http = Http("https://api.github.com", {"Authorization": "Bearer " + token, "X-GitHub-Api-Version": "2022-11-28"}, "GitHub")
        self.root = f"/repos/{repo}"

    def repository(self):
        return self.http.call("GET", self.root)

    def branch(self, branch):
        return self.http.call("GET", self.root + "/branches/" + quote(branch, safe=""))

    def ensure_issue(self, task):
        # Paginate all issues to avoid creating duplicates after a timeout/restart.
        marker = f"[team:{task['id']}]"
        for page in range(1, 101):
            rows = self.http.call("GET", self.root + f"/issues?state=all&per_page=100&page={page}")
            for row in rows:
                if row.get("title", "").startswith(marker) and "pull_request" not in row:
                    return row["number"]
            if len(rows) < 100:
                break
        else:
            raise RuntimeError("Issue listing exceeded safe pagination bound")
        row = self.http.call("POST", self.root + "/issues", {
            "title": f"{marker} {task['title']}",
            "body": task["description"] + "\n\nAcceptance:\n" + "\n".join("- " + x for x in task["acceptance"])
                + "\n\nManaged from an approved, immutable backlog. Editing this issue does NOT change execution authority.",
        })
        return row["number"]

    def pr(self, number):
        return self.http.call("GET", self.root + f"/pulls/{int(number)}")

    def files(self, number):
        result = []
        for page in range(1, 4):
            rows = self.http.call("GET", self.root + f"/pulls/{int(number)}/files?per_page=100&page={page}")
            result.extend(rows)
            if len(rows) < 100:
                return result
        raise RuntimeError("PR is too large for unattended processing")

    def ci(self, sha):
        params = urlencode({"head_sha": sha, "event": "pull_request", "per_page": 100})
        rows = self.http.call("GET", self.root + "/actions/workflows/ci.yml/runs?" + params)["workflow_runs"]
        rows = [r for r in rows if r.get("head_sha") == sha and r.get("event") == "pull_request"
                and r.get("head_repository", {}).get("full_name") == self.repo]
        if not rows:
            return "WAIT", ""
        latest = max(rows, key=lambda r: r["id"])
        link = latest["html_url"]
        if latest["status"] != "completed":
            return "WAIT", link
        if latest["conclusion"] != "success":
            return "FAIL", link
        jobs = self.http.call("GET", self.root + f"/actions/runs/{latest['id']}/jobs?per_page=100")["jobs"]
        if not any(j.get("name") == "qa" and j.get("conclusion") == "success" for j in jobs):
            return "FAIL", link
        return "PASS", link

    def merge(self, number, sha):
        result = self.http.call("PUT", self.root + f"/pulls/{int(number)}/merge", {"sha": sha, "merge_method": "squash"})
        if not result.get("merged"):
            raise RuntimeError("GitHub did not confirm merge")
        return result

    def close_issue(self, number):
        self.http.call("PATCH", self.root + f"/issues/{int(number)}", {"state": "closed"})

    def close_pr(self, number):
        self.http.call("PATCH", self.root + f"/pulls/{int(number)}", {"state": "closed"})

    def comment_pr(self, number: int, body: str) -> dict:
        return self.http.call(
            "POST",
            self.root + f"/issues/{int(number)}/comments",
            {"body": body[:60000]},
        )

    def find_open_prs(self, *, head: str | None = None, task_id: str | None = None) -> list[dict]:
        """List open PRs optionally filtered by head branch or task id in title/body."""
        matches = []
        owner = self.repo.split("/")[0]
        for page in range(1, 21):
            if head:
                path = (
                    self.root
                    + f"/pulls?state=open&per_page=100&page={page}&head="
                    + quote(f"{owner}:{head}", safe=":")
                )
            else:
                path = self.root + f"/pulls?state=open&per_page=100&page={page}"
            rows = self.http.call("GET", path)
            if not isinstance(rows, list):
                break
            for row in rows:
                if task_id:
                    title = str(row.get("title") or "")
                    body = str(row.get("body") or "")
                    marker = f"[team:{task_id}]"
                    tokens = title.replace("|", " ").replace("(", " ").replace(")", " ").split()
                    if marker not in body and marker not in title and task_id not in tokens and task_id not in title:
                        continue
                matches.append(row)
            if head or len(rows) < 100:
                break
        return matches

    def find_open_pr_number(self, *, head: str | None = None, task_id: str | None = None) -> int | None:
        rows = self.find_open_prs(head=head, task_id=task_id)
        if not rows:
            return None
        return int(rows[0]["number"])

    def request(self, title, body):
        row = self.http.call("POST", self.root + "/issues", {"title": "[owner-request] " + title[:100], "body": body[:12000] + "\n\nPENDING SCOPE REVIEW: not executable from chat text."})
        return row["html_url"]


class NullTelegram:
    """Local/optional Telegram: status still written to disk; no network commands."""

    def preflight(self):
        return {"id": 0, "username": "local-optional"}

    def updates(self, offset):
        return []

    def send(self, chat_id, text, buttons=None):
        return {"message_id": 0}

    def answer(self, callback_id):
        return True


class Telegram:
    def __init__(self, token):
        if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", token):
            raise ValueError("Invalid Telegram bot token format")
        self.http = Http("https://api.telegram.org/bot" + token, {}, "Telegram")

    def call(self, method, payload=None):
        response = self.http.call("POST", "/" + method, payload or {})
        if not response.get("ok"):
            raise ProviderError("Telegram", response.get("error_code", 0))
        return response["result"]

    def preflight(self):
        if self.call("getWebhookInfo").get("url"):
            raise RuntimeError("Bot has an existing webhook. Use a dedicated bot; do not silently replace it.")
        return self.call("getMe")

    def updates(self, offset):
        return self.call("getUpdates", {"offset": offset, "timeout": 20, "allowed_updates": ["message", "callback_query"]})

    def send(self, chat_id, text, buttons=None):
        payload = {"chat_id": chat_id, "text": text[:4000], "link_preview_options": {"is_disabled": True}}
        if buttons:
            payload["reply_markup"] = {"inline_keyboard": buttons}
        return self.call("sendMessage", payload)

    def answer(self, callback_id):
        return self.call("answerCallbackQuery", {"callback_query_id": callback_id})
