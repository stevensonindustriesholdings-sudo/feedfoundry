"use client";

import { useEffect, useState } from "react";
import { clearOrgId, getOrgId, setOrgId } from "@/lib/org-storage";

export function OrgSwitcher() {
  const [value, setValue] = useState("");

  useEffect(() => {
    setValue(getOrgId() || "");
  }, []);

  const save = () => {
    const v = value.trim();
    if (v) setOrgId(v);
    else clearOrgId();
  };

  if (process.env.NEXT_PUBLIC_APP_ENV !== "staging") {
    return null;
  }

  return (
    <div className="rounded-lg border border-dashed border-zinc-600 bg-surface/60 p-4 text-sm">
      <p className="font-medium text-zinc-300">Staging org id</p>
      <p className="mt-1 text-xs text-zinc-500">
        Stored in <code className="rounded bg-black/30 px-1">localStorage</code> as{" "}
        <code className="rounded bg-black/30 px-1">ff_org_id</code>. Empty = use server default.
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        <input
          aria-label="Organisation id"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="min-w-[200px] flex-1 rounded-md border border-surface-border bg-surface px-2 py-1 font-mono text-xs text-zinc-100"
          placeholder="org_dev_demo"
        />
        <button
          type="button"
          onClick={save}
          className="rounded-md border border-surface-border px-3 py-1 text-zinc-200 hover:bg-surface-border/40"
        >
          Save
        </button>
      </div>
    </div>
  );
}
