import pandas as pd
import numpy as np
from .models import Side, Status, Bias, Direction
from .config import DISTANCE_DECAY_FACTOR

def calculate_magnetism(current_price: float, raw_liqs: pd.DataFrame):
    # Clean and Split Liquidations
    short_liqs, long_liqs = clean_liquidations(raw_liqs)

    # Calculate Forces (Vectorized)
    # Shorts are ABOVE price -> Pull UP
    upward_mag = calculate_directional_pull(current_price, short_liqs)
    
    # Longs are BELOW price -> Pull DOWN
    downward_mag = calculate_directional_pull(current_price, long_liqs)

    total_mag = upward_mag + downward_mag
    
    # Avoid division by zero if total_mag is 0
    if total_mag == 0:
        return Bias.UNBIASED, 0.0, 0.0

    net_mag = abs(upward_mag - downward_mag)

    bias = Bias.UNBIASED
    
    # 3. Determine Bias
    if (net_mag / total_mag) > 0.05:
        if upward_mag > downward_mag: 
            bias = Bias.UP
        else:
            bias = Bias.DOWN

    return bias, upward_mag, downward_mag


def calculate_directional_pull(current_price: float, df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    
    # Calculate Distances for the whole column at once
    distances = np.abs(current_price - df['price'])
    
    # Replace any 0.0 distance with 0.01 to avoid Div/0 errors
    distances = distances.replace(0, 0.01)

    # Calculate Force: Mass / Distance^Alpha
    forces = df['usd'] / (distances ** DISTANCE_DECAY_FACTOR)

    # Sum the forces
    return forces.sum()


def clean_liquidations(binned: pd.DataFrame):
    # Keep only Active rows
    live = binned[binned['status'] == Status.ACTIVE].copy()

    # Long Positions get liquidated BELOW price (Downside Gravity)
    long_pos_liqs = live[live['side'] == Side.LONG]

    # Short Positions get liquidated ABOVE price (Upside Gravity)    
    short_pos_liqs = live[live['side'] == Side.SHORT]

    # Return: (Shorts/Upside source, Longs/Downside source)
    return short_pos_liqs, long_pos_liqs