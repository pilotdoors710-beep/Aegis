"use client";

import { useEffect, useRef, useState, type MouseEvent } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";
import TechText from "@/components/reactbits/TechText";
import { signalConsoleEntry } from "@/lib/landing/phases";
import styles from "./landing.module.css";

const Galaxy = dynamic(() => import("@/components/reactbits/Galaxy"), { ssr: false });
const DitherVeil = dynamic(() => import("@/components/ui/DitherVeil"), { ssr: false });

const WORD = "AEGIS";
const WEIGHT = 600;
const TRACKING = 0.14; // em
const STARS = ["#FCF8D8", "#E8C59E", "#d9541e"];
const COMMIT_AT = 0.12; // released past this, the scroll finishes on its own
const ARRIVE_AT = 0.985;

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));
const span = (value: number, from: number, to: number) => clamp01((value - from) / (to - from));
const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

export function LandingExperience() {
  const router = useRouter();
  const track = useRef<HTMLElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const mark = useRef<HTMLDivElement>(null);
  const readout = useRef<HTMLSpanElement>(null);
  const [fontSize, setFontSize] = useState(256);
  const [speed, setSpeed] = useState(1);
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const trackEl = track.current, stageEl = stage.current, markEl = mark.current;
    if (!trackEl || !stageEl || !markEl) return;
    const motion = matchMedia("(prefers-reduced-motion: reduce)");
    const probe = document.createElement("canvas").getContext("2d");
    let frame = 0, idle: ReturnType<typeof setTimeout> | undefined, lastY = 0, direction = 1, arrived = false;
    let start = { w: 0, h: 0 };

    router.prefetch("/console");
    history.scrollRestoration = "manual";
    window.scrollTo(0, 0);

    const travel = () => trackEl.offsetHeight - window.innerHeight;

    // Fit left-aligned TechText wordmark and stage framing
    const measure = () => {
      const width = stageEl.clientWidth, height = stageEl.clientHeight;
      const markW = markEl.clientWidth || Math.min(540, width * 0.48);
      const wanted = Math.max(54, Math.round(markW * 0.28));
      setFontSize(wanted);
      if (!probe) return;
      const family = getComputedStyle(markEl).fontFamily || "sans-serif";
      const ink = (size: number) => {
        probe.font = `${WEIGHT} ${size}px ${family}`;
        probe.letterSpacing = `${TRACKING * size}px`;
        const m = probe.measureText(WORD);
        return { w: m.actualBoundingBoxLeft + m.actualBoundingBoxRight, h: m.actualBoundingBoxAscent + m.actualBoundingBoxDescent };
      };
      const full = ink(wanted);
      const size = wanted * Math.min(1, (markW * 0.9) / Math.max(full.w, 1), (height * 0.4) / Math.max(full.h, 1));
      const fitted = ink(size);
      const pad = Math.max(14, size * 0.14);
      start = { w: fitted.w + pad * 2, h: fitted.h + pad * 2 };
      stageEl.style.setProperty("--inset-x", `${Math.max(0, width * 0.04)}px`);
      stageEl.style.setProperty("--inset-y", `${Math.max(0, height * 0.08)}px`);
      draw();
    };

    const draw = () => {
      frame = 0;
      const max = travel();
      const p = motion.matches || max <= 0 ? 0 : clamp01(window.scrollY / max);
      const t = ease(span(p, 0.02, 0.86));
      const set = (name: string, value: number) => stageEl.style.setProperty(name, value.toFixed(4));
      set("--t", t);
      set("--mark", span(p, 0.05, 0.55));
      set("--sky", 1 - span(p, 0.6, 0.95));
      set("--ground", span(p, 0.3, 0.85));
      set("--hint", 1 - span(p, 0, 0.07));
      set("--frame", span(p, 0, 0.05) * (1 - span(p, 0.92, 1)));
      stageEl.toggleAttribute("data-scrolling", p > 0.01);
      if (readout.current) {
        const w = Math.round(start.w + (stageEl.clientWidth - start.w) * t);
        const h = Math.round(start.h + (stageEl.clientHeight - start.h) * t);
        readout.current.textContent = `${WORD}  ${w} × ${h}`;
      }
      setSpeed(1 + Math.round(ease(span(p, 0, 0.8)) * 26) / 2);
      if (p >= ARRIVE_AT && !arrived) {
        arrived = true;
        signalConsoleEntry();
        router.replace("/console");
      }
    };

    // A scroll that stops part-way finishes itself, or returns if it was barely started.
    const settle = () => {
      const max = travel();
      if (arrived || motion.matches || max <= 0) return;
      const p = window.scrollY / max;
      if (p <= 0.001 || p >= ARRIVE_AT) return;
      window.scrollTo({ top: direction > 0 && p > COMMIT_AT ? max : 0, behavior: "smooth" });
    };

    const onScroll = () => {
      if (window.scrollY !== lastY) direction = window.scrollY > lastY ? 1 : -1;
      lastY = window.scrollY;
      if (!frame) frame = requestAnimationFrame(draw);
      clearTimeout(idle);
      idle = setTimeout(settle, 140);
    };
    const onMotion = () => { setReduced(motion.matches); window.scrollTo(0, 0); measure(); };

    setReduced(motion.matches);
    measure();
    document.fonts?.ready.then(measure, measure);
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", measure, { passive: true });
    motion.addEventListener("change", onMotion);
    return () => {
      cancelAnimationFrame(frame);
      clearTimeout(idle);
      history.scrollRestoration = "auto";
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", measure);
      motion.removeEventListener("change", onMotion);
    };
  }, [router]);

  const enter = (event: MouseEvent<HTMLAnchorElement>) => {
    signalConsoleEntry();
    const el = track.current;
    if (reduced || !el || event.metaKey || event.ctrlKey || event.shiftKey) return;
    event.preventDefault();
    window.scrollTo({ top: el.offsetHeight - window.innerHeight, behavior: "smooth" });
  };

  return (
    <main ref={track} className={styles.landing} data-reduced={reduced}>
      <div ref={stage} className={styles.stage}>
        <div className={styles.sky} aria-hidden="true">
          <Galaxy
            starColors={STARS}
            starSpeed={0.5}
            speed={speed}
            density={1.1}
            glowIntensity={0.35}
            twinkleIntensity={0.35}
            rotationSpeed={0.04}
            clickWarp={false}
            dpr={1.5}
          />
        </div>
        <div className={styles.ground} aria-hidden="true" />

        {/* Two-column stage: 'AEGIS' aligned left, DitherVeil shield on right */}
        <div className={styles.stageContent}>
          <div className={styles.leftColumn}>
            <div ref={mark} className={styles.markWrapper}>
              <TechText
                text={WORD}
                align="left"
                fontWeight={WEIGHT}
                fontSize={fontSize}
                letterSpacing={TRACKING}
                reveal="letter"
                dashLength={5}
                dashGap={3}
                strokeWidth={1.5}
                specks={15}
                intro="none"
                clickKick
                guides={false}
              />
            </div>
            <div className={styles.taglineBlock}>
              <p className={styles.taglineQuote}>COMMIT BEFORE CODE</p>
              <div className={styles.orangeRule} aria-hidden="true" />
              <p className={styles.taglineDesc}>
                A runtime shield between autonomous agents and the live web—stopping deception before it becomes a commitment.
              </p>
            </div>
          </div>

          <div className={styles.rightColumn}>
            <div className={styles.shieldWrapper}>
              <DitherVeil
                src="/landing/aegis-shield.jpg"
                fit="contain"
                pattern="floyd"
                pixelSize={2}
                levels={3}
                palette="duotone"
                inkColor="#080808"
                paperColor="#E8C59E"
                rimColor="#d9541e"
                rim={0.12}
                revealRadius={180}
                softness={0.65}
                linger={1.2}
                contrast={1.2}
                brightness={0.05}
                clickBurst={true}
              />
            </div>
          </div>
        </div>
        <div className={styles.frame} aria-hidden="true">
          <span ref={readout} className={styles.readout} />
          <i /><i /><i /><i />
        </div>
        <Link href="/console" className={styles.hint} onClick={enter}>
          {reduced ? "Enter console" : "Scroll to enter"}
          <span className={styles.tick} aria-hidden="true" />
        </Link>
      </div>
    </main>
  );
}
