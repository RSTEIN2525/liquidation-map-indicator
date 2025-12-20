# Configuration for the liquidation map indicator

ACTIVE_EXCHANGES = ['binance', 'bybit', 'okx', 'hyperliquid']

SYMBOLS = [
    'BTC/USDT:USDT',   # Binance
    'BTCUSDT',         # Bybit
    'BTC-USDT-SWAP',   # OKX
    'BTC-PERP',        # Common Perp Format
    'BTC/USDC:USDC',   # Hyperliquid
]

TIMEFRAME = '1h'
LOOKBACK = 24 * 7

WEIGHT_HOTZONE   = 0.70
WEIGHT_VOLUME_OI = 0.20
WEIGHT_VWAP      = 0.10 