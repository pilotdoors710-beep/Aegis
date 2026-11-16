"use client";

import { useEffect, useRef, useState } from "react";
import {
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type Simulation,
  type SimulationNodeDatum,
} from "d3-force";
import type { Schema } from "@/lib/api";
import styles from "./sybil.module.css";

type GraphView = Schema["SybilGraphView"];
export interface SelectedEdge {
  source: string;
  target: string;
  provenance: string;
}
type Kind = "observed" | "simulated" | "anchor" | "shop";
type Node = SimulationNodeDatum & { id: string; label: string; kind: Kind };
type Link = { source: Node; target: Node; kind: "observed" | "simulated" | "rec" };

const COLORS = { attack: "#d97745", bridge: "#38bdf8", shopA: "#10b981", shopAFill: "#064e3b", shopB: "#ef4444", shopBFill: "#4a2414" };

// A bridge is a simulated link from a real site (cooperating or taken over, anchors included)
// into the attack. Free links from fake sites out to real ones are not bridges.
const isBridge = (l: Link) => l.kind === "simulated" && l.source.kind !== "simulated" && l.target.kind === "simulated";

// Link layers in draw order; a null colour means the theme foreground.
const LINK_STYLES: { match: (l: Link) => boolean; dash: number[]; color: string | null; alpha: number; width: number }[] = [
  { match: (l) => l.kind === "observed", dash: [], color: null, alpha: 0.14, width: 1 },
  { match: (l) => l.kind === "simulated" && !isBridge(l), dash: [5, 4], color: COLORS.attack, alpha: 0.8, width: 1 },
  { match: isBridge, dash: [4, 3], color: COLORS.bridge, alpha: 1, width: 2 },
  { match: (l) => l.kind === "rec" && l.target.id === "shop:A", dash: [3, 3], color: COLORS.shopA, alpha: 0.9, width: 1.5 },
  { match: (l) => l.kind === "rec" && l.target.id === "shop:B", dash: [2, 4], color: COLORS.shopB, alpha: 0.9, width: 1.5 },
];
type View = { k: number; x: number; y: number };

const RADIUS: Record<Kind, number> = { observed: 3, simulated: 4.5, anchor: 7, shop: 14 };

function build(view: GraphView) {
  const xs = view.nodes.map((n) => n.x);
  const ys = view.nodes.map((n) => n.y);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  // Start near the centre at the server layout's shape, so the springs visibly unfold it.
  const nodes: Node[] = view.nodes.map((n) => ({
    id: n.id,
    label: n.label,
    kind: n.anchor ? "anchor" : n.provenance === "simulated" ? "simulated" : "observed",
    x: ((n.x - x0) / (x1 - x0 || 1) - 0.5) * 60,
    y: ((n.y - y0) / (y1 - y0 || 1) - 0.5) * 40,
  }));
  for (const shop of ["A", "B"] as const)
    nodes.push({ id: `shop:${shop}`, label: `Shop ${shop}`, kind: "shop", x: 40, y: shop === "A" ? -20 : 20 });
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const links: Link[] = [];
  for (const e of view.edges) {
    const source = byId.get(e.source);
    const target = byId.get(e.target);
    if (source && target)
      links.push({ source, target, kind: e.provenance === "simulated" ? "simulated" : "observed" });
  }
  for (const r of view.recommendations) {
    const source = byId.get(r.website);
    if (source) links.push({ source, target: byId.get(`shop:${r.shop}`)!, kind: "rec" });
  }
  return { nodes, links };
}

function segmentDistance(px: number, py: number, a: Node, b: Node) {
  const dx = b.x! - a.x!;
  const dy = b.y! - a.y!;
  const t = Math.max(0, Math.min(1, ((px - a.x!) * dx + (py - a.y!) * dy) / (dx * dx + dy * dy || 1)));
  return Math.hypot(px - (a.x! + t * dx), py - (a.y! + t * dy));
}

export function SybilGraph({
  view,
  selectedNodeId,
  selectedEdge,
  witnessCutEdges,
  witnessNodes,
  onSelectNode,
  onSelectEdge,
  onClearSelection,
}: {
  view: GraphView;
  selectedNodeId: string | null;
  selectedEdge: SelectedEdge | null;
  witnessCutEdges?: Array<{ source: string; target: string }>;
  witnessNodes?: readonly string[];
  onSelectNode: (id: string) => void;
  onSelectEdge: (edge: SelectedEdge) => void;
  onClearSelection: () => void;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const [settledView, setSettledView] = useState<GraphView | null>(null);
  const settled = settledView === view;
  // Mutable render state lives in a ref so physics frames never re-render React.
  const state = useRef({
    nodes: [] as Node[],
    links: [] as Link[],
    sim: null as Simulation<Node, undefined> | null,
    view: { k: 1, x: 0, y: 0 } as View,
    goal: { k: 1, x: 0, y: 0 } as View,
    selectedNodeId,
    selectedEdge,
    witnessCutEdges: witnessCutEdges ?? [],
    witnessNodes: new Set(witnessNodes ?? []),
    hover: null as Node | null,
    dirty: true,
    reduced: false,
    // Settled layout before any dragging, and an in-flight glide back to it.
    home: null as [number, number][] | null,
    tween: null as { from: [number, number][]; start: number } | null,
    reset: () => {},
    remember: () => {},
  });
  const callbacks = useRef({ onSelectNode, onSelectEdge, onClearSelection });

  useEffect(() => {
    callbacks.current = { onSelectNode, onSelectEdge, onClearSelection };
  }, [onSelectNode, onSelectEdge, onClearSelection]);

  useEffect(() => {
    Object.assign(state.current, {
      selectedNodeId,
      selectedEdge,
      witnessCutEdges: witnessCutEdges ?? [],
      witnessNodes: new Set(witnessNodes ?? []),
      dirty: true,
    });
  }, [selectedNodeId, selectedEdge, witnessCutEdges, witnessNodes]);

  // Physics: rebuilt whenever the server returns a new graph view.
  useEffect(() => {
    const s = state.current;
    s.reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const { nodes, links } = build(view);
    const sim = forceSimulation(nodes)
      .force(
        "link",
        forceLink<Node, Link>(links)
          .distance((l) => (l.kind === "rec" ? 90 : 28))
          .strength((l) => (l.kind === "rec" ? 0.05 : 0.25)),
      )
      .force("charge", forceManyBody<Node>().strength((n) => (n.kind === "shop" ? -400 : -18)).distanceMax(260))
      .force("collide", forceCollide<Node>((n) => RADIUS[n.kind] + 1))
      .force("x", forceX(0).strength(0.03))
      .force("y", forceY(0).strength(0.03))
      .alphaDecay(0.03)
      .on("tick", () => (s.dirty = true));
    const remember = () => {
      if (s.home) return;
      s.home = nodes.map((n) => [n.x!, n.y!]);
      setSettledView(view);
    };
    sim.on("end", remember);
    const reset = () => {
      if (!s.home) return;
      sim.stop();
      for (const n of nodes) {
        n.vx = 0;
        n.vy = 0;
      }
      s.tween = { from: nodes.map((n) => [n.x!, n.y!]), start: s.reduced ? -Infinity : performance.now() };
    };
    Object.assign(s, { nodes, links, sim, dirty: true, home: null, tween: null, reset, remember });
    let frame = 0;
    if (s.reduced) {
      sim.stop();
      sim.tick(300);
      frame = requestAnimationFrame(remember);
    }
    return () => {
      sim.stop();
      cancelAnimationFrame(frame);
    };
  }, [view]);

  // Canvas size, render loop, and pointer/zoom input.
  useEffect(() => {
    const s = state.current;
    const wrap = wrapRef.current!;
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext("2d")!;
    let width = 0;
    let height = 0;
    let frame = 0;

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      width = canvas.clientWidth;
      height = canvas.clientHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      s.dirty = true;
    };
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    resize();

    const colors = () => {
      const css = getComputedStyle(wrap);
      return { fg: css.getPropertyValue("--fg").trim() || "#eee", bg: css.getPropertyValue("--bg").trim() || "#111" };
    };
    let palette = colors();

    const draw = () => {
      const { k, x, y } = s.view;
      ctx.save();
      ctx.fillStyle = palette.bg;
      ctx.fillRect(0, 0, width, height);
      ctx.translate(width / 2 + x, height / 2 + y);
      ctx.scale(k, k);
      const lineScale = 1 / Math.max(k, 0.5);
      for (const style of LINK_STYLES) {
        ctx.beginPath();
        for (const l of s.links) {
          if (!style.match(l)) continue;
          ctx.moveTo(l.source.x!, l.source.y!);
          ctx.lineTo(l.target.x!, l.target.y!);
        }
        ctx.setLineDash(style.dash);
        ctx.strokeStyle = style.color ?? palette.fg;
        ctx.globalAlpha = style.alpha;
        ctx.lineWidth = style.width * lineScale;
        ctx.stroke();
      }
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;
      const sel = s.selectedEdge;
      if (sel) {
        const l = s.links.find((l) => l.source.id === sel.source && l.target.id === sel.target);
        if (l) {
          ctx.beginPath();
          ctx.moveTo(l.source.x!, l.source.y!);
          ctx.lineTo(l.target.x!, l.target.y!);
          ctx.strokeStyle = palette.fg;
          ctx.lineWidth = 3 * lineScale;
          ctx.stroke();
        }
      }
      if (s.witnessCutEdges && s.witnessCutEdges.length > 0) {
        ctx.beginPath();
        for (const cut of s.witnessCutEdges) {
          const l = s.links.find(
            (link) =>
              (link.source.id === cut.source && link.target.id === cut.target) ||
              (link.source.id === cut.target && link.target.id === cut.source)
          );
          if (l) {
            ctx.moveTo(l.source.x!, l.source.y!);
            ctx.lineTo(l.target.x!, l.target.y!);
          }
        }
        ctx.setLineDash([4, 3]);
        ctx.strokeStyle = "#f59e0b"; // amber min-cut highlight
        ctx.globalAlpha = 1.0;
        ctx.lineWidth = 3.5 * lineScale;
        ctx.stroke();
        ctx.setLineDash([]);
      }
      for (const n of s.nodes) {
        const r = RADIUS[n.kind];
        ctx.beginPath();
        if (n.kind === "anchor") {
          ctx.moveTo(n.x!, n.y! - r);
          ctx.lineTo(n.x! + r, n.y!);
          ctx.lineTo(n.x!, n.y! + r);
          ctx.lineTo(n.x! - r, n.y!);
          ctx.closePath();
          ctx.fillStyle = palette.bg;
          ctx.fill();
          ctx.strokeStyle = "#e8c59e";
          ctx.lineWidth = 2 * lineScale;
          ctx.stroke();
        } else if (n.kind === "shop") {
          const isShopA = n.id === "shop:A";
          ctx.roundRect(n.x! - r * 1.6, n.y! - r, r * 3.2, r * 2, 4);
          ctx.fillStyle = isShopA ? COLORS.shopAFill : COLORS.shopBFill;
          ctx.fill();
          ctx.strokeStyle = isShopA ? COLORS.shopA : COLORS.shopB;
          ctx.lineWidth = 1.5 * lineScale;
          ctx.stroke();
          ctx.fillStyle = palette.fg;
          ctx.font = "600 8px system-ui, sans-serif";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(n.label, n.x!, n.y!);
        } else {
          ctx.arc(n.x!, n.y!, r, 0, Math.PI * 2);
          ctx.fillStyle = n.kind === "simulated" ? "#d9541e" : palette.fg;
          ctx.globalAlpha = n.kind === "simulated" ? 1 : 0.55;
          ctx.fill();
          ctx.globalAlpha = 1;
        }
        if (s.witnessNodes.has(n.id)) {
          ctx.beginPath();
          ctx.arc(n.x!, n.y!, r + 3, 0, Math.PI * 2);
          ctx.strokeStyle = "#f59e0b"; // amber: a weak point (min-cut site)
          ctx.lineWidth = 2.5 * lineScale;
          ctx.stroke();
        }
        if (n.id === s.selectedNodeId || n === s.hover) {
          ctx.beginPath();
          ctx.arc(n.x!, n.y!, r + 4, 0, Math.PI * 2);
          ctx.strokeStyle = palette.fg;
          ctx.lineWidth = 2 * lineScale;
          ctx.stroke();
        }
      }
      // Label anchors and the hovered/selected node so the picture is readable without clicking.
      ctx.font = `${11 / k}px system-ui, sans-serif`;
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      ctx.fillStyle = palette.fg;
      for (const n of s.nodes)
        if (n.kind === "anchor" || n === s.hover || n.id === s.selectedNodeId)
          ctx.fillText(n.label, n.x! + RADIUS[n.kind] + 5, n.y!);
      ctx.restore();
    };

    const loop = () => {
      const ease = s.reduced ? 1 : 0.18;
      const v = s.view;
      const g = s.goal;
      if (Math.abs(v.k - g.k) > 1e-4 || Math.abs(v.x - g.x) > 0.1 || Math.abs(v.y - g.y) > 0.1) {
        v.k += (g.k - v.k) * ease;
        v.x += (g.x - v.x) * ease;
        v.y += (g.y - v.y) * ease;
        s.dirty = true;
      }
      if (s.tween && s.home) {
        const t = Math.min(1, (performance.now() - s.tween.start) / 700);
        // easeOutBack: a small springy overshoot before landing.
        const e = 1 + 2.2 * (t - 1) ** 3 + 1.2 * (t - 1) ** 2;
        s.nodes.forEach((n, i) => {
          const [fx, fy] = s.tween!.from[i];
          const [hx, hy] = s.home![i];
          n.x = fx + (hx - fx) * e;
          n.y = fy + (hy - fy) * e;
        });
        if (t === 1) s.tween = null;
        s.dirty = true;
      }
      if (s.dirty) {
        s.dirty = false;
        draw();
      }
      frame = requestAnimationFrame(loop);
    };
    frame = requestAnimationFrame(loop);

    const toWorld = (clientX: number, clientY: number) => {
      const rect = canvas.getBoundingClientRect();
      const { k, x, y } = s.view;
      return [(clientX - rect.left - width / 2 - x) / k, (clientY - rect.top - height / 2 - y) / k];
    };
    const nodeAt = (wx: number, wy: number) =>
      s.sim?.find(wx, wy, 10 / s.view.k) ?? null;

    let drag: { node: Node | null; startX: number; startY: number; moved: boolean } | null = null;
    const down = (e: PointerEvent) => {
      const [wx, wy] = toWorld(e.clientX, e.clientY);
      const node = nodeAt(wx, wy);
      drag = { node, startX: e.clientX, startY: e.clientY, moved: false };
      canvas.setPointerCapture(e.pointerId);
      if (node) {
        s.remember(); // "original" = before the first drag, even if still settling
        node.fx = node.x;
        node.fy = node.y;
        if (!s.reduced) s.sim?.alphaTarget(0.3).restart();
      }
    };
    const move = (e: PointerEvent) => {
      if (!drag) {
        const [wx, wy] = toWorld(e.clientX, e.clientY);
        const hover = nodeAt(wx, wy);
        if (hover !== s.hover) {
          s.hover = hover;
          canvas.style.cursor = hover ? "pointer" : "grab";
          s.dirty = true;
        }
        return;
      }
      if (Math.hypot(e.clientX - drag.startX, e.clientY - drag.startY) > 4) drag.moved = true;
      if (drag.node) {
        const [wx, wy] = toWorld(e.clientX, e.clientY);
        drag.node.fx = wx;
        drag.node.fy = wy;
        if (s.reduced) {
          drag.node.x = wx;
          drag.node.y = wy;
        }
        s.dirty = true;
      } else if (drag.moved) {
        s.view.x += e.movementX;
        s.view.y += e.movementY;
        s.goal = { ...s.view };
        canvas.style.cursor = "grabbing";
        s.dirty = true;
      }
    };
    const up = (e: PointerEvent) => {
      if (!drag) return;
      const { node, moved } = drag;
      drag = null;
      canvas.style.cursor = "grab";
      if (node) {
        node.fx = null;
        node.fy = null;
        s.sim?.alphaTarget(0);
      }
      if (moved) return;
      if (node) {
        if (node.kind !== "shop") callbacks.current.onSelectNode(node.id);
        return;
      }
      const [wx, wy] = toWorld(e.clientX, e.clientY);
      const tolerance = 5 / s.view.k;
      let best: Link | null = null;
      let bestDistance = tolerance;
      for (const l of s.links) {
        if (l.kind === "rec") continue;
        const d = segmentDistance(wx, wy, l.source, l.target);
        if (d < bestDistance) [best, bestDistance] = [l, d];
      }
      if (best)
        callbacks.current.onSelectEdge({
          source: best.source.id,
          target: best.target.id,
          provenance: best.kind,
        });
      else callbacks.current.onClearSelection();
    };
    const wheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left - width / 2;
      const my = e.clientY - rect.top - height / 2;
      const g = s.goal;
      const k = Math.min(12, Math.max(0.2, g.k * Math.exp(-e.deltaY * 0.0015)));
      // Keep the point under the cursor fixed while zooming.
      s.goal = { k, x: mx - ((mx - g.x) * k) / g.k, y: my - ((my - g.y) * k) / g.k };
    };
    const theme = () => {
      palette = colors();
      s.dirty = true;
    };
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", theme);
    canvas.addEventListener("pointerdown", down);
    canvas.addEventListener("pointermove", move);
    canvas.addEventListener("pointerup", up);
    canvas.addEventListener("wheel", wheel, { passive: false });
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      media.removeEventListener("change", theme);
      canvas.removeEventListener("pointerdown", down);
      canvas.removeEventListener("pointermove", move);
      canvas.removeEventListener("pointerup", up);
      canvas.removeEventListener("wheel", wheel);
    };
  }, []);


  const zoom = (factor: number) => {
    const g = state.current.goal;
    state.current.goal = { k: Math.min(12, Math.max(0.2, g.k * factor)), x: g.x * factor, y: g.y * factor };
  };
  const fit = (points = state.current.nodes.map((n): [number, number] => [n.x!, n.y!])) => {
    const canvas = canvasRef.current;
    if (!canvas || !points.length) return;
    const xs = points.map((p) => p[0]);
    const ys = points.map((p) => p[1]);
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const k = Math.min(12, 0.9 * Math.min(canvas.clientWidth / (x1 - x0 || 1), canvas.clientHeight / (y1 - y0 || 1)));
    state.current.goal = { k, x: (-(x0 + x1) / 2) * k, y: (-(y0 + y1) / 2) * k };
  };

  const reset = () => {
    state.current.reset();
    if (state.current.home) fit(state.current.home);
  };

  useEffect(() => {
    const change = () => {
      setFullscreen(document.fullscreenElement === wrapRef.current);
      window.setTimeout(() => fit(), 150); // after the canvas has resized
    };
    document.addEventListener("fullscreenchange", change);
    return () => document.removeEventListener("fullscreenchange", change);
  }, []);

  // Fit once the layout has mostly settled after a new view.
  useEffect(() => {
    const timer = window.setTimeout(() => fit(), state.current.reduced ? 0 : 1800);
    return () => window.clearTimeout(timer);
  }, [view]);

  return (
    <div ref={wrapRef} className={styles.graphWrap} data-fullscreen={fullscreen || undefined}>
      <canvas
        id="sybil-graph"
        ref={canvasRef}
        className={styles.graph}
        role="img"
        aria-label={`Graph subset with ${view.displayed_nodes} websites and ${view.displayed_edges} links. Scroll to zoom, drag to pan or move a website.`}
      />
      <div className={styles.graphTools}>
        <button type="button" className="secondary-button" onClick={() => zoom(1.4)} aria-label="Zoom in">
          +
        </button>
        <button type="button" className="secondary-button" onClick={() => zoom(1 / 1.4)} aria-label="Zoom out">
          −
        </button>
        <button type="button" className="secondary-button" onClick={() => fit()}>
          Fit
        </button>
        <button
          type="button"
          className="secondary-button"
          onClick={reset}
          disabled={!settled}
          title={settled ? "Move every website back to its settled position" : "Layout still settling"}
        >
          Reset layout
        </button>
        <button
          type="button"
          className="secondary-button"
          onClick={() =>
            fullscreen ? void document.exitFullscreen() : void wrapRef.current?.requestFullscreen()
          }
        >
          {fullscreen ? "Exit full screen" : "Full screen"}
        </button>
      </div>
      <p className={styles.graphLegend}>
        ◇ trusted site · ● real website · <span>●</span> fake site · <span style={{ color: COLORS.bridge }}>---</span> paid link from a real site · <span style={{ color: "#f59e0b" }}>○ ---</span> weak point and the links into it · <span style={{ color: COLORS.shopA }}>Shop A</span> · <span style={{ color: COLORS.shopB }}>Shop B</span> · scroll to zoom, drag to pan
      </p>
    </div>
  );
}
