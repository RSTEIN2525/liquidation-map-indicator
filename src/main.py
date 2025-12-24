from .exchange_data import fetch_data
from .entries import estimate_entries, get_summary_stats, aggregate_market_view
from typing import List, Optional
from .liquidation_price import fetch_liquidation_levels, render_bins
from .resolution import calculate_magnetism
from .models import SummaryStats, Direction, Entry
import pandas as pd
import ccxt


def main(ticker: Optional[str] = None, exchanges: Optional[List[str]] = None, lookback_days: Optional[float] = None):
    """
    Main function with optional parameters for custom analysis.
    
    Args:
        ticker: Ticker symbol (e.g., 'BTC')
        exchanges: List of exchange IDs to use
        lookback_days: Number of days to look back
    """
    from .config import get_lookback_hours
    
    # Convert days to hours if provided
    lookback_hours = get_lookback_hours(lookback_days) if lookback_days else None
    
    df = fetch_data(ticker=ticker, exchanges=exchanges, lookback=lookback_hours)
    agg_df = aggregate_market_view(df)
    entries: List[Entry] = estimate_entries(df)

    # Get Summary Stats
    recieved = get_summary_stats(df)
    summary_stats = SummaryStats(total_oi_usd=recieved.get("total_oi_usd"),
                                 close=recieved.get("cur_price"),
                                 funding_rate=recieved.get("funding_rate"),
                                 high=recieved.get("high"),
                                 low=recieved.get("low"))

    # Get My LVLs Binned
    bins, raw_liqs = fetch_liquidation_levels(
        entries,
        "dynamic",
        summary_stats.total_oi_usd,
        summary_stats.close,
        summary_stats.funding_rate,
        agg_df
    )

    # Pass the raw points into magnetism
    bias, upward_mag, downward_mag = calculate_magnetism(
        summary_stats.close, raw_liqs)

    direction = Direction(
        bias=bias,
        upward_mag=upward_mag,
        downward_mag=downward_mag
    )

    # Render
    render_bins(bins, summary_stats.close,
                summary_stats.total_oi_usd, direction)


def calculate_map_data(
    ticker: Optional[str] = None,
    exchanges: Optional[List[str]] = None,
    lookback_days: Optional[float] = None
):
    """
    This function does the heavy lifting but returns DATA, not text.
    
    Args:
        ticker: Optional ticker symbol (e.g., 'BTC', 'ETH')
        exchanges: Optional list of exchange IDs
        lookback_days: Optional lookback period in days
    """
    from .config import get_lookback_hours
    
    # Convert days to hours if provided
    lookback_hours = get_lookback_hours(lookback_days) if lookback_days else None
    
    df = fetch_data(ticker=ticker, exchanges=exchanges, lookback=lookback_hours)
    agg_df = aggregate_market_view(df)
    entries = estimate_entries(df)

    recieved = get_summary_stats(df)
    summary_stats = SummaryStats(
        total_oi_usd=recieved.get("total_oi_usd"),
        close=recieved.get("cur_price"),
        funding_rate=recieved.get("funding_rate"),
        high=recieved.get("high"),
        low=recieved.get("low")
    )

    bins, raw_liqs = fetch_liquidation_levels(
        entries,
        "dynamic",
        summary_stats.total_oi_usd,
        summary_stats.close,
        summary_stats.funding_rate,
        agg_df
    )

    bias, upward_mag, downward_mag = calculate_magnetism(
        summary_stats.close, raw_liqs
    )
    
    direction = Direction(bias=bias, upward_mag=upward_mag, downward_mag=downward_mag)

    # RETURN a dictionary that defines your API structure
    return {
        "summary": summary_stats,
        "direction": direction,
        "bins": bins,           # DataFrame of binned/bucketed data
        "raw_liqs": raw_liqs,   # DataFrame of individual liquidation points
        "generated_at": pd.Timestamp.now()
    }


if __name__ == '__main__':
    # main()
    print(ccxt.exchanges)
