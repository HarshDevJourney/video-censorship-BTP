# Setup — what you need to change to actually run this

This project runs end-to-end out of the box (uploads, chunking, scheduling,
HLS playback, seek-reprioritization) but two pieces are placeholders on
purpose — you need to fill them in before censorship actually *does*
anything.

## 1. Required — things that won't run at all without this

- [ ] **Install Docker + Docker Compose.** Everything runs via
      `docker compose up --build`.
- [ ] **Copy the env file and set your Anthropic API key:**
      ```bash
      cp .env.example .env
      ```
      Then edit `.env` and set:
      ```
      ANTHROPIC_API_KEY=sk-ant-...
      ```
      Without this, `processor/audio/ai_detector.py` will raise on every
      video — audio profanity detection has no fallback wordlist by design
      (see the audio pipeline discussion in this project's history). If you
      want it to degrade gracefully instead of erroring, that's already
      handled at the `audio_pipeline.py` level — a missing/bad key just
      means no words get beeped, not a crashed job.

## 2. Required for real censorship — currently stubbed, return `[]`

These three files are wired into the pipeline correctly but have **no
model loaded** — `detect()` returns an empty list, so chunks process
successfully but nothing gets blurred:

- [ ] `processor/detection/nudenet.py` — uncomment and configure the real
      `NudeDetector` import, point `model_path` at your downloaded weights.
- [ ] `processor/detection/violence.py` — plug in a violence classifier/localizer.
- [ ] `processor/detection/blood.py` — plug in a blood/gore detector.

Until you do this, the pipeline is fully functional for testing (upload →
chunk → schedule → HLS playback → seek reprioritization) but visually
uncensored.

## 3. First run — model downloads

- [ ] **Whisper model**: `faster-whisper` downloads its model (size set by
      `WHISPER_MODEL` in `.env`, default `base`) on first use inside the
      worker container. First video processed will be slower while it
      downloads; subsequent runs are cached in the container's filesystem
      (add a volume mount if you want it to survive container rebuilds).
- [ ] If you plan to run on GPU, adjust `device="auto"` in
      `processor/audio/transcriber.py` and the worker Dockerfile's base
      image (currently CPU-only `python:3.11-slim`).

## 4. Configuration you'll likely want to tune

In `.env` (see `.env.example` for the full list):

| Variable | What it controls | Notes |
|---|---|---|
| `CHUNK_SECONDS` | target chunk length | actual lengths vary — ffmpeg cuts on keyframes |
| `FRAME_SAMPLE_RATE` | run detectors every Nth frame | lower = more accurate, slower |
| `MAX_CONCURRENT_CHUNKS` | chunks processed in parallel per video | **must be ≤ Celery worker `--concurrency`**, or chunks queue inside Celery/Redis instead of Postgres and you lose live reprioritization on seek |
| `WHISPER_MODEL` | Whisper model size | `tiny`/`base`/`small`/`medium`/`large-v3` — bigger = more accurate, slower |
| `PROFANITY_MODEL` | which Claude model flags profanity | defaults to `claude-sonnet-4-6` |
| `AUDIO_CENSOR_MODE` | currently only `beep` is implemented | kept as a setting for a future `mute` mode |

To actually run chunks in parallel, also bump the worker's concurrency —
edit `docker/Dockerfile.worker`'s CMD or override in `docker-compose.yml`:
```yaml
worker:
  command: celery -A app.workers.celery_app worker --loglevel=info --concurrency=4
```

## 5. Scaling beyond one machine

- [ ] Run multiple `worker` replicas (`docker compose up --scale worker=3`)
      — `schedule_chunks` and `process_chunk_task` are both idempotent /
      safe under concurrent execution (chunks are marked `PROCESSING`
      before dispatch, and completed chunks are never reprocessed), so
      this works with no code changes.
- [ ] For production, replace local Docker volumes for Postgres/MinIO with
      managed services, and put the worker on GPU instances once the
      detection models are wired in.

## 6. Sanity checklist before your first upload

- [ ] `docker compose up --build` completes with no errors
- [ ] http://localhost:8000/docs loads (FastAPI is up)
- [ ] http://localhost:9001 loads and you can log in with
      `minioadmin`/`minioadmin` (MinIO is up)
- [ ] http://localhost:3000 loads (frontend is up)
- [ ] Upload a short (10–30s) test clip first — confirms the whole chain
      (chunking → scheduling → Whisper → Claude → HLS → manifest → player)
      before you throw a 30-minute video at it.
