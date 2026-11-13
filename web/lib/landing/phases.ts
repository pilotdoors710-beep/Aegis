export type Phase = "loading" | "assembling" | "ready" | "exiting" | "disassembling" | "tunnel" | "entering";
export const TIMING = {
  assembly: 1200,
  hold: 2000,
  scroll: 700,
  explosion: 650,
  disassembly: 650,
  crossfadeStart: 400,
  crossfadeEnd: 850,
  exitTotal: 1800,
  tunnel: 1400,
  recovery: 5000,
};
export const SEEN_KEY = "aegis:intro-seen:v1";
let focusOnEntry = false;
export function signalConsoleEntry() { focusOnEntry = true; }
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
