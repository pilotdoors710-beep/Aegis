"use client";

import { useEffect, useRef } from "react";
import { tunnelRenderer } from "@/lib/landing/tunnel-renderer";
import { animate, TIMING } from "@/lib/landing/phases";
import styles from "./landing.module.css";

export function SquareTunnel({ prepared, active, onComplete }: { prepared: boolean; active: boolean; onComplete: () => void }) {
  const canvas = useRef<HTMLCanvasElement>(null), latest = useRef(onComplete);
  const renderer = useRef<ReturnType<typeof tunnelRenderer> | null>(null);
  useEffect(() => { latest.current = onComplete; });
  useEffect(() => {
    if (!prepared) return;
    const element = canvas.current!;
    const lost = (event: Event) => { event.preventDefault(); renderer.current?.dispose(); renderer.current = null; latest.current(); };
    element.addEventListener("webglcontextlost", lost);
    try {
      renderer.current = tunnelRenderer(element, matchMedia("(max-width:767px)").matches);
      renderer.current.draw(0);
    } catch { latest.current(); }
    return () => { element.removeEventListener("webglcontextlost", lost); renderer.current?.dispose(); renderer.current = null; };
  }, [prepared]);
  useEffect(() => {
    if (!active) return;
    const stop = animate(TIMING.tunnel, (p) => {
      try { renderer.current?.draw(p); } catch { stop?.(); latest.current(); }
    }, () => latest.current());
    return () => stop?.();
  }, [active]);
  return <canvas ref={canvas} className={styles.tunnel} aria-hidden="true" style={{ visibility: active ? "visible" : "hidden" }} />;
}
