# Trading Engine

A personal options trading engine that runs multiple strategies against shared
market data on multiple candle timeframes. It currently targets one configured
underlying symbol at a time (SPY by default) and supports paper execution.

The project's scope is deliberately narrow:

- acquire market data and build candles;
- run independent strategies on the configured timeframes;
- manage option selection, orders, positions, and end-of-day exits;
- retain trade events and calculate strategy performance;
- expose charts and operational notifications.

Autonomous strategy research and self-learning claims have been removed. A
strategy must be explicitly implemented, tested, and registered before the
engine can run it.

> Educational and personal use only. Not financial advice. Real-money execution
> must remain disabled until its safety and deployment paths have been reviewed.

## Current state

The engine works as a long-running local Python process, but it is **not yet
VPS-ready**. Market data, objects, trade events, configuration, and some runtime
state are still file-backed. It also owns a direct Discord connection. Remote
storage, automation-harness lifecycle management, and discord-hub transport are
separate migrations; this repository does not pretend they are already done.

## Requirements

- Python 3.11 or newer (Python 3.13 is used for local development and CI)
- the sibling `automation-harness` checkout
- provider credentials for market data and brokers, when used

## Setup

From `Automations/projects`:

```bash
cd trading-engine
python -m venv .venv
source .venv/Scripts/activate       # Git Bash on Windows
python -m pip install --upgrade pip
python -m pip install -e ../automation-harness
python -m pip install -e ".[dev]"
cp cred-example.py cred.py          # then fill local secrets; never commit it
pytest
ruff check .
```

`automation-harness` is declared as a runtime dependency for the lifecycle
migration. Installing the sibling checkout first avoids relying on an
unpublished package index release.

## Run

```bash
python main.py
```

Review `config.json`, especially `REAL_MONEY_ACTIVATED`, before starting. Tests
stub credentials and do not start live provider, broker, or Discord connections.

## Development

```bash
pytest
ruff check .
python -m pip install -e ".[postgres]"  # Postgres/Alembic migration tooling
```

The codebase is still in its original flat-module layout. Moving modules under
`src/` is intentionally deferred until imports and runtime entry points can be
changed with test coverage, rather than mixed into the storage migration.

## Documentation

- [Purpose and current boundaries](docs/overview/trading-engine.md)
- [Architecture map](docs/architecture/overview.md)
- [Options subsystem](docs/architecture/options-subsystem.md)
- [Current storage](docs/data/storage-system.md)
- [Strategies](docs/strategies/README.md)
- [Configuration](docs/configuration/ticker-and-timeframes.md)
- [Roadmap](docs/roadmap.md)
