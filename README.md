# Video Content Censorship — V1

FastAPI + Celery + Redis + MinIO + PostgreSQL + FFmpeg + NudeNet + Whisper + Claude + HLS + Next.js.

## Run locally

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:3000
- API: http://localhost:8000/docs
- MinIO console: http://localhost:9001 (minioadmin / minioadmin)

## Seek-aware, priority-driven processing

Chunks are NOT processed strictly start-to-finish. Instead:

- Every chunk has a row in the `chunks` table with a `status`
  (pending/processing/completed/failed) and a `priority` (lower = sooner).
  This table IS the priority queue — Celery/Redis are only ever handed a
  capped number of "in-flight" chunk jobs (`MAX_CONCURRENT_CHUNKS`) at a time.
- `schedule_chunks` is a self-rescheduling task: it dispatches the lowest-
  priority `pending` chunks into free slots, and gets re-triggered every
  time a chunk finishes, and every time the user seeks.
- `POST /api/videos/{id}/seek {timestamp}` sets `priority = abs(chunk.start
  - timestamp)` on every still-`pending` chunk, then re-triggers the
  scheduler. Chunks near the new playhead jump the line; chunks already
  `processing` finish undisturbed; chunks already `completed` are never
  touched again — no reprocessing when the user seeks back.
- `GET /api/videos/{id}/manifest` builds an HLS playlist live from whatever
  chunks are `completed` right now (`PLAYLIST-TYPE:EVENT` until the video
  is fully done, then a closed `VOD` playlist). The frontend re-polls this
  every few seconds while processing is ongoing, so newly-finished chunks
  appear without a full reload — the player naturally buffers on parts
  that aren't ready yet instead of erroring.
- `GET /api/videos/{id}/chunks` returns per-chunk status, used to render
  the buffering bar in the UI (green = ready, yellow = processing now,
  gray = queued).

Audio transcription (Whisper) + AI profanity detection (Claude) run ONCE
per video, up front, across the full original audio for proper sentence
context — the result is cached in MinIO as JSON and each chunk task just
filters it to its own time window, rather than re-transcribing per chunk.

## Endpoints

- `POST /api/videos/upload` / `POST /api/videos/youtube` — returns `job_id`
- `GET /api/jobs/{job_id}` — status + progress, derived live from chunk completion
- `GET /api/videos/{video_id}` — video metadata
- `GET /api/videos/{video_id}/chunks` — per-chunk status (buffering bar data)
- `POST /api/videos/{video_id}/seek {timestamp}` — reprioritize unfinished chunks
- `GET /api/videos/{video_id}/manifest` — the live HLS playlist
- `GET /api/videos/{video_id}/stream` — convenience redirect info to the manifest URL

## Notes / what's stubbed

- `processor/detection/nudenet.py`, `violence.py`, `blood.py` are stubbed —
  wire in the real models (they return `[]` until then).
- Tracking uses a simple IOU tracker (`processor/tracking/tracker.py`); swap
  for ByteTrack for more robust behavior.
- `MAX_CONCURRENT_CHUNKS` should be <= the Celery worker's `--concurrency`,
  or chunks will queue in Celery instead of Postgres and lose the benefit
  of live reprioritization. Bump both together if you add GPU workers.
- A flagged word that straddles a chunk boundary gets clipped at the edge
  rather than merged across chunks — a corner case worth handling if
  `CHUNK_SECONDS` is small enough for mid-word cuts to be common.
