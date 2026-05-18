import { GasketItem } from "@/lib/api";

export const DEFAULT_SHEET_WIDTH_MM = 1250;
export const DEFAULT_SHEET_LENGTH_MM = 1500;
export const DEFAULT_NESTING_EFFICIENCY = 0.82;
const DEFAULT_SPW_METAL_FRACTION = 0.35;
const DEFAULT_SPW_FILLER_FRACTION = 0.3;
const DEFAULT_RING_RADIAL_ALLOWANCE_MM = 8;
const DEFAULT_RING_THICKNESS_MM = 3;

const DENSITIES_G_PER_CM3: Record<string, number> = {
  CS: 7.85,
  "CARBON STEEL": 7.85,
  "LOW CARBON STEEL": 7.85,
  LTCS: 7.85,
  SOFTIRON: 7.85,
  "SOFT IRON": 7.85,
  SS304: 7.9,
  SS304L: 7.9,
  SS316: 8.0,
  SS316L: 8.0,
  SS321: 8.0,
  SS347: 8.0,
  SS410: 7.75,
  "INCONEL 600": 8.47,
  "INCONEL 625": 8.44,
  "HASTELLOY C276": 8.89,
  "HASTELLOY C22": 8.69,
  "MONEL 400": 8.83,
  "INCOLOY 800": 7.94,
  "INCOLOY 825": 8.14,
  "ALLOY 20": 8.08,
  "CU-NI 70/30": 8.94,
  BRASS: 8.5,
  BRONZE: 8.8,
  TITANIUM: 4.51,
  "TITANIUM GR.2": 4.51,
  "TITANIUM GR.12": 4.54,
  ALUMINIUM: 2.7,
  ALUMINUM: 2.7,
  GRAPHITE: 1.2,
  PTFE: 2.2,
  TEFLON: 2.2,
  CNAF: 1.85,
  EPDM: 1.15,
  NEOPRENE: 1.35,
  NBR: 1.1,
  VITON: 1.85,
  MICA: 2.8,
  GRE: 1.85,
  G10: 1.85,
  G11: 1.85,
};

export type MaterialPlanRow = {
  reviewed: boolean;
  line_no: number;
  gasket_type: string;
  component: string;
  material: string;
  stock_form: string;
  width_mm: number | null;
  length_mm: number | null;
  stock_thickness_mm: number | null;
  quote_qty: number;
  quote_uom: string;
  od_mm: number | null;
  id_mm: number | null;
  thickness_mm: number | null;
  blank_area_m2: number;
  sheets_required: number;
  unit_weight_kg: number;
  total_weight_kg: number;
  density_g_cm3: number;
  basis: string;
  calculation_notes: string;
  planner_notes: string;
  description: string;
};

export type StockPlanRow = {
  reviewed: boolean;
  sl_no: number;
  type: string;
  width_mm: number | null;
  length_mm: number | string | null;
  thickness_mm: number | null;
  reqd_qty_sheets: number | null;
  reqd_qty_kg: number | null;
  notes: string;
  planner_notes: string;
  source_count: number;
};

export type MaterialPlan = {
  config: {
    sheet_width_mm: number;
    sheet_length_mm: number;
    nesting_efficiency: number;
  };
  rows: StockPlanRow[];
  summary: Array<{
    type: string;
    rows: number;
    sheets_required: number;
    total_weight_kg: number;
  }>;
  assumptions: string[];
  warnings: string[];
  totals: {
    component_count: number;
    sheet_count: number;
    total_weight_kg: number;
  };
};

export type MaterialPlanInputConfig = Partial<MaterialPlan["config"]>;

function text(value: unknown): string {
  return String(value ?? "").trim();
}

function num(value: unknown, fallback = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function density(material: string): number {
  const normalized = material.toUpperCase();
  if (DENSITIES_G_PER_CM3[normalized] !== undefined) {
    return DENSITIES_G_PER_CM3[normalized];
  }
  for (const [token, value] of Object.entries(DENSITIES_G_PER_CM3)) {
    if (token && normalized.includes(token)) {
      return value;
    }
  }
  return normalized.includes("SS") || normalized.includes("STEEL") || normalized.includes("INCONEL") ? 7.85 : 1.85;
}

function densityKgPerMm3(material: string): number {
  return density(material) / 1_000_000;
}

function materialName(value: unknown): string {
  const normalized = text(value).toUpperCase().replace(/\s+/g, " ");
  if (!normalized) return "UNSPECIFIED";
  if (normalized === "FLEXIBLE GRAPHITE" || normalized.includes("GRAPHITE")) return "GRAPHITE";
  if (normalized === "G-10" || normalized === "GRE G-10" || normalized === "GRE G10") return "G10";
  if (normalized === "G-11" || normalized === "GRE G-11" || normalized === "GRE G11") return "G11";
  return normalized;
}

function positive(value: unknown, fallback: number): number {
  const parsed = num(value, NaN);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function npsValue(size: unknown): number | null {
  const raw = text(size).replace(/["']/g, "").trim();
  if (!raw) return null;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : null;
}

function annulusAreaMm2(odMm: number, idMm: number): number {
  if (!odMm || !idMm || odMm <= idMm) return 0;
  return (Math.PI * (odMm ** 2 - idMm ** 2)) / 4;
}

function blankAreaMm2(odMm: number): number {
  return Math.max(odMm, 0) ** 2;
}

function annulusWeightKg(odMm: number, idMm: number, thicknessMm: number, material: string): number {
  return annulusAreaMm2(odMm, idMm) * Math.max(thicknessMm, 0) * densityKgPerMm3(material);
}

function sheetsRequired(areaMm2: number, sheetWidthMm: number, sheetLengthMm: number, nestingEfficiency: number): number {
  const usable = sheetWidthMm * sheetLengthMm * nestingEfficiency;
  if (areaMm2 <= 0 || usable <= 0) return 0;
  return Math.ceil(areaMm2 / usable);
}

function baseRow(item: GasketItem, component: string, material: string, stockForm: string, note: string): MaterialPlanRow {
  return {
    reviewed: false,
    line_no: num(item.line_no, 0),
    gasket_type: text(item.gasket_type || "SOFT_CUT"),
    component,
    material,
    stock_form: stockForm,
    width_mm: null,
    length_mm: null,
    stock_thickness_mm: null,
    quote_qty: positive(item.quantity, 1),
    quote_uom: text(item.uom || "NOS") || "NOS",
    od_mm: null,
    id_mm: null,
    thickness_mm: null,
    blank_area_m2: 0,
    sheets_required: 0,
    unit_weight_kg: 0,
    total_weight_kg: 0,
    density_g_cm3: density(material),
    basis: note,
    calculation_notes: "",
    planner_notes: "",
    description: text(item.ggpl_description || item.raw_description),
  };
}

function profileSheetStock(material: string, row: MaterialPlanRow, config: MaterialPlan["config"]): { width_mm: number; length_mm: number; thickness_mm: number } {
  const upper = material.toUpperCase();
  const quotedThickness = row.stock_thickness_mm ?? row.thickness_mm;
  const fallbackThickness = upper.includes("GRAPHITE") ? 1.5 : 3;
  return {
    width_mm: config.sheet_width_mm,
    length_mm: config.sheet_length_mm,
    thickness_mm: positive(quotedThickness, fallbackThickness),
  };
}

function profileCoilStock(component: string, material: string, sourceSize: unknown): { width_mm: number | null; length_mm: number | string | null; thickness_mm: number } {
  const type = component.toUpperCase();
  const size = npsValue(sourceSize);
  if (type.includes("WINDING")) {
    return {
      width_mm: size && size <= 2.5 ? 3.6 : 4.8,
      length_mm: "COIL",
      thickness_mm: 0.2,
    };
  }
  if (type.includes("FILLER")) {
    return {
      width_mm: size && size <= 2.5 ? 5.5 : 6.0,
      length_mm: "COIL",
      thickness_mm: material.includes("VERMICULITE") ? 0.5 : 1.0,
    };
  }
  if (type.includes("RING")) {
    return {
      width_mm: null,
      length_mm: null,
      thickness_mm: 3,
    };
  }
  return { width_mm: null, length_mm: null, thickness_mm: 3 };
}

function toStockType(row: MaterialPlanRow): string {
  const component = row.component.toUpperCase();
  const material = row.material.toUpperCase();
  if (component.includes("WINDING")) return `${material} WINDING`;
  if (component.includes("FILLER")) return `FILLER ${material}`;
  if (component.includes("RTJ")) return `${material} RING BLANK`;
  if (component.includes("KAMMPROFILE")) return `${material} SHEET`;
  if (component.includes("DOUBLE-JACKET")) return `${material} SHEET`;
  if (component.includes("ISK")) return `${material} SHEET`;
  return `${material} SHEET`;
}

function thicknessLabel(value: number): string {
  return Number.isInteger(value) ? `${value.toFixed(1)}` : `${value}`;
}

function addRow(rows: MaterialPlanRow[], row: MaterialPlanRow): void {
  row.total_weight_kg = row.unit_weight_kg * row.quote_qty;
  rows.push(row);
}

function planSoftCut(item: GasketItem, config: MaterialPlan["config"], assumptions: Set<string>, warnings: string[]): MaterialPlanRow[] {
  const odMm = num((item as Record<string, unknown>).od_mm, NaN);
  const idMm = num((item as Record<string, unknown>).id_mm, NaN);
  const thkMm = positive((item as Record<string, unknown>).thickness_mm, 3);
  const mat = materialName(item.moc || "UNSPECIFIED");
  const qty = positive(item.quantity, 1);
  if (!odMm || !idMm || odMm <= idMm) {
    warnings.push(`Line ${num(item.line_no, 0) || "?"}: soft-cut OD/ID missing, so weight is only a placeholder.`);
    const row = baseRow(item, "Soft-cut sheet blank", mat, "Sheet blank", "OD/ID required");
    row.quote_qty = qty;
    return [row];
  }
  assumptions.add(`Line ${num(item.line_no, 0) || "?"} dimensions were taken from the quote item.`);
  const row = baseRow(item, "Soft-cut sheet blank", mat, "Sheet blank", "Annular gasket from sheet");
  row.od_mm = odMm;
  row.id_mm = idMm;
  row.thickness_mm = thkMm;
  row.blank_area_m2 = blankAreaMm2(odMm) / 1_000_000;
  row.sheets_required = sheetsRequired(blankAreaMm2(odMm) * qty, config.sheet_width_mm, config.sheet_length_mm, config.nesting_efficiency);
  row.unit_weight_kg = annulusWeightKg(odMm, idMm, thkMm, mat);
  row.calculation_notes = "Sheet consumption uses a square OD blank. Weight uses annular area.";
  return [row];
}

function planRtj(item: GasketItem, assumptions: Set<string>, warnings: string[]): MaterialPlanRow[] {
  const qty = positive(item.quantity, 1);
  const material = materialName(item.moc || "UNSPECIFIED");
  const size = npsValue((item as Record<string, unknown>).size ?? (item as Record<string, unknown>).size_norm);
  const ringNo = text(item.ring_no);
  const ringNum = Number.parseFloat(ringNo.replace(/^[A-Z-]+/i, "").replace(/[^0-9.]/g, ""));
  const meanDiaMm = size ? size * 25.4 + 35 : Number.isFinite(ringNum) ? 12 + ringNum * 5 : 150;
  const crossSectionMm2 = ringNo.toUpperCase().startsWith("BX")
    ? 14 * 18
    : size && size <= 2
      ? 6 * 8
      : size && size <= 8
        ? 8 * 11
        : size && size <= 16
          ? 10 * 13
          : 12 * 16;
  const row = baseRow(item, "RTJ ring blank", material, "Forged/rolled ring", "CNC ring blank");
  row.unit_weight_kg = Math.PI * meanDiaMm * crossSectionMm2 * densityKgPerMm3(material);
  row.quote_qty = qty;
  row.stock_form = "Forged/rolled ring";
  row.calculation_notes = `Mean diameter ${meanDiaMm.toFixed(1)} mm, section ${crossSectionMm2.toFixed(1)} mm2.`;
  if (!ringNo) {
    warnings.push(`Line ${num(item.line_no, 0) || "?"}: RTJ ring number is missing, so the estimate is only a starter plan.`);
  }
  assumptions.add("RTJ weight is an approximate ring-blank estimate for CNC machining.");
  return [row];
}

function ringRow(item: GasketItem, component: string, materialRaw: unknown, boundaryDiaMm: number, note: string): MaterialPlanRow {
  const material = materialName(materialRaw || "UNSPECIFIED");
  const row = baseRow(item, component, material, "Ring strip/blank", note);
  const radiusAllowance = DEFAULT_RING_RADIAL_ALLOWANCE_MM;
  row.od_mm = boundaryDiaMm + radiusAllowance;
  row.id_mm = Math.max(boundaryDiaMm - radiusAllowance, 0);
  row.thickness_mm = DEFAULT_RING_THICKNESS_MM;
  row.unit_weight_kg = annulusWeightKg(row.od_mm, row.id_mm, DEFAULT_RING_THICKNESS_MM, material);
  row.calculation_notes = `Default ${radiusAllowance} mm radial ring allowance.`;
  return row;
}

function planSpw(item: GasketItem, config: MaterialPlan["config"], assumptions: Set<string>, warnings: string[]): MaterialPlanRow[] {
  const odMm = num((item as Record<string, unknown>).od_mm, NaN);
  const idMm = num((item as Record<string, unknown>).id_mm, NaN);
  const thkMm = positive((item as Record<string, unknown>).thickness_mm, 4.5);
  const rows: MaterialPlanRow[] = [];
  const winding = materialName((item as Record<string, unknown>).sw_winding_material || item.moc || "UNSPECIFIED");
  const filler = materialName((item as Record<string, unknown>).sw_filler || "GRAPHITE");
  if (!odMm || !idMm || odMm <= idMm) {
    warnings.push(`Line ${num(item.line_no, 0) || "?"}: spiral wound OD/ID missing, so winding and filler weights are only placeholders.`);
    addRow(rows, baseRow(item, "SPW winding strip", winding, "Strip coil", "OD/ID required"));
    addRow(rows, baseRow(item, "SPW filler tape", filler, "Filler tape", "OD/ID required"));
    return rows;
  }
  assumptions.add("Spiral wound estimate uses the gasket OD/ID envelope with default compaction fractions.");
  const windingRow = baseRow(item, "SPW winding strip", winding, "Strip coil", "Winding metal");
  windingRow.od_mm = odMm;
  windingRow.id_mm = idMm;
  windingRow.thickness_mm = thkMm;
  windingRow.unit_weight_kg = annulusAreaMm2(odMm, idMm) * thkMm * DEFAULT_SPW_METAL_FRACTION * densityKgPerMm3(winding);
  windingRow.calculation_notes = `${Math.round(DEFAULT_SPW_METAL_FRACTION * 100)}% compacted metal fraction.`;
  addRow(rows, windingRow);

  const fillerRow = baseRow(item, "SPW filler tape", filler, "Filler tape", "Compressed filler");
  fillerRow.od_mm = odMm;
  fillerRow.id_mm = idMm;
  fillerRow.thickness_mm = thkMm;
  fillerRow.unit_weight_kg = annulusAreaMm2(odMm, idMm) * thkMm * DEFAULT_SPW_FILLER_FRACTION * densityKgPerMm3(filler);
  fillerRow.calculation_notes = `${Math.round(DEFAULT_SPW_FILLER_FRACTION * 100)}% compacted filler fraction.`;
  addRow(rows, fillerRow);

  const innerRing = text((item as Record<string, unknown>).sw_inner_ring);
  const outerRing = text((item as Record<string, unknown>).sw_outer_ring);
  if (innerRing) {
    addRow(rows, ringRow(item, "SPW inner ring", innerRing, idMm, "ID support ring"));
  }
  if (outerRing) {
    addRow(rows, ringRow(item, "SPW outer ring", outerRing, odMm, "Centering ring"));
  }
  return rows;
}

function planKamm(item: GasketItem, config: MaterialPlan["config"], assumptions: Set<string>, warnings: string[]): MaterialPlanRow[] {
  const odMm = num((item as Record<string, unknown>).od_mm, NaN);
  const idMm = num((item as Record<string, unknown>).id_mm, NaN);
  const thkMm = positive((item as Record<string, unknown>).kamm_core_thk ?? (item as Record<string, unknown>).thickness_mm, 3);
  const qty = positive(item.quantity, 1);
  const core = materialName((item as Record<string, unknown>).kamm_core_material || item.moc || "UNSPECIFIED");
  const surface = materialName((item as Record<string, unknown>).kamm_surface_material || (item as Record<string, unknown>).kamm_covering_layer || "GRAPHITE");
  if (!odMm || !idMm || odMm <= idMm) {
    warnings.push(`Line ${num(item.line_no, 0) || "?"}: Kammprofile OD/ID missing, so weight is only a placeholder.`);
    return [baseRow(item, "Kammprofile core", core, "Plate/ring blank", "OD/ID required")];
  }
  assumptions.add("Kammprofile weight uses the gasket annulus and a starter covering allowance.");
  const rows: MaterialPlanRow[] = [];
  const coreRow = baseRow(item, "Kammprofile core", core, "Plate/ring blank", "Grooved core");
  coreRow.od_mm = odMm;
  coreRow.id_mm = idMm;
  coreRow.thickness_mm = thkMm;
  coreRow.blank_area_m2 = blankAreaMm2(odMm) / 1_000_000;
  coreRow.sheets_required = sheetsRequired(blankAreaMm2(odMm) * qty, config.sheet_width_mm, config.sheet_length_mm, config.nesting_efficiency);
  coreRow.unit_weight_kg = annulusWeightKg(odMm, idMm, thkMm, core);
  coreRow.calculation_notes = "Core weight uses annular area and core thickness.";
  addRow(rows, coreRow);

  const coverRow = baseRow(item, "Kammprofile covering", surface, "Facing sheet/tape", "Both-side covering");
  coverRow.od_mm = odMm;
  coverRow.id_mm = idMm;
  coverRow.thickness_mm = 0.5;
  coverRow.unit_weight_kg = annulusWeightKg(odMm, idMm, 1, surface);
  coverRow.calculation_notes = "Uses a 0.5 mm equivalent covering allowance per side.";
  addRow(rows, coverRow);
  return rows;
}

function planDji(item: GasketItem, warnings: string[]): MaterialPlanRow[] {
  const odMm = num((item as Record<string, unknown>).od_mm, NaN);
  const idMm = num((item as Record<string, unknown>).id_mm, NaN);
  const thkMm = positive((item as Record<string, unknown>).thickness_mm, 3);
  const jacket = materialName(item.moc || "UNSPECIFIED");
  const filler = materialName((item as Record<string, unknown>).dji_filler || "GRAPHITE");
  if (!odMm || !idMm || odMm <= idMm) {
    warnings.push(`Line ${num(item.line_no, 0) || "?"}: double-jacket OD/ID missing, so the estimate is only a placeholder.`);
    return [baseRow(item, "Double-jacket shell", jacket, "Sheet", "OD/ID required")];
  }
  const rows: MaterialPlanRow[] = [];
  const shell = baseRow(item, "Double-jacket shell", jacket, "Sheet", "Metal jacket");
  shell.od_mm = odMm;
  shell.id_mm = idMm;
  shell.thickness_mm = thkMm;
  shell.unit_weight_kg = annulusWeightKg(odMm, idMm, thkMm * 0.35, jacket);
  shell.calculation_notes = "Metal jacket uses 35% of nominal thickness.";
  addRow(rows, shell);

  const fillerRow = baseRow(item, "Double-jacket filler", filler, "Filler sheet", "Inner filler");
  fillerRow.od_mm = odMm;
  fillerRow.id_mm = idMm;
  fillerRow.thickness_mm = thkMm * 0.65;
  fillerRow.unit_weight_kg = annulusWeightKg(odMm, idMm, thkMm * 0.65, filler);
  fillerRow.calculation_notes = "Filler uses 65% of nominal thickness.";
  addRow(rows, fillerRow);
  return rows;
}

function planIsk(item: GasketItem, warnings: string[]): MaterialPlanRow[] {
  const odMm = num((item as Record<string, unknown>).od_mm, NaN);
  const idMm = num((item as Record<string, unknown>).id_mm, NaN);
  const qty = positive(item.quantity, 1);
  const gasketMat = materialName((item as Record<string, unknown>).isk_gasket_material || item.moc || "PTFE");
  if (!odMm || !idMm || odMm <= idMm) {
    warnings.push(`Line ${num(item.line_no, 0) || "?"}: insulating gasket OD/ID missing, so the estimate is only a placeholder.`);
    return [baseRow(item, "ISK gasket", gasketMat, "Kit component", "OD/ID required")];
  }
  const row = baseRow(item, "ISK gasket", gasketMat, "Kit component", "Insulating gasket kit");
  row.od_mm = odMm;
  row.id_mm = idMm;
  row.thickness_mm = 3;
  row.unit_weight_kg = annulusWeightKg(odMm, idMm, 3, gasketMat);
  row.blank_area_m2 = blankAreaMm2(odMm) / 1_000_000;
  row.sheets_required = 0;
  row.calculation_notes = "Kit hardware counts are not estimated here; gasket ring only is weighted.";
  row.quote_qty = qty;
  const rows = [row];
  const sleeve = (item as Record<string, unknown>).isk_sleeve_material;
  const washer = (item as Record<string, unknown>).isk_washer_material;
  if (sleeve) rows.push(baseRow(item, "ISK sleeves", materialName(sleeve), "Kit component", "Bolt count needed"));
  if (washer) rows.push(baseRow(item, "ISK washers", materialName(washer), "Kit component", "Bolt count needed"));
  return rows;
}

function groupSummary(rows: StockPlanRow[]) {
  const summaryMap = new Map<string, { type: string; rows: number; sheets_required: number; total_weight_kg: number }>();
  for (const row of rows) {
    const current = summaryMap.get(row.type) ?? {
      type: row.type,
      rows: 0,
      sheets_required: 0,
      total_weight_kg: 0,
    };
    current.rows += 1;
    current.sheets_required += row.reqd_qty_sheets ?? 0;
    current.total_weight_kg += row.reqd_qty_kg ?? 0;
    summaryMap.set(row.type, current);
  }
  return Array.from(summaryMap.values()).sort((a, b) => a.type.localeCompare(b.type));
}

function toStockRows(componentRows: MaterialPlanRow[], config: MaterialPlan["config"]): StockPlanRow[] {
  const grouped = new Map<string, {
    type: string;
    width_mm: number | null;
    length_mm: number | string | null;
    thickness_mm: number | null;
    reqd_qty_sheets: number | null;
    reqd_qty_kg: number | null;
    notes: Set<string>;
    planner_notes: string;
    source_count: number;
  }>();

  for (const row of componentRows) {
    const component = row.component.toUpperCase();
    const material = row.material.toUpperCase();
    let profile: { width_mm: number | null; length_mm: number | string | null; thickness_mm: number | null; reqd_qty_sheets: number | null; reqd_qty_kg: number | null; notes: string } | null = null;

    if (component.includes("WINDING") || component.includes("FILLER")) {
      const coil = profileCoilStock(row.component, row.material, row.description || row.line_no);
      profile = {
        width_mm: coil.width_mm,
        length_mm: coil.length_mm,
        thickness_mm: coil.thickness_mm,
        reqd_qty_sheets: null,
        reqd_qty_kg: row.total_weight_kg,
        notes: row.calculation_notes || row.basis,
      };
    } else if (component.includes("RTJ")) {
      profile = {
        width_mm: null,
        length_mm: null,
        thickness_mm: 3,
        reqd_qty_sheets: null,
        reqd_qty_kg: row.total_weight_kg,
        notes: row.calculation_notes || row.basis,
      };
    } else {
      const stock = profileSheetStock(material, row, config);
      const totalBlankMm2 = row.blank_area_m2 > 0 ? row.blank_area_m2 * 1_000_000 * row.quote_qty : 0;
      const sheets = totalBlankMm2 > 0
        ? sheetsRequired(totalBlankMm2, stock.width_mm, stock.length_mm, config.nesting_efficiency)
        : null;
      const kgPerSheet = stock.width_mm * stock.length_mm * stock.thickness_mm * densityKgPerMm3(material);
      profile = {
        width_mm: stock.width_mm,
        length_mm: stock.length_mm,
        thickness_mm: stock.thickness_mm,
        reqd_qty_sheets: sheets,
        reqd_qty_kg: sheets === null ? (row.total_weight_kg || null) : sheets * kgPerSheet,
        notes: [row.calculation_notes || row.basis, sheets === null ? "OD/ID missing; sheet count cannot be calculated." : ""].filter(Boolean).join(" "),
      };
    }

    const stockType = component.includes("WINDING") || component.includes("FILLER") || component.includes("RTJ")
      ? toStockType(row)
      : `${material} ${thicknessLabel(profile.thickness_mm ?? 0)} SHEET`;
    const key = `${stockType}|${profile.width_mm ?? ""}|${profile.length_mm ?? ""}|${profile.thickness_mm ?? ""}`;
    const current = grouped.get(key) ?? {
      type: stockType,
      width_mm: profile.width_mm,
      length_mm: profile.length_mm,
      thickness_mm: profile.thickness_mm,
      reqd_qty_sheets: profile.reqd_qty_sheets,
      reqd_qty_kg: profile.reqd_qty_kg,
      notes: new Set<string>(),
      planner_notes: "",
      source_count: 0,
    };
    current.source_count += 1;
    if (profile.reqd_qty_sheets !== null) {
      current.reqd_qty_sheets = (current.reqd_qty_sheets ?? 0) + profile.reqd_qty_sheets;
    }
    if (profile.reqd_qty_kg !== null) {
      current.reqd_qty_kg = (current.reqd_qty_kg ?? 0) + profile.reqd_qty_kg;
    }
    current.notes.add(profile.notes);
    grouped.set(key, current);
  }

  return Array.from(grouped.values()).map((row, index) => ({
    reviewed: false,
    sl_no: index + 1,
    type: row.type,
    width_mm: row.width_mm,
    length_mm: row.length_mm,
    thickness_mm: row.thickness_mm,
    reqd_qty_sheets: row.reqd_qty_sheets,
    reqd_qty_kg: row.reqd_qty_kg,
    notes: Array.from(row.notes).filter(Boolean).join("; "),
    planner_notes: "",
    source_count: row.source_count,
  }));
}

export function buildMaterialPlan(items: GasketItem[], inputConfig: MaterialPlanInputConfig = {}): MaterialPlan {
  const sheetWidthMm = positive(inputConfig.sheet_width_mm, DEFAULT_SHEET_WIDTH_MM);
  const sheetLengthMm = positive(inputConfig.sheet_length_mm, DEFAULT_SHEET_LENGTH_MM);
  const nestingEfficiency = Math.max(0.1, Math.min(positive(inputConfig.nesting_efficiency, DEFAULT_NESTING_EFFICIENCY), 1));
  const config = {
    sheet_width_mm: sheetWidthMm,
    sheet_length_mm: sheetLengthMm,
    nesting_efficiency: nestingEfficiency,
  };
  const componentRows: MaterialPlanRow[] = [];
  const assumptions = new Set<string>([
    `Sheet rows use ${sheetWidthMm} x ${sheetLengthMm} mm stock and ${Math.round(nestingEfficiency * 100)}% nesting efficiency.`,
    "Coil, filler, and forged or rolled ring rows are weight-based; sheet dimensions are not applied to those stock forms.",
    "Quantities are planning estimates and should be checked against approved drawings, nesting, and available stock.",
  ]);
  const warnings: string[] = [];

  for (const item of items) {
    if (item.regret || item.status === "regret") continue;
    const type = text(item.gasket_type || "SOFT_CUT").toUpperCase();
    let planned: MaterialPlanRow[] = [];
    if (type === "RTJ") planned = planRtj(item, assumptions, warnings);
    else if (type === "SPIRAL_WOUND") planned = planSpw(item, config, assumptions, warnings);
    else if (type === "KAMM") planned = planKamm(item, config, assumptions, warnings);
    else if (type === "DJI") planned = planDji(item, warnings);
    else if (type === "ISK" || type === "ISK_RTJ") planned = planIsk(item, warnings);
    else planned = planSoftCut(item, config, assumptions, warnings);
    componentRows.push(...planned);
  }

  const rows = toStockRows(componentRows, config);

  return {
    config,
    rows,
    summary: groupSummary(rows),
    assumptions: Array.from(assumptions),
    warnings,
    totals: {
      component_count: rows.length,
      sheet_count: rows.reduce((sum, row) => sum + (row.reqd_qty_sheets || 0), 0),
      total_weight_kg: rows.reduce((sum, row) => sum + (row.reqd_qty_kg || 0), 0),
    },
  };
}
