import ccxt
import pandas as pd
from typing import List, Any, Optional
from .config import ACTIVE_EXCHANGES, TIMEFRAME, LOOKBACK, SYMBOLS

def fetch_single_exchange_data(
    exchange: Any, 
    symbols: Optional[List[str]] = None,
    lookback: Optional[int] = None
) -> pd.DataFrame | None:
    """
    Fetch data from a single exchange.
    
    Args:
        exchange: CCXT exchange instance
        symbols: Optional list of symbols to try. If None, uses global SYMBOLS
        lookback: Optional lookback in hours. If None, uses global LOOKBACK
    """
    if symbols is None:
        symbols = SYMBOLS
    if lookback is None:
        lookback = LOOKBACK

    # Aggregator that Carries Each Applicable Pair (If Multiple)
    all_symbols: List[pd.DataFrame] = []

    try:

        # Pull Market
        markets = exchange.load_markets()

        # Try multiple possible symbols until one works
        valid_symbol = None
        for sym_candidate in symbols:
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
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=lookback) # Open, High, Low, Close, Volume
        funding = exchange.fetch_funding_rate(symbol)                              # Funding Rate
        current_oi = exchange.fetch_open_interest(symbol)                          # Open Interest
        ticker = exchange.fetch_ticker(symbol)                                     # Real-Time Ticker Data

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
                    symbol, timeframe=TIMEFRAME, limit=lookback
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
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume', 'volume_usd']].copy()
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
                 oi_df['oi_usd_hist'] = oi_df['oi_usd_hist'].fillna(oi_df['openInterestValue']).infer_objects(copy=False)
            
            # Try: explicit USD Value (Binance variant)
            if 'openInterestUSD' in oi_df.columns:
                 oi_df['oi_usd_hist'] = oi_df['oi_usd_hist'].fillna(oi_df['openInterestUSD']).infer_objects(copy=False)

            # Fallback: Calculate from Contracts/Amount * Price (Bybit, OKX)
            if 'openInterestAmount' in oi_df.columns:
                calculated_oi = oi_df['openInterestAmount'] * current_price
                oi_df['oi_usd_hist'] = oi_df['oi_usd_hist'].fillna(calculated_oi).infer_objects(copy=False)
            
            elif 'openInterest' in oi_df.columns: # try generic key 'openInterest'
                calculated_oi = oi_df['openInterest'] * current_price
                oi_df['oi_usd_hist'] = oi_df['oi_usd_hist'].fillna(calculated_oi).infer_objects(copy=False)

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
            
def get_exchanges(exchange_list: Optional[List[str]] = None)->List[ccxt.Exchange]:
    """
    Initialize exchange objects.
    
    Args:
        exchange_list: Optional list of exchange IDs. If None, uses ACTIVE_EXCHANGES
    """
    if exchange_list is None:
        exchange_list = ACTIVE_EXCHANGES
        
    # initialize exchanges
    exchanges: List[ccxt.Exchange] = []

    # Create Exchange Object From Each Active
    for exchange_id in exchange_list:
        try:
            # Create Exchange Object From ID
            exchange_class = getattr(ccxt, exchange_id)
            # Append to List
            exchanges.append(exchange_class())
        except AttributeError:
            print(f"⚠️ Exchange '{exchange_id}' not found in CCXT")
    
    return exchanges

def fetch_data(
    ticker: Optional[str] = None,
    exchanges: Optional[List[str]] = None,
    lookback: Optional[int] = None
)->pd.DataFrame:
    """
    Fetch data from multiple exchanges.
    
    Args:
        ticker: Optional ticker symbol (e.g., 'BTC'). If None, uses config default
        exchanges: Optional list of exchange IDs. If None, uses ACTIVE_EXCHANGES
        lookback: Optional lookback in hours. If None, uses LOOKBACK from config
    """
    from .config import get_symbols_for_ticker
    
    # Use defaults if not provided
    if ticker:
        symbols = get_symbols_for_ticker(ticker)
    else:
        symbols = SYMBOLS
    
    # Get Exchanges
    exchange_objects:List[ccxt.Exchange] = get_exchanges(exchanges)

    # List of DF
    all_df: List[pd.DataFrame] = []

    for ex in exchange_objects:
        
        # Fetch All Symbols (USDT/USDC/USD) For Single Exchange
        df = fetch_single_exchange_data(ex, symbols=symbols, lookback=lookback)

        # Only append if data was successfully fetched
        if df is not None and not df.empty:
            all_df.append(df)

    # Ensure we have at least some data
    if not all_df:
        raise ValueError("No data fetched from any exchange. Check exchange availability and symbols.")

    # Combine All Exchanges Df (Ordered By Timestamp)
    combined_df = pd.concat(all_df, ignore_index=True)
    combined_df = combined_df.sort_values('timestamp').reset_index(drop=True)

    # Fill historical gaps with current (especially Hyperliquid)
    combined_df['oi_usd_hist'] = combined_df['oi_usd_hist'].fillna(combined_df['oi_usd_current'])

    # Calculate OI delta per exchange
    combined_df = combined_df.sort_values(['exchange', 'timestamp'])
    combined_df['oi_delta'] = combined_df.groupby('exchange')['oi_usd_hist'].diff()

    return combined_df