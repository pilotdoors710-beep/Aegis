"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { dither, particles } from "@/lib/landing/pixels";
import { artworkRenderer } from "@/lib/landing/renderer";
import { animate, TIMING, type Phase } from "@/lib/landing/phases";
import styles from "./landing.module.css";

interface Props {
  phase: Phase;
  reduced: boolean;
  exitElapsed: number;
  onLoaded: (ok: boolean) => void;
  onSettled: () => void;
  onInteraction?: () => void;
}

export function AegisArtwork({ phase, reduced, exitElapsed, onLoaded, onSettled, onInteraction }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const renderer = useRef<ReturnType<typeof artworkRenderer> | null>(null);
  const progressRef = useRef(0);
  const hoverRef = useRef(0);
  const hoverFrozenRef = useRef(0);
  const cancelAssembly = useRef<(() => void) | null>(null);
  const cancelHover = useRef<(() => void) | null>(null);
  const [painted, setPainted] = useState(false);
  const onLoadedRef = useRef(onLoaded);
  const onSettledRef = useRef(onSettled);

  useEffect(() => {
    onLoadedRef.current = onLoaded;
    onSettledRef.current = onSettled;
  });

  // Initialize WebGL2 particles
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let disposed = false;
    let failed = false;

    const fail = () => {
      failed = true;
      clearTimeout(loadTimer);
      cancelAssembly.current?.();
      renderer.current?.dispose();
      renderer.current = null;
      if (!disposed) {
        setPainted(false);
        onLoadedRef.current(false);
      }
    };

    const handleContextLost = (e: Event) => {
      e.preventDefault();
      fail();
    };

    canvas.addEventListener("webglcontextlost", handleContextLost);
    const observer = new ResizeObserver(() => {
      if (renderer.current && !reduced) {
        renderer.current.draw(progressRef.current, hoverRef.current, 1);
      }
    });
    observer.observe(canvas);

    const loadTimer = setTimeout(fail, 4500);
    const image = new Image();
    image.src = "/landing/aegis-master.png";

    image.decode().then(() => {
      if (disposed || failed) return;
      clearTimeout(loadTimer);
      if (reduced) {
        onLoadedRef.current(true);
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
        renderer.current.draw(0, 0, 1);
        setPainted(true);
        onLoadedRef.current(true);
      } catch {
        fail();
      }
    }).catch(fail);

    return () => {
      disposed = true;
      clearTimeout(loadTimer);
      cancelAssembly.current?.();
      observer.disconnect();
      canvas.removeEventListener("webglcontextlost", handleContextLost);
      renderer.current?.dispose();
      renderer.current = null;
    };
  }, [reduced]);

  // Handle assembly animation
  useEffect(() => {
    cancelAssembly.current?.();
    if (reduced) {
      progressRef.current = 1;
      renderer.current?.draw(1, 0, 1);
      return;
    }
    if (phase === "assembling" && renderer.current) {
      progressRef.current = 0;
      cancelAssembly.current = animate(TIMING.assembly, (p) => {
        progressRef.current = p;
        renderer.current?.draw(p, 0, 1);
      }, () => {
        progressRef.current = 1;
        onSettledRef.current();
      });
    } else if (phase === "ready") {
      progressRef.current = 1;
      renderer.current?.draw(1, hoverRef.current, 1);
    }
    return () => cancelAssembly.current?.();
  }, [phase, reduced]);

  // Handle hover spreading: smoothly expand particle spacing outward by 6% over 300ms
  const startHoverTransition = useCallback((targetHover: number) => {
    if (reduced || phase !== "ready") return;
    cancelHover.current?.();
    const startHover = hoverRef.current;
    if (Math.abs(startHover - targetHover) < 0.001) return;
    cancelHover.current = animate(300, (p) => {
      hoverRef.current = startHover + (targetHover - startHover) * p;
      if (renderer.current && phase === "ready") {
        renderer.current.draw(1, hoverRef.current, 1);
      }
    }, () => {
      hoverRef.current = targetHover;
      if (renderer.current && phase === "ready") {
        renderer.current.draw(1, targetHover, 1);
      }
    });
  }, [phase, reduced]);

  const onPointerEnterLogo = useCallback(() => {
    onInteraction?.();
    if (phase === "ready" && matchMedia("(hover: hover) and (pointer: fine)").matches) {
      startHoverTransition(1);
    }
  }, [onInteraction, phase, startHoverTransition]);

  const onPointerLeaveLogo = useCallback(() => {
    if (phase === "ready" && matchMedia("(hover: hover) and (pointer: fine)").matches) {
      startHoverTransition(0);
    }
  }, [phase, startHoverTransition]);

  // Freeze hover value as soon as exit begins so explosion eases without a jump
  useEffect(() => {
    if (phase === "exiting" || phase === "disassembling") {
      cancelHover.current?.();
      hoverFrozenRef.current = hoverRef.current;
    }
  }, [phase]);

  // Handle exit explosion timeline
  useEffect(() => {
    if ((phase !== "exiting" && phase !== "disassembling") || reduced || !renderer.current) return;
    if (exitElapsed < 0) return;

    // 0ms..650ms: outward explosion
    const explosionDuration = TIMING.explosion;
    const pExp = Math.min(1, Math.max(0, exitElapsed / explosionDuration));
    const currentProgress = 1 - pExp;
    // Ease hover spread smoothly into the explosion vector
    const currentHover = hoverFrozenRef.current * (1 - pExp);

    // 400ms..650ms: crossfade particles out (alpha 1 -> 0 over 250ms)
    let layerAlpha = 1;
    if (exitElapsed >= TIMING.crossfadeStart) {
      const fadeProgress = (exitElapsed - TIMING.crossfadeStart) / (explosionDuration - TIMING.crossfadeStart);
      layerAlpha = Math.max(0, 1 - fadeProgress);
    }
    if (exitElapsed >= explosionDuration) {
      layerAlpha = 0;
    }

    renderer.current.draw(currentProgress, currentHover, layerAlpha);
  }, [exitElapsed, phase, reduced]);

  const showCanvas = painted && !reduced;

  return (
    <div className={styles.artworkContainer} data-artwork={showCanvas ? "pixels" : "poster"}>
      {/* Poster fallback for reduced motion or WebGL failure */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/landing/aegis-dithered.png"
        width="960"
        height="960"
        alt="Dithered Aegis shield with a Medusa relief."
        className={styles.poster}
        style={{ visibility: showCanvas ? "hidden" : "visible" }}
      />
      {/* Viewport-sized canvas */}
      <canvas
        ref={canvasRef}
        className={styles.artworkCanvas}
        aria-hidden="true"
        style={{ visibility: showCanvas ? "visible" : "hidden" }}
      />
      {/* Centered circular hover hit area */}
      {phase === "ready" && !reduced && (
        <div
          className={styles.logoHitArea}
          onPointerEnter={onPointerEnterLogo}
          onPointerLeave={onPointerLeaveLogo}
          aria-hidden="true"
        />
      )}
    </div>
  );
}
