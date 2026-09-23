"use client";

import { useEffect, useRef, useState } from "react";
import Hls from "hls.js";
import { ChunkOut, getChunks, manifestUrl, notifySeek } from "../lib/api";
import BufferBar from "./BufferBar";

/**
 * Plays the video via its live-growing HLS manifest, and:
 *  - re-fetches the manifest every few seconds while processing isn't done,
 *    so newly-completed chunks appear without a full reload
 *  - on a user seek, immediately calls /seek so the backend reprioritizes
 *    unfinished chunks near the new position, then keeps polling the
 *    manifest so playback can resume as soon as that chunk lands
 *  - polls /chunks to drive the buffering bar
 */
export default function VideoPlayer({ videoId, isDone }: { videoId: string; isDone: boolean }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsRef = useRef<Hls | null>(null);
  const [chunks, setChunks] = useState<ChunkOut[]>([]);
  const [currentTime, setCurrentTime] = useState(0);
  const [waitingOnChunk, setWaitingOnChunk] = useState(false);

  const duration = chunks.reduce((sum, c) => sum + c.duration, 0);

  // Set up hls.js once, then keep reloading the manifest until fully done.
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const load = () => {
      const savedTime = video.currentTime;
      if (Hls.isSupported()) {
        hlsRef.current?.destroy();
        const hls = new Hls({ maxBufferLength: 30 });
        hlsRef.current = hls;
        hls.loadSource(manifestUrl(videoId));
        hls.attachMedia(video);
        hls.once(Hls.Events.MANIFEST_PARSED, () => {
          if (savedTime > 0) video.currentTime = savedTime;
        });
      } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
        video.src = manifestUrl(videoId); // Safari native HLS
      }
    };

    load();
    const reloadInterval = isDone ? null : setInterval(load, 4000);
    return () => {
      if (reloadInterval) clearInterval(reloadInterval);
      hlsRef.current?.destroy();
    };
  }, [videoId, isDone]);

  // Poll chunk status for the buffering bar.
  useEffect(() => {
    const poll = () => getChunks(videoId).then(setChunks).catch(() => {});
    poll();
    const interval = setInterval(poll, isDone ? 10000 : 2000);
    return () => clearInterval(interval);
  }, [videoId, isDone]);

  // Track playhead + detect "seeked into a chunk that isn't ready yet".
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const onTimeUpdate = () => setCurrentTime(video.currentTime);

    const onSeeked = () => {
      notifySeek(videoId, video.currentTime).catch(() => {});
      const targetChunk = chunks.find(
        (c) => video.currentTime >= c.start_time && video.currentTime < c.start_time + c.duration
      );
      setWaitingOnChunk(!!targetChunk && targetChunk.status !== "completed");
    };

    video.addEventListener("timeupdate", onTimeUpdate);
    video.addEventListener("seeked", onSeeked);
    return () => {
      video.removeEventListener("timeupdate", onTimeUpdate);
      video.removeEventListener("seeked", onSeeked);
    };
  }, [videoId, chunks]);

  return (
    <div>
      <video ref={videoRef} controls style={{ width: "100%", background: "black" }} />
      {waitingOnChunk && (
        <p style={{ color: "#eab308", marginTop: 4 }}>
          Buffering — prioritizing this part of the video now…
        </p>
      )}
      <BufferBar chunks={chunks} duration={duration} currentTime={currentTime} />
    </div>
  );
}
