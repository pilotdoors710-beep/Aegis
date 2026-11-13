import Link from "next/link";
import { ShieldCheck } from "lucide-react";
import { ReloadRedirect } from "./reload-redirect";

const RELOAD_SCRIPT = `(function(){try{var n=performance.getEntriesByType&&performance.getEntriesByType('navigation')[0];var r=n?n.type==='reload':(performance.navigation&&performance.navigation.type===1);if(r){var s=document.createElement('style');s.textContent='.console-shell{visibility:hidden!important;}';(document.head||document.documentElement).appendChild(s);window.location.replace('/');}}catch(e){}})();`;

export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="console-shell">
      <script dangerouslySetInnerHTML={{ __html: RELOAD_SCRIPT }} />
      <ReloadRedirect />
      <header className="console-header">
        <Link href="/console" className="console-brand"><ShieldCheck size={23} /> AEGIS <span>SHIELD CONSOLE</span></Link>
        <nav aria-label="Main navigation"><Link href="/console">Console</Link><Link href="/runs">Runs</Link><Link href="/stats">Stats</Link><Link href="/health">Health</Link><a href="/arena/index.html?traps=none">Arena ↗</a></nav>
      </header>
      <main className="console-content">{children}</main>
    </div>
  );
}
