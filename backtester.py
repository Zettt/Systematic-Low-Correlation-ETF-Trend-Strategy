import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from indicators import generate_allocations
from strategy_config import get_strategy


class Backtester:
    def __init__(self, daily_prices, weekly_prices, strategy="sector_rotation", transaction_cost=0.001):
        """
        Initialize backtester with price data.

        Args:
            daily_prices: DataFrame of daily prices (Date, benchmark, assets)
            weekly_prices: DataFrame of weekly prices (Date, benchmark, assets)
            strategy: Strategy id or config
        """
        self.strategy = get_strategy(strategy)

        daily_prices = daily_prices.copy()
        weekly_prices = weekly_prices.copy()
        daily_prices["Date"] = pd.to_datetime(daily_prices["Date"])
        weekly_prices["Date"] = pd.to_datetime(weekly_prices["Date"])
        self.daily_prices = daily_prices.set_index("Date")
        self.weekly_prices = weekly_prices.set_index("Date")
        self.equity_curve = None
        self.trades = None
        self.transaction_cost = transaction_cost
        self.current_holdings = {}

        required_columns = set(self.strategy.universe + (self.strategy.benchmark,))
        missing_daily = required_columns.difference(self.daily_prices.columns)
        missing_weekly = required_columns.difference(self.weekly_prices.columns)
        if missing_daily:
            raise ValueError(f"Missing daily price columns for {self.strategy.strategy_id}: {sorted(missing_daily)}")
        if missing_weekly:
            raise ValueError(f"Missing weekly price columns for {self.strategy.strategy_id}: {sorted(missing_weekly)}")

    def calculate_cagr(self, equity_curve):
        """Calculate Compound Annual Growth Rate."""
        if len(equity_curve) < 2:
            return 0.0

        start_value = equity_curve.iloc[0]
        end_value = equity_curve.iloc[-1]
        years = (equity_curve.index[-1] - equity_curve.index[0]).days / 365.25
        if years <= 0 or start_value <= 0:
            return 0.0
        return (end_value / start_value) ** (1 / years) - 1

    def calculate_max_drawdown(self, equity_curve):
        """Calculate maximum drawdown."""
        if len(equity_curve) < 2:
            return 0.0, None, None

        peak = equity_curve.iloc[0]
        max_drawdown = 0.0
        peak_date = equity_curve.index[0]
        trough_date = equity_curve.index[0]

        for date, value in equity_curve.items():
            if value > peak:
                peak = value
                peak_date = date
            else:
                drawdown = (peak - value) / peak
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
                    trough_date = date
        return max_drawdown, peak_date, trough_date

    def calculate_sharpe(self, returns, risk_free_rate=0.0):
        """Calculate annualized Sharpe ratio."""
        if len(returns) < 2:
            return 0.0

        excess_returns = returns - risk_free_rate / 252
        volatility = excess_returns.std()
        if volatility == 0 or np.isnan(volatility):
            return 0.0
        return np.sqrt(252) * excess_returns.mean() / volatility

    def check_drift(self, current_allocations, allocs, tolerance=0.25):
        """Check if any position has drifted beyond tolerance."""
        for etf in current_allocations:
            if etf not in allocs:
                continue
            target = allocs[etf]
            actual = current_allocations[etf]
            if abs(actual - target) > target * tolerance:
                return True
        return False

    def run_backtest(self, initial_capital=10000, rebalance_freq="M"):
        """Run event-driven backtest."""
        portfolio_value = pd.Series(index=self.daily_prices.index, dtype=float)
        portfolio_value.iloc[0] = initial_capital
        holdings = {}
        trades = []

        rebalance_dates = pd.date_range(
            start=self.daily_prices.index[0],
            end=self.daily_prices.index[-1],
            freq="ME" if rebalance_freq == "M" else rebalance_freq,
        )

        for index in range(1, len(self.daily_prices)):
            current_date = self.daily_prices.index[index]
            prev_date = self.daily_prices.index[index - 1]

            if holdings:
                portfolio_value[current_date] = sum(
                    shares * self.daily_prices.loc[current_date, etf]
                    for etf, shares in holdings.items()
                )
            else:
                portfolio_value[current_date] = portfolio_value[prev_date]

            current_allocations = {}
            if holdings:
                total_value = portfolio_value[current_date]
                current_allocations = {
                    etf: (shares * self.daily_prices.loc[current_date, etf]) / total_value
                    for etf, shares in holdings.items()
                }

            allocations = generate_allocations(
                self.daily_prices.loc[:current_date].reset_index(),
                self.weekly_prices.loc[:current_date].reset_index(),
                current_holdings=current_allocations if holdings else None,
                universe=self.strategy.universe,
                benchmark=self.strategy.benchmark,
            )

            should_trade = current_date in rebalance_dates
            if holdings and not should_trade:
                should_trade = self.check_drift(current_allocations, allocations)
            if holdings and "CASH" in allocations and not should_trade:
                should_trade = True

            if not should_trade:
                continue

            if "CASH" in allocations:
                if holdings:
                    total_cost = 0.0
                    for etf, shares in holdings.items():
                        price = self.daily_prices.loc[current_date, etf]
                        proceeds = shares * price
                        cost = proceeds * self.transaction_cost
                        total_cost += cost
                        trades.append(
                            {
                                "date": current_date,
                                "etf": etf,
                                "shares": -shares,
                                "price": price,
                                "type": "sell",
                                "reason": "exit_signal" if current_date not in rebalance_dates else "rebalance",
                                "cost": cost,
                            }
                        )
                    portfolio_value[current_date] -= total_cost
                holdings = {}
                continue

            target_value = {
                etf: alloc * portfolio_value[current_date]
                for etf, alloc in allocations.items()
            }
            target_shares = {
                etf: target_value[etf] / self.daily_prices.loc[current_date, etf]
                for etf in allocations
            }

            total_cost = 0.0
            for etf in set(holdings).union(allocations):
                current_shares = holdings.get(etf, 0.0)
                target_share = target_shares.get(etf, 0.0)
                price = self.daily_prices.loc[current_date, etf]

                if np.isclose(current_shares, target_share):
                    continue

                trade_shares = target_share - current_shares
                trade_value = abs(trade_shares * price)
                cost = trade_value * self.transaction_cost
                total_cost += cost
                trades.append(
                    {
                        "date": current_date,
                        "etf": etf,
                        "shares": trade_shares,
                        "price": price,
                        "type": "buy" if trade_shares > 0 else "sell",
                        "reason": "rebalance",
                        "cost": cost,
                    }
                )

            portfolio_value[current_date] -= total_cost
            holdings = dict(target_shares)

        self.equity_curve = portfolio_value
        self.trades = pd.DataFrame(trades)
        return self

    def get_performance_metrics(self, risk_free_rate=0.0):
        """Calculate and return key performance metrics."""
        if self.equity_curve is None:
            raise ValueError("Must run backtest first")

        returns = self.equity_curve.pct_change().dropna()
        cagr = self.calculate_cagr(self.equity_curve)
        max_dd, peak_date, trough_date = self.calculate_max_drawdown(self.equity_curve)
        sharpe = self.calculate_sharpe(returns, risk_free_rate)

        benchmark_curve = self.daily_prices[self.strategy.benchmark]
        benchmark_returns = benchmark_curve.pct_change().dropna()
        benchmark_cagr = self.calculate_cagr(benchmark_curve)
        benchmark_max_dd = self.calculate_max_drawdown(benchmark_curve)[0]
        benchmark_sharpe = self.calculate_sharpe(benchmark_returns, risk_free_rate)

        normalized_etfs = self.daily_prices[list(self.strategy.universe)].div(
            self.daily_prices[list(self.strategy.universe)].iloc[0]
        )
        equal_weight_etf = normalized_etfs.mean(axis=1) * self.equity_curve.iloc[0]
        equal_weight_returns = equal_weight_etf.pct_change().dropna()

        return {
            "strategy": {
                "CAGR": cagr,
                "Max Drawdown": max_dd,
                "Sharpe Ratio": sharpe,
                "Peak Date": peak_date,
                "Trough Date": trough_date,
            },
            "benchmark": {
                "CAGR": benchmark_cagr,
                "Max Drawdown": benchmark_max_dd,
                "Sharpe Ratio": benchmark_sharpe,
            },
            "all_etfs": {
                "CAGR": self.calculate_cagr(equal_weight_etf),
                "Max Drawdown": self.calculate_max_drawdown(equal_weight_etf)[0],
                "Sharpe Ratio": self.calculate_sharpe(equal_weight_returns, risk_free_rate),
            },
        }

    def plot_results(self):
        """Generate performance visualization plots."""
        if self.equity_curve is None:
            raise ValueError("Must run backtest first")

        norm_equity = self.equity_curve / self.equity_curve.iloc[0]
        norm_benchmark = (
            self.daily_prices[self.strategy.benchmark] / self.daily_prices[self.strategy.benchmark].iloc[0]
        )
        normalized_etfs = self.daily_prices[list(self.strategy.universe)].div(
            self.daily_prices[list(self.strategy.universe)].iloc[0]
        )
        equal_weight_etf = normalized_etfs.mean(axis=1) * self.equity_curve.iloc[0]
        norm_etfs = equal_weight_etf / equal_weight_etf.iloc[0]

        peak = self.equity_curve.cummax()
        drawdown = (self.equity_curve - peak) / peak * 100

        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            subplot_titles=("Equity Curve Comparison", "Strategy Drawdown (%)"),
        )
        fig.add_trace(
            go.Scatter(x=norm_equity.index, y=norm_equity, name="Strategy", line=dict(color="blue")),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=norm_benchmark.index,
                y=norm_benchmark,
                name=self.strategy.benchmark,
                line=dict(color="orange"),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=norm_etfs.index, y=norm_etfs, name="Equal-Weight ETFs", line=dict(color="green")),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=drawdown.index, y=drawdown, fill="tozeroy", name="Drawdown", line=dict(color="red")),
            row=2,
            col=1,
        )
        fig.update_layout(
            height=800,
            width=1000,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=50, r=50, t=80, b=50),
        )
        fig.update_yaxes(title_text="Normalized Value", row=1, col=1)
        fig.update_yaxes(title_text="Drawdown (%)", row=2, col=1)
        return fig
