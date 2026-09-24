# Video Content Censorship

Automatic nudity, violence, and profanity censorship for video — upload a
file or paste a YouTube URL, and get back a streamable, progressively
censored version. Built to let you start watching (and even seek around)
while processing is still happening, rather than waiting for the whole
video to finish.

**Stack:** FastAPI · Celery · Redis · PostgreSQL · MinIO · FFmpeg · NudeNet · Whisper · Claude · HLS · Next.js

---

## Table of contents

- [How it works](#how-it-works)
- [Seek-aware, priority-driven processing](#seek-aware-priority-driven-processing)
- [Quick start](#quick-start)
- [Run and use guide](./RUN_AND_USE.md)
- [Configuration](#configuration)
- [API reference](#api-reference)
- [Project structure](#project-structure)
- [Known limitations](#known-limitations)

---

## How it works

A video is split into short chunks, and each chunk is processed
independently and in parallel:

- **Visual:** sampled frames run through nudity/violence/blood detectors,
  detections are smoothed across frames with an IOU tracker (so censorship
  doesn't flicker on and off), and the flagged regions are blurred.
- **Audio:** the full video's audio is transcribed once with Whisper, Claude
  flags which words are profane using full sentence context, and each
  chunk beeps out whatever flagged words fall in its own time window.
- Each censored chunk is converted to HLS segments and appended to a
  playlist that grows as processing completes, so the frontend can start
  playback before the whole video is done.

## Seek-aware, priority-driven processing

Chunks are **not** processed strictly start-to-finish. Instead:

- Every chunk is a row in the `chunks` table with a `status`
  (`pending`/`processing`/`completed`/`failed`) and a `priority`
  (lower = sooner). This table **is** the priority queue — Celery/Redis
  are only ever handed a capped number of in-flight chunk jobs
  (`MAX_CONCURRENT_CHUNKS`) at a time.
- `schedule_chunks` is a self-rescheduling task: it dispatches the
  lowest-priority `pending` chunks into free slots, and gets re-triggered
  every time a chunk finishes and every time the user seeks.
- `POST /api/videos/{id}/seek {timestamp}` sets
  `priority = abs(chunk.start - timestamp)` on every still-`pending` chunk,
  then re-triggers the scheduler. Chunks near the new playhead jump the
  line; chunks already `processing` finish undisturbed; chunks already
  `completed` are never touched again — **no reprocessing when the user
  seeks back.**
- `GET /api/videos/{id}/manifest` builds an HLS playlist live from
  whatever chunks are `completed` right now (`PLAYLIST-TYPE:EVENT` until
  the video is fully done, then a closed `VOD` playlist). The frontend
  re-polls this every few seconds while processing is ongoing, so newly
  finished chunks appear without a full reload — the player naturally
  buffers on parts that aren't ready yet instead of erroring.
- `GET /api/videos/{id}/chunks` returns per-chunk status, used to render
  a buffering bar in the UI (ready / processing now / queued).

## Quick start

```bash
git clone <this-repo>
cd video-censorship
cp .env.example .env
```

Set `ANTHROPIC_API_KEY` in `.env` (required for profanity detection — see
[Configuration](#configuration)).

```bash
docker compose up --build
```

That starts the frontend, API, worker, PostgreSQL, Redis, and MinIO
together. See [SETUP.md](./SETUP.md) for the full first-run checklist,
including wiring in real detection models (they ship as stubs — see
[Known limitations](#known-limitations)) and tuning worker concurrency.

For a complete step-by-step walkthrough covering setup, health checks,
uploads, YouTube URLs, progressive playback, logs, and shutdown, see
[RUN_AND_USE.md](./RUN_AND_USE.md).

## Configuration

All variables live in `.env` (see `.env.example` for defaults):

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Celery broker/backend |
| `MINIO_*` | Object storage credentials and bucket |
| `CHUNK_SECONDS` | Target chunk length (actual lengths vary — FFmpeg cuts on keyframes) |
| `FRAME_SAMPLE_RATE` | Run visual detectors every Nth frame |
| `MAX_CONCURRENT_CHUNKS` | Chunks processed in parallel per video — must be ≤ the Celery worker's `--concurrency` |
| `WHISPER_MODEL` | `tiny`/`base`/`small`/`medium`/`large-v3` — bigger is more accurate, slower |
| `ANTHROPIC_API_KEY` | Required — powers AI-based profanity detection |
| `PROFANITY_MODEL` | Which Claude model flags profanity |
| `AUDIO_CENSOR_MODE` | Currently only `beep` is implemented |

## API reference

| Endpoint | Description |
|---|---|
| `POST /api/videos/upload` | Multipart file upload → `job_id` |
| `POST /api/videos/youtube` | `{"url": "..."}` → `job_id` |
| `GET /api/jobs/{job_id}` | Status + progress, derived live from chunk completion |
| `GET /api/videos/{video_id}` | Video metadata |
| `GET /api/videos/{video_id}/chunks` | Per-chunk status (buffering bar data) |
| `POST /api/videos/{video_id}/seek` | `{"timestamp": <seconds>}` — reprioritize unfinished chunks |
| `GET /api/videos/{video_id}/manifest` | The live HLS playlist |
| `GET /api/videos/{video_id}/stream` | Convenience pointer to the manifest URL |

## Project structure

```text
video-censorship/
├── frontend/          Next.js — upload UI, HLS player, buffering bar
├── backend/            FastAPI + Celery — API and orchestration
│   └── app/
│       ├── api/         Route handlers
│       ├── models/       SQLAlchemy models (video, job, chunk, detection)
│       ├── services/     MinIO, YouTube (yt-dlp), transcript caching
│       └── workers/      Celery tasks: prepare_video / schedule_chunks / process_chunk_task
├── processor/          Pure processing logic (video, detection, tracking,
│                        censorship, audio, pipeline, ffmpeg utils)
├── docker/              Worker Dockerfile
└── docker-compose.yml
```

See [ARCHITECTURE.md](./ARCHITECTURE.md) for full diagrams and sequence
flows, and [SETUP.md](./SETUP.md) for the run/configuration checklist.

## Known limitations

- `processor/detection/nudenet.py`, `violence.py`, and `blood.py` ship as
  stubs — they return `[]` until real models are wired in, so the pipeline
  runs end-to-end but nothing gets visually censored out of the box.
- Tracking uses a simple IOU tracker; swap in ByteTrack for more robust
  behavior on fast motion or occlusion.
- A flagged word that straddles a chunk boundary gets clipped at the edge
  rather than merged across chunks — worth addressing if `CHUNK_SECONDS`
  is small enough for mid-word cuts to be common.
- `MAX_CONCURRENT_CHUNKS` must stay ≤ the Celery worker's `--concurrency`,
  or chunks queue inside Redis instead of Postgres and lose the benefit of
  live reprioritization on seek.