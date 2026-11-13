"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { dither, particles } from "@/lib/landing/pixels";
import { artworkRenderer } from "@/lib/landing/renderer";
import { animate, TIMING, type Phase } from "@/lib/landing/phases";
import styles from "./landing.module.css";

interface Props {
  phase: Phase;
  reduced: boolean;
  exitElapsed: number;
  onLoaded?: (ok: boolean) => void;
  onSettled?: () => void;
}

export function AegisArtwork({ phase, reduced, exitElapsed, onLoaded, onSettled }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const renderer = useRef<ReturnType<typeof artworkRenderer> | null>(null);
  const [painted, setPainted] = useState(false);
  const progressRef = useRef(0);
  const hoverRef = useRef(0);
  const hoverAnimRef = useRef<number | null>(null);
  const cancelAssemblyRef = useRef<(() => void) | null>(null);
  const onLoadedRef = useRef(onLoaded);
  const onSettledRef = useRef(onSettled);

  useEffect(() => {
    onLoadedRef.current = onLoaded;
    onSettledRef.current = onSettled;
  });

  // Smooth hover transition helper
  const animateHover = useCallback((targetHover: number) => {
    if (phase === "exiting" || phase === "entering" || reduced || !renderer.current) return;
    if (hoverAnimRef.current !== null) {
      cancelAnimationFrame(hoverAnimRef.current);
      hoverAnimRef.current = null;
    }

    const startHover = hoverRef.current;
    const startTime = performance.now();
    const duration = 220;

    const tick = (now: number) => {
      const elapsed = now - startTime;
      const t = Math.min(1, elapsed / duration);
      // Quad ease-out
      const eased = 1 - (1 - t) * (1 - t);
      hoverRef.current = startHover + (targetHover - startHover) * eased;

      renderer.current?.draw(progressRef.current, hoverRef.current, 1);

      if (t < 1) {
        hoverAnimRef.current = requestAnimationFrame(tick);
      } else {
        hoverAnimRef.current = null;
      }
    };

    hoverAnimRef.current = requestAnimationFrame(tick);
  }, [phase, reduced]);

  const handlePointerEnter = useCallback(() => {
    animateHover(1);
  }, [animateHover]);

  const handlePointerLeave = useCallback(() => {
    animateHover(0);
  }, [animateHover]);

  // Initialize WebGL2 particles and start assembly animation
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let disposed = false;
    let failed = false;

    const fail = () => {
      failed = true;
      clearTimeout(loadTimer);
      cancelAssemblyRef.current?.();
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

    const observer = new ResizeObserver(() => {
      renderer.current?.draw(progressRef.current, hoverRef.current, 1);
    });
    observer.observe(canvas);

    const loadTimer = setTimeout(fail, 4500);
    const image = new Image();
    image.src = "/landing/aegis-master.png";

    image.decode().then(() => {
      if (disposed || failed) return;
      clearTimeout(loadTimer);

      if (reduced) {
        progressRef.current = 1;
        onLoadedRef.current?.(true);
        onSettledRef.current?.();
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

        if (phase === "ready") {
          progressRef.current = 1;
          renderer.current.draw(1, 0, 1);
          onSettledRef.current?.();
        } else {
          // Smooth entrance assembly
          cancelAssemblyRef.current = animate(
            TIMING.assembly,
            (p) => {
              progressRef.current = p;
              renderer.current?.draw(p, hoverRef.current, 1);
            },
            () => {
              progressRef.current = 1;
              renderer.current?.draw(1, hoverRef.current, 1);
              onSettledRef.current?.();
            }
          );
        }
      } catch {
        fail();
      }
    }).catch(fail);

    return () => {
      disposed = true;
      clearTimeout(loadTimer);
      cancelAssemblyRef.current?.();
      if (hoverAnimRef.current !== null) {
        cancelAnimationFrame(hoverAnimRef.current);
      }
      observer.disconnect();
      canvas.removeEventListener("webglcontextlost", handleContextLost);
      renderer.current?.dispose();
      renderer.current = null;
    };
  }, [phase, reduced]);

  // Handle phase changes (e.g. ready state if assembly is done)
  useEffect(() => {
    if (phase === "ready" && renderer.current && progressRef.current < 1) {
      cancelAssemblyRef.current?.();
      progressRef.current = 1;
      renderer.current.draw(1, hoverRef.current, 1);
    }
  }, [phase]);

  // Handle exit explosion timeline:
  // "and the actual big dithered art in the right will explode"
  // 0ms..650ms: progress goes 1 -> 0, causing particles to scatter outward!
  // 400ms..650ms: particles crossfade out (layerAlpha 1 -> 0)
  useEffect(() => {
    if ((phase !== "exiting" && phase !== "disassembling") || reduced || !renderer.current) return;
    if (exitElapsed < 0) return;

    cancelAssemblyRef.current?.();
    if (hoverAnimRef.current !== null) {
      cancelAnimationFrame(hoverAnimRef.current);
      hoverAnimRef.current = null;
    }

    const explosionDuration = TIMING.explosion;
    const pExp = Math.min(1, Math.max(0, exitElapsed / explosionDuration));
    const currentProgress = 1 - pExp;

    let layerAlpha = 1;
    if (exitElapsed >= TIMING.crossfadeStart) {
      const fadeProgress = (exitElapsed - TIMING.crossfadeStart) / (explosionDuration - TIMING.crossfadeStart);
      layerAlpha = Math.max(0, 1 - fadeProgress);
    }
    if (exitElapsed >= explosionDuration) {
      layerAlpha = 0;
    }

    renderer.current.draw(currentProgress, 0, layerAlpha);
  }, [exitElapsed, phase, reduced]);

  const showCanvas = painted && !reduced;

  return (
    <div
      className={styles.artwork}
      data-artwork={showCanvas ? "pixels" : "poster"}
      onPointerEnter={handlePointerEnter}
      onPointerLeave={handlePointerLeave}
    >
      {/* Deliberately retain the exact square pixel grid; no image optimization/smoothing */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/landing/aegis-dithered.png"
        width="960"
        height="960"
        alt="Dithered Aegis shield"
        className={styles.artworkImg}
        style={{ visibility: showCanvas ? "hidden" : "visible" }}
      />
      <canvas
        ref={canvasRef}
        className={styles.artworkCanvas}
        aria-hidden="true"
        style={{ visibility: showCanvas ? "visible" : "hidden" }}
      />
    </div>
  );
}
