import { GasketItem, toNumber } from "@/lib/api";

export function getString(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.join("; ");
  return String(value);
}

export function hasText(value: unknown): boolean {
  return getString(value).trim().length > 0;
}

export function itemHasMaterial(item: GasketItem): boolean {
  return [
    item.moc,
    item.sw_winding_material,
    item.sw_filler,
    item.sw_inner_ring,
    item.sw_outer_ring,
    item.rtj_hardness_spec,
    item.isk_gasket_material,
    item.isk_core_material,
    item.kamm_core_material,
    item.kamm_surface_material,
    item.dji_filler,
  ].some(hasText);
}

export function itemHasSize(item: GasketItem): boolean {
  return hasText(item.size) || hasText(item.size_norm) || Boolean(item.od_mm && item.id_mm) || hasText(item.ring_no);
}

function uniqueNotes(notes: string[]): string[] {
  return Array.from(new Set(notes.map((note) => note.trim()).filter(Boolean)));
}

function isSheetStyleType(type: string): boolean {
  return ["SOFT_CUT", "SHEET_GASKET", "CORRUGATED", "PLUG_GASKET"].includes(type);
}

export function derivedNotesFor(item: GasketItem): string[] {
  const notes: string[] = [];
  const type = getString(item.gasket_type).toUpperCase();
  const status = getString(item.status);

  if (!hasText(item.raw_description) && !hasText(item.ggpl_description)) {
    notes.push("Customer description is empty");
  }
  if (!hasText(type)) {
    notes.push("Gasket type missing");
  }
  if (!itemHasSize(item)) {
    notes.push("Size/dimensions missing");
  }
  if (!itemHasMaterial(item)) {
    notes.push("Material/MOC missing or unclear");
  }
  if (!hasText(item.rating) && !hasText(item.standard) && type !== "RTJ") {
    notes.push("Rating/standard missing");
  }
  if (toNumber(item.quantity, 0) <= 0) {
    notes.push("Quantity missing or zero");
  }

  if (isSheetStyleType(type)) {
    if (!hasText(item.thickness_mm)) notes.push("Thickness missing");
    if (type !== "PLUG_GASKET" && !hasText(item.face_type)) notes.push("Face type missing");
  }
  if (type === "SPIRAL_WOUND") {
    if (!hasText(item.sw_winding_material)) notes.push("SW winding material missing");
    if (!hasText(item.sw_filler)) notes.push("SW filler missing");
    if (!hasText(item.sw_outer_ring)) notes.push("SW outer ring missing");
    if (!hasText(item.sw_inner_ring)) notes.push("SW inner ring not specified - confirm if required");
  }
  if (type === "RTJ") {
    if (!hasText(item.ring_no)) notes.push("RTJ ring number missing");
    if (!hasText(item.rtj_groove_type)) notes.push("RTJ groove type missing");
    if (!hasText(item.rtj_hardness_bhn) && !hasText(item.rtj_hardness_spec)) notes.push("RTJ hardness missing");
  }
  if (type === "KAMM") {
    if (!hasText(item.kamm_core_material)) notes.push("Kamm core material missing");
    if (!hasText(item.kamm_surface_material) && !hasText(item.kamm_covering_layer)) notes.push("Kamm facing/surface material missing");
  }
  if (type === "DJI") {
    if (!hasText(item.od_mm) || !hasText(item.id_mm)) notes.push("DJI OD/ID dimensions missing");
    if (!hasText(item.dji_filler)) notes.push("DJI filler missing");
    if (!hasText(item.thickness_mm)) notes.push("DJI thickness missing");
  }
  if (type === "ISK" || type === "ISK_RTJ") {
    if (!hasText(item.isk_gasket_material)) notes.push("ISK gasket material missing");
    if (!hasText(item.isk_core_material)) notes.push("ISK core material missing");
    if (!hasText(item.isk_sleeve_material)) notes.push("ISK sleeve material missing");
    if (!hasText(item.isk_primary_seal)) notes.push("ISK primary seal missing");
  }

  if (!notes.length && status === "missing") {
    notes.push("Marked missing by rules - review row fields");
  }
  if (!notes.length && status === "check") {
    notes.push("Review required - defaults, assumptions, or non-standard detail may be present");
  }
  return uniqueNotes(notes);
}

export function notesFor(item: GasketItem): string {
  const flags = Array.isArray(item.flags) ? item.flags : [];
  const defaults = Array.isArray(item.applied_defaults) ? (item.applied_defaults as unknown[]) : [];
  const notes = [
    ...flags.map(String),
    ...defaults.map((value) => `[default] ${String(value)}`),
    ...derivedNotesFor(item).map((value) => `[missing] ${value}`),
  ];
  return uniqueNotes(notes).join("; ");
}

export type CellValidation = {
  severity: "blocker" | "review" | "optional";
  message: string;
};

export function validateItemField(item: GasketItem, field: string): CellValidation | null {
  const type = getString(item.gasket_type).toUpperCase();
  if ((field === "size" || field === "size_norm" || field === "od_mm" || field === "id_mm" || field === "ring_no") && !itemHasSize(item)) {
    return { severity: "blocker", message: "Size or dimensions required" };
  }
  if ((field === "moc" || field.includes("material") || field.includes("filler")) && !itemHasMaterial(item)) {
    return { severity: "review", message: "Material unclear" };
  }
  if ((field === "rating" || field === "standard") && !hasText(item.rating) && !hasText(item.standard) && type !== "RTJ") {
    return { severity: "review", message: "Rating or standard required" };
  }
  if (field === "quantity" && toNumber(item.quantity, 0) <= 0) {
    return { severity: "blocker", message: "Quantity must be greater than zero" };
  }
  if (type === "SPIRAL_WOUND" && ["sw_winding_material", "sw_filler"].includes(field) && !hasText(item[field])) {
    return { severity: "review", message: "Spiral wound material detail required" };
  }
  if (type === "RTJ" && ["rtj_groove_type", "ring_no", "rtj_hardness_bhn"].includes(field) && !hasText(item[field])) {
    return { severity: "review", message: "RTJ detail should be checked" };
  }
  return null;
}
