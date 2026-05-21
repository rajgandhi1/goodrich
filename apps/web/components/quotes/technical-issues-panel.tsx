import { AlertTriangle, FileQuestion, Mail } from "lucide-react";

import type { GasketItem } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getString, notesFor } from "./item-validation";

type IssueGroup = {
  key: string;
  label: string;
  matches: (item: GasketItem) => boolean;
};

const groups: IssueGroup[] = [
  { key: "size", label: "Missing size / dimensions", matches: (item) => !getString(item.size || item.size_norm) && (!item.od_mm || !item.id_mm) },
  { key: "rating", label: "Missing class / rating / standard", matches: (item) => !getString(item.rating) && !getString(item.standard) },
  { key: "material", label: "Missing material / MOC", matches: (item) => !getString(item.moc) && !getString(item.sw_winding_material) && !getString(item.kamm_core_material) },
  { key: "spw", label: "Missing SW winding / filler / ring details", matches: (item) => getString(item.gasket_type).toUpperCase() === "SPIRAL_WOUND" && (!getString(item.sw_winding_material) || !getString(item.sw_filler)) },
  { key: "rtj", label: "Missing RTJ ring / groove / hardness", matches: (item) => getString(item.gasket_type).toUpperCase() === "RTJ" && (!getString(item.ring_no) || !getString(item.rtj_groove_type) || !item.rtj_hardness_bhn) },
  { key: "drawing", label: "Drawing required", matches: (item) => item.drawing_required === true || getString(item.clarification_note).toLowerCase().includes("drawing") },
  { key: "non_gasket", label: "Non-gasket items", matches: (item) => item.is_non_gasket === true || item.is_gasket === false },
  { key: "duplicate", label: "Duplicate likely", matches: (item) => Boolean(item.duplicate_group_id) },
  { key: "clarification", label: "Clarification notes", matches: (item) => Boolean(getString(item.clarification_note)) },
];

export function issueBadgesForItem(item: GasketItem): string[] {
  const badges: string[] = [];
  if (item.drawing_required === true || getString(item.clarification_note).toLowerCase().includes("drawing")) badges.push("Drawing");
  if (item.is_non_gasket === true || item.is_gasket === false) badges.push("Non-gasket");
  if (getString(item.clarification_note)) badges.push("Clarification");
  if (item.urgent === true) badges.push("Urgent");
  if (item.duplicate_group_id) badges.push("Duplicate");
  return badges;
}

export function technicalIssueSummary(items: GasketItem[]) {
  return groups.map((group) => ({
    ...group,
    rows: items
      .map((item, index) => ({ item, index }))
      .filter(({ item }) => item.status !== "regret" && group.matches(item)),
  })).filter((group) => group.rows.length);
}

export function TechnicalIssuesPanel({
  items,
  onSelectRow,
  onBuildClarification,
}: {
  items: GasketItem[];
  onSelectRow: (index: number) => void;
  onBuildClarification: () => void;
}) {
  const summary = technicalIssueSummary(items);
  const blockerCount = summary.reduce((sum, group) => sum + group.rows.length, 0);

  return (
    <div className="rounded-md border p-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium">
            <AlertTriangle className="h-4 w-4" />
            Technical review
          </div>
          <div className="mt-1 text-xs text-muted-foreground">{blockerCount} issue row(s) across {summary.length} group(s)</div>
        </div>
        <Button variant="secondary" size="sm" onClick={onBuildClarification}>
          <Mail className="h-4 w-4" />
          Build clarification
        </Button>
      </div>

      {!summary.length ? (
        <div className="mt-3 rounded-md bg-muted/30 p-3 text-sm text-muted-foreground">No grouped technical blockers found in active rows.</div>
      ) : (
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          {summary.map((group) => (
            <div key={group.key} className="rounded-md border bg-muted/20 p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-medium">{group.label}</div>
                <Badge variant={group.rows.length > 5 ? "warning" : "outline"}>{group.rows.length}</Badge>
              </div>
              <div className="mt-2 space-y-2">
                {group.rows.slice(0, 6).map(({ item, index }) => (
                  <button
                    key={`${group.key}-${index}`}
                    className="block w-full rounded-md border bg-background px-2 py-1.5 text-left text-xs hover:bg-muted"
                    onClick={() => onSelectRow(index)}
                    type="button"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">Line {getString(item.line_no) || index + 1}</span>
                      <span className="text-muted-foreground">{getString(item.gasket_type || "Gasket")}</span>
                    </div>
                    <div className="mt-1 line-clamp-2 text-muted-foreground">{notesFor(item) || getString(item.raw_description || item.ggpl_description) || "Review required"}</div>
                  </button>
                ))}
                {group.rows.length > 6 && <div className="text-xs text-muted-foreground">+ {group.rows.length - 6} more row(s)</div>}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="mt-3 flex flex-wrap gap-1.5">
        {["Drawing", "Non-gasket", "Clarification", "Urgent", "Duplicate"].map((label) => (
          <Badge key={label} variant="outline"><FileQuestion className="h-3 w-3" />{label}</Badge>
        ))}
      </div>
    </div>
  );
}
