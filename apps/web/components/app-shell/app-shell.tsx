import Link from "next/link";
import { BarChart3, Calculator, FileCheck2, FileQuestion, FileText, Layers3, LayoutDashboard, Menu, Settings } from "lucide-react";

import { ThemeToggle } from "@/components/app-shell/theme-toggle";
import { UserMenu } from "@/components/app-shell/user-menu";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

type NavItem = {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
};

const navItems: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/quotes", label: "Drafts", icon: FileText },
  { href: "/material-planning", label: "Material Planning", icon: Layers3 },
  { href: "/quotes/final", label: "Final Quotation", icon: FileCheck2 },
  { href: "/tools/converter", label: "Converter", icon: Calculator },
  { href: "/doc-assistant", label: "Doc Assistant", icon: FileQuestion },
  { href: "/settings", label: "Settings", icon: Settings },
];

function SidebarNav({ activePath }: { activePath: string }) {
  return (
    <nav className="space-y-1">
      {navItems.map((item) => {
        const Icon = item.icon;
        const active = activePath === item.href;
        return (
          <Link
            key={item.href}
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
