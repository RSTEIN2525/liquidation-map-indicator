# ========== DEFAULT VALUES ========== #
DEFAULT_TICKER = 'BTC'
DEFAULT_EXCHANGES = ['binance', 'bybit', 'okx', 'hyperliquid']
DEFAULT_LOOKBACK_DAYS = 14

# ========== LIVE CONFIG (Set by API or defaults) ========== #
ACTIVE_EXCHANGES = DEFAULT_EXCHANGES
TIMEFRAME = '1h'
LOOKBACK = 24 * DEFAULT_LOOKBACK_DAYS

# SYMBOLS is generated dynamically based on ticker
SYMBOLS = []

# ========== HELPER FUNCTIONS ========== #
def get_symbols_for_ticker(ticker: str) -> list:
    """Generate symbol list for a given ticker (BTC, ETH, etc.)"""
    ticker = ticker.upper()
    return [
        f'{ticker}/USDT:USDT',   # Binance, Bybit (some)
        f'{ticker}USDT',         # Bybit
        f'{ticker}-USDT-SWAP',   # OKX
        f'{ticker}-PERP',        # Common Perp Format
        f'{ticker}/USDC:USDC',   # Hyperliquid
    ]

def get_lookback_hours(days: float) -> int:
    """Convert days to hours for LOOKBACK"""
    return int(24 * days)

def validate_exchanges(exchanges: list) -> list:
    """Validate and filter exchange list"""
    VALID_EXCHANGES = {
        'binance', 'bybit', 'okx', 'hyperliquid', 'mexc', 
        'krakenfutures', 'kucoinfutures', 'gateio', 'bitget', 'deribit'
    }
    return [ex for ex in exchanges if ex.lower() in VALID_EXCHANGES]

def validate_ticker(ticker: str) -> str:
    """Validate ticker symbol"""
    VALID_TICKERS = {'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'ADA'}
    ticker = ticker.upper()
    return ticker if ticker in VALID_TICKERS else 'BTC'

def validate_lookback(days: float) -> float:
    """Validate lookback period (0.5 to 30 days)"""
    return max(0.5, min(30.0, days))

# Initialize with defaults
SYMBOLS = get_symbols_for_ticker(DEFAULT_TICKER)

# Weighting of Entry Detection METHODOLOGIES
WEIGHT_HOTZONE   = 0.70
WEIGHT_VOLUME_OI = 0.20
WEIGHT_VWAP      = 0.10 

# Weighting of LONG/SHORT Masks
VOL_MASK   = 0.75   # Top 25%
PRICE_MASK = 0.008  # 0.8% move
DELTA_MASK = 0.70   # Top 30%



# Liquidation Prices - Continuous Leverage Sampling
NUM_LEVERAGE_SAMPLES = 200  # Number of leverage samples per entry (more = smoother)

# Leverage profiles as normal distributions (mean, std)
LEVERAGE_PROFILES = {
    "conservative": {"mean": 12.0, "std": 8.0},   # Low leverage, wide spread
    "neutral":      {"mean": 25.0, "std": 15.0},  # Mid leverage, moderate spread  
    "aggressive":   {"mean": 60.0, "std": 25.0}   # High leverage, tighter spread
}

# Leverage bounds
MIN_LEVERAGE = 1.0
MAX_LEVERAGE = 125.0

MMR = 0.005        # 0.1% -- AVG Taker Fee on Liq.
FEE_BUFFER = 0.001 # 0.5%
TOTAL_BUFFER = MMR + FEE_BUFFER

NUM_BUCKETS = 40

# Price Resolution
DISTANCE_DECAY_FACTOR = 2