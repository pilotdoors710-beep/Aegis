"use client";

// Math Scramble by Louis Studios.
// 200 more hand-made React components at https://studios.lou15.com/?ref=21st-code

import * as React from "react";

/* Math Scramble. Louis Studios.
 * Centred lines of quiet grey words. A pointer passing over a word sends a wave
 * along its line: letters flip into coloured mathematical symbols, some in thin
 * rounded boxes, hold for a breath, then settle back to the word in the order
 * they flipped. The highlighted words never scramble. Canvas 2D, no assets. */

export interface MathScrambleProps {
  /** The lines of text, top to bottom, each centred. Lines that grow by two characters each (the default runs 13 to 25) give the clean triangle. English words read best; any characters work. */
  lines?: string[];
  /** Words or phrases drawn in the highlight colour and highlight font (default "louis studios"). They are never scrambled. Matched case-insensitively inside the lines. */
  highlight?: string[];
  /** The palette the scrambled symbols are painted in. Each flipped character picks one, with short runs of the same colour. */
  colors?: string[];
  /** Colour of the resting text. */
  color?: string;
  /** Colour of the highlighted words. */
  highlightColor?: string;
  /** Background colour painted behind the text. Use "transparent" to let the page show through. */
  background?: string;
  /** Font stack for the text and the symbols. A monospace stack keeps the even rhythm; symbols the font lacks come from the system fallback. */
  font?: string;
  /** Font stack for the highlighted words. */
  highlightFont?: string;
  /** Font size in CSS pixels. 0 uses the reference size, one character at 3.07% of the container's smaller side, shrinking only when the container cannot hold the block. */
  fontSize?: number;
  /** When true, an invisible pointer drifts through the block on a loop so the effect plays by itself (paused while a real pointer is over it). */
  autoplay?: boolean;
  /** Draw a small arrow cursor for the autoplay pointer, useful for previews and demo videos. */
  cursor?: boolean;
  /** How close the pointer must come to a word to set it off, in character widths around each word. */
  radius?: number;
  /** Playback speed multiplier for the waves, the hold and the autoplay drift. 1 is the reference pace. */
  speed?: number;
  /** Share of flipped characters drawn inside a thin rounded box, 0 to 1. */
  boxed?: number;
  /** Seconds. When set, the autoplay timeline is frozen at this moment and the pointer is ignored, for video renders and screenshots. */
  time?: number;
  /** Class name on the root element. */
  className?: string;
  /** Inline styles on the root element. */
  style?: React.CSSProperties;
}

const DEFAULT_LINES = [
  "motion design",
  "buttons loaders",
  "cards and shaders",
  "at louis studios hq",
  "every piece hand made",
  "components for products",
  "one file each no packages",
];

const DEFAULT_COLORS = [
  "#ee2c4c",
  "#f25b23",
  "#ed951a",
  "#e9c84f",
  "#a0dc3f",
  "#36d668",
  "#3fd3a5",
  "#2fc8cb",
  "#29b0e3",
  "#3c74f1",
  "#6450f1",
  "#8f3bf7",
  "#ca20ed",
  "#e12988",
];

const MONO_STACK =
  '"SF Mono", SFMono-Regular, ui-monospace, Menlo, Consolas, "Cascadia Mono", "Roboto Mono", "Liberation Mono", "DejaVu Sans Mono", monospace';
const SANS_STACK =
  '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';

/* Scramble symbols: operators, arrows, Greek, double-struck and script letters,
 * integrals and set symbols. Any symbol a device cannot draw is filtered out at
 * runtime (compared against known missing-glyph renders). */
const SYMBOLS =
  "+−×÷±∓=≠≈≃≡≤≥≪≫≺≻∝∞√∑∏∫∬∮∂∇∆∈∉∋⊂⊃⊆⊇⊐∪∩∅∀∃∄¬∧∨⊕⊗⊥∥∠∴∵⊢⊨∘⋅∗⌈⌋⟨⟩′″≀⊔ℵ" +
  "←→↑↓↔↕↖↗↘↙⇒⇐⇔⇑⇓↦↣⇄⇌" +
  "αβγδεζηθϑκλμξπρστφψωΓΔΘΛΞΠΣΦΨΩ" +
  "ℂℍℕℙℚℝℤℓ℘ℰℱℋℐℒℳℛℬℯℊℴℏħ" +
  "𝔸𝔹𝔻𝔼𝔽𝔾𝕀𝕁𝕂𝕃𝕄𝕆𝕊𝕋𝕌𝕍𝕎𝕏𝕐𝒜𝒞𝒟𝒢𝒥𝒦𝒩𝒪𝒫𝒬𝒮𝒯𝒰𝒱𝒲𝒳𝒴𝒵" +
  "(){}[]|";
const LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
const DIGITS = "0123456789";

/* The autoplay pointer: one loop of a hand-drawn path through the block.
 * Pairs of x,y in hundredths; x in half the widest line, y in line pitches
 * from the middle line. One sample per 1/30 s. */
const PATH_SRC =
  "-46,-326 -51,-264 -57,-197 -65,-98 -70,-3 -71,105 -71,197 -69,278 -67,345 -60,441 -53,510 -45,584 -39,632 -36,655 -33,672 -30,687 " +
  "-26,701 -20,713 -15,719 -7,722 3,723 8,708 14,660 19,609 22,584 24,561 24,527 21,487 18,465 14,439 4,390 -7,346 " +
  "-16,304 -27,236 -37,158 -44,56 -47,-41 -47,-102 -46,-161 -42,-240 -38,-304 -33,-365 -28,-418 -24,-453 -20,-487 -15,-524 -12,-548 -7,-576 " +
  "-1,-604 4,-627 9,-648 13,-662 17,-669 20,-677 21,-679 21,-681 21,-681 21,-681 21,-681 21,-681 21,-681 21,-681 21,-681 21,-681 " +
  "21,-681 21,-682 22,-686 23,-690 24,-693 26,-700 28,-704 28,-704 28,-704 28,-704 28,-704 28,-704 27,-701 26,-696 24,-683 20,-651 " +
  "16,-579 15,-501 16,-400 17,-291 16,-180 12,-69 4,61 -4,142 -12,202 -19,253 -27,312 -33,365 -37,437 -37,497 -37,558 -35,603 " +
  "-33,636 -32,658 -29,679 -26,690 -24,696 -20,704 -15,710 -6,713 9,701 17,670 27,627 41,579 49,525 52,451 54,377 55,336 " +
  "55,305 50,248 36,181 21,129 6,89 -4,65 -18,18 -29,-27 -40,-56 -49,-88 -56,-124 -60,-147 -63,-171 -63,-198 -63,-241 -57,-289 " +
  "-48,-330 -38,-344 -29,-345 -21,-340 -15,-326 -9,-303 0,-267 7,-244 11,-225 15,-206 16,-183 15,-158 10,-125 2,-80 -7,-48 -16,-16 " +
  "-24,16 -33,49 -43,83 -48,105 -51,126 -54,148 -57,167 -58,188 -59,215 -60,234 -60,250 -59,266 -58,275 -55,285 -49,295 -44,296 " +
  "-39,289 -33,273 -27,262 -19,253 -10,236 -5,216 1,198 5,184 10,167 14,144 18,106 20,79 21,55 22,11 22,-36 22,-87 " +
  "22,-143 21,-193 17,-239 13,-272 8,-291 2,-313 -7,-345 -12,-365 -16,-374 -21,-382 -27,-391 -33,-398 -37,-401 -40,-401 -44,-390 -50,-368 " +
  "-55,-344 -58,-310 -59,-262 -57,-202 -52,-138 -48,-78 -45,-15 -45,32 -49,86 -55,128 -60,178 -63,221 -64,257 -59,284 -45,313 -29,327 " +
  "-14,331 -1,328 10,310 18,291 26,254 30,216 34,180 37,148 39,120 41,74 42,24 43,-8 43,-54 43,-109 43,-163 42,-207 " +
  "42,-275 42,-335 41,-386 40,-404 37,-414 33,-416 21,-416 9,-410 -3,-386 -18,-347 -27,-321 -36,-287 -46,-244 -51,-216 -55,-195 -59,-167 " +
  "-63,-132 -66,-107 -70,-78 -74,-51 -77,-28 -79,-3 -82,26 -85,61 -89,100 -90,129 -91,163 -91,204 -89,249 -89,303 -89,359 -90,393 " +
  "-91,428 -91,451 -91,467 -91,481 -90,497 -87,508 -82,524 -76,540 -69,549 -61,556 -51,564 -42,567 -33,567 -25,563 -16,556 -8,553 " +
  "-1,553 4,553 8,562 11,573 11,573 11,573 11,573 11,573 11,573 11,573 11,573 11,573 11,573 11,573 15,568 28,554 " +
  "41,522 54,479 63,437 70,390 73,345";

const PATH: number[] = PATH_SRC.split(" ").flatMap((p) => p.split(",").map((v) => Number(v) / 100));
const PATH_FPS = 30;
const LOOP = 10.3; // seconds of one autoplay loop; the path ends at 9.77 s and rests off the block
const STEP = 1 / 33; // mean seconds for the wave to move one character
const HOLD = 0.5; // shortest hold of a flipped character, seconds
const HOLD_JITTER = 0.17;
const FADE_IN = 0.14;
const FADE_OUT = 0.09;
const LATENCY = 1 / 30;
const PITCH = 1.98; // line pitch in character widths
const REF_CELL = 0.0307; // character width as a share of the frame, measured on the reference
const STRETCH = 1.0; // glyphs drawn a touch wider than the font, for the reference's round, even rhythm
const WEIGHT = 500;
const SPACE = 0.54; // a word space is narrower than a letter, like the reference

/* ---------- small helpers ---------- */

function mulberry(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function pathAt(s: number): [number, number] {
  const n = PATH.length / 2;
  const f = Math.max(0, Math.min(n - 1, s * PATH_FPS));
  const i = Math.floor(f);
  const j = Math.min(n - 1, i + 1);
  const k = f - i;
  return [PATH[i * 2] + (PATH[j * 2] - PATH[i * 2]) * k, PATH[i * 2 + 1] + (PATH[j * 2 + 1] - PATH[i * 2 + 1]) * k];
}

type RGB = [number, number, number, number];
const colorCache = new Map<string, RGB>();
function parseColor(c: string): RGB {
  const hit = colorCache.get(c);
  if (hit) return hit;
  let out: RGB = [128, 128, 128, 1];
  try {
    const cv = document.createElement("canvas");
    cv.width = cv.height = 1;
    const x = cv.getContext("2d", { willReadFrequently: true });
    if (x) {
      x.clearRect(0, 0, 1, 1);
      x.fillStyle = "#000"; // ls:keep
      x.fillStyle = c;
      x.fillRect(0, 0, 1, 1);
      const d = x.getImageData(0, 0, 1, 1).data;
      out = d[3] > 0 ? [Math.round(d[0] / (d[3] / 255)), Math.round(d[1] / (d[3] / 255)), Math.round(d[2] / (d[3] / 255)), d[3] / 255] : [0, 0, 0, 0];
    }
  } catch {
    /* keep the fallback */
  }
  colorCache.set(c, out);
  return out;
}

function mix(a: RGB, b: RGB, t: number) {
  const r = Math.round(a[0] + (b[0] - a[0]) * t);
  const g = Math.round(a[1] + (b[1] - a[1]) * t);
  const bl = Math.round(a[2] + (b[2] - a[2]) * t);
  const al = a[3] + (b[3] - a[3]) * t;
  return `rgba(${r},${g},${bl},${al.toFixed(3)})`;
}

/* Drop symbols the device draws as a missing-glyph box, as nothing, or as colour emoji. */
const symbolCache = new Map<string, string[]>();
function usableSymbols(family: string): string[] {
  const hit = symbolCache.get(family);
  if (hit) return hit;
  const all = Array.from(SYMBOLS);
  let ok = all;
  try {
    const S = 40;
    const cv = document.createElement("canvas");
    cv.width = cv.height = S;
    const x = cv.getContext("2d", { willReadFrequently: true });
    if (x) {
      x.font = `28px ${family}`;
      x.textAlign = "center";
      x.textBaseline = "middle";
      const sig = (ch: string) => {
        x.clearRect(0, 0, S, S);
        x.fillStyle = "#000"; // ls:keep
        x.fillText(ch, S / 2, S / 2);
        const d = x.getImageData(0, 0, S, S).data;
        let h = 0;
        let ink = 0;
        let tint = false;
        for (let i = 0; i < d.length; i += 4) {
          const a = d[i + 3];
          if (a) {
            ink++;
            h = (Math.imul(h, 31) + a * (i + 1)) | 0;
            if (d[i] > 24 || d[i + 1] > 24 || d[i + 2] > 24) tint = true;
          }
        }
        return { h: `${h}:${ink}`, ink, tint };
      };
      const missing = new Set(["", "", "\u{1D455}", ""].map((c) => sig(c).h));
      ok = all.filter((ch) => {
        const s = sig(ch);
        return s.ink > 6 && !s.tint && !missing.has(s.h);
      });
      if (ok.length < 20) ok = all.filter((ch) => ch.length === 1);
    }
  } catch {
    ok = all;
  }
  symbolCache.set(family, ok);
  return ok;
}

/* ---------- layout ---------- */

interface Cell {
  ch: string;
  pos: number; // position along the line in character widths
  x: number; // centre x in CSS px
  space: boolean;
  word: number; // word index on the line, -1 for spaces
}
interface Hl {
  text: string;
  offs: number[]; // left offset of each character in character widths
  x: number; // left x in CSS px
  pos: number; // centre position in character widths
}
interface Line {
  cells: Cell[];
  hl: Hl[];
  y: number; // baseline in CSS px
  mid: number; // vertical centre of the lowercase letters
  words: { line: number; first: number; last: number; x0: number; x1: number }[];
}
interface Layout {
  w: number;
  h: number;
  adv: number;
  size: number;
  hlSize: number;
  pitch: number;
  half: number; // half width of the widest line, px
  halves: number[]; // half width of each line, px
  cx: number;
  cy: number; // centre of the middle line
  lines: Line[];
}

function findHighlights(line: string, hl: string[]) {
  const marks: [number, number][] = [];
  const low = line.toLowerCase();
  for (const raw of hl) {
    const h = raw.trim().toLowerCase();
    if (!h) continue;
    let from = 0;
    for (;;) {
      const i = low.indexOf(h, from);
      if (i < 0) break;
      if (!marks.some(([a, b]) => i < b && i + h.length > a)) marks.push([i, i + h.length]);
      from = i + h.length;
    }
  }
  return marks.sort((a, b) => a[0] - b[0]);
}

function buildLayout(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  lines: string[],
  hl: string[],
  font: string,
  hlFont: string,
  fontSize: number,
): Layout {
  ctx.font = `400 100px ${font}`;
  const adv100 = ctx.measureText("0").width || 60;
  const xh = (f: string) => {
    ctx.font = f;
    const m = ctx.measureText("x");
    return m.actualBoundingBoxAscent > 1 ? m.actualBoundingBoxAscent : 53;
  };
  const xhM = xh(`${WEIGHT} 100px ${font}`);
  const xhH = xh(`500 100px ${hlFont}`);
  // draw the letters so their x-height is 0.96 of a character width, like the reference
  const sizeK = Math.max(0.92, Math.min(1.1, (0.96 * adv100) / xhM));
  const hlK = xhM / xhH; // highlight font sized to share the x-height
  // rows of tokens in units of character widths
  type Tok = { kind: "c"; ch: string } | { kind: "h"; text: string; units100: number; offs: number[] };
  const rows: Tok[][] = lines.map((line) => {
    const marks = findHighlights(line, hl);
    const toks: Tok[] = [];
    let i = 0;
    for (const [a, b] of marks) {
      for (; i < a; i++) toks.push({ kind: "c", ch: line[i] });
      const text = line.slice(a, b);
      ctx.font = `500 100px ${hlFont}`;
      // the highlight is tracked out a little so it holds about as much room as the letters it
      // stands among (the reference's white word takes 0.97 of a cell per letter), keeping the triangle
      const u = (sizeK * hlK) / adv100; // units per px at 100px
      const chars = Array.from(text);
      const natural = ctx.measureText(text).width * u;
      const em = 100 * u;
      const track = chars.length > 1 ? Math.max(0, Math.min(0.09 * em, (chars.length * 0.92 - natural) / (chars.length - 1))) : 0;
      const offs: number[] = [];
      let pre = "";
      chars.forEach((ch, k) => {
        offs.push(ctx.measureText(pre).width * u + k * track);
        pre += ch;
      });
      toks.push({ kind: "h", text, units100: natural + track * (chars.length - 1), offs });
      i = b;
    }
    for (; i < line.length; i++) toks.push({ kind: "c", ch: line[i] });
    return toks;
  });
  // a space beside a highlight is drawn narrower, the sans word carries less side bearing
  const tokUnits = (row: Tok[], k: number) => {
    const t = row[k];
    if (t.kind === "h") return t.units100;
    if (/\s/.test(t.ch)) {
      const nearHl = (row[k - 1] && row[k - 1].kind === "h") || (row[k + 1] && row[k + 1].kind === "h");
      return nearHl ? SPACE + 0.12 : SPACE;
    }
    return 1;
  };
  const rowUnits = rows.map((r) => r.reduce((s, _t, k) => s + tokUnits(r, k), 0));
  const maxUnits = Math.max(1, ...rowUnits);
  const n = Math.max(1, rows.length);
  let adv: number;
  if (fontSize > 0) adv = (fontSize * adv100) / 100 / sizeK;
  else {
    // the reference size: one character is 3.07% of the frame (the smaller side);
    // shrink only when the container cannot hold the widest line or the block
    adv = Math.min(Math.min(w, h) * REF_CELL, (w * 0.94) / maxUnits, (h * 0.92) / (n * PITCH));
  }
  adv = Math.max(adv, 6.6);
  const size = (adv / adv100) * 100 * sizeK;
  const hlSize = size * hlK;
  const pitch = adv * PITCH;
  const cx = w / 2;
  const cy = h / 2;
  const out: Line[] = rows.map((row, li) => {
    const units = rowUnits[li];
    const left = cx - (units * adv) / 2;
    const mid = cy + (li - (n - 1) / 2) * pitch;
    const y = mid + adv * 0.47;
    const cells: Cell[] = [];
    const hls: Hl[] = [];
    const words: Line["words"] = [];
    let u = 0;
    let word = -1;
    let inWord = false;
    row.forEach((t, k) => {
      const tu = tokUnits(row, k);
      if (t.kind === "h") {
        hls.push({ text: t.text, offs: t.offs, x: left + u * adv, pos: u + tu / 2 });
        inWord = false;
      } else {
        const space = /\s/.test(t.ch);
        if (!space && !inWord) {
          word++;
          words.push({ line: li, first: cells.length, last: cells.length, x0: 0, x1: 0 });
        }
        inWord = !space;
        cells.push({ ch: t.ch, pos: u + tu / 2, x: left + (u + tu / 2) * adv, space, word: space ? -1 : word });
        if (!space) words[word].last = cells.length - 1;
      }
      u += tu;
    });
    for (const wd of words) {
      wd.x0 = cells[wd.first].x - adv / 2;
      wd.x1 = cells[wd.last].x + adv / 2;
    }
    return { cells, hl: hls, y, mid, words };
  });
  return { w, h, adv, size, hlSize, pitch, half: (maxUnits * adv) / 2, halves: rowUnits.map((u) => (u * adv) / 2), cx, cy, lines: out };
}

/* ---------- waves ---------- */

interface Trigger {
  t0: number;
  act: Float32Array; // activation time per cell
  hold: Float32Array; // hold per cell
  glyph: string[];
  col: Int16Array;
  bold: Uint8Array;
  italic: Uint8Array;
  box: Uint8Array;
}

function makeTrigger(
  line: Line,
  origin: number,
  t0: number,
  seed: number,
  nColors: number,
  symbols: string[],
  boxed: number,
): Trigger {
  const rnd = mulberry(seed * 2654435761 + 97);
  const n = line.cells.length;
  const act = new Float32Array(n);
  const hold = new Float32Array(n);
  const glyph: string[] = new Array(n);
  const col = new Int16Array(n);
  const bold = new Uint8Array(n);
  const italic = new Uint8Array(n);
  const box = new Uint8Array(n);
  const jit = () => 0.42 + 1.18 * Math.pow(rnd(), 1.6);
  act[origin] = t0 + LATENCY;
  for (let j = origin + 1; j < n; j++) act[j] = act[j - 1] + (line.cells[j].pos - line.cells[j - 1].pos) * STEP * jit();
  for (let j = origin - 1; j >= 0; j--) act[j] = act[j + 1] + (line.cells[j + 1].pos - line.cells[j].pos) * STEP * jit();
  let prev = Math.floor(rnd() * nColors);
  for (let j = 0; j < n; j++) {
    hold[j] = HOLD + HOLD_JITTER * rnd();
    const c = line.cells[j];
    const r = rnd();
    let g = c.ch;
    let b = 0;
    let it = 0;
    if (r < 0.45 && /[A-Za-z0-9]/.test(c.ch)) {
      const s = rnd();
      if (s < 0.1) b = 1;
      else if (s < 0.25) it = 1;
    } else if (r < 0.57) {
      g = LETTERS[Math.floor(rnd() * LETTERS.length)];
      it = rnd() < 0.5 ? 1 : 0;
      b = !it && rnd() < 0.2 ? 1 : 0;
    } else if (r < 0.62) {
      g = DIGITS[Math.floor(rnd() * DIGITS.length)];
      b = rnd() < 0.7 ? 1 : 0;
    } else {
      g = symbols[Math.floor(rnd() * symbols.length)] || c.ch;
    }
    glyph[j] = g;
    bold[j] = b;
    italic[j] = it;
    box[j] = rnd() < boxed ? 1 : 0;
    prev = rnd() < 0.5 ? prev : Math.floor(rnd() * nColors);
    col[j] = prev;
  }
  return { t0, act, hold, glyph, col, bold, italic, box };
}

/* Which word does a point touch? Returns [line, cellIndex] or null. */
function hitWord(L: Layout, px: number, py: number, radius: number): [number, number] | null {
  const pad = radius * L.adv;
  let best: [number, number] | null = null;
  let bestD = Infinity;
  for (let li = 0; li < L.lines.length; li++) {
    const ln = L.lines[li];
    if (Math.abs(py - ln.mid) > L.pitch * 0.44) continue;
    for (const wd of ln.words) {
      const d = px < wd.x0 ? wd.x0 - px : px > wd.x1 ? px - wd.x1 : 0;
      if (d <= pad && d < bestD) {
        bestD = d;
        let ci = wd.first;
        let cd = Infinity;
        for (let k = wd.first; k <= wd.last; k++) {
          const dd = Math.abs(ln.cells[k].x - px);
          if (dd < cd) {
            cd = dd;
            ci = k;
          }
        }
        best = [li, ci * 1000 + ln.cells[ci].word];
      }
    }
  }
  return best;
}

/* The scripted triggers of one autoplay loop for a layout. */
interface Scripted {
  t0: number;
  line: number;
  origin: number;
}
/* The path was drawn over a block whose lines widen evenly; warp its x so it
 * meets each of our lines at the same relative place. */
const PATH_HALVES = [8.54, 10.54, 12.54, 13.9, 16.54, 18.54, 20.54].map((u) => u / 20.54);
function pathPoint(L: Layout, s: number): [number, number] {
  const [nx, ny] = pathAt(s);
  const n = L.lines.length;
  const fr = (k: number, arr: number[]) => {
    const f = Math.max(0, Math.min(arr.length - 1, k));
    const i = Math.floor(f);
    const j = Math.min(arr.length - 1, i + 1);
    return arr[i] + (arr[j] - arr[i]) * (f - i);
  };
  // ny is in pitches from the middle of a seven-line block
  const refHalf = fr(ny + 3, PATH_HALVES);
  const ourHalf = n ? fr(ny + (n - 1) / 2, L.halves) / L.half : 1;
  const x = L.cx + nx * (ourHalf / refHalf) * L.half;
  const y = L.cy + ny * L.pitch * (n > 1 ? (n - 1) / 6 : 1);
  return [x, y];
}

function scriptFor(L: Layout, radius: number): Scripted[] {
  const out: Scripted[] = [];
  let cur = "";
  for (let s = 0; s < LOOP; s += 1 / 60) {
    const [px, py] = pathPoint(L, s);
    const hit = hitWord(L, px, py, radius);
    const key = hit ? `${hit[0]}:${hit[1] % 1000}` : "";
    if (hit && key !== cur) out.push({ t0: s, line: hit[0], origin: Math.floor(hit[1] / 1000) });
    cur = key;
  }
  return out;
}

function ghostAt(L: Layout, s: number) {
  const [x, y] = pathPoint(L, s);
  const fade = Math.min(1, s / 0.1, (9.77 - s) / 0.15);
  return { x, y, a: Math.max(0, fade) };
}

/* ---------- component ---------- */

export function MathScramble({
  lines = DEFAULT_LINES,
  highlight = ["louis studios"],
  colors = DEFAULT_COLORS,
  color = "#727275",
  highlightColor = "#ffffff",
  background = "#000000",
  font = MONO_STACK,
  highlightFont = SANS_STACK,
  fontSize = 0,
  autoplay = true,
  cursor = false,
  radius = 0.8,
  speed = 1,
  boxed = 0.33,
  time,
  className,
  style,
}: MathScrambleProps) {
  const rootRef = React.useRef<HTMLDivElement>(null);
  const canvasRef = React.useRef<HTMLCanvasElement>(null);
  const cfg = { lines, highlight, colors, color, highlightColor, background, font, highlightFont, fontSize, autoplay, cursor, radius, speed, boxed, time };
  const cfgRef = React.useRef(cfg);
  cfgRef.current = cfg;
  const kickRef = React.useRef<() => void>(() => {});
  const [reduced, setReduced] = React.useState(false);
  const reducedRef = React.useRef(reduced);
  reducedRef.current = reduced;

  React.useEffect(() => {
    const mq = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
    if (!mq) return;
    const on = () => setReduced(mq.matches);
    on();
    if (mq.addEventListener) {
      mq.addEventListener("change", on);
    } else {
      mq.addListener(on);
    }
    return () => {
      if (mq.removeEventListener) {
        mq.removeEventListener("change", on);
      } else {
        mq.removeListener(on);
      }
    };
  }, []);

  React.useEffect(() => {
    const root = rootRef.current;
    const canvas = canvasRef.current;
    if (!root || !canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let W = 0;
    let H = 0;
    let dpr = 1;
    let L: Layout | null = null;
    let layoutKey = "";
    let script: Scripted[] = [];
    let symbols: string[] = [];
    let raf = 0;
    let visible = true;
    let onscreen = true;
    let last = 0;
    let clock = 0; // effect clock, seconds
    let auto = 0; // autoplay loop clock
    let autoSeedLoop = 0;
    let scriptIdx = 0;
    let userUntil = -1; // autoplay waits until this effect time after a real pointer
    let userKey = "";
    let seedN = 1;
    const live: (Trigger | null)[] = [];
    const widthCache = new Map<string, number>();

    const ensureLayout = () => {
      const c = cfgRef.current;
      const key = [W, H, c.lines.join("\n"), c.highlight.join("|"), c.font, c.highlightFont, c.fontSize, c.radius].join("§");
      if (key === layoutKey && L) return;
      layoutKey = key;
      L = buildLayout(ctx, W, H, c.lines, c.highlight, c.font, c.highlightFont, c.fontSize);
      script = scriptFor(L, c.radius);
      symbols = usableSymbols(c.font);
      widthCache.clear();
      live.length = 0;
      for (let i = 0; i < L.lines.length; i++) live.push(null);
      scriptIdx = 0;
    };

    const resize = () => {
      const r = root.getBoundingClientRect();
      W = Math.max(1, Math.round(r.width));
      H = Math.max(1, Math.round(r.height));
      dpr = Math.min(3, window.devicePixelRatio || 1);
      canvas.width = Math.round(W * dpr);
      canvas.height = Math.round(H * dpr);
      canvas.style.width = W + "px";
      canvas.style.height = H + "px";
      layoutKey = "";
      ensureLayout();
    };

    /* Pure timeline: the latest scripted trigger per line at loop time s. */
    const pureTriggers = (E: number): (Trigger | null)[] => {
      const c = cfgRef.current;
      const res: (Trigger | null)[] = L!.lines.map(() => null);
      const loop = Math.floor(E / LOOP);
      const best: ({ t0: number; idx: number; k: number } | null)[] = L!.lines.map(() => null);
      for (const k of [loop - 1, loop]) {
        script.forEach((sc, idx) => {
          const t0 = sc.t0 + k * LOOP;
          if (t0 > E) return;
          const b = best[sc.line];
          if (!b || t0 > b.t0) best[sc.line] = { t0, idx, k };
        });
      }
      best.forEach((b, li) => {
        if (!b) return;
        const sc = script[b.idx];
        res[li] = makeTrigger(L!.lines[li], sc.origin, b.t0, b.idx + 1, c.colors.length, symbols, c.boxed);
      });
      return res;
    };

    const fire = (li: number, origin: number, t0: number, seed: number) => {
      const c = cfgRef.current;
      live[li] = makeTrigger(L!.lines[li], origin, t0, seed, c.colors.length, symbols, c.boxed);
    };

    const measure = (f: string, g: string) => {
      const k = f + "\u0000" + g;
      let v = widthCache.get(k);
      if (v === undefined) {
        ctx.font = f;
        v = ctx.measureText(g).width;
        widthCache.set(k, v);
      }
      return v;
    };

    const roundRect = (x: number, y: number, w: number, h: number, r: number) => {
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.arcTo(x + w, y, x + w, y + h, r);
      ctx.arcTo(x + w, y + h, x, y + h, r);
      ctx.arcTo(x, y + h, x, y, r);
      ctx.arcTo(x, y, x + w, y, r);
      ctx.closePath();
    };

    const draw = (E: number, trig: (Trigger | null)[], ghost: { x: number; y: number; a: number } | null) => {
      const c = cfgRef.current;
      const Lay = L!;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      if (c.background && c.background !== "transparent") {
        ctx.fillStyle = c.background;
        ctx.fillRect(0, 0, W, H);
      }
      const base = parseColor(c.color);
      const pal = c.colors.length ? c.colors.map(parseColor) : [base];
      const size = Lay.size;
      const adv = Lay.adv;
      const fN = `${WEIGHT} ${size}px ${c.font}`;
      const fB = `700 ${size}px ${c.font}`;
      const fI = `italic ${WEIGHT} ${size}px ${c.font}`;
      const fH = `500 ${Lay.hlSize}px ${c.highlightFont}`;
      const baseStr = mix(base, base, 0);
      ctx.textAlign = "center";
      ctx.textBaseline = "alphabetic";
      const lw = Math.max(1 / dpr, adv * 0.042);
      const bh = adv * 1.8;
      const br = adv * 0.2;
      for (let li = 0; li < Lay.lines.length; li++) {
        const ln = Lay.lines[li];
        const t = trig[li];
        const n = ln.cells.length;
        // per-cell state
        const amt = new Float32Array(n);
        const on = new Uint8Array(n);
        if (t) {
          for (let j = 0; j < n; j++) {
            if (ln.cells[j].space) continue;
            const age = E - t.act[j];
            if (age < 0 || age > t.hold[j]) continue;
            on[j] = 1;
            amt[j] = Math.max(0, Math.min(1, age / FADE_IN, (t.hold[j] - age) / FADE_OUT));
          }
        }
        // boxes first, behind the glyphs
        if (t) {
          ctx.lineWidth = lw;
          for (let j = 0; j < n; j++) {
            if (!on[j] || !t.box[j]) continue;
            const cell = ln.cells[j];
            const lb = j > 0 && on[j - 1] && t.box[j - 1];
            const rb = j < n - 1 && on[j + 1] && t.box[j + 1];
            const gap = Math.max(0.5, adv * 0.02);
            const ext = adv * 0.07;
            const x0 = cell.x - adv / 2 + (lb ? gap : -ext);
            const x1 = cell.x + adv / 2 - (rb ? gap : -ext);
            const top = ln.y - adv * 0.47 - bh / 2;
            const pc = pal[t.col[j] % pal.length];
            ctx.strokeStyle = mix(base, pc, amt[j]).replace(/,([0-9.]+)\)$/, (_m, a) => `,${(Number(a) * 0.9).toFixed(3)})`);
            roundRect(x0 + lw / 2, top + lw / 2, x1 - x0 - lw, bh - lw, br);
            ctx.stroke();
          }
        }
        for (let j = 0; j < n; j++) {
          const cell = ln.cells[j];
          if (cell.space) continue;
          let g = cell.ch;
          let f = fN;
          let fill = baseStr;
          if (t && on[j]) {
            g = t.glyph[j];
            f = t.bold[j] ? fB : t.italic[j] ? fI : fN;
            fill = mix(base, pal[t.col[j] % pal.length], amt[j]);
          }
          ctx.font = f;
          ctx.fillStyle = fill;
          const gw = measure(f, g) * STRETCH;
          const maxW = adv * 0.98;
          const sx = gw > maxW ? (STRETCH * maxW) / gw : STRETCH;
          ctx.setTransform(dpr * sx, 0, 0, dpr, cell.x * dpr, ln.y * dpr);
          ctx.fillText(g, 0, 0);
          ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        }
        if (ln.hl.length) {
          ctx.font = fH;
          ctx.fillStyle = c.highlightColor;
          ctx.textAlign = "left";
          for (const h of ln.hl) Array.from(h.text).forEach((ch, k) => ctx.fillText(ch, h.x + h.offs[k] * adv, ln.y));
          ctx.textAlign = "center";
        }
      }
      if (ghost && ghost.a > 0.01) {
        const s = adv * 0.5;
        ctx.save();
        ctx.globalAlpha = ghost.a;
        ctx.translate(ghost.x, ghost.y);
        ctx.scale(s / 20, s / 20);
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.lineTo(0, 16.5);
        ctx.lineTo(4, 12.8);
        ctx.lineTo(6.9, 19.2);
        ctx.lineTo(9.6, 18);
        ctx.lineTo(6.8, 11.8);
        ctx.lineTo(12, 11.6);
        ctx.closePath();
        ctx.lineJoin = "round";
        ctx.lineWidth = 1.6;
        ctx.strokeStyle = "#000000"; // ls:keep
        ctx.stroke();
        ctx.fillStyle = "#ffffff"; // ls:keep
        ctx.fill();
        ctx.restore();
      }
    };

    const animating = () => {
      if (!L) return false;
      for (let li = 0; li < live.length; li++) {
        const t = live[li];
        if (!t) continue;
        let end = 0;
        for (let j = 0; j < t.act.length; j++) end = Math.max(end, t.act[j] + t.hold[j]);
        if (clock <= end) return true;
        live[li] = null;
      }
      return false;
    };

    const frame = (now: number) => {
      raf = 0;
      const c = cfgRef.current;
      ensureLayout();
      if (!L) return;
      if (typeof c.time === "number") {
        const E = Math.max(0, c.time) * c.speed;
        const s = E - Math.floor(E / LOOP) * LOOP;
        if (!c.autoplay || reducedRef.current) draw(0, L.lines.map(() => null), null);
        else draw(E, pureTriggers(E), c.cursor ? ghostAt(L, s) : null);
        return;
      }
      if (reducedRef.current) {
        draw(0, L.lines.map(() => null), null);
        return;
      }
      const dt = last ? Math.min(0.1, (now - last) / 1000) : 0;
      last = now;
      clock += dt * c.speed;
      let ghost: ReturnType<typeof ghostAt> | null = null;
      if (c.autoplay && clock >= userUntil) {
        auto += dt * c.speed;
        if (auto >= LOOP) {
          // finish the loop's remaining triggers, then wrap
          for (; scriptIdx < script.length; scriptIdx++) {
            const sc = script[scriptIdx];
            fire(sc.line, sc.origin, clock - (auto - sc.t0), scriptIdx + 1 + autoSeedLoop * 997);
          }
          auto -= LOOP;
          scriptIdx = 0;
          autoSeedLoop++;
        }
        while (scriptIdx < script.length && script[scriptIdx].t0 <= auto) {
          const sc = script[scriptIdx];
          fire(sc.line, sc.origin, clock - (auto - sc.t0), scriptIdx + 1 + autoSeedLoop * 997);
          scriptIdx++;
        }
        if (c.cursor) ghost = ghostAt(L, auto);
      }
      draw(clock, live, ghost);
      if (visible && onscreen && (c.autoplay || animating())) raf = requestAnimationFrame(frame);
      else last = 0;
    };

    const kick = () => {
      if (!raf && visible && onscreen) raf = requestAnimationFrame(frame);
    };
    kickRef.current = () => {
      if (!raf) raf = requestAnimationFrame(frame);
    };

    const onPoint = (clientX: number, clientY: number) => {
      const c = cfgRef.current;
      if (reducedRef.current || typeof c.time === "number" || !L) return;
      const r = canvas.getBoundingClientRect();
      const px = clientX - r.left;
      const py = clientY - r.top;
      userUntil = clock + 1.6;
      const hit = hitWord(L, px, py, c.radius);
      const key = hit ? `${hit[0]}:${hit[1] % 1000}` : "";
      if (hit && key !== userKey) fire(hit[0], Math.floor(hit[1] / 1000), clock, (seedN = (seedN * 48271) % 2147483647) + 7);
      userKey = key;
      kick();
    };
    const onMove = (e: PointerEvent) => onPoint(e.clientX, e.clientY);
    const onLeave = () => {
      userKey = "";
      userUntil = clock + 1.6;
    };
    const onTouch = (e: TouchEvent) => {
      const t = e.touches[0];
      if (t) onPoint(t.clientX, t.clientY);
    };
    root.addEventListener("pointermove", onMove);
    root.addEventListener("pointerdown", onMove);
    root.addEventListener("pointerleave", onLeave);
    root.addEventListener("touchmove", onTouch, { passive: true });
    root.addEventListener("touchend", onLeave, { passive: true });

    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(() => {
      resize();
      if (!raf) raf = requestAnimationFrame(frame);
    }) : null;
    ro?.observe(root);
    const io = typeof IntersectionObserver !== "undefined" ? new IntersectionObserver((es) => {
      onscreen = es.some((e) => e.isIntersecting);
      if (onscreen) kick();
    }) : null;
    io?.observe(root);
    const onVis = () => {
      visible = document.visibilityState !== "hidden";
      last = 0;
      if (visible) kick();
    };
    document.addEventListener("visibilitychange", onVis);
    const onWinResize = () => {
      resize();
      kick();
    };
    window.addEventListener("resize", onWinResize);

    resize();
    raf = requestAnimationFrame(frame);
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(() => {
        layoutKey = "";
        widthCache.clear();
        if (!raf) raf = requestAnimationFrame(frame);
      });
    }

    return () => {
      cancelAnimationFrame(raf);
      raf = 0;
      ro?.disconnect();
      io?.disconnect();
      document.removeEventListener("visibilitychange", onVis);
      window.removeEventListener("resize", onWinResize);
      root.removeEventListener("pointermove", onMove);
      root.removeEventListener("pointerdown", onMove);
      root.removeEventListener("pointerleave", onLeave);
      root.removeEventListener("touchmove", onTouch);
      root.removeEventListener("touchend", onLeave);
    };
  }, []);

  // redraw on any prop change
  React.useEffect(() => {
    kickRef.current();
  });

  const label = lines.join(" ");
  return (
    <div
      ref={rootRef}
      className={className}
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        minHeight: 360,
        overflow: "hidden",
        background,
        touchAction: "pan-y",
        ...style,
      }}
    >
      <canvas ref={canvasRef} aria-hidden="true" style={{ position: "absolute", inset: 0, display: "block" }} />
      <p
        style={{
          position: "absolute",
          width: 1,
          height: 1,
          margin: -1,
          padding: 0,
          overflow: "hidden",
          clip: "rect(0 0 0 0)",
          whiteSpace: "nowrap",
          border: 0,
        }}
      >
        {label}
      </p>
    </div>
  );
}

export default MathScramble;
