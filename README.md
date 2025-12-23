# 🌊 Liquidation Map Indicator API

A high-performance data aggregation engine that predicts and visualizes "Liquidation Cascades" in the crypto futures market. By analyzing real-time data from multiple exchanges, this tool identifies price zones where leveraged positions are most likely to be wiped out, creating a "gravity" effect on price.

🚀 **Live API:** [https://liquidation-api-1001101479084.asia-east1.run.app/api/liquidation-map](https://liquidation-api-1001101479084.asia-east1.run.app/api/liquidation-map)

---

## 🎯 Project Goal
The goal of this project is to democratize institutional-grade market sentiment analysis. While retail traders often focus on simple indicators, whales and market makers focus on **liquidity**. This tool maps out hypothetical liquidation clusters to show:
1.  **Magnetism**: Price levels that "pull" the market toward them.
2.  **Directional Bias**: Whether the path of least resistance is Up or Down.
3.  **Intensity**: The notional USD value ($B) at risk in specific price bins.

---

## 🧠 Methodology
The engine follows a proprietary 6-step pipeline to infer hidden market data:

### 1. Infer Entry Prices
Since exact entries are private, we use three proxies implemented in `src/entries.py`:
-   **Hot Zones**: Areas where Price and Open Interest (OI) rise/fall in correlation with high volume.
-   **OI Spikes**: Large adjustments in position size regardless of immediate price movement.
-   **VWAP**: Used as a baseline "average cost" for participants during ranging markets.

### 2. Approximate Leverage Distribution
We model market behavior using profiles in `src/config.py`:
-   **Conservative**: Heavy weighting on 5x-10x leverage.
-   **Neutral**: Normal distribution centered around 20x-50x.
-   **Aggressive**: Skewed toward 75x-125x "degens."
-   **Dynamic (Real-Time)**: Automatically shifts distributions based on **Funding Rates**. High positive funding implies over-leveraged longs.

### 3. Calculate Liquidation Prices
Using the standard maintenance margin formulas:
-   **Longs**: `Entry * (1 - 1/Lev) + Buffer`
-   **Shorts**: `Entry * (1 + 1/Lev) - Buffer`

### 4. Weight by Open Interest
We pull total OI from **Binance, Bybit, OKX, and Hyperliquid**. Each hypothetical liquidation point is scaled by the actual USD value currently sitting in the market.

### 5. Binning & Status Tracking
We aggregate thousands of points into discrete price buckets (e.g., $500 bins). Crucially, we track the **Status** of each bin:
-   `ACTIVE`: Price has never touched this zone.
-   `CLEARED`: Price has recently swept this zone, "wiping" the liquidations.
-   `PARTIAL`: Price has scratched the zone but some liquidity remains.

### 6. Magnetism (Gravity) Formula
Implemented in `src/resolution.py`, we calculate a "Pull" score for the market:
\[ \text{Force} = \sum \left( \frac{\text{USD}}{\text{Distance}^2} \right) \times \text{Direction} \]
This provides a single numeric value indicating if the market is being pulled toward a cluster above or below.

---

## 🛠 Tech Stack
-   **Backend**: Python / FastAPI
-   **Data Processing**: Pandas / NumPy
-   **Exchange Connectivity**: CCXT (Unified API for 100+ exchanges)
-   **Infrastructure**: Docker / Google Cloud Run (Taiwan region to bypass regional bans)
-   **Persistence**: Google Cloud Storage (GCS) for cross-instance caching.

---

## 🚀 API Endpoints

### `GET /api/status`
Returns the current state of the global cache (`INITIALIZING`, `READY`, or `ERROR`).

### `GET /api/liquidation-map`
Returns the full DTO (Data Transfer Object) including:
-   **Summary**: Current price, High/Low, Total OI, Funding Rate.
-   **Direction**: Bias (UP/DOWN/UNBIASED) and Magnet strengths.
-   **Bins**: Sorted list of price clusters with intensity and status.

---

## 💻 Local Development

1. **Install Dependencies**:
```bash
pip install -r requirements.txt
```

2. **Run Module**:
```bash
python3 -m src.main
```

3. **Run API Server**:
```bash
uvicorn src.api:app --reload
```

---

*“In markets, price does not move where it wants; it moves where it must to find liquidity.”*

