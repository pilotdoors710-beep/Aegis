"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldCheck, ArrowUpRight } from "lucide-react";
import { Suspense, type ReactNode } from "react";
import "@/app/app-theme.css";

const links = [["/console", "Console"], ["/lab", "Trap Lab"], ["/runs", "Runs"], ["/stats", "Stats"], ["/health", "Health"]] as const;

function Navigation() {
  const pathname = usePathname();
  return <nav aria-label="Main navigation">{links.map(([href, label]) => <Link key={href} href={href} aria-current={pathname === href || pathname.startsWith(href + "/") ? "page" : undefined}>{label}</Link>)}<a href="/arena/index.html?traps=none">Arena <ArrowUpRight size={14} aria-hidden="true" /></a></nav>;
}

export function AppShell({ children }: { children: ReactNode }) {
  return <div className="app-theme console-shell">
    <a className="skip-content" href="#app-content">Skip to content</a>
    <header className="console-header">
      <Link href="/console" className="console-brand" aria-label="Aegis console"><ShieldCheck size={24} aria-hidden="true" /> Aegis <span>Shield Console</span></Link>
      <Suspense fallback={<nav aria-label="Main navigation">{links.map(([href, label]) => <Link key={href} href={href}>{label}</Link>)}<a href="/arena/index.html?traps=none">Arena</a></nav>}><Navigation /></Suspense>
    </header>
    <main id="app-content" className="console-content" tabIndex={-1}>{children}</main>
  </div>;
}
