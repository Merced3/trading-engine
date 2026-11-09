# Session: Trading Engine — discord-hub transport

**Suggested session name:** `trading-engine: discord-hub transport`

**Gate:** Read `discord-hub/docs/integrating.md` and `api.md`. Run separately
from storage and harness migrations. Do not mutate live Discord channels.

## Prompt

Replace Trading Engine's direct `discord.py` connection and credentials with
discord-hub's HTTP contract while preserving strategy execution reports, trade
notifications, file/chart delivery, message editing, and message-ID persistence.

1. Inventory every `integrations/discord` call site and behavior, including rate
   limits, edits, attachments, report updates, and day-performance parsing.
2. Map each behavior to hub endpoints. Identify features that need an explicit
   owner decision rather than silently weakening behavior.
3. Present the adapter contract and stop for review. Trading Engine keeps message
   meaning/templates; the hub owns Discord transport and tokens.
4. Add offline fake-hub contract tests for send/edit/attachment failures, returned
   message IDs, reporting updates, and hub downtime. No Discord library or types
   may leak into strategy/runtime code.
5. Implement the adapter, remove direct bot startup and `discord.py`, and migrate
   configuration to hub URL/channel registration settings.
6. Run an owner-approved bounded test-channel acceptance, then remove legacy
   credentials only after verification. Document rollback and hub-unavailable
   behavior.

**Done when:** no direct Discord connection/token remains, all reporting tests
pass, and real test-channel send/edit/attachment behavior is verified.

## Session Progress
