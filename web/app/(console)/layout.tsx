import { AppShell } from "@/components/app-shell";
import { ReloadRedirect } from "./reload-redirect";
import TargetCursor from "@/components/reactbits/TargetCursor";

// Every interactive element gets the reticle; disabled controls are skipped.
const CURSOR_TARGETS =
  'a[href], button:not(:disabled), [role="button"], [role="tab"], [role="link"], [role="menuitem"], [role="checkbox"], [role="switch"], input:not(:disabled):not([type="hidden"]), select:not(:disabled), textarea:not(:disabled), label[for], summary, [tabindex]:not([tabindex="-1"]), .cursor-target';

const RELOAD_SCRIPT = `(function(){try{var n=performance.getEntriesByType&&performance.getEntriesByType('navigation')[0];var r=n?n.type==='reload':(performance.navigation&&performance.navigation.type===1);if(r){var s=document.createElement('style');s.textContent='.console-shell{visibility:hidden!important;}';(document.head||document.documentElement).appendChild(s);window.location.replace('/');}}catch(e){}})();`;

export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppShell sybilEnabled={process.env.SYBIL_ENABLED === "true"}>
      <script dangerouslySetInnerHTML={{ __html: RELOAD_SCRIPT }} />
      <ReloadRedirect />
      {children}
      <TargetCursor targetSelector={CURSOR_TARGETS} spinDuration={2} hideDefaultCursor parallaxOn />
    </AppShell>
  );
}
