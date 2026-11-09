"""Explicit registry of strategies the engine is allowed to execute."""

from collections.abc import Callable

from strategies.options import (
    candle_ema_break,
    candle_ema_break_trend_trail,
    ema_crossover,
    ema_regime_fusion,
    ema_snapback,
    mtf_odds_onepos,
)

# Registration is deliberate: adding a Python file alone must not enable trades.
ENABLED_STRATEGY_BUILDERS: tuple[Callable[[], object], ...] = (
    candle_ema_break.build_strategy,
    candle_ema_break_trend_trail.build_strategy,
    ema_crossover.build_strategy,
    ema_regime_fusion.build_strategy,
    ema_snapback.build_strategy,
    mtf_odds_onepos.build_strategy,
)


def load_strategies() -> list[object]:
    """Build every registered strategy, flattening multi-instance builders."""
    strategies: list[object] = []
    for build in ENABLED_STRATEGY_BUILDERS:
        built = build()
        if isinstance(built, (list, tuple)):
            strategies.extend(item for item in built if item is not None)
        elif built is not None:
            strategies.append(built)
    return strategies
