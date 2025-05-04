import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from indicators import generate_allocations

class Backtester:
    def __init__(self, daily_prices, weekly_prices):
        """
        Initialize backtester with price data
        
        Args:
            daily_prices: DataFrame of daily prices (Date, ETF1, ETF2, ..., SPY)
            weekly_prices: DataFrame of weekly prices (Date, ETF1, ETF2, ..., SPY)
        """
        # Convert dates to datetime and set as index
        daily_prices['Date'] = pd.to_datetime(daily_prices['Date'])
        weekly_prices['Date'] = pd.to_datetime(weekly_prices['Date'])
        self.daily_prices = daily_prices.set_index('Date')
        self.weekly_prices = weekly_prices.set_index('Date')
        self.equity_curve = None
        self.trades = None
        
    def calculate_cagr(self, equity_curve):
        """Calculate Compound Annual Growth Rate"""
        if len(equity_curve) < 2:
            return 0.0
        
        start_value = equity_curve.iloc[0]
        end_value = equity_curve.iloc[-1]
        years = (equity_curve.index[-1] - equity_curve.index[0]).days / 365.25
        
        if years <= 0 or start_value <= 0:
            return 0.0
            
        return (end_value / start_value) ** (1/years) - 1
    
    def calculate_max_drawdown(self, equity_curve):
        """Calculate maximum drawdown (peak to trough decline)"""
        if len(equity_curve) < 2:
            return (0.0, None, None)
        
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
        
        return (max_drawdown, peak_date, trough_date)
    
    def calculate_sharpe(self, returns, risk_free_rate=0.0):
        """Calculate annualized Sharpe ratio"""
        if len(returns) < 2:
            return 0.0
        
        excess_returns = returns - risk_free_rate/252
        return np.sqrt(252) * excess_returns.mean() / excess_returns.std()
    
    def run_backtest(self, initial_capital=10000, rebalance_freq='M'):
        """
        Run event-driven backtest
        
        Args:
            initial_capital: Starting portfolio value
            rebalance_freq: Pandas offset string for rebalance frequency
                           'M' for month-end rebalancing (changed from 'W-FRI')
        """
        # Initialize portfolio
        portfolio_value = pd.Series(index=self.daily_prices.index, dtype=float)
        portfolio_value.iloc[0] = initial_capital
        holdings = {}
        trades = []
        
        # Get rebalance dates (month-end)
        rebalance_dates = pd.date_range(
            start=self.daily_prices.index[0],
            end=self.daily_prices.index[-1],
            freq='ME' if rebalance_freq == 'M' else rebalance_freq
        )
        
        # Run through each day
        for i in range(1, len(self.daily_prices)):
            current_date = self.daily_prices.index[i]
            prev_date = self.daily_prices.index[i-1]
            
            # Update portfolio value based on price changes
            if holdings:
                daily_returns = self.daily_prices.loc[current_date] / self.daily_prices.loc[prev_date] - 1
                portfolio_value[current_date] = sum(
                    shares * self.daily_prices.loc[current_date, etf]
                    for etf, shares in holdings.items()
                )
            else:
                portfolio_value[current_date] = portfolio_value[prev_date]
            
            # Convert holdings to allocation dict for signal checking
            current_allocations = {}
            if holdings:
                total_value = portfolio_value[current_date]
                current_allocations = {
                    etf: (shares * self.daily_prices.loc[current_date, etf]) / total_value
                    for etf, shares in holdings.items()
                }
            
            # Check signals daily
            allocations = generate_allocations(
                self.daily_prices.loc[:current_date].reset_index(),
                self.weekly_prices.loc[:current_date].reset_index(),
                current_allocations if holdings else None
            )
            
            # Execute trades if we get exit signal or it's rebalance day
            should_trade = current_date in rebalance_dates
            
            # Check if we need to exit positions
            if holdings and 'CASH' in allocations and not should_trade:
                # Exit signal triggered outside rebalance date
                should_trade = True
            
            if should_trade:
                
                # Execute trades
                if 'CASH' in allocations:
                    # Move to cash
                    if holdings:
                        for etf, shares in holdings.items():
                            trades.append({
                                'date': current_date,
                                'etf': etf,
                                'shares': -shares,
                                'price': self.daily_prices.loc[current_date, etf],
                                'type': 'sell',
                                'reason': 'exit_signal' if not current_date in rebalance_dates else 'rebalance'
                            })
                    holdings = {}
                else:
                    # Rebalance to target allocations
                    target_value = {etf: alloc * portfolio_value[current_date] 
                                  for etf, alloc in allocations.items()}
                    
                    # Calculate target shares
                    target_shares = {
                        etf: target_value[etf] / self.daily_prices.loc[current_date, etf]
                        for etf in allocations
                    }
                    
                    # Execute trades
                    for etf in set(holdings.keys()).union(allocations.keys()):
                        current_shares = holdings.get(etf, 0)
                        target_share = target_shares.get(etf, 0)
                        
                        if not np.isclose(current_shares, target_share):
                            trade_shares = target_share - current_shares
                            trades.append({
                                'date': current_date,
                                'etf': etf,
                                'shares': trade_shares,
                                'price': self.daily_prices.loc[current_date, etf],
                                'type': 'buy' if trade_shares > 0 else 'sell',
                                'reason': 'rebalance'
                            })
                    
                    holdings = {etf: shares for etf, shares in target_shares.items()}
        
        self.equity_curve = portfolio_value
        self.trades = pd.DataFrame(trades)
        return self
    
    def get_performance_metrics(self, risk_free_rate=0.0):
        """Calculate and return key performance metrics"""
        if self.equity_curve is None:
            raise ValueError("Must run backtest first")
            
        returns = self.equity_curve.pct_change().dropna()
        cagr = self.calculate_cagr(self.equity_curve)
        max_dd, peak_date, trough_date = self.calculate_max_drawdown(self.equity_curve)
        sharpe = self.calculate_sharpe(returns, risk_free_rate)
        
        # Benchmark (SPY) metrics
        spy_returns = self.daily_prices['SPY'].pct_change().dropna()
        spy_cagr = self.calculate_cagr(self.daily_prices['SPY'])
        spy_max_dd = self.calculate_max_drawdown(self.daily_prices['SPY'])[0]
        spy_sharpe = self.calculate_sharpe(spy_returns, risk_free_rate)
        
        return {
            'strategy': {
                'CAGR': cagr,
                'Max Drawdown': max_dd,
                'Sharpe Ratio': sharpe,
                'Peak Date': peak_date,
                'Trough Date': trough_date
            },
            'benchmark': {
                'CAGR': spy_cagr,
                'Max Drawdown': spy_max_dd,
                'Sharpe Ratio': spy_sharpe
            }
        }
    
    def plot_results(self):
        """Generate performance visualization plots"""
        if self.equity_curve is None:
            raise ValueError("Must run backtest first")
            
        # Create normalized series for comparison
        norm_equity = self.equity_curve / self.equity_curve.iloc[0]
        norm_spy = self.daily_prices['SPY'] / self.daily_prices['SPY'].iloc[0]
        
        # Calculate drawdowns
        peak = self.equity_curve.cummax()
        drawdown = (self.equity_curve - peak) / peak * 100  # Convert to percentage
        
        # Create subplots with 2 rows
        fig = make_subplots(rows=2, cols=1, 
                           shared_xaxes=True,
                           vertical_spacing=0.08,
                           subplot_titles=('Equity Curve Comparison', 'Strategy Drawdown (%)'))
        
        # Add equity curves to top subplot
        fig.add_trace(
            go.Scatter(x=norm_equity.index, y=norm_equity, 
                      name='Strategy', line=dict(color='blue')),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(x=norm_spy.index, y=norm_spy, 
                      name='SPY', line=dict(color='orange')),
            row=1, col=1
        )
        
        # Add drawdown to bottom subplot
        fig.add_trace(
            go.Scatter(x=drawdown.index, y=drawdown, 
                      fill='tozeroy', 
                      name='Drawdown', 
                      line=dict(color='red')),
            row=2, col=1
        )
        
        # Update layout
        fig.update_layout(
            height=800,
            width=1000,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=50, r=50, t=80, b=50)
        )
        
        fig.update_yaxes(title_text="Normalized Value", row=1, col=1)
        fig.update_yaxes(title_text="Drawdown (%)", row=2, col=1)
        
        return fig