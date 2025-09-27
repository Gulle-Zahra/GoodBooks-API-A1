
import os
import pandas as pd
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
DB_NAME = os.getenv("DB_NAME", "goodbooks")
USE_SAMPLES = os.getenv("USE_SAMPLES", "1") in ("1", "true", "True")

BASE = "https://raw.githubusercontent.com/zygmuntz/goodbooks-10k/master/samples" if USE_SAMPLES else "https://raw.githubusercontent.com/zygmuntz/goodbooks-10k/master"
FILES = {
    "books": f"{BASE}/books.csv",
    "ratings": f"{BASE}/ratings.csv",
    "tags": f"{BASE}/tags.csv",
    "book_tags": f"{BASE}/book_tags.csv",
    "to_read": f"{BASE}/to_read.csv"
}

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

def ingest_books():
    df = pd.read_csv(FILES["books"])
    ops = []
    for _, r in df.iterrows():
        doc = {
            "book_id": int(r["book_id"]),
            "goodreads_book_id": int(r["goodreads_book_id"]) if not pd.isna(r["goodreads_book_id"]) else None,
            "title": r.get("title"),
            "authors": r.get("authors"),
            "original_publication_year": int(r["original_publication_year"]) if not pd.isna(r["original_publication_year"]) else None,
            "average_rating": float(r["average_rating"]),
            "ratings_count": int(r["ratings_count"]) if not pd.isna(r["ratings_count"]) else None,
            "image_url": r.get("image_url"),
            "small_image_url": r.get("small_image_url")
        }
        ops.append(UpdateOne({"book_id": doc["book_id"]}, {"$set": doc}, upsert=True))
    if ops:
        db.books.bulk_write(ops, ordered=False)
    print("books ingested")

def ingest_generic(name, cols, cast_map=None):
    df = pd.read_csv(FILES[name])
    ops = []
    for _, r in df.iterrows():
        doc = {}
        for c in cols:
            val = r.get(c)
            if pd.isna(val):
                doc[c] = None
            else:
                doc[c] = cast_map[c](val) if (cast_map and c in cast_map) else val
        key = {cols[0]: doc[cols[0]]}
        ops.append(UpdateOne(key, {"$set": doc}, upsert=True))
        if len(ops) >= 5000:
            db[name].bulk_write(ops, ordered=False)
            ops = []
    if ops:
        db[name].bulk_write(ops, ordered=False)
    print(f"{name} ingested")

def main():
    ingest_books()
    ingest_generic("ratings", ["user_id","book_id","rating"], {"user_id":int,"book_id":int,"rating":int})
    ingest_generic("tags", ["tag_id","tag_name"], {"tag_id":int})
    ingest_generic("book_tags", ["goodreads_book_id","tag_id","count"], {"goodreads_book_id":int,"tag_id":int,"count":int})
    ingest_generic("to_read", ["user_id","book_id"], {"user_id":int,"book_id":int})
    print("All sample data ingested")

if __name__ == "__main__":
    main()
