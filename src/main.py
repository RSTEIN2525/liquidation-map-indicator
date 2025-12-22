from .exchange_data import fetch_data
from .entries import estimate_entries, Entry, get_summary_stats, aggregate_market_view
from typing import List
from .liquidation_price import fetch_liquidation_levels, render_bins
from dataclasses import dataclass


@dataclass
class SummaryStats:
    total_oi_usd: float
    close: float
    funding_rate: float
    high: float
    low: float


def main():

    df = fetch_data()
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
    bins = fetch_liquidation_levels(
        entries, 
        "dynamic", 
        summary_stats.total_oi_usd, 
        summary_stats.close, 
        summary_stats.funding_rate,
        agg_df
    )

    # Render
    render_bins(bins, summary_stats.close, summary_stats.total_oi_usd)


if __name__ == '__main__':
    main()
