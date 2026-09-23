"use client";

import { ChunkOut } from "../lib/api";

/**
 * Shows which parts of the video are ready, so seeking-ahead behavior is
 * visible: a green segment means "already processed, instant playback";
 * gray means "not started/queued"; yellow means "actively processing now"
 * (this is where the scheduler prioritizes whatever's closest to the
 * current playhead).
 */
export default function BufferBar({
  chunks,
  duration,
  currentTime,
}: {
  chunks: ChunkOut[];
  duration: number;
  currentTime: number;
}) {
  if (!duration || chunks.length === 0) return null;

  const colorFor = (status: ChunkOut["status"]) => {
    switch (status) {
      case "completed":
        return "#22c55e";
      case "processing":
        return "#eab308";
      case "failed":
        return "#ef4444";
      default:
        return "#3f3f46";
    }
  };

  const playheadPct = Math.min(100, (currentTime / duration) * 100);

  return (
    <div style={{ position: "relative", width: "100%", height: 10, marginTop: 8 }}>
      <div style={{ display: "flex", width: "100%", height: "100%", borderRadius: 4, overflow: "hidden" }}>
        {chunks.map((c) => (
          <div
            key={c.index}
            title={`chunk ${c.index}: ${c.status}`}
            style={{
              width: `${(c.duration / duration) * 100}%`,
              backgroundColor: colorFor(c.status),
              transition: "background-color 0.3s",
            }}
          />
        ))}
      </div>
      <div
        style={{
          position: "absolute",
          top: -2,
          left: `${playheadPct}%`,
          width: 2,
          height: 14,
          backgroundColor: "white",
        }}
      />
    </div>
  );
}
