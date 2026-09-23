const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type JobStatus = "pending" | "running" | "completed" | "failed";
export type ChunkStatus = "pending" | "processing" | "completed" | "failed";

export interface JobOut {
  id: string;
  video_id: string;
  status: JobStatus;
  progress: number;
  error?: string | null;
}

export interface ChunkOut {
  index: number;
  start_time: number;
  duration: number;
  status: ChunkStatus;
}

export async function uploadVideo(file: File): Promise<{ job_id: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_URL}/api/videos/upload`, { method: "POST", body: form });
  if (!res.ok) throw new Error("Upload failed");
  return res.json();
}

export async function submitYoutubeUrl(url: string): Promise<{ job_id: string }> {
  const res = await fetch(`${API_URL}/api/videos/youtube`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) throw new Error("Submission failed");
  return res.json();
}

export async function getJob(jobId: string): Promise<JobOut> {
  const res = await fetch(`${API_URL}/api/jobs/${jobId}`);
  if (!res.ok) throw new Error("Job not found");
  return res.json();
}

export async function getChunks(videoId: string): Promise<ChunkOut[]> {
  const res = await fetch(`${API_URL}/api/videos/${videoId}/chunks`);
  if (!res.ok) return [];
  return res.json();
}

export function manifestUrl(videoId: string): string {
  return `${API_URL}/api/videos/${videoId}/manifest`;
}

export async function notifySeek(videoId: string, timestamp: number): Promise<void> {
  await fetch(`${API_URL}/api/videos/${videoId}/seek`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ timestamp }),
  });
}
