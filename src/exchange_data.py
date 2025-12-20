import ccxt
import pandas as pd
from typing import List, Any
from .config import ACTIVE_EXCHANGES, TIMEFRAME, LOOKBACK, SYMBOLS

def fetch_single_exchange_data(exchange: Any) -> pd.DataFrame | None:

    # Aggregator that Carries Each Applicable Pair (If Multiple)
    all_symbols: List[pd.DataFrame] = []

    try:

        # Pull Market
        markets = exchange.load_markets()

        # Try multiple possible symbols until one works
        valid_symbol = None
        for sym_candidate in SYMBOLS:
            if sym_candidate in markets:
                valid_symbol = sym_candidate
                break

        # No Valid Symbol Exists
        if not valid_symbol:
            print(f"No valid symbol found for {exchange.id}")
            return None

        # First Working Symbol
        symbol = valid_symbol

        # Core Data That Will Be Duplicated Across Timestamps (1/T.F. Metric)
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=LOOKBACK) # Open, High, Low, Close, Volume
        funding = exchange.fetch_funding_rate(symbol)                             # Funding Rate
        current_oi = exchange.fetch_open_interest(symbol)                         # Open Interest
        ticker = exchange.fetch_ticker(symbol)                                    # Real-Time Ticker Data

        # Gets Current Price For Ticker Via: {markPrice -> last -> close -> OHLCV close}
        current_price = (
            ticker.get('markPrice') or 
            ticker.get('last') or 
            ticker.get('close') or 
            (ohlcv[-1][4] if ohlcv else None)
        )
        
        # Error: Price DNE 
        if current_price is None:
            print(f"{exchange.id}: Warning - Could not determine mark/current price")

        # Historical Open Interest
        oi_history = None

        # Exchnage Has ccxt api-interface default
        if exchange.has['fetchOpenInterestHistory']:
            try:
                # Pull OI History overy tf, lookback
                oi_history = exchange.fetch_open_interest_history(
                    symbol, timeframe=TIMEFRAME, limit=LOOKBACK
                )

            # Base CCXT API Failed    
            except Exception as e:
                print(f"{exchange.id}: Unified OI history failed: {e}")

        # Build base candle DataFrame
        df = pd.DataFrame(
            ohlcv,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        df['volume_usd'] = df['volume'] * df['close']
        df = df[['timestamp', 'close', 'volume', 'volume_usd']].copy()
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        # Add static/current fields
        df['funding_rate'] = funding.get('fundingRate')
        
        # Robust current OI check
        df['oi_usd_current'] = (
            current_oi.get('openInterestValue') or 
            current_oi.get('openInterestAmount', 0) * (current_price or 0) #OKX Fallback
        )
        
        df['mark_price'] = current_price
        df['exchange'] = exchange.id
        df['symbol'] = symbol

        # Historical Open Interest
        if oi_history: # Validate Field Exists

            # Build Open Interest Dataframe
            oi_df = pd.DataFrame(oi_history)

            # Clean Timestamp
            oi_df['timestamp'] = pd.to_datetime(oi_df['timestamp'], unit='ms')

            # Initialize target column with NaNs
            oi_df['oi_usd_hist'] = float('nan')

            # Try: explicit USD Value (CCXT Standard API)
            if 'openInterestValue' in oi_df.columns:
                 oi_df['oi_usd_hist'] = oi_df['oi_usd_hist'].fillna(oi_df['openInterestValue'])
            
            # Try: explicit USD Value (Binance variant)
            if 'openInterestUSD' in oi_df.columns:
                 oi_df['oi_usd_hist'] = oi_df['oi_usd_hist'].fillna(oi_df['openInterestUSD'])

            # Fallback: Calculate from Contracts/Amount * Price (Bybit, OKX)
            if 'openInterestAmount' in oi_df.columns:
                calculated_oi = oi_df['openInterestAmount'] * current_price
                oi_df['oi_usd_hist'] = oi_df['oi_usd_hist'].fillna(calculated_oi)
            
            elif 'openInterest' in oi_df.columns: # try generic key 'openInterest'
                calculated_oi = oi_df['openInterest'] * current_price
                oi_df['oi_usd_hist'] = oi_df['oi_usd_hist'].fillna(calculated_oi)

            # Cleanup
            if 'oi_usd_hist' in oi_df.columns:
               
                # Drop rows where we still couldn't find ANY data
                oi_df = oi_df.dropna(subset=['oi_usd_hist'])
                
                # Organize & Clean Dups
                oi_df = oi_df[['timestamp', 'oi_usd_hist']]
                oi_df = oi_df.drop_duplicates(subset=['timestamp'])
                
                # Merge to Main DF
                df = df.merge(oi_df, on='timestamp', how='left')
                df['oi_usd_hist'] = df['oi_usd_hist'].ffill()
            else:
                df['oi_usd_hist'] = None
        else:
            df['oi_usd_hist'] = None

        all_symbols.append(df)

        if all_symbols:
            exchange_df = pd.concat(all_symbols, ignore_index=True)
            return exchange_df
        else:
            return None

    except Exception as e:
        print(f"Error in {exchange.id}: {e}")
        # traceback.print_exc() # Uncomment for deep debugging
        return None
            
def get_exchanges()->List[ccxt.Exchange]:
     # initialize exchanges
    exchanges: List[ccxt.Exchange] = []

    # Create Exchange Object From Each Active
    for exchange_id in ACTIVE_EXCHANGES:
        
        # Create Exchange Object From ID
        exchange_class = getattr(ccxt, exchange_id)

        # Append to List
        exchanges.append(exchange_class())
    
    return exchanges

def fetch_data()->pd.DataFrame:
     # Get Exchanges
    exchanges:List[ccxt.Exchange] = get_exchanges()

    # List of DF
    all_df: List[pd.DataFrame] = []

    for ex in exchanges:
        
        # Fetch All Symbols (USDT/USDC/USD) For Single Exchange
        df = fetch_single_exchange_data(ex)

        # Push to Aggregator
        all_df.append(df)

    # Combine All Exchanges Df (Ordered By Timestamp)
    combined_df = pd.concat(all_df, ignore_index=True)
    combined_df = combined_df.sort_values('timestamp').reset_index(drop=True)

    # Fill historical gaps with current (especially Hyperliquid)
    combined_df['oi_usd_hist'] = combined_df['oi_usd_hist'].fillna(combined_df['oi_usd_current'])

    # Calculate OI delta per exchange
    combined_df = combined_df.sort_values(['exchange', 'timestamp'])
    combined_df['oi_delta'] = combined_df.groupby('exchange')['oi_usd_hist'].diff()

    return combined_df