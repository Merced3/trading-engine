# Session: Trading Engine — VPS deployment

**Suggested session name:** `trading-engine: NYC3 VPS rollout`

**Gate:** P2f storage cutover, harness lifecycle, and discord-hub transport are
verified. Real-money activation is a separate explicit decision and is not part
of this prompt.

## Prompt

Deploy Trading Engine to its own NYC3 VPS using the shared ops conventions.
Start in paper mode and size from measured engine/query requirements, not the
old laptop's historical 1.9 GB raw-quote artifact.

1. Read `ops/DATA.md`, `ops/RUNBOOK.md`, and P3b. Inventory CPU, memory, network,
   browser/Selenium needs, ports, secrets, and external provider/broker effects.
2. Present sizing, cost, service topology, firewall/Tailscale policy, backup,
   health, and rollback plan; stop for owner approval before provisioning.
3. Add reproducible container/service configuration and environment-based
   secrets. No authoritative local market/trade storage and no baked-in tokens.
4. Test build and startup offline; include migrations, health/readiness, graceful
   shutdown, restart recovery, and log rotation.
5. Deploy paper mode through the reviewed ops path. Verify provider connections,
   remote reads/writes, strategy analytics, hub delivery, and reboot recovery.
6. Keep source data under the deletion gate until backup + restore evidence and
   explicit owner approval are complete. Do not enable real-money execution.

**Done when:** the paper-mode VPS service survives restart, passes health and
remote-data checks, has backup/rollback runbooks, and makes no unintended live
orders or public network exposures.

## Session Progress
