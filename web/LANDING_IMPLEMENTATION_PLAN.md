# Aegis animated landing page — implementation handoff

Status: implemented on 13 Nov 2026. Production Chrome verification and remaining device limits are recorded in README.md. This document retains the approved requirements and implementation map.

## 1. Objective and authorized scope

Build a cinematic first-visit entrance to the existing Shield Console:

1. A detailed, dithered depiction of the mythological Aegis shield assembles from scattered square pixels on black.
2. Large slab-serif text fades in: **“Check before committing.”** Smaller copy explains Aegis.
3. A gently blinking **“Click anywhere to continue”** prompt invites entry.
4. Clicking reverses the shield assembly into pixel disintegration.
5. A black scene with equally sized, differently oriented, glowing yellow square frames creates a short forward flight into the console.
6. The existing working console appears, ready to launch a preset.

The user explicitly approved replacing first-visit entry with this animation, provided there is a visible Skip intro link and direct console access. This is an approved exception to project_brief.md §8's presets-first view. Record the narrow exception in §8 during implementation; preserve the requirement for directly accessible one-click demo presets.

All application changes stay in web/. Update session_notes.md as required by the repository. Preserve existing APIs, live runs, approval gates, samples, evidence, replays, stats, and the static arena. Do not change generated API types or backend contracts. This task does not include a redesign of the console itself.

Interpret “the actual Aegis” as the mythological protective shield associated with Athena: a circular ancient shield with a central Gorgoneion/Medusa relief, serpentine detailing, and an ornamental rim. This is an original artistic interpretation, not a claim of reproducing one uniquely established historical object. It must read as a physical artifact, not a generic shield icon or the word AEGIS drawn in particles.

### Make the tunnel frames fully 3D and glowing

- Replace the CSS border frames with volumetric hollow square meshes in the WebGL renderer. Each frame has visible front, back, inner, and outer surfaces.
- Give every frame identical dimensions and thickness, with independent rotations around all three axes and staggered depth positions.
- Use #FCF808 emissive yellow surfaces with bloom, producing bright cores and soft surrounding light against black.
- Move the camera smoothly through the frames’ openings toward the console. Preserve the planned 1100ms tunnel duration.
- Update the rendering approach, tunnel specification, implementation steps, and acceptance checklist consistently.
- Verify that thickness remains visible at oblique angles, glow remains clear without obscuring the openings, and perspective alone accounts for apparent size differences.

## 2. Fixed visual direction

| Element | Specification |
| --- | --- |
| Background | Solid #000000 across the complete entrance and transition |
| Artwork palette | #DD700B orange, #7C7D75 gray, #FCF808 yellow; black/transparent negative space |
| Artifact | Front-facing shield, very slight oblique lighting, embossed Medusa face, clear rim and silhouette |
| Dithering | Deliberate square ordered dithering; hard pixel edges, no blurred noise overlay |
| Headline | “Check before” / “committing.”; uppercase/lowercase exactly as shown, period included |
| Headline font | Self-hosted Roboto Slab, weight 800; slab-serif fallback; no browser runtime font CDN |
| Headline color | #FCF808 |
| Supporting type | Existing Geist; warm off-white #F1EFE5 on black |
| Supporting copy | “Aegis protects browser agents from deceptive interfaces and checks that their actions match what you authorized.” |
| Eyebrow | “AEGIS / RUNTIME SECURITY FOR BROWSER AGENTS” |
| Prompt | Exact visible text “Click anywhere to continue” plus an optional small square cursor |
| Skip | Small but clearly readable “Skip intro” link at top right; minimum 44 × 44 CSS-pixel hit area |
| Tunnel | Hollow square frames with subtle physical edge depth, yellow cores and soft yellow halos |

Gray is an artwork tone, not the color for small explanatory text. Keep body-copy contrast readable. Yellow and orange supply lighting and dimensional relief; all three specified colors must be visible in the settled artwork.

At 1280 × 720 and wider, use a two-column composition: copy on the left (about 48%), shield on the right (about 45%), with generous black negative space. Reserve a top row for the wordmark and Skip intro. Use a headline size around clamp(64px, 7.5vw, 144px), line-height 0.94, and restrained negative letter spacing. Place the continue prompt near the bottom center within the safe area.

Below 768px, stack the shield above the headline. Use clamp(42px, 10vw, 68px) for the headline and an artwork box around min(42svh, 320px). On short screens shrink the artwork first; allow scrolling if required so copy and controls remain available. Never crop the prompt or skip link. Respect safe-area insets and test at 360 × 640, 390 × 844, 768 × 1024, 1280 × 720, and 1920 × 1080.

## 3. Routes and entry rules

Use separate route groups so the landing page does not inherit the console navigation or content padding:

| URL | Behavior |
| --- | --- |
| / | Landing entrance on direct visits and whenever refreshed |
| /console | Existing home screen and demo presets, immediately accessible |
| /?intro=play | Explicitly replay the entrance, even after it was seen |
| /?intro=skip | Immediately replace with /console |
| /runs, /runs/[id], /stats, /health, /arena/* | Existing behavior, no intro interception |

Move web/app/(console)/page.tsx to web/app/(console)/console/page.tsx. Fix relative imports after moving it. Create web/app/(landing)/page.tsx for /. Do not leave two page files resolving to /.

Use sessionStorage key aegis:intro-seen:v1, written only on successful entry or explicit skip. Storage is optional: catch failures and continue. Read it after mount to avoid server/client markup mismatches. Keep repeat-visit redirects visually black and brief; no mandatory second animation. Do not put browser globals in server components.

Update the console brand and Console navigation links to /console. Search all frontend home links and route assumptions, including README and verification scripts. Keep existing run and arena URLs intact. Use /console for stage demos so the introduction consumes none of the paired-run time budget.

Prefetch /console once the client is ready. On tunnel completion, navigate with router.replace('/console') so Back does not immediately replay the introduction. A Skip intro anchor must have a real href='/console', work without JavaScript, and remain available throughout the transition. Without JavaScript, show the static artwork and an Enter console link; do not leave a noninteractive black canvas.

## 4. Artwork deliverable — finish this before motion

Create and commit an original shield master at web/public/landing/aegis-master.png, longest edge at least 3072 pixels, with transparency around the artifact. Use image generation if the implementation environment supplies it, following its skill instructions. Otherwise author a detailed layered SVG master at the equivalent path and use that consistently. Deliver the actual asset in the implementation commit; a prompt or remote URL is not a finished asset.

Art direction for generation or SVG construction:

> An isolated ancient Aegis shield, circular bronze artifact with an expressive sculpted Medusa/Gorgoneion face at its center, serpentine hair and engraved concentric rim, deeply embossed metal, dramatic directional highlights, readable front-facing silhouette. Compose for an orange, stone-gray and acid-yellow pixel-dither treatment on pure black. No lettering, background scene, pedestal, modern logo, watermark or cropped rim. Rich relief details should remain readable after conversion into square pixels.

Also commit a palette-dithered static poster at web/public/landing/aegis-dithered.png. Supply local font files and their license at web/public/landing/fonts/. The agent must inspect the actual artwork before continuing; reject an asset that resembles a plain badge or loses the face entirely under dithering. Keep the master reasonably compressed, aiming for under 1.5 MB, and the poster under 600 KB. These are budgets to measure, not claims that they have already been achieved.

## 5. Rendering and dependency choice

Use React for phase changes and small custom WebGL2 renderers for artwork pixels and the volumetric square tunnel. Render the tunnel to a texture, blur it in two quarter-resolution passes, then combine it with the sharp emissive surfaces for bloom. Use the Web Animations API only for the static/reduced-motion entry fade. No Three.js, React Three Fiber, GSAP, or Motion dependency is required. Consult the installed Next.js documentation under web/node_modules/next/dist/docs/ before implementing route groups, client boundaries, asset loading, fonts, and prefetching.

### Dither and pixel renderer

- Decode the local master once. Draw it to a temporary 2D canvas and read its pixels once, outside the animation loop.
- Resample to a logical grid whose longest edge starts around 300 samples on desktop and 200 on mobile. Discard transparent background cells. Cap particles at 36,000 desktop and 16,000 mobile by reducing the grid before allocation.
- Quantize source colors into the three artwork colors with ordered 4 × 4 Bayer perturbation followed by nearest-palette selection. Use alpha for silhouette/background and luminance for shadow density. Ensure the relief and all three colors survive; do not replace the original image with a uniform random dot cloud.
- Each occupied grid cell becomes one instanced quad. Store final position, seeded scatter position, palette color, and a short seeded delay once in typed arrays. Use a fixed PRNG seed, never Math.random() during React rendering.
- Use one quad geometry and instanced attributes, with a single draw call per animation frame. The vertex shader interpolates scatter to target with staggered eased progress; the fragment shader outputs a hard-edged square. Avoid thousands of DOM nodes.
- Suggested scattered positions: target plus a seeded radial displacement of 0.35–1.2 times the artwork width, with gentle directional variation. Pixels should travel from outside the shield silhouette into its relief; they should not just fade in where they already belong.
- Use the same particle data and trajectory in reverse for exit. Reverse the per-pixel delay ordering as well; keep the current visual progress if entry is interrupted. Exit should visibly dismantle the artifact into the same small square pixels.
- Scale the canvas backing buffer by min(devicePixelRatio, 2), and cap backing-buffer area around 3 million pixels. Size the canvas to the artwork region, not the entire 4K display. Keep cell boundaries crisp and avoid smoothing a low-resolution screenshot.
- Once assembled, draw the final frame and stop requestAnimationFrame. Keep only the slow prompt animation active while waiting.
- Reserve the artwork box before loading so there is no layout jump. Keep the poster visible until the renderer has produced a matching first frame; do not flash an empty canvas.
- On context creation failure, shader failure, image-decode failure, or webglcontextlost, reveal the static poster and keep entry working. If the poster also fails, show readable copy and entry controls. WebGL support is never a condition for reaching the product.

### Square tunnel

- Create 14 frames on desktop and 9 on mobile. Each is an actual hollow square mesh with front, back, inner and outer surfaces: 240 × 240 world units desktop, 180 × 180 mobile, 3-unit bars and 10-unit depth. Dimensions stay identical within each scene.
- Give each frame its own fixed rotation around X, Y and Z: approximately ±30°, ±30°, and ±55° respectively. Use deterministic seeded rotations with no repeating aligned sequence. Maintain a clear center opening.
- Stagger frames along depth from roughly z=-5200px to z=-900px, spacing about 330px. Small deterministic lateral offsets of up to 70px are allowed. All squares retain the same world-space side length; differences in apparent size come from perspective and depth.
- Use a 900-unit perspective projection and a depth buffer in WebGL2; preserve physical mesh depth at oblique angles.
- Advance the camera by approximately 5900 units over 1100ms with cubic-bezier(.45, 0, .2, 1). Frames pass around the viewer; the camera does not rotate or shake.
- Shade #FCF808 emissive surfaces by face direction, retaining a bright core. Add actual fixed-radius separable bloom from the offscreen scene, keeping center openings clear. Animate camera travel and crossing fades; do not animate blur radius.
- Fade each frame before its camera crossing and near-plane clipping. End on black over the final 150ms, then reveal the console without a yellow or white flash.

## 6. State machine and timing

One coordinator owns all phases. Keep a synchronous ref guard against repeated activation, alongside React state. Do not scatter route changes across animation components.

| Phase | Normal duration | Visible behavior |
| --- | --- | --- |
| loading | Asset-dependent, bounded | Copy and static poster; Skip intro and entry already usable |
| assembling | 1200ms | Pixels converge; headline fades in from 250–1000ms; supporting text fades in from 450–1050ms |
| ready | Until user enters | Settled shield and copy; prompt softly pulses |
| disassembling | 650ms | Copy fades out in 180ms; shield follows its assembly path in reverse |
| tunnel | 1100ms | Black background, forward flight past glowing yellow square frames |
| entering | Route-dependent, bounded | Fade tunnel to black over final 150ms; replace route with /console |

Use opacity and a small translateY (at most 12px) for text. Keep each headline line together; avoid per-letter animation. Prompt opacity may pulse between 0.4 and 1 over 1.6 seconds; no hard strobe. Stop blinking immediately when entry begins.

The exit takes about 1.75 seconds after activation, excluding route delivery. Continue stays usable during loading and assembly: if clicked early, reverse from the current assembly progress, not from an invented complete shield. If assets are unavailable, use a short fade and enter the console. Skip intro bypasses all remaining motion immediately.

Precreate the tunnel shortly before it is needed, initially hidden and noninteractive. Wait for animation completion through animation handles or renderer callbacks; use timeout only as a recovery guard. After 3 seconds of exit work, abandon unfinished decorative motion and navigate. If route delivery then stalls, show a clear “Open console” anchor instead of leaving a black screen.

## 7. Input, accessibility, and lifecycle

- Use a real, focusable full-viewport button beneath the decorative artwork and copy for “continue anywhere”; its accessible name is “Enter Aegis console”. Put Skip intro above it. Avoid nesting links or text containers inside a button. Decorative visual layers use pointer-events: none and aria-hidden where appropriate.
- Activate on click, Enter, or Space. Ignore key repeats. Skip has its own action. Preserve text selection: after a drag that selects copy, do not treat the resulting click as entry.
- Once accepted, disable the continue trigger. Rapid click/tap/key combinations must start exactly one exit and one route transition. Do not pass the triggering click through to console controls.
- Use a semantic h1 and real text outside canvas. Static poster alt text: “Dithered Aegis shield with a Medusa relief.” Avoid duplicate screen-reader artwork descriptions.
- Respect prefers-reduced-motion at startup and when it changes. Show the complete static artwork immediately, keep the prompt steady, and replace all particle/tunnel movement with a 150ms opacity fade on activation.
- Pause the renderer when document.hidden. On resume, resume elapsed active time; do not jump unpredictably through several phases. If the user has already requested entry, it is acceptable to finish navigation while hidden.
- ResizeObserver updates viewport-dependent uniforms/backing-buffer size without changing seeds or restarting animation. Keep normalized target positions stable. Rebuild particle grids only at idle boundaries when necessary.
- Cancel animation frames, WAAPI animations, timers, observers, and event listeners on unmount. Delete GPU buffers, shaders, and programs. Strict Mode mount/unmount/remount must not duplicate canvases or listeners.
- When /console mounts after entry, move keyboard focus to its main heading using a one-time entry signal; do not steal focus during ordinary console use.

## 8. File-level implementation map

| File | Responsibility |
| --- | --- |
| web/app/(landing)/page.tsx | Server-rendered landing route, metadata and initial static content |
| web/app/(landing)/landing-experience.tsx | Client coordinator, entry rules, phases, keyboard and navigation |
| web/app/(landing)/aegis-artwork.tsx | Canvas lifecycle, asset decoding and static fallback |
| web/app/(landing)/square-tunnel.tsx | WebGL tunnel preparation, animation and resource lifecycle |
| web/app/(landing)/landing.module.css | Scoped layout, typography, glow, prompt and reduced-motion styles |
| web/lib/landing/pixels.ts | Seeded PRNG, dither preparation and immutable particle buffers |
| web/lib/landing/renderer.ts | WebGL2 setup, instancing, progress uniforms and disposal |
| web/lib/landing/tunnel-renderer.ts | Volumetric meshes, perspective, crossing fades and bloom |
| web/lib/landing/gl.ts | GPU allocations, cleanup and bounded canvas sizing |
| web/lib/landing/phases.ts | Phase definitions, timings and permitted transitions |
| web/public/landing/* | Shield artwork, poster, local slab font and license |
| web/app/(console)/console/page.tsx | Existing presets screen moved from the root route |
| web/app/(console)/layout.tsx | Console navigation targets /console |
| web/app/layout.tsx | Font registration only if required; do not change console typography |
| web/lib/verify-day1.mjs | Extend route smoke check to include /console |
| web/README.md | Entry URLs, replay/skip behavior, asset attribution and fallback behavior |
| project_brief.md §8 | Record the user-approved first-visit entrance exception |
| session_notes.md | Short completion entry with real verification results |

Paths are a proposed allocation; consolidate small helpers where sensible. Keep CSS scoped to the landing route so global console colors and sizes do not change.

## 9. Execution order for a single implementation pass

1. Read the full project brief, latest session notes, relevant AGENTS.md files, and installed Next.js guides. Inspect git status; preserve others' changes. Confirm the approved exception recorded above.
2. Create the final shield artwork and local slab font assets. Inspect the static composition at desktop and mobile sizes before spending time on motion.
3. Move the console home to /console, create the root landing route, update navigation, and verify direct access to console, runs, health, stats and arena.
4. Implement the state machine, real continue/skip controls, session behavior, and reduced-motion/static fallback first. Every path must already lead to /console.
5. Implement deterministic dithering and pixel assembly, then reverse the same trajectories for disassembly. Verify early click, repeated click, resize, missing assets and context loss.
6. Add the equal-size volumetric WebGL frames, emissive surfaces, bloom and forward camera movement. Tune camera crossings to avoid flashes and huge border sweeps.
7. Connect prefetch, tunnel completion, navigation, focus transfer and timeout recovery. Inspect the complete journey in a production build.
8. Run the checks below, review screenshots and a motion recording, fix failures, and document actual results. Update the brief exception, README and session notes.
9. Follow repository delivery rules: focused commit(s) directly on main, web checks before publishing, git pull --rebase origin main, then git push origin main. Resolve changes in scope before publishing; do not overwrite another developer's work. Respect environment approval requirements for git metadata/network operations.

## 10. Verification and acceptance

Run from web/:

```text
pnpm typecheck
pnpm lint
pnpm build
node --test lib/events.test.mjs lib/run-evidence.test.mjs lib/verify-day1.test.mjs
```

Use the existing browser-testing facilities if available. Add focused interaction coverage for duplicate activation, early entry, skip, reduced motion and fallback navigation; do not build tests that merely mirror CSS constants. Do not add a new large test framework solely for this entrance.

Acceptance checklist:

- [x] The settled artifact is recognizably an embossed Medusa Aegis shield, with the three requested colors and deliberate square dithering.
- [x] The headline is large slab-serif text and fades in while the shield assembles; body copy remains readable.
- [x] Pixels visibly travel into the image, then reverse outward on activation. Exit is not just an opacity dissolve.
- [x] The continue prompt blinks gently; clicking anywhere on the non-skip landing surface enters.
- [x] The tunnel contains multiple volumetric yellow square meshes with front/back/inner/outer surfaces, independent orientations, identical local dimensions and bloom. Thickness is visible at oblique angles; apparent size changes result from perspective and depth.
- [x] The exit feels continuous: artwork disperses, black square tunnel advances, console appears. No layout jump, white flash, full-screen strobe or scroll jump in the inspected production Chrome recording.
- [x] /console always opens directly; samples, preset launch requests, run routes and approval dialogs passed mocked browser checks. Landing interactions themselves never create a run. This is not a deployed live-run verification.
- [x] Fresh visit, repeat visit, replay query, skip query, Back, refresh and direct deep links follow the entry table.
- [x] Early click, rapid clicks, keyboard activation, touch, resize and simulated tab hiding did not trap the user or duplicate navigation in browser checks.
- [x] Reduced motion, JavaScript disabled, unavailable storage, failed artwork load and unavailable WebGL all leave a usable route into the console.
- [x] Controls remain visible at every specified viewport and at 200% browser zoom. Keyboard focus is visible; there is no per-frame screen-reader announcement.
- [x] No requestAnimationFrame loop remains after settlement or after entry. GPU resources and animation handles are disposed on exit.
- [ ] Record the entrance on a typical laptop and a real mid-range phone where available. Target smooth 60fps on a 60Hz display and no repeated long animation frames over 33ms. Inspect real traces; desktop CPU throttling alone does not prove phone GPU performance.
- [ ] If profiling shows excessive GPU fill, first reduce particle count/backing-buffer area, then glow footprint and frame count; keep the required artwork, reverse assembly and square-flight sequence.
- [x] Report unavailable device/browser checks honestly. Laptop Chrome screenshots, video and trace were inspected. Real phone, Safari and Firefox checks remain outstanding; see README.md for measured timing and limitations.

## Copy-paste instruction for the implementing agent

Implement web/LANDING_IMPLEMENTATION_PLAN.md completely. The user approved the first-visit intro exception documented there. Read project_brief.md and session_notes.md first. Deliver the actual shield and font assets, landing route, reversible pixel assembly, glowing square tunnel, direct /console entry, accessibility and failure paths. Preserve the existing console and backend behavior. Verify the production build and browser journey, report what was actually checked, update the brief/README/session notes, and follow the repository's main-branch delivery rules. This request is for implementation, not another planning pass.
