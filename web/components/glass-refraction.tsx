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
// Every measurement runs before any style/canvas write in the frame.
const placements = new Set<() => (() => void) | undefined>();
let frame = 0;
function schedule() {
  if (frame || document.hidden || !placements.size) return;
  frame = requestAnimationFrame(() => {
    frame = 0;
    const writes = Array.from(placements, measure => measure());
    writes.forEach(write => write?.());
  });
}
function visibilityChanged() {
  if (document.hidden) { cancelAnimationFrame(frame); frame = 0; }
  else schedule();
}
function follow(place: () => (() => void) | undefined) {
  if (!placements.size) {
    window.addEventListener("scroll", schedule, true);
    window.addEventListener("resize", schedule);
    document.addEventListener("toggle", schedule, true);
    document.addEventListener("visibilitychange", visibilityChanged);
  }
  placements.add(place);
  return () => {
    placements.delete(place);
    if (placements.size) return;
    window.removeEventListener("scroll", schedule, true);
    window.removeEventListener("resize", schedule);
    document.removeEventListener("toggle", schedule, true);
    document.removeEventListener("visibilitychange", visibilityChanged);
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
    let dirty = true;
    const configure = () => {
      if (preference.matches) { stop?.(); stop = undefined; return; }
      if (!visible || stop) { if (visible) schedule(); return; }
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
      let geometry = "";
      const paint = () => {
        copy.style.display = source && context ? "block" : "none";
        copy.dataset.preblurred = source?.dataset.preblurred ?? "false";
        if (!source || !context) return;
        context.fillStyle = "#001219"; context.fillRect(0, 0, copy.width, copy.height);
      };
      const place = () => {
        if (!visible || document.hidden) return;
        const rect = surface.getBoundingClientRect();
        // Overscan supplies pixels for the full-dome displacement near the edges.
        const padding = 40;
        const left = rect.left - padding, top = rect.top - padding;
        const width = Math.max(1, Math.ceil(rect.width + padding * 2));
        const height = Math.max(1, Math.ceil(rect.height + padding * 2));
        const viewportWidth = innerWidth, viewportHeight = innerHeight;
        const next = `${left},${top},${width},${height},${viewportWidth},${viewportHeight}`;
        if (!dirty && next === geometry) return;
        return () => {
          dirty = false; geometry = next;
          if (copy.width !== width) copy.width = width;
          if (copy.height !== height) copy.height = height;
          Object.assign(scene.style, {
            left: `${-padding}px`, top: `${-padding}px`, width: `${width}px`, height: `${height}px`,
            backgroundSize: `${viewportWidth}px ${viewportHeight}px`, backgroundPosition: `${-left}px ${-top}px`,
          });
          paint();
          if (source && context) {
            const margin = Number(source.dataset.scenePadding ?? 0);
            context.drawImage(source, -left - margin, -top - margin, viewportWidth + margin * 2, viewportHeight + margin * 2);
          }
        };
      };
      dirty = true;
      try {
        const glass = createGlass(surface, {
          fit: true, clip: true, radius: parseFloat(getComputedStyle(host).borderTopLeftRadius) || 12,
          ...optics[variant], chroma: .12, mapScale: innerWidth < 600 ? .75 : 1,
        });
        layer.dataset.refraction = "active";
        const unfollowScene = followDitheringScene(canvas => { source = canvas; dirty = true; schedule(); });
        const unfollow = follow(place);
        schedule();
        const resize = new ResizeObserver(schedule); resize.observe(host);
        stop = () => {
          unfollowScene(); unfollow(); resize.disconnect();
          glass.destroy(); scene.remove(); delete layer.dataset.refraction;
        };
      } catch { scene.remove(); }
    };
    const observer = new IntersectionObserver(entries => {
      const next = entries[0].isIntersecting;
      if (visible === next) return;
      visible = next;
      // Keep the lens/map allocation, but exclude off-screen filters from paint.
      layer.style.visibility = visible ? "" : "hidden";
      configure();
    });
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
    const additions = new Set<Element>([root]);
    const collect = () => {
      pending = 0;
      let changed = false;
      const add = (element: HTMLElement) => {
        if (!root.contains(element)) return;
        let entry = mounts.get(element);
        if (!entry || entry.mount.parentElement !== element) {
          const mount = document.createElement(element.tagName === "OL" ? "li" : "span");
          mount.dataset.glassMount = "";
          mount.setAttribute("aria-hidden", "true");
          element.append(mount);
          entry = { mount, key: String(sequence++) };
          mounts.set(element, entry);
          changed = true;
        }
      };
      for (const node of additions) {
        if (node instanceof HTMLElement && node.matches(targets)) add(node);
        node.querySelectorAll<HTMLElement>(targets).forEach(add);
      }
      additions.clear();
      for (const [element, { mount }] of mounts) {
        if (!root.contains(element)) { mount.remove(); mounts.delete(element); changed = true; }
        else if (mount.parentElement !== element) add(element);
      }
      if (changed) setHosts(Array.from(mounts, ([element, entry]) => ({ element, ...entry })));
      schedule();
    };
    const observer = new MutationObserver(records => {
      let structural = false;
      for (const record of records) {
        const target = record.target instanceof Element ? record.target : record.target.parentElement;
        if (!target || target.closest("[data-glass-mount]")) continue;
        if (record.type === "attributes") {
          // Animated decorative spans cannot move a glass host. Ignore their
          // per-frame gradients/opacity instead of measuring the whole page.
          if (target.matches(targets) || target.querySelector(targets)) schedule();
          continue;
        }
        const nodes = [...record.addedNodes, ...record.removedNodes];
        if (nodes.every(node => node instanceof Element && node.hasAttribute("data-glass-mount"))) continue;
        structural = true;
        record.addedNodes.forEach(node => { if (node instanceof Element) additions.add(node); });
      }
      if (structural && !pending) pending = requestAnimationFrame(collect);
    });
    observer.observe(root, { childList: true, subtree: true, attributes: true, attributeFilter: ["style", "data-open"] });
    collect();
    return () => { observer.disconnect(); cancelAnimationFrame(pending); mounts.forEach(({ mount }) => mount.remove()); };
  }, []);
  return hosts.map(({ element: host, mount, key }) => createPortal(<GlassRefraction variant={host.matches("button,.primary-button,.secondary-button") ? "control" : host.matches(".badge,.chip,.task-line > span") ? "compact" : "panel"} />, mount, key));
}
