/** Types for the vendored, MIT-licensed liquidglass.dev engine. */
export interface GlassOptions {
  fit?: boolean;
  clip?: boolean;
  radius?: number;
  refraction?: number;
  bezel?: number;
  curvature?: number;
  chroma?: number;
  blur?: number;
  specular?: number;
  specularWidth?: number;
  mapScale?: number;
  hidden?: boolean;
}

export interface GlassController {
  update(options: GlassOptions): void;
  flush(): void;
  destroy(): void;
  readonly filterId: string;
}

export function createGlass(target: HTMLElement, options?: GlassOptions): GlassController;
