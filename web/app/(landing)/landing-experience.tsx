"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { SEEN_KEY, signalConsoleEntry, TIMING, type Phase } from "@/lib/landing/phases";
import { AegisArtwork } from "./aegis-artwork";
import { SquareTunnel } from "./square-tunnel";
import styles from "./landing.module.css";

export function LandingExperience({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("loading"), [reduced, setReduced] = useState(false);
  const [routeSlow, setRouteSlow] = useState(false);
  const [initialized, setInitialized] = useState(false);
  const accepted = useRef(false), navigated = useRef(false), available = useRef(false);
  const root = useRef<HTMLElement>(null), phaseRef = useRef<Phase>("loading");
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const changePhase = useCallback((value: Phase) => { phaseRef.current = value; setPhase(value); }, []);

  const navigate = useCallback(() => {
    if (navigated.current) return;
    navigated.current = true; accepted.current = true;
    changePhase("entering"); signalConsoleEntry();
    router.replace("/console");
    timers.current.push(setTimeout(() => setRouteSlow(true), 2000));
  }, [changePhase, router]);

  useEffect(() => {
    let mounted = true;
    try { sessionStorage.removeItem(SEEN_KEY); } catch {}
    const params = new URLSearchParams(location.search);
    if (params.get("intro") === "skip") navigate();
    else queueMicrotask(() => { if (mounted) setInitialized(true); });
    router.prefetch("/console");
    const query = matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => {
      setReduced(query.matches);
      if (query.matches) {
        if (accepted.current) navigate();
        else changePhase("ready");
      }
    };
    update(); query.addEventListener("change", update);
    const pendingTimers = timers.current;
    return () => { mounted = false; query.removeEventListener("change", update); pendingTimers.forEach(clearTimeout); };
  }, [changePhase, navigate, router]);

  const enter = () => {
    if (accepted.current || window.getSelection()?.toString()) return;
    accepted.current = true;
    timers.current.push(setTimeout(() => navigate(), TIMING.recovery));
    if (reduced || !available.current) {
      changePhase("disassembling");
      const animation = root.current!.querySelector(`.${styles.composition}`)!.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 150, fill: "forwards" });
      animation.finished.then(() => navigate()).catch(() => navigate());
      fade.current = animation;
    } else changePhase("disassembling");
  };
  const fade = useRef<Animation | null>(null);
  useEffect(() => () => fade.current?.cancel(), []);
  const onLoaded = useCallback((ok: boolean) => {
    available.current = ok;
    if (phaseRef.current === "loading") changePhase(ok ? "assembling" : "ready");
    // Context loss during an accepted exit must still release the user.
    else if (!ok && accepted.current) navigate();
    else if (!ok && phaseRef.current === "assembling") changePhase("ready");
  }, [changePhase, navigate]);
  const settled = useCallback(() => { if (phaseRef.current === "assembling") changePhase("ready"); }, [changePhase]);
  const disassembled = useCallback(() => {
    if (phaseRef.current === "disassembling" && available.current && !reduced) changePhase("tunnel");
  }, [changePhase, reduced]);

  return <main ref={root} className={styles.landing} data-phase={phase} data-reduced={reduced} data-initialized={initialized}
    onClick={(event) => { if (!(event.target as HTMLElement).closest("a,button")) enter(); }}>
    <button className={styles.continue} aria-label="Enter Aegis console" disabled={["disassembling", "tunnel", "entering"].includes(phase)}
      onClick={enter} onKeyDown={(event) => { if (event.repeat) event.preventDefault(); }} />
    <header className={styles.header}><span className={styles.brand}>AEGIS<span className={styles.brandSquare} /></span></header>
    <div className={styles.composition}>
      <div className={styles.copy}>{children}</div>
      <AegisArtwork phase={phase} reduced={reduced} onLoaded={onLoaded} onSettled={settled} onExit={disassembled} />
    </div>
    <footer className={styles.footer}><span className={styles.index}>01 / BEFORE THE ACTION</span>
      <p className={styles.prompt}>Click anywhere to continue <span aria-hidden="true">▪</span></p>
      <span aria-hidden="true" />
    </footer>
    <SquareTunnel prepared={!reduced && (phase === "disassembling" || phase === "tunnel")} active={phase === "tunnel"} onComplete={navigate} />
    {routeSlow && <a className={styles.recovery} href="/console">Open console ↗</a>}
    <noscript><style>{`.${styles.continue}{display:none} .${styles.landing}[data-initialized="false"] .${styles.composition}{opacity:1;visibility:visible}`}</style><a className={styles.recovery} href="/console">Open console ↗</a></noscript>
  </main>;
}
