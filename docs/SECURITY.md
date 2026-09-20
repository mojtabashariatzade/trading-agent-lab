# Security and limitations

This is a tested STARTER, not a production audit or a proof that AI-generated
software is correct. Mock API tests do not certify online behavior or vendor
schema stability. Cursor v1 is currently documented as a public beta.

Trust boundary: operator-controlled immutable image and persistent state versus
untrusted candidate repository code. The controller never imports or executes
candidate code; its only remote calls target fixed HTTPS providers. Redirects
are rejected. HTTP exceptions omit token-bearing URLs and response bodies.

Cloud workers inevitably have development access to their research repository.
Prevent writes/merges to main using provider-enforced actor restrictions, not
prompts alone. Do not inject broker, controller, Telegram or paid-data secrets
into Cursor cloud environments. Read only the needed public research data.

CI executes untrusted code on fresh GitHub-hosted runners with read-only token,
no repository secrets, no persisted checkout credential and finite timeout.
Do not convert it to pull_request_target or attach a privileged self-hosted runner.
Changes to workflow files, protected tests, controller and policy are refused by
the controller even if the candidate says the changes are harmless.

Independent QA means a fresh context/run, not a guarantee of independence from
the same model's blind spots. A CI pass and a JSON PASS may both miss defects.
Human owner approval is therefore kept for every starter merge. Financial,
security, production and paid-scope changes need dedicated review.

The starter reporter uses deterministic templates. Natural-language chat planning,
autonomous backlog expansion, monetary-usage reconciliation, GitHub App token
rotation, externally supervised liveness alerts and audited phased auto-merge
are NOT implemented. Do not describe them as deployed capabilities.

Backups and host monitoring must live outside the controller. A dead controller
cannot send its own reliable Telegram outage message. Use hosting-provider
health alerts; configure their recipient outside the code agent.
