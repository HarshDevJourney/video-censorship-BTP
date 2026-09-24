# Run and Use Video Censorship

This guide explains how to run the complete application with Docker Compose and use the web interface.

## 1. Prerequisites

Install the following on your Windows machine:

- Docker Desktop with Linux containers enabled
- Git
- An Anthropic API key if you want audio profanity detection

The application runs these services in containers:

- Frontend: Next.js at `http://localhost:3000`
- Backend API: FastAPI at `http://localhost:8000`
- PostgreSQL: database on port `5432`
- Redis: task queue on port `6379`
- MinIO: object storage at `http://localhost:9000` and console at `http://localhost:9001`
- Worker: Celery video-processing worker

## 2. Get the project

Open PowerShell and run:

```powershell
git clone <repository-url>
Set-Location video-censorship
```

If you already have the project, change to its folder instead:

```powershell
Set-Location C:\path\to\video-censorship
```

## 3. Create the environment file

Create `.env` from the provided template:

```powershell
Copy-Item .env.example .env
```

Open `.env` in VS Code and set your Anthropic key:

```dotenv
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

The other values in `.env.example` are suitable for Docker Compose because they use the Compose service names (`postgres`, `redis`, and `minio`). Do not replace those host names with `localhost` while the backend and worker are running in containers.

Important settings:

- `CHUNK_SECONDS`: target length of each processing chunk. Smaller chunks can start playing sooner but create more work.
- `FRAME_SAMPLE_RATE`: how often frames are sampled by visual detectors. Lower values improve coverage but increase processing time.
- `MAX_CONCURRENT_CHUNKS`: maximum chunks processed at once per video. Keep this at or below the worker concurrency.
- `WHISPER_MODEL`: Whisper model size. `tiny` is fastest; larger models are more accurate and use more resources.
- `AUDIO_CENSOR_MODE`: currently supported value is `beep`.

Never commit `.env` or share the API key.

## 4. Build and start the application

From the project root, run:

```powershell
docker compose up --build
```

Keep this terminal open to watch startup and processing logs. The first build can take several minutes because it installs FFmpeg and Python dependencies.

To start the services in the background instead:

```powershell
docker compose up --build -d
```

View running containers:

```powershell
docker compose ps
```

Expected services are `postgres`, `redis`, `minio`, `backend`, `worker`, and `frontend`. The backend and frontend may take a little longer to become ready than the database and Redis services.

## 5. Check that the services are ready

Open these URLs in a browser:

- Web application: [http://localhost:3000](http://localhost:3000)
- API health check: [http://localhost:8000/health](http://localhost:8000/health)
- Interactive API documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
- MinIO console: [http://localhost:9001](http://localhost:9001)

The API health check should return:

```json
{"status":"ok"}
```

The default MinIO console login is:

```text
Username: minioadmin
Password: minioadmin
```

Use a short video, around 10 to 30 seconds, for the first test. The first video may take longer because Whisper downloads its model inside the worker container.

## 6. Submit a local video

1. Open [http://localhost:3000](http://localhost:3000).
2. Select **Get started**.
3. Choose a local video file in the file picker.
4. Wait for the upload to finish. The application redirects to the processing page.
5. Leave the processing page open while the job runs.

The processing page shows:

- Job status: `pending`, `running`, `completed`, or `failed`
- Percentage of chunks completed
- A video player using the live HLS manifest
- A chunk bar showing ready, processing, and queued parts

Playback can begin as soon as a processed chunk is available. The whole video does not need to finish first.

## 7. Submit a YouTube video

1. Open [http://localhost:3000/upload](http://localhost:3000/upload).
2. Paste a YouTube watch URL into the text field, for example:

   ```text
   https://www.youtube.com/watch?v=VIDEO_ID
   ```

3. Select **Submit YouTube URL**.
4. Wait for the processing page to open.

The worker downloads the source video before chunk processing starts. Download availability and YouTube restrictions can affect this workflow.

## 8. Watch and seek while processing

Use the normal video controls to play, pause, and seek. When you seek to a part that is not ready yet:

1. The frontend sends the new timestamp to the API.
2. The backend prioritizes unfinished chunks near that timestamp.
3. The worker processes the requested area as soon as capacity is available.
4. The HLS manifest is refreshed automatically while the job is running.

Already completed chunks are kept and are not processed again. A short buffering delay is expected when seeking into a queued chunk.

## 9. Read logs and diagnose failures

Show all service logs:

```powershell
docker compose logs -f
```

Show only the backend and worker logs:

```powershell
docker compose logs -f backend worker
```

Common checks:

- If the page cannot connect, confirm `backend` and `frontend` are healthy with `docker compose ps`.
- If a job fails during audio processing, confirm `ANTHROPIC_API_KEY` is set in `.env`, then restart with `docker compose up -d --build`.
- If processing is slow on the first run, wait for the Whisper model download to finish.
- If video playback is unavailable, inspect the worker logs for FFmpeg, storage, or model errors.

## 10. Stop the application

Stop the containers and keep database and video data:

```powershell
docker compose down
```

Start them again later with:

```powershell
docker compose up -d
```

To stop the application and delete the PostgreSQL and MinIO volumes, use this only when you are sure you want to remove stored data:

```powershell
docker compose down -v
```

## 11. Current limitation: visual detectors are stubs

The files `processor/detection/nudenet.py`, `processor/detection/violence.py`, and `processor/detection/blood.py` currently return no detections until real models are wired in. The full upload, chunking, scheduling, audio processing, HLS playback, and seeking workflow can still be tested, but visual regions will not be blurred by default.

See [SETUP.md](./SETUP.md) for model integration, worker concurrency, GPU, and production deployment notes.

## 12. Optional API testing

The FastAPI Swagger UI at [http://localhost:8000/docs](http://localhost:8000/docs) can be used to inspect and call the API directly. The main endpoints are:

- `POST /api/videos/upload`
- `POST /api/videos/youtube`
- `GET /api/jobs/{job_id}`
- `GET /api/videos/{video_id}/chunks`
- `POST /api/videos/{video_id}/seek`
- `GET /api/videos/{video_id}/manifest`
