import Link from "next/link";
import { ShieldCheck } from "lucide-react";

export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  return <div className="console-shell">
    <header className="console-header">
      <Link href="/" className="console-brand"><ShieldCheck size={23} /> AEGIS <span>SHIELD CONSOLE</span></Link>
      <nav aria-label="Main navigation"><Link href="/">Console</Link><Link href="/runs">Runs</Link><Link href="/stats">Stats</Link><Link href="/health">Health</Link><a href="/arena/index.html?traps=none">Arena ↗</a></nav>
    </header>
    <main className="console-content">{children}</main>
  </div>;
}
