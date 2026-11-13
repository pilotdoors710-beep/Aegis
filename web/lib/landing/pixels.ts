export const PALETTE = [[221, 112, 11], [124, 125, 117], [252, 248, 8]] as const;
const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5];

export function randomSource(seed = 231117) {
  return () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 4294967296;
  };
}

/** Shared by the checked-in poster and the GPU artwork; no per-frame sampling. */
export function dither(rgba: Uint8ClampedArray | Uint8Array, width: number, height: number) {
  const result = new Uint8ClampedArray(rgba.length);
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const i = (y * width + x) * 4;
    const level = BAYER[(y % 4) * 4 + x % 4] / 16;
    const luminance = (rgba[i] * .2126 + rgba[i + 1] * .7152 + rgba[i + 2] * .0722) / 255;
    if (rgba[i + 3] < 100 || luminance < .045 + level * .17) continue;
    const perturb = (level - .5) * 100;
    const rgb = [rgba[i] + perturb, rgba[i + 1] + perturb, rgba[i + 2] + perturb];
    let nearest = 0, distance = Infinity;
    PALETTE.forEach((color, n) => {
      const delta = color.reduce((sum, value, c) => sum + (value - rgb[c]) ** 2, 0);
      if (delta < distance) { distance = delta; nearest = n; }
    });
    result.set([...PALETTE[nearest], 255], i);
  }
  return result;
}

export function particles(rgba: Uint8ClampedArray, width: number, height: number) {
  const random = randomSource();
  const data: number[] = [];
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const i = (y * width + x) * 4;
    if (!rgba[i + 3]) continue;
    const tx = (x + .5) / width - .5, ty = .5 - (y + .5) / height;
    const angle = Math.atan2(ty, tx) + (random() - .5) * .9;
    const radius = .35 + random() * .85;
    data.push(tx, ty, tx + Math.cos(angle) * radius, ty + Math.sin(angle) * radius,
      rgba[i] / 255, rgba[i + 1] / 255, rgba[i + 2] / 255, random() * .22);
  }
  return { data: new Float32Array(data), count: data.length / 8, cell: 1 / width };
}
