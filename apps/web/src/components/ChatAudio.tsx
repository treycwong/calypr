"use client";

import { Download, Pause, Play } from "lucide-react";
import { useRef, useState } from "react";

import { downloadUrl, filenameFrom } from "@/lib/download";

// The inline player for audio emitted by the Voice/TTS node (`[▶ caption](url)`). A custom compact
// control — not the raw browser <audio controls> bar — so it looks consistent on the Playground and
// the share page. A hidden <audio> is the engine; React state drives play/pause, the scrubber, and
// the time readout. Renders identically wherever <Markdown> renders an audio link.

function fmt(t: number): string {
  if (!Number.isFinite(t) || t < 0) return "0:00";
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function extFromSrc(src: string): string {
  const m = /^data:audio\/([a-z0-9]+)/i.exec(src);
  if (m) return m[1] === "mpeg" ? "mp3" : m[1];
  const dot = src.split("?")[0].split(".").pop();
  return dot && dot.length <= 4 ? dot : "mp3";
}

export function ChatAudio({ src, label }: { src: string; label: string }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState(0);
  const [duration, setDuration] = useState(0);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [saving, setSaving] = useState(false);

  function toggle() {
    const el = audioRef.current;
    if (!el) return;
    if (el.paused) void el.play();
    else el.pause();
  }

  function seek(e: React.ChangeEvent<HTMLInputElement>) {
    const el = audioRef.current;
    if (!el) return;
    const t = Number(e.target.value);
    el.currentTime = t;
    setCurrent(t);
  }

  async function download() {
    if (saving) return;
    setSaving(true);
    try {
      await downloadUrl(src, filenameFrom(label || "audio", extFromSrc(src)));
    } finally {
      setSaving(false);
    }
  }

  if (failed) {
    return (
      <span className="my-1 inline-flex items-center gap-1 text-xs text-muted-foreground">
        🔊 audio unavailable —{" "}
        <a href={src} target="_blank" rel="noopener noreferrer" className="underline">
          open
        </a>
      </span>
    );
  }

  return (
    <span className="my-0.5 inline-flex max-w-full items-center gap-1.5 rounded-full border border-border bg-muted/40 py-0.5 pl-0.5 pr-2 align-middle">
      <audio
        ref={audioRef}
        src={src}
        preload="metadata"
        onLoadedMetadata={(e) => {
          setDuration(e.currentTarget.duration);
          setReady(true);
        }}
        onTimeUpdate={(e) => setCurrent(e.currentTarget.currentTime)}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => {
          setPlaying(false);
          setCurrent(0);
        }}
        onError={() => setFailed(true)}
      />
      <button
        type="button"
        onClick={toggle}
        disabled={!ready}
        data-testid="audio-toggle"
        aria-label={playing ? "Pause" : "Play"}
        className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground transition hover:opacity-90 disabled:opacity-50"
      >
        {playing ? (
          <Pause className="h-3 w-3" />
        ) : (
          <Play className="ml-px h-3 w-3" />
        )}
      </button>
      <input
        type="range"
        min={0}
        max={duration || 0}
        step={0.1}
        value={current}
        onChange={seek}
        disabled={!ready}
        data-testid="audio-scrubber"
        aria-label="Seek"
        className="h-1 w-24 cursor-pointer accent-primary sm:w-28"
      />
      <span className="shrink-0 font-mono text-[10px] tabular-nums text-muted-foreground">
        {fmt(current)} / {fmt(duration)}
      </span>
      <button
        type="button"
        onClick={download}
        disabled={saving}
        data-testid="audio-download"
        aria-label="Download audio"
        className="shrink-0 text-muted-foreground transition hover:text-foreground disabled:opacity-50"
      >
        <Download className="h-3 w-3" />
      </button>
    </span>
  );
}
