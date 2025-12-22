from enum import Enum
from .config import LEVERAGE_DISTRIBUTIONS, LEVERAGE_TIERS,  TOTAL_BUFFER, NUM_BUCKETS
from typing import List
from .entries import Side, Entry
import pandas as pd
from dataclasses import dataclass
import random
import numpy as np

from . import entries

class Status(Enum):
    ACTIVE = "ACTIVE"
    CLEARED = "CLEARED"
    PARTIAL = "PARTIAL"

@dataclass
class Liquidation:
    liq_price: float
    amnt_usd_liq: float
    side: str  # 'long' or 'short'
    entry_start_time: pd.Timestamp = None

# Get Weights From Config Helper
def get_leverage_distribution(profile: str = "neutral", funding_rate: float = 0.0) -> List[float]:


    if profile == "dynamic":
        
        # Base = Neutral (We'll Scale Based on Funding Rate)
        weights = LEVERAGE_DISTRIBUTIONS["neutral"].copy()

        # Guage Aggression
        aggressiveness = abs(funding_rate) * 10000 #(0.0003 -> 3.0)
        aggressiveness = min(aggressiveness, 2.0)  # Cap @ 2.0

        # Shift weights toward higher leverage
        for i in range(len(weights)):

            # Higher i = higher leverage tier
            shift_factor = (i / (len(weights) - 1)) ** 1.5  # more shift to high tiers
            weights[i] *= (1 + aggressiveness * shift_factor * 0.5)

        # Re-normalize
        total = sum(weights)
        weights = [w / total for w in weights]

        return weights


    else:
        return LEVERAGE_DISTRIBUTIONS.get(profile, LEVERAGE_DISTRIBUTIONS["neutral"])


def get_liq(entry_price: float, leverage: int, is_long: bool) -> float:
    base = 1 / leverage

    if is_long:
        return entry_price * (1 - base) + entry_price * TOTAL_BUFFER
    else:
        return entry_price * (1 + base) - entry_price * TOTAL_BUFFER


def fetch_liquidation_levels(entries: List[Entry], distribution: str, total_oi_usd, close_usd: float, funding_rate:float, agg_df: pd.DataFrame):

    # Will Store All Price Liq Lvls
    liquidations: List[Liquidation] = []

    leverage_distribution = get_leverage_distribution(profile=distribution, funding_rate=funding_rate)

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
            side_str = 'long' if is_long_liq else 'short'

            liquidations.append(Liquidation(
                liq_price=liq_price, 
                amnt_usd_liq=usd, 
                side=side_str, 
                entry_start_time=entry.start_time
            ))
        
    binned = bin_liquidations(liquidations, close_usd, agg_df, NUM_BUCKETS)
    return binned

def bin_liquidations(liquidations: List[Liquidation], current_price: float, agg_df: pd.DataFrame, num_buckets: int = 20):
    if not liquidations:
        return pd.DataFrame()

    df_liq = pd.DataFrame([{
        'price': l.liq_price, 
        'usd': l.amnt_usd_liq, 
        'side': l.side, 
        'entry_start_time': l.entry_start_time
    } for l in liquidations])

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
    binned = df_liq.groupby('bucket', observed=False)['usd'].sum().reset_index()

    # Add mid price and intensity %
    binned['mid_price'] = binned['bucket'].apply(lambda x: x.mid)
    max_usd = binned['usd'].max()
    binned['intensity'] = (binned['usd'] / max_usd * 100).round(1) if max_usd > 0 else 0

    # Sort by intensity
    binned = binned.sort_values('intensity', ascending=False)

    return add_liquidation_status(binned, df_liq, agg_df)

def add_liquidation_status(binned: pd.DataFrame, df_liq: pd.DataFrame, agg_df: pd.DataFrame) -> pd.DataFrame:
    
    # Stores Status Per; Pushed to DF Col @END
    statuses = []
    
    # Iterate Through ALl Bins
    for row in binned.itertuples():
        bucket = row.bucket  # Pull Our Interval object
        
        # Extract original liquidations in bucket
        group = df_liq[df_liq['bucket'] == bucket]
        
        if group.empty:
            statuses.append(Status.ACTIVE)  # no points = active by default
            continue
        
        cleared_usd = 0.0
        partial_usd = 0.0
        bin_usd = group['usd'].sum()
        
        # Check each point individually for max acc.
        for p in group.itertuples():

            # Only Pull Price history after this specific entry was opened
            history_after = agg_df[agg_df['timestamp'] > p.entry_start_time]
            
            if history_after.empty:
                # No history after entry = active
                continue
            
            # Get relevant extremes after entry
            low_after = history_after['low'].min()
            high_after = history_after['high'].max()
            
            # Bin edges for this point
            bin_low = bucket.left
            bin_high = bucket.right
            
            # Determine if cleared/partial
            if p.side == 'long':
                fully_cleared = low_after <= bin_low
                partially = low_after < bin_high and not fully_cleared
            else:  # short
                fully_cleared = high_after >= bin_high
                partially = high_after > bin_low and not fully_cleared
            
            # Weight by this point's USD
            if fully_cleared:
                cleared_usd += p.usd
            elif partially:
                partial_usd += p.usd
            # else active = rest
        
        # Aggregate status weighted by USD
        cleared_pct = cleared_usd / bin_usd if bin_usd > 0 else 0
        partial_pct = partial_usd / bin_usd if bin_usd > 0 else 0
        
        # Majority rule: if >80% cleared, full cleared; >20% partial, partial; else active
        if cleared_pct > 0.8:
            status = Status.CLEARED
        elif partial_pct > 0.2 or cleared_pct > 0.2:
            status = Status.PARTIAL
        else:
            status = Status.ACTIVE
        
        statuses.append(status)
    
    binned['status'] = statuses
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
        cleared = row['status']
        print(f"{cleared} | {side:5} ${row['mid_price']:8,.0f} | {bar:<20} {row['intensity']:5.1f}% (${row['usd']/1e9:.2f}B)")


    

    
