"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldCheck } from "lucide-react";
import { Suspense, useState, type ReactNode } from "react";
import ClickSpark from "@/components/reactbits/ClickSpark";
import StaggeredMenu from "@/components/reactbits/StaggeredMenu";
import { arrivedFromEntrance } from "@/lib/landing/phases";
import "@/app/app-theme.css";

const Galaxy = dynamic(() => import("@/components/reactbits/Galaxy"), { ssr: false });

const pages = [["/console", "Console"], ["/lab", "Trap Lab"], ["/scan", "Scan"], ["/runs", "Runs"], ["/stats", "Stats"]] as const;
const also = [{ label: "Health", link: "/health" }, { label: "Arena", link: "/arena/index.html?traps=none", external: true }];
const STARS = ["#f3eee3", "#E8C59E", "#d9541e"];
const SPARKS = ["#d9541e", "#f3eee3"];

function Menu({ pathname }: { pathname: string }) {
  const here = (href: string) => pathname === href || pathname.startsWith(href + "/");
  const dashboard = pathname === "/console";
  const section = [...pages, ["/health", "Health"] as const].find(([href]) => here(href))?.[1];
  return <div id={dashboard ? "console-menu-home" : undefined}><StaggeredMenu
    isFixed
    position="right"
    colors={dashboard ? ["#2B3D55", "#B8925A"] : ["#3a1d12", "#d9541e"]}
    accentColor={dashboard ? "#B8925A" : "#d9541e"}
    menuButtonColor={dashboard ? "#142033" : "#f3eee3"}
    openMenuButtonColor={dashboard ? "#142033" : "#f3eee3"}
    socialsTitle="Also"
    socialItems={also}
    items={pages.map(([link, label]) => ({ label, link, ariaLabel: label, current: here(link) }))}
    logo={<Link href="/console" className="console-brand" aria-label="Aegis console"><ShieldCheck size={22} aria-hidden="true" /><b>AEGIS</b>{section && <span>{section}</span>}</Link>}
  /></div>;
}

function CurrentMenu() {
  return <Menu pathname={usePathname()} />;
}

export function AppShell({ children }: { children: ReactNode }) {
  const [arriving] = useState(arrivedFromEntrance);
  return <div className="app-theme console-shell" data-arriving={arriving || undefined}>
    <a className="skip-content" href="#app-content">Skip to content</a>
    {/* The same star field as the entrance, turned down so it sits behind the glass. */}
    <div className="console-sky" aria-hidden="true">
      <Galaxy starColors={STARS} density={0.55} starSpeed={0.3} speed={0.5} glowIntensity={0.22} twinkleIntensity={0.2} rotationSpeed={0.02} mouseInteraction={false} clickWarp={false} intro={false} opacity={0.6} dpr={1} />
    </div>
    <Suspense fallback={<Menu pathname="" />}><CurrentMenu /></Suspense>
    <ClickSpark sparkColor={SPARKS} sparkSize={9} sparkRadius={22} sparkCount={8} duration={420}>
      <main id="app-content" className="console-content" tabIndex={-1}>{children}</main>
    </ClickSpark>
  </div>;
}
