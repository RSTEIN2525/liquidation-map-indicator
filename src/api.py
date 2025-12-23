import time
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from apscheduler.schedulers.background import BackgroundScheduler
import pandas as pd
from google.cloud import storage
import json

from .models import CacheStatus, LiquidationMapResponse
from .main import calculate_map_data

# Configuration
BUCKET_NAME = "liquidation-cache-crypto-dash-482023"
STORAGE_CLIENT = storage.Client()

# The Cache (In-Memory)
GLOBAL_CACHE = {
    "data": None,
    "status": CacheStatus.INITIALIZING
}

def save_to_gcs(data: LiquidationMapResponse):
    """Persists the cache to Google Cloud Storage"""
    try:
        bucket = STORAGE_CLIENT.bucket(BUCKET_NAME)
        blob = bucket.blob("latest_map.json")
        # Use model_dump_json() for Pydantic V2
        blob.upload_from_string(
            data.model_dump_json(), 
            content_type='application/json'
        )
        print("✅ Cache persisted to GCS")
    except Exception as e:
        print(f"❌ GCS Save failed: {e}")

def load_from_gcs() -> LiquidationMapResponse:
    """Attempts to load the cache from GCS on startup"""
    try:
        bucket = STORAGE_CLIENT.bucket(BUCKET_NAME)
        blob = bucket.blob("latest_map.json")
        if blob.exists():
            content = blob.download_as_text()
            response = LiquidationMapResponse.model_validate_json(content)
            print("✨ Cache recovered from GCS")
            return response
    except Exception as e:
        print(f"⚠️ GCS Recovery failed (normal if first run): {e}")
    return None

def update_cache():
    """Main loop: Fetch from exchanges and update global state"""
    try:
        # Call Main Sequence (The heavy lifting)
        result = calculate_map_data()

        # Validate Data Present
        if not result['bins'].empty:
            # Prepare for Pydantic serialization
            bins_df = result['bins'].copy()
            bins_df['bucket'] = bins_df['bucket'].astype(str)
            
            # Construct the DTO
            response = LiquidationMapResponse(
                summary=result['summary'],
                direction=result['direction'],
                bins=bins_df.to_dict(orient='records'),
                timestamp=time.time()
            )

            # Update local memory
            GLOBAL_CACHE["data"] = response
            GLOBAL_CACHE["status"] = CacheStatus.READY

            # Persist to GCS
            save_to_gcs(response)

    except Exception as e:
        print(f"❌ Update Failed: {e}")
        # Only set error if we don't already have some data
        if GLOBAL_CACHE["data"] is None:
            GLOBAL_CACHE["status"] = CacheStatus.ERROR

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. On Startup: Try to recover from GCS immediately
    cached_data = load_from_gcs()
    if cached_data:
        GLOBAL_CACHE["data"] = cached_data
        GLOBAL_CACHE["status"] = CacheStatus.READY

    # 2. Setup Background Scheduler for regular updates
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_cache, 'interval', hours=1)
    scheduler.start()

    # 3. Always run a fresh update in the background
    thread = threading.Thread(target=update_cache)
    thread.start()

    yield

    # On Shutdown
    scheduler.shutdown()

# Define APP
app = FastAPI(lifespan=lifespan)

# ========== The Endpoints ========== #
@app.get("/api/status")
def get_status():
    """Simple check to see if server is running"""
    return {"status": GLOBAL_CACHE["status"]}

@app.get("/api/liquidation-map", response_model=LiquidationMapResponse)
def get_liquidation_map():
    """Get the full dataset for the UI"""
    if GLOBAL_CACHE["status"] != CacheStatus.READY:
        raise HTTPException(
            status_code=503, 
            detail={"error": "Data is warming up, please wait...", "status": GLOBAL_CACHE["status"]}
        )

    return GLOBAL_CACHE["data"]
