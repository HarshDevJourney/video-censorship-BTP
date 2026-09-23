# Architecture — Seek-Aware Video Censorship Pipeline

## 1. High-level diagram

```text
                         ┌─────────────────────────┐
                         │       Next.js UI         │
                         │  Upload / YouTube URL     │
                         │  HLS Player (hls.js)      │
                         │  Buffering bar (chunks)   │
                         └────────────┬────────────┘
                                      │ HTTP (poll manifest, seek, chunks)
                                      ▼
                         ┌─────────────────────────┐
                         │        FastAPI            │
                         │  /upload /youtube          │
                         │  /jobs/{id}                │
                         │  /videos/{id}/chunks        │
                         │  /videos/{id}/seek           │
                         │  /videos/{id}/manifest        │
                         └────────────┬────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
              PostgreSQL           Redis             MinIO
         videos / jobs /      (Celery broker,   original / raw_chunks /
         chunks / detections   NOT the priority   output (HLS) /
         ◄── priority queue        queue)          flagged_words.json
              lives here
                    │
                    │ status + priority per chunk
                    ▼
         ┌───────────────────────────┐
         │      schedule_chunks       │  self-rescheduling Celery task
         │  (reads `chunks` table,    │  triggered by: upload, chunk
         │   dispatches top-priority  │  completion, and /seek calls
         │   PENDING chunks into      │
         │   free worker slots)       │
         └─────────────┬─────────────┘
                        ▼
              ┌───────────────────┐
              │  process_chunk_task │  ×N Celery workers
              └─────────┬──────────┘
                        │
          ┌─────────────┴─────────────┐
          ▼                           ▼
   Visual pipeline               Audio pipeline
   (per chunk, every time)       (once per video, cached)
          │                           │
          ▼                           ▼
   NudeNet / Violence /        Whisper transcription
   Blood detectors                    │
          │                           ▼
          ▼                    Claude flags profane
   IOU Tracker (stabilize          word spans
   boxes across frames)                │
          │                           ▼
          ▼                    Beep the flagged spans
   Blur/pixelate/mask          in THIS chunk's own audio
   the tracked region          (sliced from cached JSON,
          │                    not re-transcribed)
          └─────────────┬─────────────┘
                        ▼
                     FFmpeg
                (re-encode + HLS-ify
                 this one chunk)
                        │
                        ▼
              Upload chunk's .ts segments
              to MinIO, record them on the
              Chunk row (status=COMPLETED)
                        │
                        ▼
              schedule_chunks runs again
              (a slot just freed up)
```

## 2. Why Postgres is the priority queue, not Redis

Celery/Redis queues are FIFO lists — once a task is sitting in Redis, there's
no clean way to move it to the front. So chunks are never bulk-dispatched to
Celery. Instead:

- Every chunk is a row in `chunks`: `status` (pending/processing/completed/
  failed) and `priority` (float, lower = sooner).
- `schedule_chunks` only ever dispatches up to `MAX_CONCURRENT_CHUNKS` chunks
  at a time — whatever is `PENDING` with the lowest `priority`.
- It re-runs after every chunk finishes (a slot freed up) and after every
  `/seek` call (priorities changed).

This means re-prioritization is just an `UPDATE chunks SET priority = ...`
— nothing has to be pulled back out of Redis.

## 3. What a seek actually does

```text
User is watching a 10-min video, processed up through minute 2.
User drags the scrubber to minute 6.

Frontend: video "seeked" event fires
    ↓
POST /api/videos/{id}/seek {timestamp: 360}
    ↓
Backend: for every chunk still PENDING,
    priority = abs(chunk.start_time - 360)
    → the chunk covering minute 6 now has priority ≈ 0
    → chunks between minute 2–6 still have low-ish priority (they were
      already close in the original sequential order, or they simply
      lose the race to minute 6's chunk — either is fine)
    → chunks between minute 6–10 also get reprioritized, closest first
    ↓
schedule_chunks.delay() — next free worker slot picks up
the minute-6 chunk first
    ↓
Frontend: keeps re-polling /manifest every ~4s.
Player shows "buffering" because the manifest doesn't
extend to minute 6 yet — once that chunk lands, the
manifest grows to include it, and playback continues.
```

If the user then scrubs back to minute 3 (already completed before the
jump): `/seek` only touches `PENDING` rows, so the minute-3 chunk (already
`COMPLETED`) is untouched — it's already in the manifest, playback is
instant, no reprocessing.

## 4. Sequence for a fresh upload

```text
POST /upload
   ↓
FastAPI: save original to MinIO, create Video + Job rows, status=QUEUED
   ↓
prepare_video.delay(job_id, video_id)
   ↓
Celery worker:
   1. get local copy of source (download from MinIO, or yt-dlp for YouTube)
   2. probe duration
   3. extract full audio → Whisper transcribe → Claude flags profane words
      → cache flagged_words.json in MinIO (done ONCE per video)
   4. ffmpeg segment-split into chunks → probe each chunk's REAL duration
      (segment muxer cuts on keyframes, so lengths aren't uniform)
   5. upload each raw chunk to MinIO, create a Chunk row per chunk
      (priority = index, i.e. sequential by default)
   6. schedule_chunks.delay(video_id)
   ↓
schedule_chunks: dispatches the first MAX_CONCURRENT_CHUNKS chunks
   ↓
process_chunk_task (×N in parallel):
   - download this chunk's raw video from MinIO
   - filter cached flagged_words to this chunk's time window, shift to
     chunk-relative time
   - extract THIS chunk's own audio (guarantees frame/audio sync), beep
     flagged spans
   - visual: sample frames → detect → track → blur → re-encode with
     beeped audio muxed in
   - ffmpeg → HLS segments, upload to MinIO, record on Chunk row
   - mark chunk COMPLETED
   - schedule_chunks.delay(video_id) again
   ↓
Frontend polls /manifest — grows as chunks complete;
polls /chunks — drives the green/yellow/gray buffering bar
```

## 5. Project structure

```text
video-censorship/
├── frontend/                    Next.js — upload UI, HLS player, buffering bar
│   ├── app/
│   │   ├── page.tsx
│   │   ├── upload/page.tsx
│   │   └── video/[jobId]/page.tsx
│   ├── components/
│   │   ├── VideoPlayer.tsx      hls.js, manifest polling, seek → /seek
│   │   └── BufferBar.tsx        renders chunk status as a colored bar
│   └── lib/api.ts               typed fetch wrappers for the backend API
│
├── backend/                     FastAPI + Celery — API + orchestration
│   └── app/
│       ├── api/                 videos.py, jobs.py, streaming.py (manifest)
│       ├── models/               video.py, job.py, chunk.py, detection.py
│       ├── schemas/              pydantic I/O models
│       ├── services/             storage.py (MinIO), youtube.py (yt-dlp),
│       │                          transcript_cache.py (cached Whisper output)
│       └── workers/
│           ├── celery_app.py
│           └── tasks.py         prepare_video / schedule_chunks / process_chunk_task
│
├── processor/                   Pure processing logic (no FastAPI/DB imports
│   │                             except where tasks.py wires it in)
│   ├── video/                   chunker.py, frame_sampler.py
│   ├── detection/                nudenet.py, violence.py, blood.py (stubbed),
│   │                              detector.py (merges all three)
│   ├── tracking/                 tracker.py (IOU tracker)
│   ├── censorship/                blur.py, pixelate.py, mask.py
│   ├── audio/                     transcriber.py (Whisper), ai_detector.py
│   │                              (Claude), censor.py (beep)
│   ├── pipeline/                  chunk_pipeline.py (one chunk: detect→track→
│   │                              censor→encode), audio_pipeline.py (whole-
│   │                              video transcribe+detect, cached)
│   └── utils/ffmpeg.py           all ffmpeg/ffprobe subprocess wrappers
│
├── docker/Dockerfile.worker      Celery worker image (bundles backend + processor)
├── docker-compose.yml
└── .env.example
```
