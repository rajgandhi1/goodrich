import { Clock3 } from "lucide-react";

import type { Quote } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { quoteTimelineEvents } from "./activity-utils";

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function QuoteTimeline({ quote }: { quote: Quote | null }) {
  const events = quoteTimelineEvents(quote).slice(0, 10);
  return (
    <details className="rounded-md border p-3">
      <summary className="cursor-pointer text-sm font-medium">
        <span className="inline-flex items-center gap-2"><Clock3 className="h-4 w-4" />Quote timeline</span>
      </summary>
      <div className="mt-3 space-y-2">
        {events.map((event) => (
          <div key={event.id} className="grid gap-2 rounded-md border bg-muted/20 p-2 text-sm md:grid-cols-[160px_110px_1fr]">
            <div className="text-xs text-muted-foreground">{formatDate(event.at)}</div>
            <Badge variant="outline">{event.kind}</Badge>
            <div>
              <div className="font-medium">{event.title}</div>
              <div className="mt-1 text-xs text-muted-foreground">{event.detail || "No detail recorded"}</div>
            </div>
          </div>
        ))}
        {!events.length && <div className="text-sm text-muted-foreground">No timeline events recorded yet.</div>}
      </div>
    </details>
  );
}
