"use client";

import { Dithering } from "@paper-design/shaders-react";
import { useEffect, useState } from "react";

// The hero backdrop: a slow-breathing dithered sphere (Paper Shaders' WebGL Dithering effect),
// sitting behind the headline. The parent applies a radial mask so the field fades out where the
// text lives. Params follow the library's default preset — the look of the 21st.dev
// "hero-dithering-card" this replaces our ASCII field with — at a gentler speed.
export function HeroDither() {
  // Match HeroAscii's behavior: near-still under prefers-reduced-motion.
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  return (
    <Dithering
      className="absolute inset-0 h-full w-full"
      colorBack="#000000"
      colorFront="#00b2ff"
      shape="sphere"
      type="4x4"
      size={2}
      scale={0.6}
      speed={reduced ? 0 : 0.55}
    />
  );
}
