// One WebGL scene supplies cropped pixels to the visible glass surfaces.
type Listener = (canvas: HTMLCanvasElement | null) => void;
const listeners = new Set<Listener>();
let current: HTMLCanvasElement | null = null;

export function publishDitheringScene(canvas: HTMLCanvasElement | null) {
  current = canvas;
  listeners.forEach(listener => listener(canvas));
}

export function followDitheringScene(listener: Listener) {
  listeners.add(listener);
  listener(current);
  return () => { listeners.delete(listener); };
}
