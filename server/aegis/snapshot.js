// The single in-page snapshot script (brief §3). Run via page.evaluate() once per step.
// Returns {url, title, viewport, elements[]} in DOM order. Stamps data-cs-id so ids are stable
// for the lifetime of a document. Text is collected whatever its visibility: a typical DOM agent
// reads hidden text, and leaving it out would silently protect the unshielded baseline.
() => {
  if (document.readyState === "loading") return null; // half-parsed page: caller waits, retries
  const NEARBY_PX = 80;
  const MAX_TEXT = 300;
  const INTERACTIVE_TAGS = new Set(["A", "BUTTON", "INPUT", "SELECT", "TEXTAREA", "SUMMARY"]);
  const INTERACTIVE_ROLES = new Set([
    "button", "link", "checkbox", "radio", "switch", "tab", "menuitem", "option", "combobox",
    "textbox",
  ]);
  const SKIP_TAGS = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "TEMPLATE", "HEAD", "META", "LINK"]);
  const IMPLICIT_ROLE = {
    A: "link", BUTTON: "button", SELECT: "combobox", TEXTAREA: "textbox", SUMMARY: "button",
    H1: "heading", H2: "heading", H3: "heading", H4: "heading", DIALOG: "dialog",
  };
  const INPUT_ROLE = { checkbox: "checkbox", radio: "radio", submit: "button", button: "button" };

  const clean = (s) => (s || "").replace(/\s+/g, " ").trim().slice(0, MAX_TEXT);

  const isInteractive = (el) =>
    INTERACTIVE_TAGS.has(el.tagName) ||
    INTERACTIVE_ROLES.has(el.getAttribute("role") || "") ||
    el.hasAttribute("onclick") ||
    typeof el.onclick === "function";

  const roleOf = (el) => {
    const explicit = el.getAttribute("role");
    if (explicit) return explicit;
    if (el.tagName === "INPUT") return INPUT_ROLE[el.type] || "textbox";
    return IMPLICIT_ROLE[el.tagName] || null;
  };

  const labelText = (el) => {
    const parts = [];
    if (el.labels) for (const l of el.labels) parts.push(l.textContent);
    const by = el.getAttribute("aria-labelledby");
    if (by) for (const id of by.split(/\s+/)) parts.push(document.getElementById(id)?.textContent);
    parts.push(el.getAttribute("aria-label"), el.getAttribute("title"));
    return clean(parts.filter(Boolean).join(" "));
  };

  const ownText = (el) => {
    if (el.tagName === "INPUT" || el.tagName === "SELECT" || el.tagName === "TEXTAREA") {
      const t = labelText(el) || clean(el.getAttribute("placeholder"));
      if (el.tagName === "INPUT" && ["submit", "button"].includes(el.type)) return clean(el.value) || t;
      return t;
    }
    if (isInteractive(el)) return clean(el.textContent) || labelText(el);
    // Text block: direct text nodes only (children report their own text).
    let s = "";
    for (const n of el.childNodes) if (n.nodeType === Node.TEXT_NODE) s += n.textContent + " ";
    return clean(s);
  };

  // --- colour / contrast (WCAG) ---
  const parseRGB = (c) => {
    const m = c && c.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(/[\s,/]+/).filter(Boolean).map(Number);
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  };
  const lum = ({ r, g, b }) => {
    const f = (v) => ((v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const blend = (top, bottom) => ({
    r: top.r * top.a + bottom.r * (1 - top.a),
    g: top.g * top.a + bottom.g * (1 - top.a),
    b: top.b * top.a + bottom.b * (1 - top.a),
    a: 1,
  });
  const backgroundOf = (el) => {
    // Composite ancestor backgrounds bottom-up over white.
    const layers = [];
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const bg = parseRGB(getComputedStyle(n).backgroundColor);
      if (bg && bg.a > 0) {
        layers.push(bg);
        if (bg.a >= 1) break;
      }
    }
    let c = { r: 255, g: 255, b: 255, a: 1 };
    for (let i = layers.length - 1; i >= 0; i--) c = blend(layers[i], c);
    return c;
  };
  const contrastOf = (el, style, opacity) => {
    const fg = parseRGB(style.color);
    if (!fg) return null;
    const bg = backgroundOf(el);
    const eff = blend({ ...fg, a: fg.a * opacity }, bg);
    const [l1, l2] = [lum(eff), lum(bg)].sort((a, b) => b - a);
    return Math.round(((l1 + 0.05) / (l2 + 0.05)) * 100) / 100;
  };

  const effectiveOpacity = (el) => {
    let o = 1;
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      o *= parseFloat(getComputedStyle(n).opacity);
    }
    return Math.round(o * 1000) / 1000;
  };

  const isVisible = (el, style, rect, opacity) => {
    if (style.display === "none" || style.visibility !== "visible") return false;
    if (opacity < 0.05) return false;
    if (rect.width < 2 || rect.height < 2) return false;
    const docW = Math.max(document.documentElement.scrollWidth, innerWidth);
    const docH = Math.max(document.documentElement.scrollHeight, innerHeight);
    const x = rect.left + scrollX, y = rect.top + scrollY;
    if (x + rect.width <= 0 || y + rect.height <= 0 || x >= docW || y >= docH) return false;
    if (style.clipPath && style.clipPath.startsWith("inset(100%")) return false;
    if (style.clip && /rect\(0(px)?,? 0(px)?,? 0(px)?,? 0(px)?\)/.test(style.clip)) return false;
    return true;
  };

  if (window.__csNext === undefined) window.__csNext = 1;
  const stamp = (el) => {
    if (!el.dataset.csId) el.dataset.csId = "e" + window.__csNext++;
    return el.dataset.csId;
  };

  const out = [];
  const nodes = [];
  const walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_ELEMENT, {
    acceptNode: (n) => (SKIP_TAGS.has(n.tagName) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
  });
  for (let el = walker.currentNode; el; el = walker.nextNode()) {
    if (el.nodeType !== 1) continue;
    const interactive = isInteractive(el);
    // Text inside an interactive ancestor is already reported as that ancestor's text.
    if (!interactive && el.parentElement?.closest("a,button,summary,[role=button],[role=link]")) continue;
    const text = ownText(el);
    if (!interactive && !text) continue;
    nodes.push([el, interactive, text]);
  }

  // Stamp everything first so occluded_by can name the covering element.
  for (const [el] of nodes) stamp(el);

  const rects = new Map();
  for (const [el, interactive, text] of nodes) {
    const style = getComputedStyle(el);
    // Chrome keeps a layout box for content inside a closed <details>; checkVisibility() knows it
    // is not rendered. Report it like display:none (no box), so has_box() means "rendered".
    const rendered = !el.checkVisibility || el.checkVisibility();
    const r = rendered ? el.getBoundingClientRect() : new DOMRect(0, 0, 0, 0);
    rects.set(el, r);
    const opacity = effectiveOpacity(el);
    const visible = isVisible(el, style, r, opacity);

    let occluded_by = null;
    if (visible && interactive) {
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      if (cx >= 0 && cy >= 0 && cx < innerWidth && cy < innerHeight) {
        const top = document.elementFromPoint(cx, cy);
        const isLabelFor = top && top.tagName === "LABEL" && el.labels && [...el.labels].includes(top);
        if (top && top !== el && !el.contains(top) && !isLabelFor) {
          const host = top.closest("[data-cs-id]") || top;
          occluded_by = stamp(host);
        }
      }
    }

    out.push({
      id: el.dataset.csId,
      tag: el.tagName.toLowerCase(),
      role: roleOf(el),
      text,
      nearby_text: "",
      href: el.tagName === "A" && el.getAttribute("href") !== null ? el.href : null,
      download: el.tagName === "A" && el.hasAttribute("download"),
      onclick: el.hasAttribute("onclick") || typeof el.onclick === "function",
      bbox: [r.left, r.top, r.width, r.height].map((v) => Math.round(v * 10) / 10),
      visible,
      opacity,
      contrast_ratio: text ? contrastOf(el, style, opacity) : null,
      occluded_by,
      checked: el.tagName === "INPUT" && ["checkbox", "radio"].includes(el.type) ? el.checked : null,
      value:
        el.tagName === "SELECT"
          ? el.options[el.selectedIndex]?.text ?? null
          : el.tagName === "TEXTAREA" || (el.tagName === "INPUT" && !["checkbox", "radio", "submit", "button"].includes(el.type))
            ? el.value
            : null,
      _interactive: interactive,
    });
  }

  // nearby_text: text of other text-bearing elements within NEARBY_PX of this element's box.
  const texts = out.filter((e) => e.text && !e._interactive);
  for (const e of out) {
    const [x, y, w, h] = e.bbox;
    const near = [];
    for (const t of texts) {
      if (t === e) continue;
      const [tx, ty, tw, th] = t.bbox;
      const dx = Math.max(0, tx - (x + w), x - (tx + tw));
      const dy = Math.max(0, ty - (y + h), y - (ty + th));
      if (dx <= NEARBY_PX && dy <= NEARBY_PX && t.text !== e.text) near.push(t.text);
    }
    e.nearby_text = clean(near.join(" | ")).slice(0, 200);
    delete e._interactive;
  }

  return {
    url: location.href,
    title: document.title,
    viewport: [innerWidth, innerHeight],
    elements: out,
  };
}
