"use client";

import { useEffect, useRef, useState } from "react";
import { dither, particles } from "@/lib/landing/pixels";
import { artworkRenderer } from "@/lib/landing/renderer";
import { TIMING, type Phase } from "@/lib/landing/phases";
import styles from "./landing.module.css";

interface Props {
  phase: Phase;
  reduced: boolean;
  exitElapsed: number;
  origin?: { x: number; y: number; size: number } | null;
  onLoaded?: (ok: boolean) => void;
  onSettled?: () => void;
}

export function AegisArtwork({ phase, reduced, exitElapsed, origin, onLoaded, onSettled }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const renderer = useRef<ReturnType<typeof artworkRenderer> | null>(null);
  const [painted, setPainted] = useState(false);
  const onLoadedRef = useRef(onLoaded);
  const onSettledRef = useRef(onSettled);

  useEffect(() => {
    onLoadedRef.current = onLoaded;
    onSettledRef.current = onSettled;
  });

  // Initialize WebGL2 particles in background so they are ready for the commit explosion
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let disposed = false;
    let failed = false;

    const fail = () => {
      failed = true;
      clearTimeout(loadTimer);
      renderer.current?.dispose();
      renderer.current = null;
      if (!disposed) {
        setPainted(false);
        onLoadedRef.current?.(false);
      }
    };

    const handleContextLost = (e: Event) => {
      e.preventDefault();
      fail();
    };

    canvas.addEventListener("webglcontextlost", handleContextLost);
    const loadTimer = setTimeout(fail, 4500);
    const image = new Image();
    image.src = "/landing/aegis-master.png";

    image.decode().then(() => {
      if (disposed || failed) return;
      clearTimeout(loadTimer);
      if (reduced) {
        onLoadedRef.current?.(true);
        return;
      }
      try {
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
          side = Math.max(1, Math.floor(side * Math.sqrt(limit / occupied) * 0.97));
        }
        const pixelData = particles(colors, side, side);
        renderer.current = artworkRenderer(canvas, pixelData);
        setPainted(true);
        onLoadedRef.current?.(true);
        onSettledRef.current?.();
      } catch {
        fail();
      }
    }).catch(fail);

    return () => {
      disposed = true;
      clearTimeout(loadTimer);
      canvas.removeEventListener("webglcontextlost", handleContextLost);
      renderer.current?.dispose();
      renderer.current = null;
    };
  }, [reduced]);

  // Handle exit explosion timeline: only draws when exit begins
  useEffect(() => {
    if ((phase !== "exiting" && phase !== "disassembling") || reduced || !renderer.current) return;
    if (exitElapsed < 0) return;

    // 0ms..650ms: outward explosion from the button position
    const explosionDuration = TIMING.explosion;
    const pExp = Math.min(1, Math.max(0, exitElapsed / explosionDuration));
    const currentProgress = 1 - pExp;

    // 400ms..650ms: crossfade particles out (alpha 1 -> 0 over 250ms)
    let layerAlpha = 1;
    if (exitElapsed >= TIMING.crossfadeStart) {
      const fadeProgress = (exitElapsed - TIMING.crossfadeStart) / (explosionDuration - TIMING.crossfadeStart);
      layerAlpha = Math.max(0, 1 - fadeProgress);
    }
    if (exitElapsed >= explosionDuration) {
      layerAlpha = 0;
    }

    renderer.current.draw(currentProgress, 0, layerAlpha, origin);
  }, [exitElapsed, origin, phase, reduced]);

  // Only show the canvas during the exit explosion! Before that, it is hidden and nothing is drawn behind text!
  const isExploding = painted && (phase === "exiting" || phase === "disassembling") && exitElapsed >= 0 && !reduced;

  return (
    <div
      className={styles.artworkContainer}
      style={{
        visibility: isExploding ? "visible" : "hidden",
        opacity: isExploding ? 1 : 0,
        pointerEvents: "none",
      }}
      aria-hidden="true"
    >
      <canvas
        ref={canvasRef}
        className={styles.artworkCanvas}
        aria-hidden="true"
      />
    </div>
  );
}
