"use client";

// Last-resort boundary: replaces the root layout if it (or a top-level render) crashes, so the
// app never white-screens. Self-contained inline styles — globals.css may not be applied here.
export default function GlobalError({ reset }: { error: Error; reset: () => void }) {
  const btn: React.CSSProperties = {
    borderRadius: 8,
    padding: "0.5rem 1rem",
    fontSize: "0.875rem",
    cursor: "pointer",
    border: "1px solid rgba(255,255,255,0.15)",
    background: "transparent",
    color: "inherit",
    textDecoration: "none",
  };
  return (
    <html lang="en">
      <body
        style={{
          display: "flex",
          minHeight: "100vh",
          margin: 0,
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "1rem",
          fontFamily: "system-ui, -apple-system, sans-serif",
          background: "#04060a",
          color: "#fff",
          textAlign: "center",
          padding: "2rem",
        }}
      >
        <h1 style={{ fontSize: "1.125rem", fontWeight: 500, margin: 0 }}>Something went wrong</h1>
        <p style={{ fontSize: "0.875rem", color: "#94a3b8", maxWidth: "24rem", margin: 0 }}>
          The app hit an unexpected error. Please reload the page.
        </p>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button type="button" onClick={reset} style={btn}>
            Try again
          </button>
          {/* Hard navigation (full reload) is intentional: the root crashed, so a client-side
              <Link> can't be trusted to recover. */}
          {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
          <a href="/" style={btn}>
            Go home
          </a>
        </div>
      </body>
    </html>
  );
}
