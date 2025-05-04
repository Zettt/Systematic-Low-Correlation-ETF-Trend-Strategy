import pandas as pd
from indicators import generate_allocations

def main():
    # Load data
    daily_prices = pd.read_csv('data/daily_prices.csv')
    weekly_prices = pd.read_csv('data/weekly_prices.csv')
    
    # Generate allocations
    allocations = generate_allocations(daily_prices, weekly_prices)
    
    print("Target Portfolio Allocations:")
    for etf, weight in allocations.items():
        print(f"{etf}: {weight:.1%}")

if __name__ == "__main__":
    main()