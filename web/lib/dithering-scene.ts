// One WebGL scene supplies cropped pixels to the visible glass surfaces.
type Listener = (canvas: HTMLCanvasElement | null) => void;
const listeners = new Set<Listener>();
let current: HTMLCanvasElement | null = null;
let snapshot: HTMLCanvasElement | null = null;

export function publishDitheringScene(canvas: HTMLCanvasElement | null) {
  // Read the WebGL framebuffer once per scene revision, rather than once per
  // glass surface (including every scroll). Bake the static 14px blur here too,
  // so scrolling does not run a large blur filter on every individual crop.
  if (canvas) {
    snapshot ??= document.createElement("canvas");
    const context = snapshot.getContext("2d", { alpha: false });
    const canBlur = context && "filter" in context;
    const scale = canvas.width / Math.max(1, canvas.clientWidth);
    const padding = canBlur ? Math.round(40 * scale) : 0;
    const width = canvas.width + padding * 2, height = canvas.height + padding * 2;
    if (snapshot.width !== width) snapshot.width = width;
    if (snapshot.height !== height) snapshot.height = height;
    if (context) {
      context.fillStyle = "#001219"; context.fillRect(0, 0, width, height);
      if (canBlur) context.filter = `blur(${14 * scale}px)`;
      context.drawImage(canvas, padding, padding);
      if (canBlur) context.filter = "none";
    }
    snapshot.dataset.preblurred = String(!!canBlur);
    snapshot.dataset.scenePadding = canBlur ? "40" : "0";
    current = context ? snapshot : canvas;
  } else {
    current = null;
    snapshot = null;
  }
  listeners.forEach(listener => listener(current));
}

export function followDitheringScene(listener: Listener) {
  listeners.add(listener);
  listener(current);
  return () => { listeners.delete(listener); };
}
