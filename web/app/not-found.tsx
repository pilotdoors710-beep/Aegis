import Link from "next/link";

// Replaces Next's built-in 404, which hardcodes system-ui, so the site keeps its three fonts.
export default function NotFound() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
      <h1 className="font-mono text-sm tracking-widest">404</h1>
      <p className="text-lg">This page could not be found.</p>
      <Link href="/console" className="underline underline-offset-4">
        Back to the console
      </Link>
    </main>
  );
}
