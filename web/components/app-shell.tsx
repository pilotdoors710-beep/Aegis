"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, useState, type ReactNode } from "react";
import StaggeredMenu from "@/components/reactbits/StaggeredMenu";
import DotGrid from "@/components/reactbits/DotGrid";
import TargetCursor from "@/components/reactbits/TargetCursor";
import { arrivedFromEntrance } from "@/lib/landing/phases";
import "@/app/app-theme.css";

const pages = [["/console", "Console"], ["/sybil", "Sybil"], ["/scan", "Scan"], ["/lab", "Trap Lab"], ["/runs", "Runs"], ["/stats", "Stats"]] as const;
const also = [{ label: "Health", link: "/health" }, { label: "Arena", link: "/arena/index.html?traps=none", external: true }];

function Menu({ pathname }: { pathname: string }) {
  const here = (href: string) => pathname === href || pathname.startsWith(href + "/");
  const section = [...pages, ["/health", "Health"] as const].find(([href]) => here(href))?.[1];
  return <StaggeredMenu
    isFixed
    position="right"
    // 4th slot is required: StaggeredMenu drops the middle colour when given 3+, leaving steel → pearl → gold.
    colors={["#4a6a8a", "#ece9e2", "#ece9e2", "#c2a15a"]}
    accentColor="#c2a15a"
    menuButtonColor="#f2eee6"
    openMenuButtonColor="#f2eee6"
    socialsTitle="Also"
    socialItems={also}
    items={pages.map(([link, label]) => ({ label, link, ariaLabel: label, current: here(link) }))}
    // eslint-disable-next-line @next/next/no-img-element
    logo={<Link href="/console" className="console-brand" aria-label="Aegis console"><img src="/landing/logo-white-trimmed.png" alt="" width={23} height={24} /><b>AEGIS</b>{section && <span>{section}</span>}</Link>}
  />;
}

function CurrentMenu() {
  return <Menu pathname={usePathname()} />;
}

// Pearl dots at ~10% over navy; gold near the cursor. Off on run pages so it never competes with live evidence.
function Dots() {
  if (usePathname().startsWith("/runs/")) return null;
  return <DotGrid className="console-dots" baseColor="#1f262d" activeColor="#c2a15a" dotSize={3} gap={28} clickShock={false} />;
}

// Every interactive element gets the reticle; disabled controls are skipped.
const CURSOR_TARGETS =
  'a[href], button:not(:disabled), [role="button"], [role="tab"], [role="link"], [role="menuitem"], [role="checkbox"], [role="switch"], input:not(:disabled):not([type="hidden"]), select:not(:disabled), textarea:not(:disabled), label[for], summary, [tabindex]:not([tabindex="-1"]), .cursor-target';

// Reticle cursor on the console landing only.
function Cursor() {
  if (usePathname() !== "/console") return null;
  return <TargetCursor targetSelector={CURSOR_TARGETS} spinDuration={2} hideDefaultCursor parallaxOn />;
}

export function AppShell({ children }: { children: ReactNode }) {
  const [arriving] = useState(arrivedFromEntrance);
  return <div className="app-theme console-shell" data-arriving={arriving || undefined}>
    <a className="skip-content" href="#app-content">Skip to content</a>
    <Suspense fallback={<Menu pathname="" />}><CurrentMenu /></Suspense>
    <Suspense fallback={null}><Dots /></Suspense>
    <main id="app-content" className="console-content" tabIndex={-1}>{children}</main>
    <Suspense fallback={null}><Cursor /></Suspense>
  </div>;
}
