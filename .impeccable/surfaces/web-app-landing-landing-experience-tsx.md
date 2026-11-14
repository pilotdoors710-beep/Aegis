---
version: 1
slug: "web-app-landing-landing-experience-tsx"
primary_target: "web/app/(landing)/landing-experience.tsx"
related_targets: ["web/app/(landing)/page.tsx"]
---

# Entrance (`/`)

Scope: the landing route only. Visitor mode: Experience. Audience: a judge or first-time visitor arriving at the live URL; the presenter starts stage demos at `/console`, so this surface never sits in the timed run.
Job: say "Aegis" once, show that it inspects, and carry the visitor into the console. Action: scroll (or the visible link, or the keyboard) to enter `/console`.
Constraints: no claims, no numbers, no marketing copy. Reduced motion gets a still field and a plain link. Leaving for `/console` must not leave `/` in history.

## Direction contract

THESIS: The entrance is one wordmark in a star field and nothing else. Scrolling is the only act, and it carries the visitor through an inspection frame that grows until it contains the whole screen. It refuses the headline, subcopy and button hero, and it refuses a slider or hold-to-confirm gate.

OWN-WORLD: Black star field (React Bits Galaxy) with cream, sand and orange stars. The wordmark AEGIS in Geist 600, capitals, wide tracking, cream `#FCF8D8`. The drafting vocabulary of React Bits TechText: dashed vector outlines, a 1px hairline frame with square corner handles, 10px monospace measurement readouts. Orange `#d9541e` appears only as the console's light arriving at the moment of entry.

STORY: The visitor reads the name, moves the pointer and sees letters become measured outlines (it inspects), scrolls, and arrives inside the console already knowing its accent and ground.

FIRST VIEWPORT: Full-bleed star field. The wordmark centred, about two thirds of the viewport width at 1280. One line, "Scroll to enter", centred near the bottom edge with a slow tick beneath it; it is a real link to `/console`. Nothing else.

FORM: seed: none (pinned). Pinned by the user: "replace the current hero page background with the galaxy background component"; "apply the same font as the tech text component from react bits, and put some more spacing between the letters and make it bigger overall"; "instead of a hold transition, make a scroll transition into the console area just do something that looks good". Signature interaction: a scroll scrub. The inspection frame grows from the wordmark's bounds to the viewport edges with a live pixel readout, the stars accelerate, the wordmark racks out of focus toward the viewer, and the console's ground fills the frame. Released past a short threshold it completes on its own; released before it, it returns. At the end the route changes to `/console`, whose shell rises into the same ground.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
