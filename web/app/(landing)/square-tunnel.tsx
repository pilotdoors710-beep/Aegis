"use client";

import { useEffect, useRef } from "react";
import { tunnelRenderer } from "@/lib/landing/tunnel-renderer";
import styles from "./landing.module.css";

interface Props {
  prepared: boolean;
  opacity: number;
  progress: number;
  onContextLost?: () => void;
}

export function SquareTunnel({ prepared, opacity, progress, onContextLost }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const renderer = useRef<ReturnType<typeof tunnelRenderer> | null>(null);
  const onContextLostRef = useRef(onContextLost);

  useEffect(() => {
    onContextLostRef.current = onContextLost;
  });

  useEffect(() => {
    if (!prepared) return;
    const element = canvas.current;
    if (!element) return;

    const lost = (event: Event) => {
      event.preventDefault();
      renderer.current?.dispose();
      renderer.current = null;
      onContextLostRef.current?.();
    };

    element.addEventListener("webglcontextlost", lost);
    try {
      renderer.current = tunnelRenderer(element, matchMedia("(max-width:767px)").matches);
      renderer.current.draw(0);
    } catch {
      onContextLostRef.current?.();
    }

    return () => {
      element.removeEventListener("webglcontextlost", lost);
      renderer.current?.dispose();
      renderer.current = null;
    };
  }, [prepared]);

  useEffect(() => {
    if (!renderer.current || opacity <= 0) return;
    try {
      renderer.current.draw(progress);
    } catch {
      onContextLostRef.current?.();
    }
  }, [opacity, progress]);

  return (
    <canvas
      ref={canvas}
      className={styles.tunnel}
      aria-hidden="true"
      style={{
        opacity,
        visibility: opacity > 0 ? "visible" : "hidden",
      }}
    />
  );
}
