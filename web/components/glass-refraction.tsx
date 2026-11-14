"use client";

import { useEffect, useRef } from "react";
import { createGlass } from "@/lib/liquid-glass-engine";
import styles from "./glass-refraction.module.css";

// One scheduled placement pass for every glass edge, even during rapid scrolling.
const placements = new Set<() => void>();
let placementFrame = 0;
function schedulePlacement() {
  if (placementFrame) return;
  placementFrame = requestAnimationFrame(() => {
    placementFrame = 0;
    for (const place of placements) place();
  });
}
function followBackdrop(place: () => void) {
  if (!placements.size) {
    window.addEventListener("scroll", schedulePlacement, { passive: true, capture: true });
    window.addEventListener("resize", schedulePlacement, { passive: true });
    document.addEventListener("toggle", schedulePlacement, true);
  }
  placements.add(place);
  schedulePlacement();
  return () => {
    placements.delete(place);
    if (placements.size) return;
    window.removeEventListener("scroll", schedulePlacement, true);
    window.removeEventListener("resize", schedulePlacement);
    document.removeEventListener("toggle", schedulePlacement, true);
    cancelAnimationFrame(placementFrame);
    placementFrame = 0;
  };
}

/** A shape-specific refractive rim over an aligned copy of the known backdrop.
 *  Uses CSS filter (not an SVG backdrop-filter), including WebKit/Gecko fixes.
 *  Text, click targets and accessibility semantics are never copied or filtered.
 */
export function GlassRefraction({ control = false }: { control?: boolean }) {
  const layerRef = useRef<HTMLSpanElement>(null);
  const surfaceRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const layer = layerRef.current;
    const surface = surfaceRef.current;
    const host = layer?.parentElement;
    if (!layer || !surface || !host) return;

    const preference = matchMedia("(prefers-reduced-transparency: reduce), (prefers-contrast: more), (forced-colors: active)");
    let stop: (() => void) | undefined;
    const configure = () => {
      stop?.();
      stop = undefined;
      if (preference.matches) return;

      const sky = host.closest(".app-theme")?.querySelector<HTMLElement>(".console-sky");
      const panel = control ? host.closest<HTMLElement>(".featured-run, .spotlight-card") : null;
      const source = panel ?? sky;
      if (!source) return;

      // Clone only the empty sky element: its CSS gradients/rings are the known
      // backdrop. Never clone WebGL canvases, page text, inputs or event handlers.
      const scene = panel ? document.createElement("span") : source.cloneNode(false) as HTMLElement;
      scene.classList.add(styles.scene);
      scene.setAttribute("aria-hidden", "true");
      Object.assign(scene.style, {
        position: "absolute", zIndex: "0", margin: "0", transform: "none",
        backgroundColor: panel ? "#ECEBEF" : "#2B3D55",
      });
      if (panel) scene.style.backgroundImage = getComputedStyle(panel).backgroundImage;
      surface.append(scene);

      const place = () => {
        const bounds = surface.getBoundingClientRect();
        const backdrop = source.getBoundingClientRect();
        Object.assign(scene.style, {
          left: `${backdrop.left - bounds.left}px`, top: `${backdrop.top - bounds.top}px`,
          width: `${backdrop.width}px`, height: `${backdrop.height}px`,
        });
      };
      place();

      try {
        const glass = createGlass(surface, {
          fit: true, clip: true,
          radius: parseFloat(getComputedStyle(host).borderTopLeftRadius) || 24,
          refraction: control ? 6 : 22,
          bezel: control ? .6 : .28,
          curvature: 4, chroma: .1, blur: control ? 0 : .35,
          specular: control ? .7 : .55, specularWidth: 1.5, mapScale: 1,
        });
        layer.dataset.refraction = "active";
        const unfollow = followBackdrop(place);
        const observer = new ResizeObserver(schedulePlacement);
        observer.observe(source);
        observer.observe(host);
        stop = () => {
          observer.disconnect();
          unfollow();
          glass.destroy();
          scene.remove();
          delete layer.dataset.refraction;
        };
      } catch {
        // Decoration is optional: a graphics failure retains the frosted CSS UI.
        scene.remove();
      }
    };
    configure();
    preference.addEventListener("change", configure);
    return () => {
      preference.removeEventListener("change", configure);
      stop?.();
    };
  }, [control]);

  return <span ref={layerRef} className={`${styles.layer}${control ? ` ${styles.control}` : ""}`} aria-hidden="true"><span ref={surfaceRef} className={styles.surface} /></span>;
}
