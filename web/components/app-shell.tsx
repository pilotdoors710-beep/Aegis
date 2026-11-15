"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, useState, type ReactNode } from "react";
import StaggeredMenu from "@/components/reactbits/StaggeredMenu";
import DotGrid from "@/components/reactbits/DotGrid";
import { arrivedFromEntrance } from "@/lib/landing/phases";
import "@/app/app-theme.css";

const pages = [["/console", "Console"], ["/lab", "Trap Lab"], ["/scan", "Scan"], ["/runs", "Runs"], ["/stats", "Stats"]] as const;
const also = [{ label: "Health", link: "/health" }, { label: "Arena", link: "/arena/index.html?traps=none", external: true }];

function Menu({ pathname, sybilEnabled = false }: { pathname: string; sybilEnabled?: boolean }) {
  const navigation = sybilEnabled ? [...pages, ["/sybil", "Sybil"] as const] : pages;
  const here = (href: string) => pathname === href || pathname.startsWith(href + "/");
  const section = [...navigation, ["/health", "Health"] as const].find(([href]) => here(href))?.[1];
  return <StaggeredMenu
    isFixed
    position="right"
    colors={["#132131", "#1f3347"]}
    accentColor="#c2a15a"
    menuButtonColor="#f2eee6"
    openMenuButtonColor="#f2eee6"
    socialsTitle="Also"
    socialItems={also}
    items={navigation.map(([link, label]) => ({ label, link, ariaLabel: label, current: here(link) }))}
    // eslint-disable-next-line @next/next/no-img-element
    logo={<Link href="/console" className="console-brand" aria-label="Aegis console"><img src="/landing/logo-white-trimmed.png" alt="" width={23} height={24} /><b>AEGIS</b>{section && <span>{section}</span>}</Link>}
  />;
}

function CurrentMenu({ sybilEnabled }: { sybilEnabled: boolean }) {
  return <Menu pathname={usePathname()} sybilEnabled={sybilEnabled} />;
}

// Pearl dots at ~10% over navy; gold near the cursor. Off on run pages so it never competes with live evidence.
function Dots() {
  if (usePathname().startsWith("/runs/")) return null;
  return <DotGrid className="console-dots" baseColor="#1f262d" activeColor="#c2a15a" dotSize={3} gap={28} clickShock={false} />;
}

export function AppShell({ children, sybilEnabled = false }: { children: ReactNode; sybilEnabled?: boolean }) {
  const [arriving] = useState(arrivedFromEntrance);
  return <div className="app-theme console-shell" data-arriving={arriving || undefined}>
    <a className="skip-content" href="#app-content">Skip to content</a>
    <Suspense fallback={<Menu pathname="" sybilEnabled={sybilEnabled} />}><CurrentMenu sybilEnabled={sybilEnabled} /></Suspense>
    <Suspense fallback={null}><Dots /></Suspense>
    <main id="app-content" className="console-content" tabIndex={-1}>{children}</main>
  </div>;
}
