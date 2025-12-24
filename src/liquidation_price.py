from .config import (
    LEVERAGE_PROFILES, 
    NUM_LEVERAGE_SAMPLES,
    MIN_LEVERAGE,
    MAX_LEVERAGE,
    TOTAL_BUFFER, 
    NUM_BUCKETS
)
from typing import List, Tuple
from .models import Side, Entry, Status, Liquidation, Direction
import pandas as pd
import random
import numpy as np

from . import entries


def sample_leverages(
    profile: str = "neutral", 
    funding_rate: float = 0.0, 
    num_samples: int = None
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Sample leverages from a continuous normal distribution with probability weights.
    
    This creates smooth, realistic liquidation gradients with proper USD allocation
    based on how likely each leverage is to be used.
    
    Args:
        profile: 'conservative', 'neutral', 'aggressive', or 'dynamic'
        funding_rate: Current funding rate (used for dynamic adjustment)
        num_samples: Number of samples to generate (defaults to NUM_LEVERAGE_SAMPLES)
    
    Returns:
        Tuple of (leverages, weights) where:
        - leverages: Array of leverage values between MIN_LEVERAGE and MAX_LEVERAGE
        - weights: Probability weights (sum to 1.0) based on normal distribution density
    """
    if num_samples is None:
        num_samples = NUM_LEVERAGE_SAMPLES
    
    # Dynamic profile adjusts based on funding rate
    if profile == "dynamic":
        # High funding = market is hot = traders use higher leverage
        aggressiveness = min(abs(funding_rate) * 10000, 2.0)  # 0.0003 -> 3.0, cap at 2.0
        
        mean = 25.0 + (aggressiveness * 30.0)  # 25x -> 85x as funding increases
        std = 15.0 - (aggressiveness * 5.0)    # 15 -> 5 (tighter distribution at high funding)
        
    else:
        # Use predefined profile
        params = LEVERAGE_PROFILES.get(profile, LEVERAGE_PROFILES["neutral"])
        mean = params["mean"]
        std = params["std"]
    
    # Sample from normal distribution
    leverages = np.random.normal(mean, std, num_samples)
    
    # Clip to realistic bounds
    leverages = np.clip(leverages, MIN_LEVERAGE, MAX_LEVERAGE)
    
    # Calculate probability density for each leverage using numpy
    # PDF of normal distribution: (1 / (σ√(2π))) * e^(-((x-μ)²)/(2σ²))
    # This ensures leverages near the mean get more USD allocation
    coefficient = 1.0 / (std * np.sqrt(2 * np.pi))
    exponent = -((leverages - mean) ** 2) / (2 * std ** 2)
    pdf_values = coefficient * np.exp(exponent)
    
    # Normalize to sum to 1.0
    weights = pdf_values / pdf_values.sum()
    
    return leverages, weights


def get_liq(entry_price: float, leverage: int, is_long: bool) -> float:
    base = 1 / leverage

    if is_long:
        return entry_price * (1 - base) + entry_price * TOTAL_BUFFER
    else:
        return entry_price * (1 + base) - entry_price * TOTAL_BUFFER


def fetch_liquidation_levels(entries: List[Entry], distribution: str, total_oi_usd, close_usd: float, funding_rate: float, agg_df: pd.DataFrame):

    # Will Store All Price Liq Lvls
    liquidations: List[Liquidation] = []

    # Sample continuous leverages with probability weights
    # Leverages near the mean get higher weights (more USD allocation)
    leverages, weights = sample_leverages(profile=distribution, funding_rate=funding_rate)

    for entry in entries:
        # Determine direction for this entry
        if entry.side == Side.NEUTRAL:
            is_long_liq = random.random() < 0.5
        else:
            is_long_liq = (entry.side == Side.LONG)
        
        side_str = 'long' if is_long_liq else 'short'
        
        # Create liquidation point for each sampled leverage
        # USD allocation is weighted by probability (common leverages get more USD)
        for leverage, weight in zip(leverages, weights):
            liq_price = get_liq(entry.price, leverage, is_long_liq)
            usd = entry.weight * weight * total_oi_usd  # Weight varies by leverage probability!
            
            liquidations.append(Liquidation(
                liq_price=liq_price,
                amnt_usd_liq=usd,
                side=side_str,
                entry_start_time=entry.start_time
            ))

    binned = bin_liquidations(liquidations, close_usd, agg_df, NUM_BUCKETS)

    # Create a DF of Raw Points (Used in Calculating Gravity; Easiest Place to Extract)
    raw_data = []
    for l in liquidations:
        status = Status.ACTIVE
        history = agg_df[agg_df['timestamp'] > l.entry_start_time]

        if not history.empty:
            low_after = history['low'].min()
            high_after = history['high'].max()

            if l.side == 'long':
                if low_after <= l.liq_price:
                    status = Status.CLEARED
            else:  # short
                if high_after >= l.liq_price:
                    status = Status.CLEARED

        raw_data.append({
            'price': l.liq_price,
            'usd': l.amnt_usd_liq,
            'side': Side.LONG if l.side == 'long' else Side.SHORT,
            'entry_start_time': l.entry_start_time,
            'status': status
        })

    df_liq = pd.DataFrame(raw_data)

    # Return Tuple
    return binned, df_liq


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
    binned = df_liq.groupby('bucket', observed=False)[
        'usd'].sum().reset_index()

    # Add mid price and intensity %
    binned['mid_price'] = binned['bucket'].apply(lambda x: x.mid)
    max_usd = binned['usd'].max()
    binned['intensity'] = (binned['usd'] / max_usd *
                           100).round(1) if max_usd > 0 else 0

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
def render_bins(binned, current_price, total_oi_usd, direction: Direction):
    print(f"\n{'='*60}")
    print(f"{'LIQUIDATION HEATMAP':^60}")
    print(f"{'='*60}")
    print(
        f"Current Price: ${current_price:,.0f} | Total OI: ${total_oi_usd/1e9:.2f}B\n")
    print(
        f"Directional Bias: {direction.bias.name} | UPWARD MAGNET: {direction.upward_mag:,.2f} | DOWNWARD MAGNET: {direction.downward_mag:,.2f}\n")

    for _, row in binned.head(15).iterrows():
        bar = '█' * int(row['intensity'] / 5)
        side = "LONG" if row['mid_price'] < current_price else "SHORT"
        # Access enum name for cleaner printing
        status_name = row['status'].name if hasattr(
            row['status'], 'name') else str(row['status'])
        print(
            f"{status_name:8} | {side:5} ${row['mid_price']:8,.0f} | {bar:<20} {row['intensity']:5.1f}% (${row['usd']/1e9:.2f}B)")
