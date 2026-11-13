"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import styles from "./landing.module.css";

interface SliderControlProps {
  disabled?: boolean;
  onCommit: (origin?: { x: number; y: number; size: number } | null) => void;
}

export function SliderControl({ disabled = false, onCommit }: SliderControlProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const thumbRef = useRef<HTMLDivElement>(null);
  const [maxTravel, setMaxTravel] = useState(256);
  const [offset, setOffset] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [committed, setCommitted] = useState(false);
  const startX = useRef(0);
  const startOffset = useRef(0);
  const activePointerId = useRef<number | null>(null);
  const onCommitRef = useRef(onCommit);

  useEffect(() => {
    onCommitRef.current = onCommit;
  }, [onCommit]);

  useEffect(() => {
    const el = trackRef.current;
    if (!el) return;
    const update = () => {
      setMaxTravel(Math.max(0, el.clientWidth - 48 - 12));
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const triggerCommit = useCallback(() => {
    if (committed) return;
    setCommitted(true);
    setIsDragging(false);
    setOffset(maxTravel);

    const track = trackRef.current?.getBoundingClientRect();
    const thumb = thumbRef.current?.getBoundingClientRect();
    const origin = track
      ? {
          x: track.right - (thumb?.width ? thumb.width / 2 + 6 : 30),
          y: track.top + track.height / 2,
          size: thumb?.width || 48,
        }
      : thumb
      ? {
          x: thumb.left + thumb.width / 2,
          y: thumb.top + thumb.height / 2,
          size: thumb.width,
        }
      : null;

    onCommitRef.current(origin);
  }, [committed, maxTravel]);

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (disabled || committed || e.button !== 0) return;
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
      activePointerId.current = e.pointerId;
    } catch {}
    startX.current = e.clientX;
    startOffset.current = offset;
    setIsDragging(true);
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isDragging || committed) return;
    const delta = e.clientX - startX.current;
    const nextOffset = Math.max(0, Math.min(maxTravel, startOffset.current + delta));
    setOffset(nextOffset);
    if (maxTravel > 0 && nextOffset / maxTravel >= 0.9) {
      triggerCommit();
    }
  };

  const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isDragging || committed) return;
    setIsDragging(false);
    if (activePointerId.current !== null) {
      try { e.currentTarget.releasePointerCapture(activePointerId.current); } catch {}
      activePointerId.current = null;
    }
    if (maxTravel > 0 && offset / maxTravel >= 0.9) {
      triggerCommit();
    } else {
      setOffset(0);
    }
  };

  const handlePointerCancel = (e: React.PointerEvent<HTMLDivElement>) => {
    if (committed) return;
    setIsDragging(false);
    if (activePointerId.current !== null) {
      try { e.currentTarget.releasePointerCapture(activePointerId.current); } catch {}
      activePointerId.current = null;
    }
    setOffset(0);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (disabled || committed) return;
    if (e.key === "End") {
      e.preventDefault();
      triggerCommit();
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      const next = Math.min(maxTravel, offset + Math.max(20, maxTravel * 0.25));
      setOffset(next);
      if (maxTravel > 0 && next / maxTravel >= 0.9) {
        triggerCommit();
      }
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      setOffset((prev) => Math.max(0, prev - Math.max(20, maxTravel * 0.25)));
    }
  };

  const progressPercent = maxTravel > 0 ? Math.round((offset / maxTravel) * 100) : 0;

  return (
    <div
      ref={trackRef}
      className={styles.sliderTrack}
      role="slider"
      aria-label="Slide to enter Aegis console"
      aria-disabled={disabled}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={progressPercent}
      tabIndex={disabled ? -1 : 0}
      onKeyDown={handleKeyDown}
      data-dragging={isDragging}
      data-committed={committed}
      data-disabled={disabled}
    >
      <div
        ref={thumbRef}
        className={styles.sliderThumb}
        style={{
          transform: `translateX(${offset}px)`,
          transition: isDragging ? "none" : "transform 250ms cubic-bezier(0.2, 0.9, 0.3, 1)",
          opacity: committed ? 0 : 1,
        }}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerCancel}
      >
        {/* Dithered Medusa shield artwork as the arrow button */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/landing/aegis-dithered.png"
          alt=""
          width="48"
          height="48"
          className={styles.sliderThumbArt}
          draggable={false}
        />
        {/* Arrow overlay indicating slide direction */}
        <div className={styles.sliderThumbArrow} aria-hidden="true">
          <svg
            viewBox="0 0 24 24"
            width="18"
            height="18"
            stroke="#DD700B"
            strokeWidth="3"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M5 12h14M12 5l7 7-7 7" />
          </svg>
        </div>
      </div>
    </div>
  );
}
