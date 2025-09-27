
from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
import os
from dotenv import load_dotenv
load_dotenv()

client = MongoClient(os.getenv("MONGO_URI", "mongodb://mongo:27017"))
db = client[os.getenv("DB_NAME", "goodbooks")]

# books
db.books.create_index([("book_id", ASCENDING)], unique=True)
db.books.create_index([("title", TEXT), ("authors", TEXT)], name="books_text_index")
db.books.create_index([("average_rating", DESCENDING)])
# ratings
db.ratings.create_index([("book_id", ASCENDING)])
db.ratings.create_index([("user_id", ASCENDING), ("book_id", ASCENDING)], unique=True)
# tags
db.tags.create_index([("tag_id", ASCENDING)], unique=True)
db.tags.create_index([("tag_name", ASCENDING)])
# book_tags
db.book_tags.create_index([("tag_id", ASCENDING)])
db.book_tags.create_index([("goodreads_book_id", ASCENDING)])
# to_read
db.to_read.create_index([("user_id", ASCENDING), ("book_id", ASCENDING)], unique=True)

print("Indexes created")
