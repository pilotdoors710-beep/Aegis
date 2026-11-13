"use client";

import { useEffect, useRef, useState } from "react";
import { dither, particles } from "@/lib/landing/pixels";
import { artworkRenderer } from "@/lib/landing/renderer";
import { animate, TIMING, type Phase } from "@/lib/landing/phases";
import styles from "./landing.module.css";

type Props = { phase: Phase; reduced: boolean; onLoaded: (ok: boolean) => void; onSettled: () => void; onExit: () => void };

export function AegisArtwork(props: Props) {
  const canvas = useRef<HTMLCanvasElement>(null), latest = useRef(props);
  const renderer = useRef<ReturnType<typeof artworkRenderer> | null>(null);
  const progress = useRef(0), cancel = useRef<(() => void) | null>(null);
  const [painted, setPainted] = useState(false);
  useEffect(() => { latest.current = props; });
  useEffect(() => {
    const element = canvas.current!;
    let disposed = false, failed = false;
    const fail = () => {
      failed = true; clearTimeout(loadTimer); cancel.current?.(); renderer.current?.dispose(); renderer.current = null;
      if (!disposed) { setPainted(false); latest.current.onLoaded(false); }
    };
    const lost = (event: Event) => { event.preventDefault(); fail(); };
    element.addEventListener("webglcontextlost", lost);
    const observer = new ResizeObserver(() => { renderer.current?.draw(progress.current); });
    observer.observe(element);
    const loadTimer = setTimeout(fail, 4500);
    const image = new Image(); image.src = "/landing/aegis-master.png";
    image.decode().then(() => {
      if (disposed || failed) return;
      clearTimeout(loadTimer);
      if (latest.current.reduced) { latest.current.onLoaded(true); return; }
      try {
        // Reduce the logical grid before allocation; even a fully opaque image fits the cap.
        const mobile = matchMedia("(max-width: 767px)").matches;
        let side = mobile ? 200 : 300;
        const limit = mobile ? 16000 : 36000;
        const sample = document.createElement("canvas");
        const ctx = sample.getContext("2d", { willReadFrequently: true });
        if (!ctx) throw new Error("Sampling unavailable");
        let colors: Uint8ClampedArray;
        for (;;) {
          sample.width = sample.height = side;
          ctx.drawImage(image, 0, 0, side, side);
          colors = dither(ctx.getImageData(0, 0, side, side).data, side, side);
          let occupied = 0;
          for (let i = 3; i < colors.length; i += 4) if (colors[i]) occupied++;
          if (occupied <= limit) break;
          side = Math.max(1, Math.floor(side * Math.sqrt(limit / occupied) * .97));
        }
        const pixels = particles(colors, side, side);
        renderer.current = artworkRenderer(element, pixels);
        renderer.current.draw(0); setPainted(true); latest.current.onLoaded(true);
      } catch { fail(); }
    }).catch(fail);
    return () => {
      disposed = true; clearTimeout(loadTimer); cancel.current?.(); observer.disconnect();
      element.removeEventListener("webglcontextlost", lost); renderer.current?.dispose(); renderer.current = null;
    };
  }, []);

  useEffect(() => {
    cancel.current?.();
    if (props.reduced) {
      progress.current = 1;
      renderer.current?.draw(1);
      return;
    }
    if (props.phase === "ready") renderer.current?.draw(1);
    if (props.phase === "assembling" && renderer.current) {
      const start = progress.current;
      cancel.current = animate(TIMING.assembly, (p) => {
        progress.current = start + (1 - start) * p; renderer.current?.draw(progress.current);
      }, () => latest.current.onSettled());
    } else if (props.phase === "disassembling") {
      if (!renderer.current) { latest.current.onExit(); return; }
      const start = progress.current;
      cancel.current = animate(TIMING.disassembly, (p) => {
        progress.current = start * (1 - p); renderer.current?.draw(progress.current);
      }, () => latest.current.onExit());
    }
    return () => cancel.current?.();
  }, [props.phase, props.reduced]);

  const showCanvas = painted && !props.reduced;
  return <div className={styles.artwork} data-artwork={showCanvas ? "pixels" : "poster"}>
    {/* Deliberately retain the exact square pixel grid; no image optimization/smoothing. */}
    {/* eslint-disable-next-line @next/next/no-img-element */}
    <img src="/landing/aegis-dithered.png" width="960" height="960" alt="Dithered Aegis shield with a Medusa relief." style={{ visibility: showCanvas ? "hidden" : "visible" }} />
    <canvas ref={canvas} aria-hidden="true" style={{ visibility: showCanvas ? "visible" : "hidden" }} />
  </div>;
}
