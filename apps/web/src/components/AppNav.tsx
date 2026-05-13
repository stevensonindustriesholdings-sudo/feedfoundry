"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const primary = [
  { href: "/", label: "Home" },
  { href: "/pricing", label: "Pricing" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/upload", label: "Upload" },
  { href: "/jobs", label: "Jobs" },
  { href: "/outputs", label: "Outputs" },
  { href: "/archive", label: "Archive" },
] as const;

export function AppNav() {
  const pathname = usePathname();
  const systemActive = pathname === "/system" || pathname.startsWith("/system/");

  return (
    <header className="sticky top-0 z-40 border-b border-surface-border/90 bg-surface-raised/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
        <Link href="/" className="group flex items-center gap-2 no-underline">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/15 ring-1 ring-accent/30">
            <span className="h-2.5 w-2.5 rounded-full bg-accent" aria-hidden />
          </span>
          <span className="text-lg font-semibold tracking-tight text-zinc-50 group-hover:text-white">FeedFoundry</span>
        </Link>
        <nav className="flex flex-wrap items-center gap-x-0.5 gap-y-2 text-sm" aria-label="Main">
          {primary.map(({ href, label }) => {
            const active = pathname === href || (href !== "/" && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={
                  active
                    ? "rounded-md bg-surface-border px-2.5 py-1.5 text-zinc-50 no-underline"
                    : "rounded-md px-2.5 py-1.5 text-zinc-400 no-underline hover:bg-surface-border/50 hover:text-zinc-100"
                }
              >
                {label}
              </Link>
            );
          })}
          <span className="mx-1 hidden h-4 w-px bg-surface-border sm:inline" aria-hidden />
          <Link
            href="/system"
            className={
              systemActive
                ? "rounded-md px-2.5 py-1.5 text-xs font-medium text-zinc-400 no-underline ring-1 ring-surface-border sm:ml-0"
                : "rounded-md px-2.5 py-1.5 text-xs font-medium text-zinc-600 no-underline hover:text-zinc-400 sm:ml-0"
            }
          >
            Service
          </Link>
        </nav>
      </div>
    </header>
  );
}
