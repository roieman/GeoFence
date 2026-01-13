import time
import os
from datetime import datetime, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
# Get MongoDB URI from environment variable
MONGO_URI = os.getenv("MONGODB_URI")
if not MONGO_URI:
    raise ValueError("MONGODB_URI environment variable not set. Please set it in your .env file or environment.")
DB_NAME = "geofence"
SOURCE_COLL = "containers"
TARGET_COLL = "containers_regular"

# IMPORTANT: Change this to the actual name of your time field in the source collection!
TIME_FIELD = "timestamp" 

# Batch size: How much time to copy at once. 
# 6 hours is usually a safe sweet spot for performance vs. memory.
CHUNK_HOURS = 6 

def run_migration():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    source = db[SOURCE_COLL]
    
    print(f"--- Starting Migration: {SOURCE_COLL} -> {TARGET_COLL} ---")

    # 1. Auto-detect the Start and End dates
    print("Detecting date range...")
    try:
        first_doc = source.find_one({}, sort=[(TIME_FIELD, 1)])
        last_doc = source.find_one({}, sort=[(TIME_FIELD, -1)])
        
        if not first_doc:
            print("Source collection appears empty.")
            return

        start_date = first_doc[TIME_FIELD]
        final_date = last_doc[TIME_FIELD]
        
        # Ensure dates are datetime objects (Time Series usually guarantees this)
        if not isinstance(start_date, datetime):
             # Handle rare cases where it might be a string, though unlikely in TS collections
             print(f"Error: Field '{TIME_FIELD}' is not a Date object.")
             return
             
    except Exception as e:
        print(f"Error detecting dates. Check your TIME_FIELD name. Details: {e}")
        return

    print(f"Range detected: {start_date} to {final_date}")
    print(f"Batch size: {CHUNK_HOURS} hours")
    print("------------------------------------------------")

    # 2. Loop through the time range
    current_start = start_date
    
    while current_start < final_date:
        # Calculate the end of this specific batch
        current_end = current_start + timedelta(hours=CHUNK_HOURS)
        
        # Don't go past the absolute final date
        if current_end > final_date:
            current_end = final_date + timedelta(seconds=1) # +1 sec to include the last doc

        print(f"Processing batch: {current_start} -> {current_end} ... ", end="", flush=True)
        
        start_time = time.time()
        
        try:
            # 3. The Aggregation Pipeline
            pipeline = [
                {
                    "$match": {
                        TIME_FIELD: {
                            "$gte": current_start,
                            "$lt": current_end
                        }
                    }
                },
                {
                    "$merge": {
                        "into": TARGET_COLL,
                        "whenMatched": "replace",   # Idempotent: safe to re-run
                        "whenNotMatched": "insert"
                    }
                }
            ]
            
            # Execute with allowDiskUse to prevent memory limits on large batches
            db.command('aggregate', SOURCE_COLL, pipeline=pipeline, cursor={}, allowDiskUse=True)
            
            elapsed = time.time() - start_time
            print(f"Done ({elapsed:.2f}s)")

        except Exception as e:
            print(f"\nFAILED on batch starting {current_start}.")
            print(f"Error: {e}")
            print("Stopping script. Fix error and update 'start_date' logic to resume.")
            break

        # Move to next batch
        current_start = current_end

    print("------------------------------------------------")
    print("Migration Loop Complete.")
    
    # 4. Verify Counts
    src_count = source.count_documents({})
    tgt_count = db[TARGET_COLL].count_documents({})
    print(f"Verification: Source Docs: {src_count} | Target Docs: {tgt_count}")

if __name__ == "__main__":
    run_migration()