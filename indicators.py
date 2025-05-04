import pandas as pd
import numpy as np

def calculate_sma(prices, window):
    """Calculate simple moving average for given window"""
    return prices.rolling(window=window).mean()

def calculate_correlations(weekly_prices, window=26):
    """
    Calculate rolling correlations with SPY for each ETF
    Returns DataFrame with correlation values
    """
    weekly_prices = weekly_prices.set_index('Date')
    correlations = {}
    for etf in weekly_prices.columns:
        if etf != 'SPY':
            correlations[f'{etf}_corr'] = weekly_prices[etf].rolling(window=window).corr(weekly_prices['SPY'])
    return pd.DataFrame(correlations)

def check_entry_signals(daily_prices):
    """
    Check entry conditions:
    Close > SMA50 and SMA50 > SMA200
    Returns DataFrame with boolean entry signals
    """
    daily_prices = daily_prices.set_index('Date')
    entry_signals = {}
    for etf in daily_prices.columns:
        sma50 = calculate_sma(daily_prices[etf], 50)
        sma200 = calculate_sma(daily_prices[etf], 200)
        entry_signals[f'{etf}_entry'] = (daily_prices[etf] > sma50) & (sma50 > sma200)
    return pd.DataFrame(entry_signals)

def check_exit_signals(daily_prices):
    """
    Check exit conditions:
    Close < SMA200 OR SMA50 < SMA200
    Returns DataFrame with boolean exit signals
    """
    daily_prices = daily_prices.set_index('Date')
    exit_signals = {}
    for etf in daily_prices.columns:
        sma50 = calculate_sma(daily_prices[etf], 50)
        sma200 = calculate_sma(daily_prices[etf], 200)
        exit_signals[f'{etf}_exit'] = (daily_prices[etf] < sma200) | (sma50 < sma200)
    return pd.DataFrame(exit_signals)

def calculate_indicators():
    """
    Main function to calculate all indicators
    Returns combined DataFrame with all indicators
    """
    # Load data and set Date as index
    daily_prices = pd.read_csv('data/daily_prices.csv').set_index('Date')
    weekly_prices = pd.read_csv('data/weekly_prices.csv')
    
    # Calculate indicators
    sma50 = daily_prices.apply(lambda x: calculate_sma(x, 50))
    sma200 = daily_prices.apply(lambda x: calculate_sma(x, 200))
    correlations = calculate_correlations(weekly_prices)
    entry_signals = check_entry_signals(daily_prices.reset_index())
    exit_signals = check_exit_signals(daily_prices.reset_index())
    
    # Combine all indicators
    indicators = pd.concat([
        daily_prices,
        sma50.add_suffix('_sma50'),
        sma200.add_suffix('_sma200'),
        entry_signals,
        exit_signals,
        correlations.reindex(daily_prices.index).ffill()  # Align with daily data
    ], axis=1)
    
    return indicators.reset_index()

def generate_allocations(daily_prices, weekly_prices, current_holdings=None):
    """
    Generate target portfolio allocations based on:
    - Entry signals (Close > SMA50 and SMA50 > SMA200)
    - Exit signals (Close < SMA200 OR SMA50 < SMA200)
    - Lowest correlation to SPY
    - Equal weighting among 1-3 selected ETFs
    
    Args:
        daily_prices: DataFrame of daily prices
        weekly_prices: DataFrame of weekly prices
        current_holdings: dict of current ETF holdings (for exit signal checking)
    
    Returns dict of {etf: target_weight} allocations
    """
    # Get entry and exit signals
    entry_signals = check_entry_signals(daily_prices)
    exit_signals = check_exit_signals(daily_prices)
    
    # Handle exits first if we have current holdings
    if current_holdings:
        for etf in current_holdings:
            if etf != 'CASH' and exit_signals[f'{etf}_exit'].iloc[-1]:
                return {'CASH': 1.0}
    
    # Filter ETFs by entry signals
    filtered = [etf.replace('_entry', '') for etf in entry_signals.columns
              if entry_signals[etf].iloc[-1]]
    
    # If no ETFs pass entry filter, return all cash
    if not filtered:
        return {'CASH': 1.0}
    
    # Calculate correlations
    correlations = calculate_correlations(weekly_prices).add_suffix('_corr')
    last_correlations = correlations.iloc[-1].to_dict()
    
    # Filter to only include ETFs that passed trend filter
    corr_subset = {k.replace('_corr', ''): v
                  for k, v in last_correlations.items()
                  if k.replace('_corr', '') in filtered}
    
    # Sort by correlation (ascending) and take top 3
    sorted_etfs = sorted(corr_subset.items(), key=lambda x: x[1])
    selected = [etf for etf, corr in sorted_etfs[:3]]
    
    # Equal weight allocation
    num_selected = len(selected)
    if num_selected == 1:
        return {selected[0]: 1.0}
    else:
        return {etf: 1.0/num_selected for etf in selected}

if __name__ == "__main__":
    indicators_df = calculate_indicators()
    print(indicators_df.head())
    indicators_df.to_csv('data/indicators.csv', index=False)