"use client";

import * as React from "react";
import Link from "next/link";
import { BarChart3, Calculator, CheckCircle2, FileCheck2, FileQuestion, FileSearch, FileText, Layers3, LayoutDashboard, Menu, Plus, Search, Settings, ShoppingCart, Upload } from "lucide-react";

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
  description?: string;
  icon: React.ComponentType<{ className?: string }>;
  roles?: AppRole[];
  step?: string;
};

type NavSection = {
  title: string;
  items: NavItem[];
};

const everyone: AppRole[] = ["admin", "management", "approver", "sales", "estimation", "technical", "planning", "purchase", "viewer"];

const navSections: NavSection[] = [
  {
    title: "Overview",
    items: [
      { href: "/dashboard", label: "Today’s work", description: "Open tasks, delayed work, and team load", icon: LayoutDashboard, roles: ["admin", "management", "approver", "sales", "estimation", "technical", "planning", "purchase"] },
    ],
  },
  {
    title: "Main workflow",
    items: [
      { href: "/quotes", label: "Prepare enquiry", description: "Capture, clean, review, and assign sales rep", icon: FileText, roles: ["admin", "management", "sales", "estimation", "technical"], step: "1" },
      { href: "/material-planning", label: "Plan materials", description: "Breakdown sizes and plan stock/purchase", icon: Layers3, roles: ["admin", "management", "planning", "purchase"], step: "2" },
      { href: "/quotes/final", label: "Prepare quotation", description: "Pricing, terms, approval, and PDF", icon: FileCheck2, roles: ["admin", "management", "approver", "sales"], step: "3" },
      { href: "/purchase-orders", label: "Customer PO", description: "Accepted quotations and order handover", icon: CheckCircle2, roles: ["admin", "management", "approver", "sales", "planning", "purchase"], step: "4" },
    ],
  },
  {
    title: "Support tools",
    items: [
      { href: "/doc-assistant", label: "Read documents", description: "Ask questions from customer files", icon: FileQuestion, roles: ["admin", "management", "sales", "estimation", "technical"] },
      { href: "/vendor-enquiries", label: "Vendor RFQs", description: "Supplier enquiries and comparison", icon: ShoppingCart, roles: ["admin", "management", "planning", "purchase"] },
      { href: "/tools/converter", label: "Unit converter", description: "Sizes, pressure, rating, torque", icon: Calculator, roles: ["admin", "management", "estimation", "technical", "planning", "purchase"] },
      { href: "/history", label: "Activity history", description: "Exports, stage changes, and notes", icon: FileSearch, roles: everyone },
    ],
  },
  {
    title: "Admin",
    items: [
      { href: "/settings", label: "Users & settings", description: "Roles, preferences, and access", icon: Settings, roles: ["admin"] },
    ],
  },
];

const workflowGuide = [
  { step: "1", label: "Prepare enquiry", href: "/quotes" },
  { step: "2", label: "Plan materials", href: "/material-planning" },
  { step: "3", label: "Quote customer", href: "/quotes/final" },
  { step: "4", label: "Receive PO", href: "/purchase-orders" },
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
  const visibleHrefs = new Set(visibleSections.flatMap((section) => section.items.map((item) => item.href)));
  const visibleWorkflowGuide = workflowGuide.filter((item) => visibleHrefs.has(item.href));
  return (
    <nav className="space-y-5">
      <div className="rounded-lg border bg-background p-3">
        <div className="mb-2 text-[11px] font-semibold uppercase tracking-normal text-muted-foreground">Quote workflow</div>
        <div className="space-y-1">
          {visibleWorkflowGuide.map((item) => {
            const active = activePath === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2 rounded-md px-2 py-1.5 text-xs text-muted-foreground hover:bg-muted hover:text-foreground",
                  active && "bg-primary/10 text-foreground",
                )}
              >
                <span className={cn("flex h-5 w-5 items-center justify-center rounded-full border text-[11px]", active && "border-primary bg-primary text-primary-foreground")}>{item.step}</span>
                <span className="truncate">{item.label}</span>
              </Link>
            );
          })}
        </div>
      </div>
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
                  "flex items-start gap-2 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                  active && "bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground",
                )}
              >
                {item.step ? (
                  <span className={cn("mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[11px]", active ? "border-primary-foreground" : "border-border")}>{item.step}</span>
                ) : (
                  <Icon className="mt-0.5 h-4 w-4 shrink-0" />
                )}
                <span className="min-w-0">
                  <span className="block truncate">{item.label}</span>
                  {item.description && <span className={cn("block truncate text-[11px] font-normal", active ? "text-primary-foreground/80" : "text-muted-foreground")}>{item.description}</span>}
                </span>
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
      <aside className="fixed inset-y-0 left-0 hidden w-72 border-r bg-card lg:block">
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

      <div className="lg:pl-72">
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
