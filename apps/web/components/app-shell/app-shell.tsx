"use client";

import * as React from "react";
import Link from "next/link";
import { BarChart3, Calculator, FileCheck2, FileQuestion, FileSearch, FileText, Layers3, LayoutDashboard, Menu, Plus, Search, Settings, ShoppingCart, Upload } from "lucide-react";

import { ThemeToggle } from "@/components/app-shell/theme-toggle";
import { UserMenu } from "@/components/app-shell/user-menu";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { AppRole, getCurrentAppUser, USERS_CHANGED_EVENT } from "@/lib/auth/users";
import { cn } from "@/lib/utils";

type NavItem = {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  roles?: AppRole[];
};

type NavSection = {
  title: string;
  items: NavItem[];
};

const everyone: AppRole[] = ["admin", "management", "approver", "sales", "estimation", "technical", "planning", "purchase", "viewer"];

const navSections: NavSection[] = [
  {
    title: "Work Queue",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["admin", "management", "approver", "sales", "estimation", "technical", "planning", "purchase"] },
      { href: "/quotes", label: "Enquiries", icon: FileText, roles: ["admin", "management", "sales", "estimation", "technical"] },
      { href: "/history", label: "History", icon: FileSearch, roles: everyone },
    ],
  },
  {
    title: "Technical",
    items: [
      { href: "/quotes", label: "Review Queue", icon: FileText, roles: ["admin", "management", "estimation", "technical"] },
      { href: "/doc-assistant", label: "Doc Assistant", icon: FileQuestion, roles: ["admin", "management", "sales", "estimation", "technical"] },
      { href: "/tools/converter", label: "Converter", icon: Calculator, roles: ["admin", "management", "estimation", "technical", "planning", "purchase"] },
    ],
  },
  {
    title: "Commercial",
    items: [
      { href: "/quotes/final", label: "Quotation", icon: FileCheck2, roles: ["admin", "management", "approver", "sales"] },
      { href: "/dashboard", label: "Approvals", icon: LayoutDashboard, roles: ["admin", "management", "approver"] },
    ],
  },
  {
    title: "Planning / Purchase",
    items: [
      { href: "/material-planning", label: "Material Planning", icon: Layers3, roles: ["admin", "management", "planning", "purchase"] },
      { href: "/vendor-enquiries", label: "Vendor Enquiries", icon: ShoppingCart, roles: ["admin", "management", "planning", "purchase"] },
    ],
  },
  {
    title: "Admin",
    items: [
      { href: "/settings", label: "Settings", icon: Settings, roles: ["admin"] },
    ],
  },
];

function SidebarNav({ activePath }: { activePath: string }) {
  const [role, setRole] = React.useState<AppRole>("admin");
  const [recent, setRecent] = React.useState<Array<{ id: string; label: string; href: string }>>([]);
  React.useEffect(() => {
    const refresh = () => setRole(getCurrentAppUser().role);
    const refreshRecent = () => {
      try {
        setRecent(JSON.parse(window.localStorage.getItem("gq_recent_quotes") || "[]"));
      } catch {
        setRecent([]);
      }
    };
    refresh();
    refreshRecent();
    window.addEventListener(USERS_CHANGED_EVENT, refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener(USERS_CHANGED_EVENT, refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);
  const visibleSections = navSections
    .map((section) => ({ ...section, items: section.items.filter((item) => role === "admin" || !item.roles || item.roles.includes(role)) }))
    .filter((section) => section.items.length);
  return (
    <nav className="space-y-5">
      {visibleSections.map((section) => (
        <div key={section.title} className="space-y-1">
          <div className="px-3 text-[11px] font-semibold uppercase tracking-normal text-muted-foreground">{section.title}</div>
          {section.items.map((item) => {
            const Icon = item.icon;
            const active = activePath === item.href;
            return (
              <Link
                key={`${section.title}-${item.href}-${item.label}`}
                href={item.href}
                className={cn(
                  "flex h-9 items-center gap-2 rounded-md px-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                  active && "bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground",
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </div>
      ))}
      {recent.length > 0 && (
        <div className="space-y-1 border-t pt-4">
          <div className="px-3 text-[11px] font-semibold uppercase tracking-normal text-muted-foreground">Recent</div>
          {recent.slice(0, 4).map((item) => (
            <Link
              key={item.id}
              href={item.href}
              className="block truncate rounded-md px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              {item.label}
            </Link>
          ))}
        </div>
      )}
    </nav>
  );
}

export function AppShell({
  children,
  activePath,
  title,
  breadcrumb,
}: {
  children: React.ReactNode;
  activePath: string;
  title: string;
  breadcrumb: string;
}) {
  return (
    <div className="min-h-screen bg-background">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r bg-card lg:block">
        <div className="flex h-16 items-center gap-3 border-b px-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <BarChart3 className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold">GGPL Quote</div>
            <div className="truncate text-xs text-muted-foreground">Goodrich Gasket Pvt. Ltd.</div>
          </div>
        </div>
        <div className="p-4">
          <SidebarNav activePath={activePath} />
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b bg-background/95 px-4 backdrop-blur md:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <Sheet>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open navigation">
                  <Menu className="h-5 w-5" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left">
                <SheetHeader>
                  <SheetTitle>GGPL Quote</SheetTitle>
                </SheetHeader>
                <div className="mt-6">
                  <SidebarNav activePath={activePath} />
                </div>
              </SheetContent>
            </Sheet>
            <div className="min-w-0">
              <div className="truncate text-xs font-medium text-muted-foreground">{breadcrumb}</div>
              <h1 className="truncate text-lg font-semibold tracking-normal">{title}</h1>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" className="hidden md:inline-flex" asChild>
              <Link href="/quotes"><Plus className="h-4 w-4" />New enquiry</Link>
            </Button>
            <Button variant="secondary" size="sm" className="hidden md:inline-flex" asChild>
              <Link href="/quotes"><Upload className="h-4 w-4" />Upload</Link>
            </Button>
            <Button variant="ghost" size="icon" className="hidden md:inline-flex" asChild aria-label="Search quotes">
              <Link href="/history"><Search className="h-4 w-4" /></Link>
            </Button>
            <Badge variant="outline" className="hidden md:inline-flex">
              Local workspace
            </Badge>
            <ThemeToggle />
            <UserMenu />
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl px-4 py-6 md:px-6">{children}</main>
      </div>
    </div>
  );
}
