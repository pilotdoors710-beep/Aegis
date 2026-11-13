"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { SEEN_KEY, signalConsoleEntry, TIMING, animate, type Phase } from "@/lib/landing/phases";
import { SquareTunnel } from "./square-tunnel";
import { SliderControl } from "./slider-control";
import { AegisArtwork } from "./aegis-artwork";
import { MathScramble } from "@/components/ui/math-scramble";
import styles from "./landing.module.css";

const Scene = dynamic(() => import("./scene").then((m) => m.Scene), { ssr: false });

type Stage = "loading" | "title" | "quote" | "description" | "ready";

export function LandingExperience() {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("loading");
  const [stage, setStage] = useState<Stage>("loading");
  const [reduced, setReduced] = useState(false);
  const [routeSlow, setRouteSlow] = useState(false);
  const [initialized, setInitialized] = useState(false);
  const [darkOverlayOpacity, setDarkOverlayOpacity] = useState(0);
  const [tunnelOpacity, setTunnelOpacity] = useState(0);
  const [tunnelProgress, setTunnelProgress] = useState(0);
  const [tunnelPrepared, setTunnelPrepared] = useState(false);
  const [exitElapsed, setExitElapsed] = useState(-1);

  // Progressive background dimming states
  const [flowOpacity, setFlowOpacity] = useState(0.85);
  const [veilOpacity, setVeilOpacity] = useState(0.15);
  const [flowContrast, setFlowContrast] = useState(1.0);

  const accepted = useRef(false);
  const navigated = useRef(false);
  const root = useRef<HTMLElement>(null);
  const phaseRef = useRef<Phase>("loading");
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

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
      return;
    }
    router.prefetch("/console");

    const queryMotion = matchMedia("(prefers-reduced-motion: reduce)");

    queueMicrotask(() => {
      if (!mounted) return;
      setInitialized(true);
      const isRed = queryMotion.matches;
      setReduced(isRed);
      if (isRed) {
        changePhase("ready");
        setStage("ready");
        setFlowOpacity(0.32);
        setVeilOpacity(0.65);
        setFlowContrast(0.70);
        setTunnelPrepared(true);
      } else {
        // 0–800ms: AEGIS rises through clipped mask; FlowField ~85% opacity, 15% veil
        changePhase("title");
        setStage("title");
        setFlowOpacity(0.85);
        setVeilOpacity(0.15);
        setFlowContrast(1.0);
        setTunnelPrepared(true);

        // 700–1,400ms: Quote fades and rises, orange rule expands; FlowField ~55% opacity, 45% veil
        timers.current.push(
          setTimeout(() => {
            if (!mounted || phaseRef.current === "exiting" || phaseRef.current === "entering") return;
            changePhase("quote");
            setStage("quote");
            setFlowOpacity(0.55);
            setVeilOpacity(0.45);
            setFlowContrast(0.85);
          }, TIMING.quoteStart)
        );

        // 1,300–2,100ms: Description fades upward as a complete block; FlowField ~32% opacity, 65% veil
        timers.current.push(
          setTimeout(() => {
            if (!mounted || phaseRef.current === "exiting" || phaseRef.current === "entering") return;
            changePhase("description");
            setStage("description");
            setFlowOpacity(0.32);
            setVeilOpacity(0.65);
            setFlowContrast(0.70);
          }, TIMING.descStart)
        );

        // 2,050–2,550ms: SLIDE TO ENTER label and slider appear; slider becomes interactive
        timers.current.push(
          setTimeout(() => {
            if (!mounted || phaseRef.current === "exiting" || phaseRef.current === "entering") return;
            changePhase("ready");
            setStage("ready");
          }, TIMING.controlStart)
        );
      }
    });

    const updateMotion = () => {
      const isRed = queryMotion.matches;
      setReduced(isRed);
      if (isRed) {
        changePhase("ready");
        setStage("ready");
        setFlowOpacity(0.32);
        setVeilOpacity(0.65);
        setFlowContrast(0.70);
        setTunnelPrepared(true);
      }
    };
    queryMotion.addEventListener("change", updateMotion);

    const pendingTimers = timers.current;
    return () => {
      mounted = false;
      queryMotion.removeEventListener("change", updateMotion);
      pendingTimers.forEach(clearTimeout);
    };
  }, [changePhase, navigate, router]);

  // Handle slide completion: trigger right artwork explosion, frame transition, and navigate
  const handleSliderCommit = useCallback(() => {
    if (accepted.current) return;
    accepted.current = true;

    // 5-second recovery timeout
    timers.current.push(setTimeout(() => navigate(), TIMING.recovery));

    changePhase("exiting");
    setTunnelPrepared(true);

    if (reduced) {
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

    // Shared exit timeline:
    // 0–400ms: hero text fades out on the left; artwork on the right explodes outwards (0–650ms)
    // 400ms: square frames begin fading in
    // 400–850ms: crossfade into dark tunnel
    // 400–1,800ms: frame flight continues through tunnel
    // 1,800ms: complete tunnel and navigate to /console
    const stopExit = animate(TIMING.exitTotal, (p) => {
      const t = p * TIMING.exitTotal;
      setExitElapsed(t);

      if (t >= TIMING.crossfadeStart) {
        const fade = Math.min(1, (t - TIMING.crossfadeStart) / (TIMING.crossfadeEnd - TIMING.crossfadeStart));
        setDarkOverlayOpacity(fade);
        setTunnelOpacity(fade);
      } else {
        setDarkOverlayOpacity(0);
        setTunnelOpacity(0);
      }

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
      data-stage={stage}
      data-reduced={reduced}
      data-initialized={initialized}
    >
      {/* ThreeUI FlowField background scene with progressive dimming */}
      <div
        className={styles.sceneWrapper}
        style={{
          opacity: flowOpacity,
          filter: `contrast(${flowContrast})`,
          transition: reduced ? "none" : "opacity 600ms ease, filter 600ms ease",
        }}
        aria-hidden="true"
      >
        <Scene />
      </div>

      {/* Neutral veil for progressive dimming: #7C7D75 */}
      <div
        className={styles.veil}
        style={{
          opacity: veilOpacity,
          transition: reduced ? "none" : "opacity 600ms ease",
        }}
        aria-hidden="true"
      />

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

      {/* Two-column composition: hero text on left, actual big dithered artwork on right */}
      <div className={styles.composition} data-stage={stage}>
        {/* Left column: Centered/left-aligned cinematic in-viewport hero composition */}
        <div className={styles.hero} data-stage={stage}>
          {/* 1. AEGIS as single h1 rising through clipped mask */}
          <div className={styles.titleMask}>
            <h1 className={styles.title}>AEGIS</h1>
          </div>

          {/* 2. COMMIT BEFORE CODE quote and expanding orange rule */}
          <div className={styles.quoteBlock}>
            <p className={styles.quote}>COMMIT BEFORE CODE</p>
            <div className={styles.orangeRule} aria-hidden="true" />
          </div>

          {/* 3. Cinematic description copy block with MathScramble on hover */}
          <div className={styles.descriptionBlock}>
            <p className={styles.description}>
              “A runtime shield between autonomous agents and the live web—stopping deception before it becomes a commitment.”
            </p>
            <div className={styles.mathScrambleLayer} aria-hidden="true">
              <MathScramble
                lines={[
                  "“A runtime shield between autonomous agents",
                  "and the live web—stopping deception",
                  "before it becomes a commitment.”",
                ]}
                highlight={["autonomous agents", "runtime shield", "commitment"]}
                color="transparent"
                highlightColor="transparent"
                background="transparent"
                colors={["#DD700B", "#FCF8D8", "#E8C59E", "#A86442", "#5E2C1D", "#D9DADF"]}
                font='var(--font-geist-sans), -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
                highlightFont='var(--font-geist-sans), -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
                fontSize={15}
                autoplay={false}
                cursor={false}
                radius={0.8}
                speed={1}
                boxed={0.25}
                style={{ width: "100%", height: "100%", minHeight: "unset" }}
              />
            </div>
          </div>

          {/* 4. Labeled slide-to-enter control */}
          <div className={styles.controlBlock}>
            <span className={styles.sliderLabel}>SLIDE TO ENTER</span>
            <SliderControl
              disabled={phase !== "ready"}
              onCommit={handleSliderCommit}
            />
          </div>
        </div>

        {/* Right column: The big dithered art that explodes on commit */}
        <div className={styles.artworkWrapper}>
          <AegisArtwork
            phase={phase}
            reduced={reduced}
            exitElapsed={exitElapsed}
          />
        </div>
      </div>

      {/* Fallback recovery control: icon-only */}
      {routeSlow && (
        <a className={styles.recovery} href="/console" aria-label="Open console">
          <ArrowRight size={22} />
        </a>
      )}

      {/* Noscript accessible fallback */}
      <noscript>
        <div className={styles.composition} data-stage="ready">
          <div className={styles.hero} data-stage="ready">
            <div className={styles.titleMask}>
              <h1 className={styles.title}>AEGIS</h1>
            </div>
            <div className={styles.quoteBlock}>
              <p className={styles.quote}>COMMIT BEFORE CODE</p>
              <div className={styles.orangeRule} />
            </div>
            <p className={styles.description}>
              “A runtime shield between autonomous agents and the live web—stopping deception before it becomes a commitment.”
            </p>
            <a className={styles.noscriptLink} href="/console">
              Open console
            </a>
          </div>
          <div className={styles.artworkWrapper}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/landing/aegis-dithered.png"
              width="960"
              height="960"
              alt="Dithered Aegis shield"
              className={styles.artworkImg}
            />
          </div>
        </div>
      </noscript>
    </main>
  );
}
