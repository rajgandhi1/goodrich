import { Suspense } from "react";

import { AppShell } from "@/components/app-shell/app-shell";
import { QuotesClient } from "../quotes/quotes-client";

export default function MaterialPlanningPage() {
  return (
    <AppShell activePath="/material-planning" title="Material Planning" breadcrumb="Workspace / Material Planning">
      <Suspense fallback={<div className="rounded-md border p-4 text-sm text-muted-foreground">Loading material planning workspace...</div>}>
        <QuotesClient section="material" />
      </Suspense>
    </AppShell>
  );
}
