import Link from "next/link";

export default function Home() {
  return (
    <div>
      <h1>Video Censorship</h1>
      <p>Upload a video or paste a YouTube URL, then watch it while it processes.</p>
      <Link href="/upload">Get started →</Link>
    </div>
  );
}
