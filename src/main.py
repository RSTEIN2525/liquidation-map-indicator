from .exchange_data import fetch_data
from .entries import estimate_entries, Entry,get_summary_stats
from typing import List
from .liquidation_price import fetch_liquidation_levels, render_bins

def main():
   
    df = fetch_data()
    entries: List[Entry] = estimate_entries(df)
    
    # Get Summary Stats
    recieved = get_summary_stats(df)
    total_oi_usd = recieved.get("total_oi_usd")
    close        = recieved.get("cur_price")

    # Get My LVLs Binned
    bins = fetch_liquidation_levels(entries, "neutral", total_oi_usd, close)

    # Render
    render_bins(bins, close, total_oi_usd)

if __name__ == '__main__':
    main()
