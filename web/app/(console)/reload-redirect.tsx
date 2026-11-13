"use client";

import { useEffect } from "react";

export function ReloadRedirect() {
  useEffect(() => {
    try {
      const nav = performance.getEntriesByType?.("navigation")?.[0] as PerformanceNavigationTiming | undefined;
      const isReload = nav ? nav.type === "reload" : performance.navigation?.type === 1;
      if (isReload) {
        document.querySelector<HTMLElement>(".console-shell")?.style.setProperty("visibility", "hidden");
        window.location.replace("/");
      }
    } catch {}
  }, []);

  return null;
}
