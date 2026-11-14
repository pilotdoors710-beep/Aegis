export type Phase =
  | "loading"
  | "title"
  | "quote"
  | "description"
  | "ready"
  | "exiting"
  | "entering"
  | "assembling"
  | "disassembling"
  | "tunnel";

export const TIMING = {
  titleStart: 0,
  titleEnd: 800,
  quoteStart: 700,
  quoteEnd: 1400,
  descStart: 1300,
  descEnd: 2100,
  controlStart: 2050,
  controlEnd: 2550,
  totalEntrance: 2550,
  crossfadeStart: 400,
  crossfadeEnd: 850,
  exitTotal: 1800,
  recovery: 5000,
  // Retained legacy timings for backward compatibility with artwork modules
  assembly: 1200,
  hold: 2000,
  scroll: 700,
  explosion: 650,
  disassembly: 650,
  tunnel: 1400,
};

export const SEEN_KEY = "aegis:intro-seen:v1";
let focusOnEntry = false;
export function signalConsoleEntry() { focusOnEntry = true; }
/** True while the visitor is arriving from the entrance; the console shell reads it to rise into place. */
export function arrivedFromEntrance() { return focusOnEntry; }
export function consumeConsoleEntry() {
  const value = focusOnEntry;
  focusOnEntry = false;
  return value;
}

/** Active-time animation: hidden tabs don't consume the sequence. */
export function animate(duration: number, draw: (progress: number) => void, done: () => void) {
  let frame = 0, elapsed = 0, previous = performance.now(), cancelled = false;
  const tick = (now: number) => {
    elapsed += Math.min(now - previous, 64);
    previous = now;
    const progress = Math.min(1, elapsed / duration);
    draw(progress);
    if (cancelled) return;
    if (progress === 1) done();
    else frame = requestAnimationFrame(tick);
  };
  const visibility = () => {
    cancelAnimationFrame(frame);
    if (!document.hidden && !cancelled) { previous = performance.now(); frame = requestAnimationFrame(tick); }
  };
  document.addEventListener("visibilitychange", visibility);
  const finish = done;
  done = () => { document.removeEventListener("visibilitychange", visibility); finish(); };
  if (!document.hidden) frame = requestAnimationFrame(tick);
  return () => { cancelled = true; cancelAnimationFrame(frame); document.removeEventListener("visibilitychange", visibility); };
}
