"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { createGlass } from "@/lib/liquid-glass-engine";
import { followDitheringScene } from "@/lib/dithering-scene";
import styles from "./glass-refraction.module.css";

type Material = "panel" | "control" | "compact";
const optics = {
  // A full dome bends the background across the entire surface. The optical
  // centre has zero displacement by symmetry, rather than a broad flat region.
  panel: { refraction: 28, bezel: 1, curvature: 2.5, blur: .8, specular: .3 },
  control: { refraction: 9, bezel: 1, curvature: 2.5, blur: .3, specular: .4 },
  compact: { refraction: 5, bezel: 1, curvature: 2.5, blur: .2, specular: .25 },
};
const placements = new Set<() => void>();
let frame = 0;
function schedule() {
  if (frame) return;
  frame = requestAnimationFrame(() => { frame = 0; placements.forEach(place => place()); });
}
function follow(place: () => void) {
  if (!placements.size) {
    window.addEventListener("scroll", schedule, true);
    window.addEventListener("resize", schedule);
    document.addEventListener("toggle", schedule, true);
  }
  placements.add(place);
  return () => {
    placements.delete(place);
    if (placements.size) return;
    window.removeEventListener("scroll", schedule, true);
    window.removeEventListener("resize", schedule);
    document.removeEventListener("toggle", schedule, true);
    cancelAnimationFrame(frame); frame = 0;
  };
}

/** Only the decorative, aligned scene is filtered; content and hit targets stay native. */
export function GlassRefraction({ variant = "panel", list = false }: { variant?: Material; list?: boolean }) {
  const layerRef = useRef<HTMLElement>(null);
  const surfaceRef = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const layer = layerRef.current, surface = surfaceRef.current;
    const host = layer?.parentElement?.parentElement;
    const sky = host?.closest(".app-theme")?.querySelector<HTMLElement>(".console-sky");
    if (!layer || !surface || !host || !sky) return;
    const preference = matchMedia("(prefers-reduced-transparency: reduce), (prefers-contrast: more), (forced-colors: active)");
    let visible = false;
    let stop: (() => void) | undefined;
    const configure = () => {
      stop?.(); stop = undefined;
      if (!visible || preference.matches) return;
      const scene = document.createElement("span");
      scene.className = styles.scene;
      // A cropped copy of the shared shader is refracted, leaving native content sharp.
      scene.style.background = getComputedStyle(sky).background;
      const copy = document.createElement("canvas");
      copy.style.cssText = "position:absolute;inset:0;width:100%;height:100%;display:none";
      scene.append(copy);
      const context = copy.getContext("2d", { alpha: false });
      surface.append(scene);
      let source: HTMLCanvasElement | null = null;
      let left = 0, top = 0, width = 1, height = 1;
      const paint = () => {
        copy.style.display = source && context ? "block" : "none";
        if (!source || !context) return;
        context.fillStyle = "#001219"; context.fillRect(0, 0, width, height);
        context.drawImage(source, -left, -top, innerWidth, innerHeight);
      };
      const place = () => {
        const rect = surface.getBoundingClientRect();
        // Overscan supplies pixels for the full-dome displacement near the edges.
        const padding = 40;
        left = rect.left - padding; top = rect.top - padding;
        width = Math.max(1, Math.ceil(rect.width + padding * 2));
        height = Math.max(1, Math.ceil(rect.height + padding * 2));
        if (copy.width !== width) copy.width = width;
        if (copy.height !== height) copy.height = height;
        Object.assign(scene.style, {
          left: `${-padding}px`, top: `${-padding}px`, width: `${width}px`, height: `${height}px`,
          backgroundSize: `${innerWidth}px ${innerHeight}px`, backgroundPosition: `${-left}px ${-top}px`,
        });
        paint();
      };
      place();
      try {
        const glass = createGlass(surface, {
          fit: true, clip: true, radius: parseFloat(getComputedStyle(host).borderTopLeftRadius) || 12,
          ...optics[variant], chroma: .12, mapScale: innerWidth < 600 ? .75 : 1,
        });
        layer.dataset.refraction = "active";
        const unfollowScene = followDitheringScene(canvas => { source = canvas; paint(); });
        const unfollow = follow(place);
        const resize = new ResizeObserver(schedule); resize.observe(host);
        stop = () => {
          unfollowScene(); unfollow(); resize.disconnect();
          glass.destroy(); scene.remove(); delete layer.dataset.refraction;
        };
      } catch { scene.remove(); }
    };
    const observer = new IntersectionObserver(entries => { visible = entries[0].isIntersecting; configure(); });
    observer.observe(host);
    preference.addEventListener("change", configure);
    return () => { observer.disconnect(); preference.removeEventListener("change", configure); stop?.(); };
  }, [variant]);
  const Tag = list ? "li" : "span";
  return <Tag ref={layerRef as React.Ref<HTMLLIElement & HTMLSpanElement>} className={styles.layer} data-glass-layer={variant} aria-hidden="true"><span ref={surfaceRef} className={styles.surface} /></Tag>;
}

const targets = ".featured-run,.spotlight-card,.staggered-menu-header,.staggered-menu-panel,.console-card,.agent-pane,.sample-banner,.outcome-card,.permission-pair-section,.permission-pair-card,.ledger-panel,.event-feed,.evidence-card,.approval-dialog,.approval-buttons,.audit-check,.two-view,.outcome-recurring,.replay-controls,.primary-button,.secondary-button,.approval-buttons button,.inspect-button,.badge,.chip,.task-line > span,.sm-toggle";

/** Covers dynamic sample and dialog surfaces as well as the initial preset grid. */
export function DashboardGlass() {
  const [hosts, setHosts] = useState<{ element: HTMLElement; mount: HTMLElement; key: string }[]>([]);
  useEffect(() => {
    const root = document.querySelector(".app-theme");
    if (!root) return;
    let pending = 0;
    let sequence = 0;
    const mounts = new Map<HTMLElement, { mount: HTMLElement; key: string }>();
    const collect = () => {
      pending = 0;
      const next = Array.from(root.querySelectorAll<HTMLElement>(targets), element => {
        let entry = mounts.get(element);
        if (!entry || entry.mount.parentElement !== element) {
          const mount = document.createElement(element.tagName === "OL" ? "li" : "span");
          mount.dataset.glassMount = "";
          mount.setAttribute("aria-hidden", "true");
          element.append(mount);
          entry = { mount, key: String(sequence++) };
          mounts.set(element, entry);
        }
        return { element, ...entry };
      });
      for (const [element, { mount }] of mounts) if (!root.contains(element)) { mount.remove(); mounts.delete(element); }
      setHosts(previous => previous.length === next.length && previous.every((host, i) => host.element === next[i].element && host.mount === next[i].mount) ? previous : next);
    };
    const observer = new MutationObserver(records => {
      if (records.some(record => record.type === "attributes" && !(record.target as Element).closest?.("[data-glass-layer]"))) schedule();
      if (records.every(record => (record.target as Element).closest?.("[data-glass-layer]"))) return;
      if (!records.some(record => record.type === "childList")) return;
      if (!pending) pending = requestAnimationFrame(collect);
    });
    observer.observe(root, { childList: true, subtree: true, attributes: true, attributeFilter: ["style", "data-open"] });
    collect();
    return () => { observer.disconnect(); cancelAnimationFrame(pending); mounts.forEach(({ mount }) => mount.remove()); };
  }, []);
  return hosts.map(({ element: host, mount, key }) => createPortal(<GlassRefraction variant={host.matches("button,.primary-button,.secondary-button") ? "control" : host.matches(".badge,.chip,.task-line > span") ? "compact" : "panel"} />, mount, key));
}
