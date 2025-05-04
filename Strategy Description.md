# ETF Trend-Following Trading Strategy Implementation Guide

This guide outlines the implementation details for a trend-following ETF trading strategy designed as a complement to a passive ETF allocation. The strategy uses simple moving average filters and correlation metrics to identify trading opportunities across a diverse set of ETFs, with specific guidance on managing position drift.

## Strategy Overview

The core strategy employs trend filters to identify ETFs in strong uptrends while selecting those with the lowest correlation to the S\&P 500 to enhance portfolio diversification. Historical performance indicates a 10.10% CAGR since 1999 with relatively low correlation (0.04) to the S\&P 500.

## Data Requirements

**ETF Universe:**

- TLT - 20+ Year Treasury Bonds
- TBF - Short 20+ Year Treasury Bonds
- DBC - Commodities
- IEF - 7-10 Year Treasury Bonds
- GLD - Gold
- QQQ - Nasdaq 100
- HYG - High Yield Corporate Bonds

**Required Data:**

- Daily closing prices for all ETFs and S\&P 500
- Weekly prices (for correlation calculations)


## Implementation Steps

### 1. Calculate Technical Indicators

```
For each ETF in the universe:
    Calculate 50-day simple moving average (50-day SMA)
    Calculate 200-day simple moving average (200-day SMA)
```


### 2. Apply Trend Filters

```
For each ETF in the universe:
    If (Current Close Price > 50-day SMA) AND (50-day SMA > 200-day SMA):
        Add ETF to filtered_candidates list
```

The two conditions represent a dual confirmation of an uptrend - the price must be above its intermediate-term average, and the intermediate-term average must be above the long-term average.

### 3. Calculate Correlations

```
For each ETF in filtered_candidates:
    Calculate 26-week correlation with S&P 500 using weekly price data
    Store the correlation value
```


### 4. Select ETFs with Lowest Correlation

```
Sort filtered_candidates by their correlation to S&P 500 (ascending order)
If len(filtered_candidates) >= 3:
    selected_etfs = filtered_candidates[0:3]  # Take top 3 with lowest correlation
Elif len(filtered_candidates) > 0:
    selected_etfs = filtered_candidates  # Take all that passed filters
Else:
    selected_etfs = []  # No ETFs passed filters
```


### 5. Portfolio Construction

```
If len(selected_etfs) == 0:
    Allocate 100% to cash
Elif len(selected_etfs) == 1:
    Allocate 100% to the single ETF
Else:
    Allocate equally among selected_etfs
```


### 6. Position Drift Management

```
# Set relative tolerance bands
tolerance_band = 25%  # Allow 25% relative drift from target allocation

# Example with 2 ETFs:
# Initial allocation: ETF1 = 50%, ETF2 = 50%
# Acceptable range for ETF1: 37.5% to 62.5% (50% ± 25% of 50%)
# Acceptable range for ETF2: 37.5% to 62.5% (50% ± 25% of 50%)

# Only rebalance if:
# 1. An ETF position exceeds its tolerance band, OR
# 2. An ETF no longer meets trend criteria (exit signal)

For each ETF in current_portfolio:
    target_allocation = 1 / len(current_portfolio)
    lower_bound = target_allocation - (target_allocation * tolerance_band)
    upper_bound = target_allocation + (target_allocation * tolerance_band)
    
    current_allocation = ETF_value / total_portfolio_value
    
    # Only rebalance if position has drifted beyond the tolerance band
    if current_allocation < lower_bound or current_allocation > upper_bound:
        Rebalance to target_allocation
```


### 7. Monitor for Exit Signals

```
For each position in current_portfolio:
    If (Current Close Price < 200-day SMA) OR (50-day SMA < 200-day SMA):
        Sell the position
        # The funds from the sold position are either:
        # 1. Reallocated to remaining positions, OR
        # 2. Held as cash until the next review period
```


## Rebalancing Logic and Schedule

```
# Run check at predetermined frequency (e.g., weekly or monthly)
Perform full strategy evaluation (steps 1-5) at regular intervals:
    - Identify ETFs that meet trend criteria
    - Select ETFs with lowest correlation
    - Adjust portfolio as needed

# Position Drift Handling:
- Allow positions to drift within 25% relative tolerance bands
- Only rebalance positions that exceed their bands
- Priority is given to trend/correlation criteria over maintaining exact allocations
- When adding new positions:
    Equal-weight among new positions
```


## Performance Metrics to Monitor

- CAGR (Compound Annual Growth Rate)
- Maximum Drawdown
- Sharpe Ratio
- Correlation to S\&P 500
- Turnover Rate


## Implementation Notes

1. The strategy uses generous 25% relative tolerance bands to allow winning positions to grow while maintaining reasonable diversification. This means if the target allocation is 50%, the position can drift between 37.5% and 62.5% before triggering a rebalance.
2. Rebalancing is primarily driven by trend filter conditions rather than allocation drift. When an ETF falls below its trend requirements, it's sold regardless of its current weight.
3. The correlation calculation should use weekly bars over a 26-week lookback period to focus on medium-term relationships rather than short-term noise.
4. If no ETFs pass the filters, the implementation should move to cash until candidates emerge.
5. The "Golden Cross" (50-day MA above 200-day MA) is a common technical indicator signaling bullish conditions, while the "Death Cross" (50-day MA below 200-day MA) signals bearish conditions.
6. Position weights may become significantly unbalanced during strong trends in a particular asset class, which is an intentional feature of the strategy that allows for maximizing returns in strongly trending markets.
7. A 25% relative band is recommended as it provides significant flexibility while still preventing extreme concentration - this aligns with the strategy's emphasis on allowing position drift while maintaining some diversification benefits.

