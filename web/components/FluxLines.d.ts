import type { ComponentType, HTMLAttributes } from "react";

export interface FluxLinesProps extends HTMLAttributes<HTMLDivElement> {
  colors?: string[];
  speed?: number;
  scale?: number;
  turbulence?: number;
  fluidity?: number;
  rimWidth?: number;
  sharpness?: number;
  shimmer?: number;
  glow?: number;
  lineWidth?: number;
  flowDirection?: "up" | "down" | "left" | "right";
  mouseInteraction?: boolean;
  mouseStrength?: number;
  mouseRadius?: number;
  mouseDampening?: number;
  clickSwirl?: boolean;
  intro?: boolean;
  lightMode?: boolean;
  transparent?: boolean;
  backgroundColor?: string;
  opacity?: number;
  paused?: boolean;
  mixBlendMode?: React.CSSProperties["mixBlendMode"];
  dpr?: number;
}

declare const FluxLines: ComponentType<FluxLinesProps>;
export default FluxLines;
