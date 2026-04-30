import type { CaseInput, FieldErrors, IntakeMode } from "@/lib/types";

const VAGUE_ONE_WORD = new Set([
  "saas",
  "b2b",
  "b2c",
  "d2c",
  "shop",
  "store",
  "app",
  "startup",
  "retail",
  "ecommerce",
  "agency",
  "consulting",
]);

const WEAK_REVENUE = /^(n\/a|na|unknown|not\s*sure|tbd|unsure|none)\s*$/i;

function hasAmountSignal(text: string): boolean {
  if (!text.trim()) return false;
  return (
    WEAK_REVENUE.test(text) ||
    /\d/.test(text) ||
    /[\$£€]/.test(text) ||
    /\b(arr|mrr|revenue)\b/i.test(text) ||
    /\b\d*[.]?\d*\s*[kmb]\b/i.test(text) ||
    /\b(million|thousand|billion)\b/i.test(text)
  );
}

export function normalizeRevenuePeriod(text: string): string {
  const t = text.trim().toLowerCase();
  if (/\b(annual|yearly|per\s*year|each\s*year|a\s*year)\b/.test(t) || t === "year") return "annual";
  if (/\b(quarterly|each\s*quarter|per\s*quarter|q[1-4])\b/.test(t) || t === "quarter") return "quarterly";
  if (/\b(monthly|each\s*month|per\s*month|a\s*month)\b/.test(t) || t === "month") return "monthly";
  if (/\b(weekly|each\s*week|per\s*week|a\s*week)\b/.test(t) || t === "week") return "weekly";
  return text.trim();
}

export function normalizeProfitType(text: string): string {
  const t = text.trim().toLowerCase();
  if (/break[\s-]?even|breakeven/.test(t)) return "break-even";
  if (/\bloss\b|losing|\blose\b/.test(t)) return "loss";
  if (/\bprofit\b|profitable/.test(t)) return "profit";
  return text.trim();
}

export function normalizeHeadcount(text: string): string {
  const m = text.replace(/,/g, "").match(/\d+/);
  return m ? m[0] : text.trim();
}

export function validateField(
  mode: IntakeMode,
  field: keyof CaseInput,
  value: string,
): string | undefined {
  const t = value.trim();
  if (field === "business_model") {
    if (!t) return "Please describe what the company does and how it makes money.";
    const words = t.toLowerCase().split(/\s+/).filter(Boolean);
    if (words.length < 2 && (VAGUE_ONE_WORD.has(words[0] ?? "") || (words[0] ?? "").length <= 4)) {
      return "Please expand this. Example: B2B SaaS selling HR software by subscription.";
    }
  }
  if (field === "revenue_amount" && !hasAmountSignal(t)) {
    return "Revenue should include a number, e.g. $1M ARR or 500k yearly.";
  }
  if (field === "revenue_period" && (mode !== "quick" || t)) {
    if (!t && mode !== "quick") return "Revenue period must be weekly, monthly, quarterly, or annual.";
    if (t && !["weekly", "monthly", "quarterly", "annual", "yearly", "year", "month", "week", "quarter"].some((v) => t.includes(v))) {
      return "Revenue period must be weekly, monthly, quarterly, or annual.";
    }
  }
  if (field === "profit_or_loss_type") {
    if (!/\b(profit|profitable|loss|losing|break-even|breakeven)\b/i.test(t)) {
      return "Use profit, loss, break-even, profitable, or losing.";
    }
  }
  if (field === "profit_or_loss_amount" && !hasAmountSignal(t)) {
    return "Profit/loss amount should include a number or scale.";
  }
  if (field === "headcount") {
    const m = t.replace(/,/g, "").match(/\d+/);
    if (!m || Number(m[0]) <= 0) return "Headcount must be a number.";
  }
  if (field === "marketing_spend" && mode !== "quick") {
    if (!t) return "Add an amount, % of revenue, or words like no/minimal/unknown.";
    if (!hasAmountSignal(t) && !/\b(no|none|minimal|low|unknown|n\/a|na)\b/i.test(t)) {
      return "Marketing spend should be numeric or a clear qualifier.";
    }
  }
  if (field === "cash_reserves" && mode !== "quick" && !t) {
    return "Describe cash reserves or runway.";
  }
  if (field === "main_problem" && t.length < 8) {
    return "Main problem should be a real business issue (e.g. high churn, low retention).";
  }
  if (field === "main_goal" && t.length < 6) {
    return "State a concrete business goal.";
  }
  if ((field === "company_name" || field === "industry") && mode === "detailed" && !t) {
    return `Please provide ${field.replace("_", " ")}.`;
  }
  return undefined;
}

export function validateCase(mode: IntakeMode, input: CaseInput): FieldErrors {
  const fields = Object.keys(input) as (keyof CaseInput)[];
  const errors: FieldErrors = {};
  for (const f of fields) {
    if (f === "extra_context") continue;
    const err = validateField(mode, f, input[f]);
    if (err) errors[f] = err;
  }
  return errors;
}

export function normalizeCase(mode: IntakeMode, input: CaseInput): CaseInput {
  const out: CaseInput = { ...input };
  out.revenue_period = normalizeRevenuePeriod(out.revenue_period);
  out.profit_or_loss_type = normalizeProfitType(out.profit_or_loss_type);
  out.headcount = normalizeHeadcount(out.headcount);
  if (mode === "quick") {
    out.company_name = out.company_name || "";
    out.industry = out.industry || "";
  }
  return out;
}
