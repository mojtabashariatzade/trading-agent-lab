# Cutover gate — MAF durable

**Status: SWITCHED (owner-approved 2026-09-21)**

Live default is now `ORCHESTRATION_BACKEND=maf_durable`.

## Rollback

```powershell
$env:ORCHESTRATION_BACKEND = "legacy"
.\scripts\start-supervisor.ps1 -Restart
```

## Completed gates

- [x] Full suite green
- [x] Resume / parallel / status / flag tests
- [x] Isolated live proof while legacy ran
- [x] Owner approval ("tabdil kon")
- [ ] Docker Desktop + native DTS emulator (optional; local_checkpoint active until then)

## Temporal

Not selected.
