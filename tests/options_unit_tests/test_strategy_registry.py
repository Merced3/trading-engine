from strategies.options import ENABLED_STRATEGY_BUILDERS, load_strategies


def test_registered_strategies_load_explicitly():
    strategies = load_strategies()

    assert strategies
    assert len(ENABLED_STRATEGY_BUILDERS) == 6
    assert all(getattr(strategy, "name", None) for strategy in strategies)
    assert len({strategy.name for strategy in strategies}) == len(strategies)
