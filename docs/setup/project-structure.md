# Project structure

The repository currently uses its original flat-module layout. A future `src/`
move should be a separate mechanical refactor with import and entry-point tests.

```text
trading-engine/
├── main.py                  # Process orchestration and scheduling
├── config.json              # Local runtime configuration
├── cred-example.py          # Credential field reference; cred.py is ignored
├── data_acquisition.py      # Provider REST/websocket acquisition
├── objects.py               # Zone/level calculations
├── paths.py                 # Current local-storage path registry
├── session.py               # Market calendar and session timing
├── shared_state.py          # Legacy shared price state and logging
├── indicators/              # EMA and flag state
├── integrations/            # Discord and economic calendar adapters
├── options/                 # Quotes, execution, orders, positions, trade ledger
├── pipeline/                # Candle construction and event publication
├── runtime/                 # Market bus, strategy runner, reporting
├── storage/                 # Parquet/DuckDB and object persistence
├── strategies/options/      # Explicit executable strategies
├── tools/                   # Maintenance and trade analytics commands
├── utils/                   # Shared helpers
├── web_dash/                # Dash charts and websocket refresh service
├── tests/                   # Offline unit and integration tests
├── docs/                    # Current contracts, runbooks, and ADRs
├── pyproject.toml           # Packaging, dependencies, lint, and test config
└── .github/workflows/       # CI
```

`storage/` also contains ignored runtime data. Those files are not package
source and must not be deleted by cleanup commands. The old `venv/` is ignored;
use `.venv/` created by the currently installed Python.
