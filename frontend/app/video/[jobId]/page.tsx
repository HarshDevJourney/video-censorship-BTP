"use client";

import { useEffect, useState } from "react";
import { getJob, JobOut } from "../../../lib/api";
import VideoPlayer from "../../../components/VideoPlayer";

export default function VideoPage({ params }: { params: { jobId: string } }) {
  const [job, setJob] = useState<JobOut | null>(null);

  useEffect(() => {
    const poll = () => getJob(params.jobId).then(setJob).catch(() => {});
    poll();
    const interval = setInterval(poll, 3000);
    return () => clearInterval(interval);
  }, [params.jobId]);

  if (!job) return <p>Loading…</p>;

  const isDone = job.status === "completed";

  return (
    <div>
      <h1>Your video</h1>
      <p>
        Status: <strong>{job.status}</strong> ({job.progress}% of chunks done)
      </p>
      {job.error && <p style={{ color: "#ef4444" }}>{job.error}</p>}

      {/* The video_id — playback (and seeking) can start the moment the
          first chunk exists, well before the whole video is processed. */}
      <VideoPlayer videoId={job.video_id} isDone={isDone} />

      <p style={{ marginTop: 16, fontSize: 14, color: "#888" }}>
        You can scrub ahead any time — the part of the video you land on jumps
        to the front of the processing queue. Parts you've already watched
        stay cached and never reprocess.
      </p>
    </div>
  );
}
