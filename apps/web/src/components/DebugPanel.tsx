"use client";

import { useState } from "react";

export function DebugPanel({ title, json }: { title: string; json: unknown }) {
  const [open, setOpen] = useState(false);
  const text = JSON.stringify(json, null, 2);
  return (
    <section className="mt-6 rounded-lg border border-dashed border-surface-border bg-surface/50 p-3 text-xs">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 text-left font-medium text-zinc-400"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        <span>
          <span className="text-zinc-500">Technical details</span>
          <span className="text-zinc-400"> · {title}</span>
        </span>
        <span aria-hidden className="shrink-0 tabular-nums text-zinc-500">
          {open ? "−" : "+"}
        </span>
      </button>
      {open ? (
        <pre className="mt-2 max-h-80 overflow-auto rounded bg-black/40 p-2 font-mono text-zinc-300" tabIndex={0}>
          {text}
        </pre>
      ) : null}
    </section>
  );
}
