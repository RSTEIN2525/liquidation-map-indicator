from .config import LEVERAGE_DISTRIBUTIONS, LEVERAGE_TIERS,  TOTAL_BUFFER, NUM_BUCKETS
from typing import List
from .entries import Side, Entry
import pandas as pd
from dataclasses import dataclass
import random
import numpy as np

from . import entries


@dataclass
class Liquidation:
    liq_price: float
    amnt_usd_liq: float

# Get Weights From Config Helper
def get_leverage_distribution(profile: str = "neutral") -> List[float]:
    return LEVERAGE_DISTRIBUTIONS.get(profile, LEVERAGE_DISTRIBUTIONS["neutral"])


def get_liq(entry_price: float, leverage: int, is_long: bool) -> float:
    base = 1 / leverage

    if is_long:
        return entry_price * (1 - base) + entry_price * TOTAL_BUFFER
    else:
        return entry_price * (1 + base) - entry_price * TOTAL_BUFFER


def fetch_liquidation_levels(entries: List[Entry], distribution: str, total_oi_usd, close_usd: float):

    # Will Store All Price Liq Lvls
    liquidations: List[Liquidation] = []

    leverage_distribution = get_leverage_distribution(profile=distribution)

    for entry in entries:
        for leverage, probability in zip(LEVERAGE_TIERS, leverage_distribution):

            # Associated LEVERAGE has 0 PROB.
            if probability == 0:
                continue

            # Randomly assign neutral to long/short liq direction
            if entry.side == Side.NEUTRAL:
                is_long_liq = random.random() < 0.5
            else:
                is_long_liq = (entry.side == Side.LONG)

            liq_price = get_liq(entry.price, leverage, is_long_liq)
            usd = entry.weight * probability * total_oi_usd

            liquidations.append(Liquidation(
                liq_price=liq_price, amnt_usd_liq=usd))
        
    binned = bin_liquidations(liquidations,close_usd, NUM_BUCKETS)
    return binned

def bin_liquidations(liquidations: List[Liquidation], current_price: float, num_buckets: int = 20):
    if not liquidations:
        return pd.DataFrame()

    df_liq = pd.DataFrame([{'price': l.liq_price, 'usd': l.amnt_usd_liq} for l in liquidations])

    # Create symmetric buckets around current price
    max_distance = df_liq['price'].sub(current_price).abs().max()

    # Just In Case They're All Clustered; Stops Error Down Line
    if max_distance == 0:
        max_distance = current_price * 0.01

    bucket_size = max_distance / (num_buckets // 2)

    # Edges: from low to high, centered on current
    lower = current_price - (num_buckets // 2) * bucket_size
    upper = current_price + (num_buckets // 2) * bucket_size
    edges = np.linspace(lower, upper, num_buckets + 1)

    df_liq['bucket'] = pd.cut(df_liq['price'], bins=edges, include_lowest=True)
    binned = df_liq.groupby('bucket')['usd'].sum().reset_index()

    # Add mid price and intensity %
    binned['mid_price'] = binned['bucket'].apply(lambda x: x.mid)
    max_usd = binned['usd'].max()
    binned['intensity'] = (binned['usd'] / max_usd * 100).round(1)

    # Sort by intensity
    binned = binned.sort_values('intensity', ascending=False)

    return binned


# Render Helper
def render_bins(binned, current_price, total_oi_usd):
    print(f"\n{'='*60}")
    print(f"{'LIQUIDATION HEATMAP':^60}")
    print(f"{'='*60}")
    print(f"Current Price: ${current_price:,.0f} | Total OI: ${total_oi_usd/1e9:.2f}B\n")

    for _, row in binned.head(15).iterrows():
        bar = '█' * int(row['intensity'] / 5)
        side = "LONG" if row['mid_price'] < current_price else "SHORT"
        print(f"{side:5} ${row['mid_price']:8,.0f} | {bar:<20} {row['intensity']:5.1f}% (${row['usd']/1e9:.2f}B)")


    

    
