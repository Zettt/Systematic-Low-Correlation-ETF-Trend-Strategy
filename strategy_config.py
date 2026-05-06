from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StrategyConfig:
    strategy_id: str
    display_name: str
    universe: tuple[str, ...]
    benchmark: str = "SPY"

    @property
    def data_dir(self) -> Path:
        return Path("data") / self.strategy_id

    @property
    def daily_prices_path(self) -> Path:
        return self.data_dir / "daily_prices.csv"

    @property
    def weekly_prices_path(self) -> Path:
        return self.data_dir / "weekly_prices.csv"

    @property
    def indicators_path(self) -> Path:
        return self.data_dir / "indicators.csv"


STRATEGIES = {
    "core": StrategyConfig(
        strategy_id="core",
        display_name="Core Low-Correlation ETF Strategy",
        universe=("TLT", "TBF", "DBC", "IEF", "GLD", "QQQ", "HYG"),
    ),
    "sector_rotation": StrategyConfig(
        strategy_id="sector_rotation",
        display_name="Sector Rotation Low-Correlation ETF Strategy",
        universe=(
            "TLT",
            "TBF",
            "DBC",
            "IEF",
            "GLD",
            "HYG",
            "XLB",
            "XLE",
            "XLF",
            "XLI",
            "XLK",
            "XLP",
            "XLU",
            "XLV",
            "XLY",
            "XLRE",
            "XLC",
        ),
    ),
}


def get_strategy(strategy):
    if isinstance(strategy, StrategyConfig):
        return strategy
    try:
        return STRATEGIES[strategy]
    except KeyError as exc:
        available = ", ".join(sorted(STRATEGIES))
        raise ValueError(f"Unknown strategy '{strategy}'. Available: {available}") from exc
