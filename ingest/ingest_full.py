
import os
import pandas as pd
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv
from tqdm import tqdm
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
DB_NAME = os.getenv("DB_NAME", "goodbooks")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "20000"))
BATCH_WRITE = int(os.getenv("BATCH_WRITE", "5000"))
RATINGS_PATH = os.getenv("RATINGS_PATH", "https://raw.githubusercontent.com/zygmuntz/goodbooks-10k/master/ratings.csv")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

def chunked_ratings_import(path):
    it = pd.read_csv(path, chunksize=CHUNK_SIZE, iterator=True)
    total = 0
    for chunk in tqdm(it, desc="chunks"):
        ops = []
        for _, r in chunk.iterrows():
            try:
                user_id = int(r["user_id"])
                book_id = int(r["book_id"])
                rating = int(r["rating"])
            except Exception:
                continue
            ops.append(UpdateOne({"user_id": user_id, "book_id": book_id}, {"$set": {"user_id": user_id, "book_id": book_id, "rating": rating}}, upsert=True))
            if len(ops) >= BATCH_WRITE:
                db.ratings.bulk_write(ops, ordered=False)
                ops = []
        if ops:
            db.ratings.bulk_write(ops, ordered=False)
        total += len(chunk)
        print(f"Processed total rows: {total}")
    print("Full ratings import finished")

if __name__ == "__main__":
    chunked_ratings_import(RATINGS_PATH)
