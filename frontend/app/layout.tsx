export const metadata = {
  title: "Video Censorship",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ background: "#111", color: "#eee", fontFamily: "sans-serif", margin: 0 }}>
        <div style={{ maxWidth: 800, margin: "0 auto", padding: 24 }}>{children}</div>
      </body>
    </html>
  );
}
