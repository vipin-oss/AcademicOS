"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { GraduationCap, LayoutDashboard, Boxes, FileText, BookOpen, Users, Presentation, FlaskConical, Briefcase, Search, Calendar, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

/** `href: null` = module not built yet; rendered as a disabled item. */
const NAV = [
  { label: "Dashboard", icon: LayoutDashboard, href: "/" },
  { label: "Objects", icon: Boxes, href: "/objects" },
  { label: "Documents", icon: FileText, href: "/documents" },
  { label: "Publications", icon: BookOpen, href: "/publications" },
  { label: "Students", icon: Users, href: "/students" },
  { label: "Teaching", icon: Presentation, href: "/teaching" },
  { label: "Research", icon: FlaskConical, href: "/research" },
  { label: "Faculty", icon: Briefcase, href: "/faculty" },
  { label: "Search", icon: Search, href: null },
  { label: "Events", icon: Calendar, href: null },
  { label: "Settings", icon: Settings, href: null },
] as const;

export function Sidebar() {
  const pathname = usePathname();

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);

  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3 py-5 md:flex">
      <div className="mb-6 flex items-center gap-2 px-2">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--accent)] text-white">
          <GraduationCap className="h-5 w-5" />
        </div>
        <span className="text-lg font-semibold text-[var(--text-primary)]">AcademicOS</span>
      </div>
      <nav className="flex flex-col gap-1">
        {NAV.map((item) => {
          const Icon = item.icon;
          const base =
            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors";

          if (!item.href) {
            return (
              <span
                key={item.label}
                aria-disabled="true"
                title="Coming soon"
                className={cn(base, "cursor-not-allowed text-[var(--text-tertiary)]")}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </span>
            );
          }

          const active = isActive(item.href);
          return (
            <Link
              key={item.label}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                base,
                active
                  ? "bg-[var(--accent-subtle)] text-[var(--accent)]"
                  : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]",
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
