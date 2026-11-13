// Rebuild the poster with the exact same dither function as the GPU renderer.
// Usage: node lib/landing/prepare-assets.mjs PATH_TO_GENERATED_PNG
import { createRequire } from "node:module";
import { dither } from "./pixels.ts";
const require = createRequire(import.meta.url);
const sharp = require(require.resolve("sharp", { paths: [require.resolve("next/package.json")] }));
if (process.argv[2]) {
  await sharp(process.argv[2]).resize(2950, 2950, { kernel: "nearest", fit: "contain", background: "#00000000" })
    .extend({ top: 61, bottom: 61, left: 61, right: 61, background: "#00000000" })
    .png({ palette: true, quality: 40, dither: 0, effort: 10, compressionLevel: 9 }).toFile("public/landing/aegis-master.png");
}
const { data, info } = await sharp("public/landing/aegis-master.png").resize(240, 240).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
await sharp(Buffer.from(dither(data, info.width, info.height)), { raw: { width: info.width, height: info.height, channels: 4 } })
  .resize(960, 960, { kernel: "nearest" }).png({ palette: true }).toFile("public/landing/aegis-dithered.png");
console.log("Prepared transparent master and dithered poster.");
