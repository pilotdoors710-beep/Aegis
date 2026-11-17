import Link from "next/link";
import "./app-theme.css";

// Replaces Next's built-in 404, which hardcodes system-ui, so the site keeps its fonts and theme.
export default function NotFound() {
  return (
    <main className="app-theme flex flex-1 flex-col items-center justify-center gap-6 p-8 text-center">
      <span className="label">Error 404 · blocked</span>
      <h1 className="text-5xl">Nothing to check here.</h1>
      <p className="lede">This page doesn&apos;t exist. The link may be old or mistyped.</p>
      <div className="flex flex-wrap justify-center gap-4">
        <Link href="/console" className="primary-button">Open the console</Link>
        <Link href="/" className="secondary-button">Home</Link>
      </div>
    </main>
  );
}
