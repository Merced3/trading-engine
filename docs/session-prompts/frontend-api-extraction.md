# Session: Trading Engine — frontend API and future website

**Suggested session name:** `trading-engine: frontend API`

**Gate:** Remote analytics data is available through stable engine queries. The
personal website does not exist yet; do not make it a deployment blocker.

## Prompt

Decouple Trading Engine from its local Dash diagnostic UI so a future personal
website can present trading analytics without embedding engine rules or receiving
Postgres/R2 credentials. Keep the existing `web_dash` usable locally until the
replacement read path is proven.

1. Inventory chart, viewport, position, run, and strategy-report data needs.
2. Design engine-owned read-only HTTP/WebSocket contracts with explicit schemas,
   timeframe/timezone semantics, pagination/bounds, and authentication/network
   policy. Prefer a small API over exposing database/object-storage credentials.
3. Present API examples and stop for review. Decide which endpoints are public,
   Tailscale-only, or owner-authenticated; default to private.
4. Add contract tests and implement the API against storage adapters, not local
   file paths. Avoid coupling response shapes to Dash components.
5. Keep `web_dash` as a local diagnostic consumer during migration, then measure
   and document its retirement path.
6. Later, build the personal website as a separate frontend project consuming
   these APIs. No website work is required in this session.

**Done when:** stable tested APIs serve the required charts and positive/negative
strategy analytics remotely, access is private by default, and the future website
has no need for direct data-store secrets or trading-domain implementation.

## Session Progress
