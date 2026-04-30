"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function AppHeader() {
  const pathname = usePathname();
  return (
    <header className="surface-elevated app-header">
      <div>
        <div style={{ fontWeight: 700 }}>AI Consulting Studio</div>
        <div className="muted" style={{ fontSize: "0.84rem" }}>Multi-agent management consulting workspace</div>
      </div>
      <nav className="app-header-nav">
        <Link className={pathname === "/" ? "btn btn-soft" : "btn btn-ghost"} href="/">Home</Link>
        <Link className={pathname.startsWith("/dashboard") ? "btn btn-soft" : "btn btn-ghost"} href="/dashboard">Dashboard</Link>
      </nav>
    </header>
  );
}
