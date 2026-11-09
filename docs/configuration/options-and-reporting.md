# Options and reporting configuration

These values currently live in `config.json` and are read directly by runtime
code. Configuration is not yet environment-based or database-backed.

## Options

- `NUM_OUT_OF_MONEY`: number of out-of-money contracts considered by selection.
- `OPTION_EXPIRATION_DTE`: expiration selector; `not specified` currently
  resolves to `0dte`.
- `RECORD_OPTIONS_QUOTES`: records every polled quote to a daily JSONL file.
  Keep this false unless raw capture is required: one historical day file is
  approximately 1.56 GB.
- `OPTIONS_QUOTES_DIR`: destination for optional raw quote recordings.
- `REAL_MONEY_ACTIVATED`: selects real-money behavior where implemented. Keep
  false during development and migration.

## Strategy reporting

`STRATEGY_REPORTING` controls Discord strategy reports:

- `enabled`: enable report delivery.
- `use_test_channel`: route to the configured test channel.
- `update_existing`: edit existing reports instead of always creating new ones.

`STRATEGY_TAG_INCLUDE_TIMEFRAME` includes the candle timeframe in strategy tags,
which keeps same-strategy results separate across timeframes.

## Indicators and sessions

- `EMAS`: EMA periods and chart colors.
- `TIMEFRAMES`: active candle timeframes and strategy event subscriptions.
- `LIVE_BARS`: expected regular-session candle counts by timeframe.
- `MINS_BEFORE_MAJOR_NEWS_ORDER_CANCELATION`: news safety buffer used by the
  economic-calendar integration.
