"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { uploadVideo, submitYoutubeUrl } from "../../lib/api";

export default function UploadPage() {
  const router = useRouter();
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = async (file: File) => {
    setSubmitting(true);
    setError(null);
    try {
      const { job_id } = await uploadVideo(file);
      router.push(`/video/${job_id}`);
    } catch (e) {
      setError("Upload failed. Is the backend running?");
    } finally {
      setSubmitting(false);
    }
  };

  const handleYoutube = async () => {
    if (!youtubeUrl) return;
    setSubmitting(true);
    setError(null);
    try {
      const { job_id } = await submitYoutubeUrl(youtubeUrl);
      router.push(`/video/${job_id}`);
    } catch (e) {
      setError("Submission failed. Is the backend running?");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <h1>Upload a video</h1>

      <input
        type="file"
        accept="video/*"
        disabled={submitting}
        onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
      />

      <p style={{ margin: "24px 0 8px" }}>— or —</p>

      <input
        type="text"
        placeholder="https://youtube.com/watch?v=..."
        value={youtubeUrl}
        onChange={(e) => setYoutubeUrl(e.target.value)}
        style={{ width: "100%", padding: 8 }}
      />
      <button onClick={handleYoutube} disabled={submitting} style={{ marginTop: 8, padding: "8px 16px" }}>
        Submit YouTube URL
      </button>

      {submitting && <p>Submitting…</p>}
      {error && <p style={{ color: "#ef4444" }}>{error}</p>}
    </div>
  );
}
