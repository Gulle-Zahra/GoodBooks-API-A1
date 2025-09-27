# app/main.py
import os, time, json
from fastapi import FastAPI, HTTPException, Request, Depends, Query, Path, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "goodbooks")
API_KEY = os.getenv("API_KEY", "dev-key")
LOG_PATH = os.getenv("LOG_PATH", "logging.jsonl")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

app = FastAPI(title="GoodBooks API (MongoDB)")

# ---------- Models ----------
class BookOut(BaseModel):
    book_id: Optional[int]
    goodreads_book_id: Optional[int]
    title: Optional[str]
    authors: Optional[str]
    original_publication_year: Optional[int]
    average_rating: Optional[float]
    ratings_count: Optional[int]
    image_url: Optional[str]
    small_image_url: Optional[str]

class RatingIn(BaseModel):
    user_id: int
    book_id: int
    rating: int = Field(..., ge=1, le=5)

class PagedResponse(BaseModel):
    items: List[Dict[str, Any]]
    page: int
    page_size: int
    total: int

# ---------- Auth ----------
def require_key(request: Request):
    key = request.headers.get("x-api-key")
    if key != API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid api key")

# ---------- Logging middleware ----------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    t0 = time.time()
    client_ip = request.client.host if request.client else None
    try:
        resp = await call_next(request)
    except Exception as e:
        dt = int((time.time()-t0)*1000)
        entry = {"route": request.url.path, "method": request.method, "params": dict(request.query_params),
                 "status": 500, "latency_ms": dt, "client_ip": client_ip, "ts": time.time()}
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")
        raise
    dt = int((time.time()-t0)*1000)
    entry = {"route": request.url.path, "method": request.method, "params": dict(request.query_params),
             "status": resp.status_code, "latency_ms": dt, "client_ip": client_ip, "ts": time.time()}
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return resp

# ---------- Utilities ----------
def paginate_cursor(cursor, page: int, page_size: int):
    skip = (page - 1) * page_size
    items = list(cursor.skip(skip).limit(page_size))
    for d in items:
        d.pop("_id", None)
    return items

# ---------- Routes ----------
@app.get("/healthz")
def healthz():
    try:
        client.admin.command("ping")
        return {"status": "ok"}
    except Exception:
        raise HTTPException(status_code=500, detail="mongo unreachable")

@app.get("/books", response_model=PagedResponse)
def list_books(q: Optional[str] = None, tag: Optional[str] = None,
               min_avg: Optional[float] = None,
               year_from: Optional[int] = None, year_to: Optional[int] = None,
               sort: str = Query("avg", regex="^(avg|ratings_count|year|title)$"),
               order: str = Query("desc", regex="^(asc|desc)$"),
               page: int = Query(1, ge=1),
               page_size: int = Query(20, ge=1, le=100)):
    filt = {}
    if q:
        filt["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"authors": {"$regex": q, "$options": "i"}}
        ]
    if min_avg is not None:
        filt["average_rating"] = {"$gte": float(min_avg)}
    if year_from is not None or year_to is not None:
        y = {}
        if year_from is not None: y["$gte"] = year_from
        if year_to is not None: y["$lte"] = year_to
        filt["original_publication_year"] = y

    if tag:
        tag_doc = db.tags.find_one({"tag_name": tag})
        if not tag_doc:
            return {"items": [], "page": page, "page_size": page_size, "total": 0}
        tag_id = tag_doc["tag_id"]
        book_gids = [bt["goodreads_book_id"] for bt in db.book_tags.find({"tag_id": tag_id}, {"goodreads_book_id":1})]
        filt["goodreads_book_id"] = {"$in": book_gids}

    sort_map = {"avg": "average_rating", "ratings_count": "ratings_count", "year": "original_publication_year", "title": "title"}
    direction = -1 if order == "desc" else 1

    total = db.books.count_documents(filt)
    cursor = db.books.find(filt).sort([(sort_map[sort], direction)])
    items = paginate_cursor(cursor, page, page_size)
    return {"items": items, "page": page, "page_size": page_size, "total": total}

@app.get("/books/{book_id}", response_model=BookOut)
def get_book(book_id: int = Path(..., ge=1)):
    doc = db.books.find_one({"book_id": book_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="book not found")
    return doc

@app.get("/books/{book_id}/tags")
def book_tags(book_id: int):
    book = db.books.find_one({"book_id": book_id}, {"goodreads_book_id": 1})
    if not book: raise HTTPException(status_code=404, detail="book not found")
    gid = book.get("goodreads_book_id")
    if not gid: return {"items": []}
    pipeline = [
        {"$match": {"goodreads_book_id": gid}},
        {"$lookup": {"from": "tags", "localField": "tag_id", "foreignField": "tag_id", "as": "tag"}},
        {"$unwind": "$tag"},
        {"$project": {"tag_id":1, "count":1, "tag_name":"$tag.tag_name"}}
    ]
    items = list(db.book_tags.aggregate(pipeline))
    for d in items: d.pop("_id", None)
    return {"items": items}

@app.get("/authors/{author_name}/books", response_model=PagedResponse)
def author_books(author_name: str, page: int = 1, page_size: int = 20):
    filt = {"authors": {"$regex": author_name, "$options": "i"}}
    total = db.books.count_documents(filt)
    items = paginate_cursor(db.books.find(filt).sort([("original_publication_year", -1)]), page, page_size)
    return {"items": items, "page": page, "page_size": page_size, "total": total}

@app.get("/tags")
def list_tags(page: int = 1, page_size: int = 50):
    total = db.tags.count_documents({})
    items = paginate_cursor(db.tags.find({}).sort([("tag_name", 1)]), page, page_size)
    for t in items:
        t["book_count"] = db.book_tags.count_documents({"tag_id": t["tag_id"]})
    return {"items": items, "page": page, "page_size": page_size, "total": total}

@app.get("/users/{user_id}/to-read")
def user_to_read(user_id: int, page: int = 1, page_size: int = 50):
    total = db.to_read.count_documents({"user_id": user_id})
    items = paginate_cursor(db.to_read.find({"user_id": user_id}), page, page_size)
    return {"items": items, "page": page, "page_size": page_size, "total": total}

@app.get("/books/{book_id}/ratings/summary")
def ratings_summary(book_id: int):
    total = db.ratings.count_documents({"book_id": book_id})
    if total == 0:
        return {"avg": None, "count": 0, "histogram": {str(i): 0 for i in range(1,6)}}
    pipeline = [
        {"$match": {"book_id": book_id}},
        {"$group": {"_id": "$rating", "count": {"$sum": 1}}},
    ]
    counts = {str(i): 0 for i in range(1,6)}
    for row in db.ratings.aggregate(pipeline):
        counts[str(row["_id"])] = row["count"]
    avg = next(db.ratings.aggregate([{"$match": {"book_id": book_id}}, {"$group": {"_id": None, "avg": {"$avg": "$rating"}}}]), {}).get("avg")
    return {"avg": avg, "count": total, "histogram": counts}

@app.post("/ratings", dependencies=[Depends(require_key)])
def post_rating(r: RatingIn):
    try:
        res = db.ratings.update_one({"user_id": r.user_id, "book_id": r.book_id}, {"$set": {"rating": r.rating}}, upsert=True)
        if res.upserted_id:
            return {"detail": "created"}
        else:
            return {"detail": "updated"}
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="duplicate rating")
