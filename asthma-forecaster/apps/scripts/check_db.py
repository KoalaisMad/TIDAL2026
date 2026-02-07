#!/usr/bin/env python3
"""Check MongoDB connection and count documents in tidal.daily."""
import sys
import os

# project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
except ImportError:
    pass

def main():
    try:
        from db.daily_dataset import get_collection
        coll = get_collection()
        db_name = coll.database.name
        coll_name = coll.name
        n = coll.count_documents({})
        # Mask URI for display
        uri = os.environ.get("MONGODB_URI", "")
        if "@" in uri:
            uri = "..." + uri[uri.rindex("@"):]
        else:
            uri = uri or "mongodb://localhost:27017"
        print(f"Connected: {uri}")
        print(f"Database: {db_name!r}  Collection: {coll_name!r}  ->  {n} document(s)")
        if n > 0:
            for doc in coll.find({}).sort("date", 1).limit(5):
                print(f"  - {doc.get('date')} | location_id={doc.get('location_id')} | AQI={doc.get('AQI')} | season={doc.get('season')}")
        else:
            print("No documents. Run: python3 pull_by_location_date.py --lat 37.77 --lon -122.42 --date 2025-02-07 --no-raw --mongodb")
    except Exception as e:
        print(f"Error: {e}")
        print("Check MONGODB_URI in .env (for Atlas, use your connection string; password special chars must be URL-encoded).")
        sys.exit(1)

if __name__ == "__main__":
    main()
