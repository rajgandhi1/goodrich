"use client";

import * as React from "react";
import Link from "next/link";
import { BarChart3, CheckCircle2, FileCheck2, FileQuestion, FileSearch, FileText, Layers3, LayoutDashboard, Menu, PanelLeftClose, PanelLeftOpen, Plus, Settings } from "lucide-react";

import { ThemeToggle } from "@/components/app-shell/theme-toggle";
import { UserMenu } from "@/components/app-shell/user-menu";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { AppRole, getCurrentAppUser, setCurrentAppUser, USERS_CHANGED_EVENT } from "@/lib/auth/users";
import { getAccessSettingsRemote, getCurrentAppUserRemote } from "@/lib/api";
import { ACCESS_SETTINGS_CHANGED_EVENT, AppCapability, canRole, getAccessSettings, normalizeAccessSettings, saveAccessSettings } from "@/lib/auth/access-control";
import { cn } from "@/lib/utils";

type NavItem = {
  href: string;
  label: string;
  description?: string;
  icon: React.ComponentType<{ className?: string }>;
  roles?: AppRole[];
  capability?: AppCapability;
  step?: string;
};

type NavSection = {
  title: string;
  items: NavItem[];
};

const navSections: NavSection[] = [
  {
    title: "Overview",
    items: [
      { href: "/dashboard", label: "Dashboard", description: "Overview, quick stats, and recent activity", icon: LayoutDashboard, capability: "view_dashboard" },
    ],
  },
  {
    title: "Main workflow",
    items: [
      { href: "/quotes", label: "Enquiry", description: "Capture, clean, review, and assign sales rep", icon: FileText, capability: "view_enquiry", step: "1" },
      { href: "/material-planning", label: "Material planning", description: "Breakdown sizes and plan stock/purchase", icon: Layers3, capability: "view_material_planning", step: "2" },
      { href: "/quotes/final", label: "Quotation", description: "Pricing, terms, approval, and PDF", icon: FileCheck2, capability: "view_quotation", step: "3" },
      { href: "/purchase-orders", label: "Customer PO", description: "Accepted quotations and order handover", icon: CheckCircle2, capability: "view_purchase_orders", step: "4" },
    ],
  },
  {
    title: "Support tools",
    items: [
      { href: "/doc-assistant", label: "Read documents", description: "Ask questions from customer files", icon: FileQuestion, capability: "view_doc_assistant" },
      { href: "/history", label: "Reports / Analytics", description: "System usage, exports, stage changes, and notes", icon: FileSearch, capability: "view_history" },
    ],
  },
  {
    title: "Admin",
    items: [
      { href: "/settings", label: "User Management", description: "Manage users, roles, permissions, and system settings", icon: Settings, capability: "view_settings" },
    ],
  },
];

function SidebarNav({ activePath, collapsed = false }: { activePath: string; collapsed?: boolean }) {
  const [role, setRole] = React.useState<AppRole>(() => getCurrentAppUser().role);
  const [accessSettings, setAccessSettings] = React.useState(() => getAccessSettings());
  React.useEffect(() => {
    const refresh = () => {
      setRole(getCurrentAppUser().role);
      setAccessSettings(getAccessSettings());
    };
    refresh();
    getCurrentAppUserRemote()
      .then((user) => {
        setCurrentAppUser(user);
        setRole(user.role);
      })
      .catch(() => undefined);
    getAccessSettingsRemote()
      .then((settings) => {
        const normalized = normalizeAccessSettings(settings);
        saveAccessSettings(normalized);
        setAccessSettings(normalized);
      })
      .catch(() => setAccessSettings(getAccessSettings()));
    window.addEventListener(USERS_CHANGED_EVENT, refresh);
    window.addEventListener(ACCESS_SETTINGS_CHANGED_EVENT, refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener(USERS_CHANGED_EVENT, refresh);
      window.removeEventListener(ACCESS_SETTINGS_CHANGED_EVENT, refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);
  const visibleSections = navSections
    .map((section) => ({ ...section, items: section.items.filter((item) => !item.capability || canRole(role, item.capability, accessSettings)) }))
    .filter((section) => section.items.length);
  return (
    <nav className={cn("space-y-5", collapsed && "space-y-4")}>
      {visibleSections.map((section) => (
        <div key={section.title} className="space-y-1">
          {!collapsed && <div className="px-3 text-[11px] font-semibold uppercase tracking-normal text-muted-foreground">{section.title}</div>}
          {section.items.map((item) => {
            const Icon = item.icon;
            const active = activePath === item.href;
            return (
              <Link
                key={`${section.title}-${item.href}-${item.label}`}
                href={item.href}
                className={cn(
                  "flex items-start gap-2 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                  collapsed && "justify-center px-2",
                  active && "bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground",
                )}
                title={collapsed ? item.description ? `${item.label} - ${item.description}` : item.label : undefined}
              >
                {item.step ? (
                  <span className={cn("mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[11px]", active ? "border-primary-foreground" : "border-border")}>{item.step}</span>
                ) : (
                  <Icon className="mt-0.5 h-4 w-4 shrink-0" />
                )}
                {!collapsed && (
                <span className="min-w-0">
                  <span className="block truncate">{item.label}</span>
                  {item.description && <span className={cn("block truncate text-[11px] font-normal", active ? "text-primary-foreground/80" : "text-muted-foreground")}>{item.description}</span>}
                </span>
                )}
              </Link>
            );
          })}
        </div>
      ))}
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
  const [role, setRole] = React.useState<AppRole>(() => getCurrentAppUser().role);
  const [accessSettings, setAccessSettings] = React.useState(() => getAccessSettings());
  const [sidebarCollapsed, setSidebarCollapsed] = React.useState(false);
  React.useEffect(() => {
    const refresh = () => {
      setRole(getCurrentAppUser().role);
      setAccessSettings(getAccessSettings());
    };
    refresh();
    getCurrentAppUserRemote()
      .then((user) => {
        setCurrentAppUser(user);
        setRole(user.role);
      })
      .catch(() => undefined);
    getAccessSettingsRemote()
      .then((settings) => {
        const normalized = normalizeAccessSettings(settings);
        saveAccessSettings(normalized);
        setAccessSettings(normalized);
      })
      .catch(() => setAccessSettings(getAccessSettings()));
    window.addEventListener(USERS_CHANGED_EVENT, refresh);
    window.addEventListener(ACCESS_SETTINGS_CHANGED_EVENT, refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener(USERS_CHANGED_EVENT, refresh);
      window.removeEventListener(ACCESS_SETTINGS_CHANGED_EVENT, refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);
  return (
    <div className="min-h-screen bg-background">
      <aside className={cn("fixed inset-y-0 left-0 hidden flex-col border-r bg-card lg:flex", sidebarCollapsed ? "w-16" : "w-72")}>
        <div className="flex h-16 items-center gap-3 border-b px-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <BarChart3 className="h-5 w-5" />
          </div>
          {!sidebarCollapsed && (
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold">GGPL Quote</div>
              <div className="truncate text-xs text-muted-foreground">Goodrich Gasket Pvt. Ltd.</div>
            </div>
          )}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          <SidebarNav activePath={activePath} collapsed={sidebarCollapsed} />
        </div>
      </aside>

      <div className={cn(sidebarCollapsed ? "lg:pl-16" : "lg:pl-72")}>
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b bg-background/95 px-4 backdrop-blur md:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              className="hidden lg:inline-flex"
              aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              onClick={() => setSidebarCollapsed((value) => !value)}
            >
              {sidebarCollapsed ? <PanelLeftOpen className="h-5 w-5" /> : <PanelLeftClose className="h-5 w-5" />}
            </Button>
            <Sheet>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open navigation">
                  <Menu className="h-5 w-5" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="flex flex-col overflow-hidden">
                <SheetHeader>
                  <SheetTitle>GGPL Quote</SheetTitle>
                </SheetHeader>
                <div className="mt-6 min-h-0 flex-1 overflow-y-auto pr-2">
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
            {canRole(role, "create_enquiry", accessSettings) && (
              <Button variant="secondary" size="sm" className="hidden md:inline-flex" asChild>
                <Link href="/quotes?new=1"><Plus className="h-4 w-4" />New enquiry</Link>
              </Button>
            )}
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
