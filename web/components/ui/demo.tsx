"use client";

import * as React from "react";
import { MathScramble } from "@/components/ui/math-scramble";

/** Math Scramble filling the preview. Move the pointer over the words to scramble them. */
export default function MathScrambleDemo() {
  return (
    <main className="relative h-screen min-h-[340px] w-full overflow-hidden" style={{ backgroundColor: "#000000" }}>
      <MathScramble autoplay style={{ width: "100%", height: "100%" }} />
    </main>
  );
}
