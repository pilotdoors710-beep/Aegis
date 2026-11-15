"use client";

import { useEffect, useRef, useState, type MouseEvent } from "react";
import dynamic from "next/dynamic";
import localFont from "next/font/local";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "motion/react";
import TechText from "@/components/reactbits/TechText";
import { GlassFold } from "@/components/ui/glass-fold";
import { signalConsoleEntry } from "@/lib/landing/phases";
import styles from "./landing.module.css";
import { ParticleLogo } from "./particle-logo";

const DecryptedText = dynamic(() => import("@/components/reactbits/DecryptedText"), { ssr: false });

// THEBOLDFONT free version (Sven Pels), wordmark only.
const boldFont = localFont({
  src: "../../public/landing/fonts/the_bold_font/THEBOLDFONT-FREEVERSION.woff",
  weight: "700",
  display: "block",
});

const scriptFont = localFont({
  src: "../../public/landing/fonts/great-vibes/GreatVibes-Regular.ttf",
  weight: "400",
  display: "swap",
  variable: "--font-landing-script",
});

const WORD = "AEGIS";
const WEIGHT = 700;
const TRACKING = 0.38; // em
const FONT_MAX = 640;
// Dark steel ground keeps the pearl (#F2EEE6) wordmark and copy readable.
const GLASS = { color1: "#4682B4", color2: "#0B131C", color3: "#C2A15A" }; // steel blue, ground, antique gold
const COMMIT_AT = 0.03; // released past this (~30px), the scroll finishes on its own
const FINISH_MS = 1100;
const ARRIVE_AT = 0.985;
const HOVER_TILT = 6; // deg, extra lean toward the cursor while it is over the hero copy

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));
const span = (value: number, from: number, to: number) => clamp01((value - from) / (to - from));
const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

const springTransition = {
  type: "spring" as const,
  stiffness: 80,
  damping: 14,
  mass: 0.9,
};

export function LandingExperience() {
  const router = useRouter();
  const track = useRef<HTMLElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const mark = useRef<HTMLDivElement>(null);
  const broad = useRef<HTMLDivElement>(null);
  const copy = useRef<HTMLDivElement>(null);
  const readout = useRef<HTMLSpanElement>(null);
  const finishRef = useRef<() => void>(() => {});
  const [speed, setSpeed] = useState(1);
  const [fontSize, setFontSize] = useState(160);
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const trackEl = track.current, stageEl = stage.current, markEl = mark.current, broadEl = broad.current;
    if (!trackEl || !stageEl || !markEl || !broadEl) return;
    const motion = matchMedia("(prefers-reduced-motion: reduce)");
    const probe = document.createElement("canvas").getContext("2d");
    let frame = 0, tween = 0, idle: ReturnType<typeof setTimeout> | undefined, lastY = 0, direction = 1, arrived = false;
    let start = { w: 0, h: 0 };
    let inkBox = { l: 0, t: 0, r: 0, b: 0 }; // wordmark ink box in stage (= viewport) pixels

    router.prefetch("/console");
    history.scrollRestoration = "manual";
    window.scrollTo(0, 0);

    const travel = () => trackEl.offsetHeight - window.innerHeight;

    // Same fit TechText uses, so the frame starts exactly on the wordmark's ink.
    // offset* ignores the zoom-in transform, so this is the resting position.
    const measure = () => {
      const width = stageEl.clientWidth, height = stageEl.clientHeight;
      if (!probe) return;
      const family = getComputedStyle(broadEl).fontFamily || "sans-serif";
      const ink = (size: number) => {
        probe.font = `${WEIGHT} ${size}px ${family}`;
        probe.letterSpacing = `${TRACKING * size}px`;
        const m = probe.measureText(WORD);
        return { w: m.actualBoundingBoxLeft + m.actualBoundingBoxRight, h: m.actualBoundingBoxAscent + m.actualBoundingBoxDescent };
      };
      // Size to the left column; TechText's own canvas spans the whole stage so dragged letters aren't clipped.
      const column = broadEl.offsetParent as HTMLElement | null;
      const colW = column?.offsetWidth ?? width, colH = column?.offsetHeight ?? height;
      const full = ink(FONT_MAX);
      const size = FONT_MAX * Math.min(1, (colW * 0.9) / Math.max(full.w, 1), (colH * 0.66) / Math.max(full.h, 1));
      setFontSize(size);
      const fitted = ink(size);
      const pad = Math.max(14, size * 0.14);
      start = { w: Math.round(fitted.w + pad * 2), h: Math.round(fitted.h + pad * 2) };
      // TechText align="left" starts the ink 5% into its box.
      const inkLeft = (column?.offsetLeft ?? 0) + broadEl.offsetLeft + broadEl.offsetWidth * 0.05;
      const cx = inkLeft + fitted.w / 2;
      const cy = (column?.offsetTop ?? 0) + colH / 2; // the canvas is centred on the column
      const px = (name: string, value: number) => stageEl.style.setProperty(name, `${Math.max(0, value)}px`);
      px("--inset-l", cx - start.w / 2);
      px("--inset-r", width - cx - start.w / 2);
      px("--inset-t", cy - start.h / 2);
      px("--inset-b", height - cy - start.h / 2);
      inkBox = { l: cx - start.w / 2, t: cy - start.h / 2, r: cx + start.w / 2, b: cy + start.h / 2 };
      px("--ink-left", inkLeft);
      px("--ink-bottom", cy + fitted.h / 2);
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

    // Timed ease-out instead of native smooth scroll, whose speed depends on distance and browser.
    const finish = () => {
      if (tween || arrived) return;
      const from = window.scrollY, t0 = performance.now();
      const step = (now: number) => {
        const x = Math.min(1, (now - t0) / FINISH_MS);
        window.scrollTo(0, from + (travel() - from) * (1 - (1 - x) ** 3));
        tween = x < 1 ? requestAnimationFrame(step) : 0;
      };
      tween = requestAnimationFrame(step);
    };
    finishRef.current = finish;

    // A scroll that stops part-way finishes itself, or returns if it was barely started.
    const settle = () => {
      const max = travel();
      if (tween || arrived || motion.matches || max <= 0) return;
      const p = window.scrollY / max;
      if (p <= 0.001 || p >= ARRIVE_AT) return;
      if (direction > 0 && p > COMMIT_AT) finish();
      else window.scrollTo({ top: 0, behavior: "smooth" });
    };

    const onScroll = () => {
      if (window.scrollY !== lastY) direction = window.scrollY > lastY ? 1 : -1;
      lastY = window.scrollY;
      if (!frame) frame = requestAnimationFrame(draw);
      clearTimeout(idle);
      idle = setTimeout(settle, 90);
    };
    // The letter canvas covers the whole stage, so hover is judged against the wordmark + copy box, not DOM targets.
    const hover = (x: number, y: number) => {
      markEl.style.setProperty("--hover-y", `${(x * HOVER_TILT).toFixed(2)}deg`);
      markEl.style.setProperty("--hover-x", `${(-y * HOVER_TILT).toFixed(2)}deg`);
    };
    const onPointer = (e: PointerEvent) => {
      if (e.pointerType !== "mouse" || motion.matches || stageEl.hasAttribute("data-scrolling")) return hover(0, 0);
      const c = copy.current?.getBoundingClientRect();
      const l = Math.min(inkBox.l, c?.left ?? inkBox.l), r = Math.max(inkBox.r, c?.right ?? inkBox.r);
      const t = Math.min(inkBox.t, c?.top ?? inkBox.t), b = Math.max(inkBox.b, c?.bottom ?? inkBox.b);
      const inside = r > l && b > t && e.clientX >= l && e.clientX <= r && e.clientY >= t && e.clientY <= b;
      if (!inside) return hover(0, 0);
      hover(((e.clientX - l) / (r - l)) * 2 - 1, ((e.clientY - t) / (b - t)) * 2 - 1);
    };
    const onLeave = () => hover(0, 0);

    const onMotion = () => { setReduced(motion.matches); window.scrollTo(0, 0); measure(); };

    setReduced(motion.matches);
    measure();
    document.fonts?.ready.then(measure, measure);
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", measure, { passive: true });
    window.addEventListener("pointermove", onPointer, { passive: true });
    document.documentElement.addEventListener("mouseleave", onLeave);
    motion.addEventListener("change", onMotion);
    return () => {
      cancelAnimationFrame(frame);
      cancelAnimationFrame(tween);
      clearTimeout(idle);
      history.scrollRestoration = "auto";
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", measure);
      window.removeEventListener("pointermove", onPointer);
      document.documentElement.removeEventListener("mouseleave", onLeave);
      motion.removeEventListener("change", onMotion);
    };
  }, [router]);

  const enter = (event: MouseEvent<HTMLAnchorElement>) => {
    signalConsoleEntry();
    if (reduced || event.metaKey || event.ctrlKey || event.shiftKey) return;
    event.preventDefault();
    finishRef.current();
  };

  return (
    <main ref={track} className={`${styles.landing} ${scriptFont.variable}`} data-reduced={reduced}>
      <div ref={stage} className={styles.stage}>
        <div className={styles.sky} aria-hidden="true">
          <GlassFold {...GLASS} speed={0.4 * speed} noise={0.1} />
        </div>
        <div className={styles.ground} aria-hidden="true" />
        <ParticleLogo src="/landing/logo-white-trimmed.png" className={styles.particleLogo} />
        <div ref={mark} className={styles.mark}>
          <div className={styles.wordmarkZoom}>
            <div ref={broad} className={`${styles.wordmarkBroad} ${boldFont.className}`}>
              <TechText
                text={WORD}
                color="#e6dcc8" // warm bone, so the wordmark reads apart from the brighter subtitle
                fontWeight={WEIGHT}
                fontSize={fontSize}
                align="left"
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
          </div>
          <div ref={copy} className={styles.subtitleWrapper}>
            <motion.div
              className={styles.headlineMotion}
              initial={reduced ? false : { opacity: 0, y: 48 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{
                ...springTransition,
                delay: 0.85,
              }}
            >
              <DecryptedText
                text="PROTECT YOUR AGENTS LIKE NEVER BEFORE"
                animateOn="inViewHover"
                revealDirection="center"
                speed={40}
                maxIterations={15}
                sequential={true}
                scrambleColor="#c2a15a"
                className={styles.subtitleRevealed}
                encryptedClassName={styles.subtitleEncrypted}
                parentClassName={styles.displaySubtitle}
              />
            </motion.div>
            <motion.p
              className={styles.heroDescription}
              initial={reduced ? false : { opacity: 0, y: 44 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{
                ...springTransition,
                delay: 1.0,
              }}
            >
              𝕐𝕠𝕦 𝕘𝕒𝕧𝕖 𝕪𝕠𝕦𝕣 𝔸𝕀 𝕒 𝕔𝕒𝕣𝕕 𝕒𝕟𝕕 𝕥𝕠𝕝𝕕 𝕚𝕥 𝕥𝕠 𝕓𝕣𝕠𝕨𝕤𝕖 𝕥𝕙𝕖 𝕨𝕖𝕓—𝕓𝕦𝕥 𝕥𝕙𝕖 𝕚𝕟𝕥𝕖𝕣𝕟𝕖𝕥 𝕚𝕤 𝕗𝕦𝕝𝕝 𝕠𝕗 𝕥𝕣𝕒𝕡𝕤 𝕨𝕒𝕚𝕥𝕚𝕟𝕘 𝕥𝕠 𝕥𝕣𝕚𝕔𝕜 𝕚𝕥. 𝔸𝕖𝕘𝕚𝕤 𝕒𝕔𝕥𝕤 𝕒𝕤 𝕒 𝕣𝕖𝕒𝕝-𝕥𝕚𝕞𝕖 𝕓𝕠𝕕𝕪𝕘𝕦𝕒𝕣𝕕 𝕠𝕧𝕖𝕣 𝕪𝕠𝕦𝕣 𝕒𝕘𝕖𝕟𝕥’𝕤 𝕤𝕙𝕠𝕦𝕝𝕕𝕖𝕣, 𝕔𝕒𝕥𝕔𝕙𝕚𝕟𝕘 𝕤𝕟𝕖𝕒𝕜𝕪 𝕤𝕦𝕓𝕤𝕔𝕣𝕚𝕡𝕥𝕚𝕠𝕟𝕤, 𝕜𝕚𝕝𝕝𝕚𝕟𝕘 𝕕𝕖𝕔𝕖𝕡𝕥𝕚𝕧𝕖 𝕔𝕙𝕖𝕔𝕜𝕠𝕦𝕥𝕤, 𝕒𝕟𝕕 𝕧𝕖𝕣𝕚𝕗𝕪𝕚𝕟𝕘 𝕥𝕙𝕖 𝕣𝕖𝕔𝕖𝕚𝕡𝕥 𝕓𝕖𝕗𝕠𝕣𝕖 𝕒 𝕤𝕚𝕟𝕘𝕝𝕖 𝕕𝕠𝕝𝕝𝕒𝕣 𝕝𝕖𝕒𝕧𝕖𝕤 𝕪𝕠𝕦𝕣 𝕨𝕒𝕝𝕝𝕖𝕥.
            </motion.p>
          </div>
        </div>
        <div className={styles.frame} aria-hidden="true">
          <span ref={readout} className={styles.readout} />
          <i /><i /><i /><i />
        </div>
        <motion.div
          className={styles.hintWrapper}
          initial={reduced ? false : { opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{
            ...springTransition,
            delay: 1.18,
          }}
        >
          <Link href="/console" className={styles.hint} onClick={enter}>
            {reduced ? "Enter console" : "Scroll to enter"}
            <span className={styles.tick} aria-hidden="true" />
          </Link>
        </motion.div>
      </div>
    </main>
  );
}
