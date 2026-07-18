"use client";

import { useEffect } from "react";
import { RefreshCw } from "lucide-react";

export default function Error({ error, reset }) {
  useEffect(() => {
    console.error("Frontend error boundary:", error);
  }, [error]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--bg)] p-4 text-ink">
      <section className="glass max-w-xl rounded-3xl border p-6 text-center">
        <div className="text-xs font-black uppercase tracking-[0.2em] text-accent">Rail Dashboard</div>
        <h1 className="mt-3 text-2xl font-black">Something went wrong in the screen.</h1>
        <p className="mt-2 text-sm text-muted">
          The app caught the error instead of closing. Use retry after the backend is reachable.
        </p>
        <button
          type="button"
          onClick={reset}
          className="focus-ring mt-5 inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-accent px-4 text-sm font-extrabold text-white shadow-glow hover:bg-accent/90"
        >
          <RefreshCw size={16} />
          Retry
        </button>
      </section>
    </main>
  );
}
