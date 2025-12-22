from .exchange_data import fetch_data
from .entries import estimate_entries, get_summary_stats, aggregate_market_view
from typing import List
from .liquidation_price import fetch_liquidation_levels, render_bins
from .resolution import calculate_magnetism
from .models import SummaryStats, Direction, Entry


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


if __name__ == '__main__':
    main()
