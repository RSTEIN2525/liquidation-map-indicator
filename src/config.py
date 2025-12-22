# Exchagnge
ACTIVE_EXCHANGES = ['binance', 'bybit', 'okx', 'hyperliquid']

SYMBOLS = [
    'BTC/USDT:USDT',   # Binance
    'BTCUSDT',         # Bybit
    'BTC-USDT-SWAP',   # OKX
    'BTC-PERP',        # Common Perp Format
    'BTC/USDC:USDC',   # Hyperliquid
]

TIMEFRAME = '1h'
LOOKBACK = 24 * 14

# Weighting of Entry Detection METHODOLOGIES
WEIGHT_HOTZONE   = 0.70
WEIGHT_VOLUME_OI = 0.20
WEIGHT_VWAP      = 0.10 

# Weighting of LONG/SHORT Masks
VOL_MASK   = 0.75   # Top 25%
PRICE_MASK = 0.008  # 0.8% move
DELTA_MASK = 0.70   # Top 30%



# Liquidation Prices
LEVERAGE_TIERS = [5, 10, 20, 25, 50, 75, 100, 125]

LEVERAGE_DISTRIBUTIONS = {
    "conservative": [0.25, 0.25, 0.20, 0.15, 0.10, 0.03, 0.01, 0.01],  # heavy low lev
    "neutral":      [0.10, 0.15, 0.20, 0.20, 0.15, 0.10, 0.07, 0.03],  # bell around 20-50x
    "aggressive":   [0.05, 0.08, 0.10, 0.12, 0.20, 0.20, 0.15, 0.10],  # heavy high lev
}

MMR = 0.005        # 0.1% -- AVG Taker Fee on Liq.
FEE_BUFFER = 0.001 # 0.5%
TOTAL_BUFFER = MMR + FEE_BUFFER

NUM_BUCKETS = 20

# Price Resolution
DISTANCE_DECAY_FACTOR = 2