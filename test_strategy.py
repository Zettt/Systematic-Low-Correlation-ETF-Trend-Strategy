import pandas as pd
import numpy as np
from indicators import generate_allocations, check_entry_signals, check_exit_signals

def check_drift(current_allocations, target_allocations, tolerance=0.25):
    """Check if any position has drifted beyond tolerance"""
    for etf in current_allocations:
        if etf not in target_allocations:
            continue
        target = target_allocations[etf]
        actual = current_allocations[etf]
        if abs(actual - target) > target * tolerance:
            return True, etf, actual, target
    return False, None, None, None

def test_signals():
    """Test entry and exit signal generation"""
    # Load data
    daily_prices = pd.read_csv('data/daily_prices.csv')
    weekly_prices = pd.read_csv('data/weekly_prices.csv')
    
    # Get latest signals
    entry_signals = check_entry_signals(daily_prices)
    exit_signals = check_exit_signals(daily_prices)
    
    print("\nLatest Signals:")
    print("\nEntry Signals:")
    for col in entry_signals.columns:
        if entry_signals[col].iloc[-1]:
            print(f"✓ {col.replace('_entry', '')}")
        else:
            print(f"✗ {col.replace('_entry', '')}")
            
    print("\nExit Signals:")
    for col in exit_signals.columns:
        if exit_signals[col].iloc[-1]:
            print(f"⚠ {col.replace('_exit', '')}")
        else:
            print(f"  {col.replace('_exit', '')}")

def test_allocations():
    """Test allocation generation with and without holdings"""
    # Load data
    daily_prices = pd.read_csv('data/daily_prices.csv')
    weekly_prices = pd.read_csv('data/weekly_prices.csv')
    
    # Test without holdings
    print("\nNew Portfolio Allocations:")
    allocations = generate_allocations(daily_prices, weekly_prices)
    for etf, weight in allocations.items():
        print(f"{etf}: {weight:.1%}")
    
    # Test with example holdings
    test_holdings = {'TLT': 0.5, 'GLD': 0.5}
    print("\nAllocations with Current Holdings:")
    allocations = generate_allocations(daily_prices, weekly_prices, test_holdings)
    for etf, weight in allocations.items():
        print(f"{etf}: {weight:.1%}")

def test_drift():
    """Test position drift from target allocations"""
    # Load data
    daily_prices = pd.read_csv('data/daily_prices.csv')
    weekly_prices = pd.read_csv('data/weekly_prices.csv')
    
    # Example current holdings
    test_holdings = {'TLT': 0.5, 'GLD': 0.5}
    
    # Get target allocations
    target_allocs = generate_allocations(daily_prices, weekly_prices)
    
    # Check drift
    has_drift, drifted_etf, actual, target = check_drift(test_holdings, target_allocs)
    
    print("\nPosition Drift Check:")
    if has_drift:
        print(f"⚠ {drifted_etf} has drifted: Current {actual:.1%} vs Target {target:.1%}")
        print("Rebalancing recommended")
    else:
        print("✓ All positions within drift tolerance")

if __name__ == "__main__":
    print("Testing Strategy Implementation")
    print("=" * 30)
    test_signals()
    test_allocations()
    test_drift()