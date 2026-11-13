# Aegis artwork

Original artistic interpretation generated with the built-in OpenAI imagegen tool on 13 Nov 2026. It depicts a mythological Aegis with a Medusa/Gorgoneion relief; it is not a reproduction of one established historical object.

Final generation prompt:

> Website asset: isolated complete circular ancient bronze Aegis shield, large sculpted Medusa female face in center, relief serpentine hair, engraved Greek concentric ornamental rim, rich deeply embossed metal detail, museum artifact, front facing silhouette, dramatic directional highlights. Warm orange bronze, stone-gray midtones, acid-yellow metallic highlights, black crevices; must read clearly after square dithering. Transparent background, no scene, pedestal, words, logo, watermark or cropped rim. Longest edge at least 3072 pixels. Original artistic interpretation.

The generated source was 1254 × 1254. `aegis-master.png` is a padded, palette-compressed 3072 × 3072 derivative; enlargement does not add source detail. It preserves alpha and occupies 1,449,102 bytes. The three-color ordered-dither poster, `aegis-dithered.png`, is 960 × 960 (240 logical cells enlarged with nearest-neighbor sampling), 33,035 bytes. Both are committed here and served locally.

Rebuild the poster from the committed master with Node 24 and the existing Next.js Sharp package, from `web/`:

```text
node lib/landing/prepare-assets.mjs
```

The optional source-path argument rebuilds the master too. Runtime dithering uses the same function, with grid reduction before GPU allocation to keep within desktop/mobile particle caps. Black shadow cells and transparent background cells are omitted.

Roboto Slab is self-hosted in `fonts/roboto-slab.ttf`, loaded only on the landing route at weight 800. Source: [Google Fonts Roboto Slab](https://github.com/google/fonts/tree/main/apache/robotoslab). Its Apache 2.0 license is in `fonts/LICENSE.txt`. No font requests go to a third-party host at browser runtime.
