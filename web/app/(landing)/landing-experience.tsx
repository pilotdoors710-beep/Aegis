"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { SEEN_KEY, signalConsoleEntry, TIMING, animate, type Phase } from "@/lib/landing/phases";
import { AegisArtwork } from "./aegis-artwork";
import { SquareTunnel } from "./square-tunnel";
import { SliderControl } from "./slider-control";
import styles from "./landing.module.css";

export function LandingExperience() {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("loading");
  const [reduced, setReduced] = useState(false);
  const [routeSlow, setRouteSlow] = useState(false);
  const [initialized, setInitialized] = useState(false);
  const [exitElapsed, setExitElapsed] = useState(-1);
  const [darkOverlayOpacity, setDarkOverlayOpacity] = useState(0);
  const [tunnelOpacity, setTunnelOpacity] = useState(0);
  const [tunnelProgress, setTunnelProgress] = useState(0);
  const [tunnelPrepared, setTunnelPrepared] = useState(false);

  const accepted = useRef(false);
  const navigated = useRef(false);
  const available = useRef(false);
  const root = useRef<HTMLElement>(null);
  const phaseRef = useRef<Phase>("loading");
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const userInteracted = useRef(false);
  const autoScrollRan = useRef(false);
  const stopAutoScroll = useRef<(() => void) | null>(null);

  const changePhase = useCallback((value: Phase) => {
    phaseRef.current = value;
    setPhase(value);
  }, []);

  const navigate = useCallback(() => {
    if (navigated.current) return;
    navigated.current = true;
    accepted.current = true;
    changePhase("entering");
    signalConsoleEntry();
    router.replace("/console");
    timers.current.push(setTimeout(() => setRouteSlow(true), 2000));
  }, [changePhase, router]);

  useEffect(() => {
    let mounted = true;
    try { sessionStorage.removeItem(SEEN_KEY); } catch {}
    const params = new URLSearchParams(location.search);
    if (params.get("intro") === "skip") {
      navigate();
    } else {
      queueMicrotask(() => { if (mounted) setInitialized(true); });
    }
    router.prefetch("/console");

    const query = matchMedia("(prefers-reduced-motion: reduce)");
    const updateMotion = () => {
      setReduced(query.matches);
      if (query.matches) {
        if (accepted.current) navigate();
        else changePhase("ready");
      }
    };
    updateMotion();
    query.addEventListener("change", updateMotion);

    // Track user manual scrolling / interaction to cancel automatic scroll reveal
    const onUserScrollOrTouch = () => {
      userInteracted.current = true;
      if (stopAutoScroll.current) {
        stopAutoScroll.current();
        stopAutoScroll.current = null;
      }
    };

    window.addEventListener("wheel", onUserScrollOrTouch, { passive: true });
    window.addEventListener("touchmove", onUserScrollOrTouch, { passive: true });
    window.addEventListener("pointerdown", onUserScrollOrTouch, { passive: true });
    window.addEventListener("keydown", onUserScrollOrTouch, { passive: true });

    const pendingTimers = timers.current;
    return () => {
      mounted = false;
      query.removeEventListener("change", updateMotion);
      window.removeEventListener("wheel", onUserScrollOrTouch);
      window.removeEventListener("touchmove", onUserScrollOrTouch);
      window.removeEventListener("pointerdown", onUserScrollOrTouch);
      window.removeEventListener("keydown", onUserScrollOrTouch);
      pendingTimers.forEach(clearTimeout);
      stopAutoScroll.current?.();
    };
  }, [changePhase, navigate, router]);

  const onLoaded = useCallback((ok: boolean) => {
    available.current = ok;
    if (phaseRef.current === "loading") {
      changePhase(ok ? "assembling" : "ready");
    } else if (!ok && accepted.current) {
      navigate();
    } else if (!ok && phaseRef.current === "assembling") {
      changePhase("ready");
    }
  }, [changePhase, navigate]);

  const settled = useCallback(() => {
    if (phaseRef.current === "assembling") {
      changePhase("ready");
      setTunnelPrepared(true);

      // Start 2,000ms hold from the assembly-complete callback
      if (!reduced) {
        timers.current.push(
          setTimeout(() => {
            if (userInteracted.current || autoScrollRan.current || accepted.current) return;
            autoScrollRan.current = true;
            const startY = window.scrollY;
            const targetY = startY + 160;
            stopAutoScroll.current = animate(TIMING.scroll, (p) => {
              if (userInteracted.current) {
                stopAutoScroll.current?.();
                stopAutoScroll.current = null;
                return;
              }
              const eased = 0.5 - 0.5 * Math.cos(p * Math.PI);
              window.scrollTo(0, startY + (targetY - startY) * eased);
            }, () => {
              stopAutoScroll.current = null;
            });
          }, TIMING.hold)
        );
      }
    }
  }, [changePhase, reduced]);

  // Handle slide completion: trigger explosion, frame transition, and navigate
  const handleSliderCommit = useCallback(() => {
    if (accepted.current) return;
    accepted.current = true;
    userInteracted.current = true;
    stopAutoScroll.current?.();
    stopAutoScroll.current = null;

    // 5-second recovery timeout so it cannot cut off the animation
    timers.current.push(setTimeout(() => navigate(), TIMING.recovery));

    if (reduced || !available.current) {
      changePhase("exiting");
      if (root.current) {
        const animation = root.current.animate([{ opacity: 1 }, { opacity: 0 }], {
          duration: 150,
          fill: "forwards",
        });
        animation.finished.then(() => navigate()).catch(() => navigate());
      } else {
        navigate();
      }
      return;
    }

    changePhase("exiting");
    setTunnelPrepared(true);

    // Shared exit timeline:
    // 0ms: explosion begins, slider fades
    // 400ms: square frames begin fading in behind remaining particles
    // 400–850ms: crossfade particles & gray background into dark tunnel
    // 650ms onward: particle layer finishes; frame flight continues
    // 1800ms: complete tunnel and navigate to /console
    const stopExit = animate(TIMING.exitTotal, (p) => {
      const t = p * TIMING.exitTotal;
      setExitElapsed(t);

      // 400ms..850ms: crossfade particles & gray background into dark tunnel
      if (t >= TIMING.crossfadeStart) {
        const fade = Math.min(1, (t - TIMING.crossfadeStart) / (TIMING.crossfadeEnd - TIMING.crossfadeStart));
        setDarkOverlayOpacity(fade);
        setTunnelOpacity(fade);
      } else {
        setDarkOverlayOpacity(0);
        setTunnelOpacity(0);
      }

      // 400ms..1800ms: frame flight
      if (t >= TIMING.crossfadeStart) {
        const flight = Math.min(1, (t - TIMING.crossfadeStart) / (TIMING.exitTotal - TIMING.crossfadeStart));
        setTunnelProgress(flight);
      } else {
        setTunnelProgress(0);
      }
    }, () => {
      navigate();
    });

    timers.current.push(stopExit as unknown as ReturnType<typeof setTimeout>);
  }, [changePhase, navigate, reduced]);

  return (
    <main
      ref={root}
      className={styles.landing}
      data-phase={phase}
      data-reduced={reduced}
      data-initialized={initialized}
    >
      {/* Dark background overlay for crossfading to dark tunnel */}
      <div
        className={styles.darkOverlay}
        style={{
          opacity: darkOverlayOpacity,
          visibility: darkOverlayOpacity > 0 ? "visible" : "hidden",
        }}
        aria-hidden="true"
      />

      {/* 3D square-frame tunnel layer */}
      <SquareTunnel
        prepared={tunnelPrepared && !reduced}
        opacity={tunnelOpacity}
        progress={tunnelProgress}
        onContextLost={navigate}
      />

      {/* Centered viewport-sized particle artwork */}
      <AegisArtwork
        phase={phase}
        reduced={reduced}
        exitElapsed={exitElapsed}
        onLoaded={onLoaded}
        onSettled={settled}
      />

      {/* Scrollable container hosting the slider control just below initial fold */}
      <div className={styles.scrollContent}>
        <div className={styles.heroSection} />
        <div className={styles.sliderSection}>
          <SliderControl
            disabled={phase === "loading" || phase === "assembling" || phase === "exiting" || phase === "entering"}
            onCommit={handleSliderCommit}
          />
        </div>
      </div>

      {/* Fallback recovery control: icon-only to honor text-free design */}
      {routeSlow && (
        <a className={styles.recovery} href="/console" aria-label="Open console">
          <ArrowRight size={22} />
        </a>
      )}

      {/* Noscript accessible fallback */}
      <noscript>
        <style>{`.${styles.landing}[data-initialized="false"] .${styles.scrollContent}{opacity:1;visibility:visible}`}</style>
        <a className={styles.recovery} href="/console" aria-label="Open console">
          <ArrowRight size={22} />
        </a>
      </noscript>
    </main>
  );
}
