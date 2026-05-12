"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Home" },
  { href: "/pricing", label: "Pricing" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/upload", label: "Upload" },
  { href: "/jobs", label: "Jobs" },
  { href: "/outputs", label: "Outputs" },
  { href: "/archive", label: "Archive" },
  { href: "/system", label: "System" },
] as const;

export function AppNav() {
  const pathname = usePathname();
  return (
    <header className="border-b border-surface-border bg-surface-raised/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
        <Link href="/" className="text-lg font-semibold tracking-tight text-zinc-100 no-underline">
          FeedFoundry
        </Link>
        <nav className="flex flex-wrap gap-x-1 gap-y-2 text-sm" aria-label="Main">
          {links.map(({ href, label }) => {
            const active = pathname === href || (href !== "/" && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={
                  active
                    ? "rounded-md bg-surface-border px-2 py-1 text-zinc-100 no-underline"
                    : "rounded-md px-2 py-1 text-zinc-300 no-underline hover:bg-surface-border/60 hover:text-zinc-100"
                }
              >
                {label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
