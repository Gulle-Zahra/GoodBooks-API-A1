# Design note — GoodBooks API 

## Overview
This API provides read and write access to the GoodBooks-10k dataset using MongoDB as the backing store. The primary goal is a production-like REST API supporting ingestion, filtered listing, tag joins, per-book rating summaries, and authenticated rating creation.

## Schema (collections)
- **books**
  - `book_id` (int, unique)
  - `goodreads_book_id` (int)
  - `title` (string)
  - `authors` (string)
  - `original_publication_year` (int)
  - `average_rating` (float)
  - `ratings_count` (int)
  - `image_url`, `small_image_url` (strings)

- **ratings**
  - `user_id` (int)
  - `book_id` (int)
  - `rating` (int 1–5)
  - unique index on (`user_id`, `book_id`) ensures one rating per user-book pair

- **tags**
  - `tag_id` (int)
  - `tag_name` (string)

- **book_tags**
  - `goodreads_book_id` (int)
  - `tag_id` (int)
  - `count` (int)

- **to_read**
  - `user_id` (int)
  - `book_id` (int)
  - unique (`user_id`, `book_id`)

## Indexes
Minimum indexes implemented:
- `books`: unique `book_id`, text index on `title`+`authors`, index on `average_rating` (DESC)
- `ratings`: index on `book_id`; unique index on (`user_id`, `book_id`)
- `tags`: `tag_id` unique, `tag_name`
- `book_tags`: `tag_id`, `goodreads_book_id`
- `to_read`: unique (`user_id`, `book_id`)

## Design trade-offs
- **Normalization vs embedding**: tags are normalized into `tags` + `book_tags` rather than embedded arrays in `books`. This keeps `books` lightweight and avoids data duplication, but requires joins (via `$lookup`) for tag queries. For high-performance read workloads, one could denormalize popular tags into a `tags` array inside `books`.
- **ratings as separate collection**: Because the dataset has millions of ratings, `ratings` are separate for write performance and scaling. Embedding ratings in `books` would not scale.
- **On-demand aggregation**: rating histograms/averages are computed via aggregation. For heavy traffic, materialize these aggregates or cache them (Redis) and update in the background.

## Ingestion & idempotency
- ingestion scripts use `UpdateOne(..., upsert=True)` with `bulk_write` so they are idempotent and safe to re-run.
- For full-scale `ratings.csv` (~6M rows) the `ingest_full.py` uses `pandas.read_csv(..., chunksize=...)` + batched bulk writes.
- Create heavy indexes **after** bulk load to avoid indexing overhead during ingestion.

## Security & operational notes
- Simple API key `x-api-key` for write access to `/ratings`. For production use consider OAuth2 or token-based auth.
- Logging: JSONL per-request logs with `{ route, params, status, latency_ms, client_ip, ts }` for easy ingestion to log stores.
- Health check `/healthz` pings Mongo.


