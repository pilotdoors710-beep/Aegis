import { AppShell } from "@/components/app-shell";
import { ReloadRedirect } from "./reload-redirect";

const RELOAD_SCRIPT = `(function(){try{var n=performance.getEntriesByType&&performance.getEntriesByType('navigation')[0];var r=n?n.type==='reload':(performance.navigation&&performance.navigation.type===1);if(r){var s=document.createElement('style');s.textContent='.console-shell{visibility:hidden!important;}';(document.head||document.documentElement).appendChild(s);window.location.replace('/');}}catch(e){}})();`;

export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppShell>
      <script dangerouslySetInnerHTML={{ __html: RELOAD_SCRIPT }} />
      <ReloadRedirect />
      {children}
    </AppShell>
  );
}
