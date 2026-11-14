// Dashboard effects share a frame and read geometry before painting. This is
// deliberately opt-in; the landing page keeps its own animation lifecycle.
type EffectFrame = (now: number) => void | (() => void);
const frames = new Map<number, EffectFrame>();
let sequence = 0;
let frame = 0;

export function requestEffectFrame(callback: EffectFrame) {
  const id = ++sequence;
  frames.set(id, callback);
  if (!frame) frame = requestAnimationFrame(now => {
    frame = 0;
    const batch = [...frames];
    frames.clear();
    const writes = batch.map(([, read]) => read(now));
    writes.forEach(write => write?.());
  });
  return id;
}

export function cancelEffectFrame(id: number) {
  frames.delete(id);
  if (!frames.size) { cancelAnimationFrame(frame); frame = 0; }
}

// One native listener per event instead of one listener per card. Pointer
// handlers only record the latest coordinates; geometry is read in the frame.
const events = new Map<string, { listeners: Set<EventListener>; dispatch: EventListener }>();
export function followEffectEvent(type: string, listener: EventListener) {
  let group = events.get(type);
  if (!group) {
    const listeners = new Set<EventListener>();
    const dispatch: EventListener = event => listeners.forEach(callback => callback(event));
    group = { listeners, dispatch };
    events.set(type, group);
    window.addEventListener(type, dispatch, { capture: true, passive: true });
  }
  group.listeners.add(listener);
  return () => {
    group.listeners.delete(listener);
    if (!group.listeners.size) {
      window.removeEventListener(type, group.dispatch, true);
      events.delete(type);
    }
  };
}
