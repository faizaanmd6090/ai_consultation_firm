"use client";

import { useMemo, useState } from "react";

import { analyzeCase } from "@/lib/api";
import { normalizeCase, validateCase, validateField } from "@/lib/intakeValidation";
import { EMPTY_CASE, type AnalyzeCaseResponse, type CaseInput, type FieldErrors, type IntakeMode } from "@/lib/types";

type Props = {
  onResult: (response: AnalyzeCaseResponse) => void;
  onLoading: (loading: boolean) => void;
  onError: (err: string | null) => void;
};

type FieldDef = {
  key: keyof CaseInput;
  label: string;
  placeholder?: string;
  multiline?: boolean;
};

const QUICK_FIELDS: FieldDef[] = [
  { key: "business_model", label: "What does your company do, and how does it make money?", placeholder: "B2B SaaS selling HR software via subscription", multiline: true },
  { key: "revenue_amount", label: "Revenue amount", placeholder: "$2M ARR" },
  { key: "profit_or_loss_type", label: "Profit / loss type", placeholder: "profit, loss, break-even" },
  { key: "profit_or_loss_amount", label: "Profit / loss amount", placeholder: "$50k loss per month" },
  { key: "headcount", label: "Headcount", placeholder: "42" },
  { key: "main_problem", label: "Main problem", placeholder: "high churn, rising CAC", multiline: true },
  { key: "main_goal", label: "Main goal", placeholder: "improve margins and stabilize runway", multiline: true },
  { key: "extra_context", label: "Extra context (optional)", multiline: true },
];

const GUIDED_FIELDS: FieldDef[] = [
  ...QUICK_FIELDS.slice(0, 2),
  { key: "revenue_period", label: "Revenue period", placeholder: "weekly / monthly / quarterly / annual" },
  ...QUICK_FIELDS.slice(2, 5),
  { key: "marketing_spend", label: "Marketing spend", placeholder: "20% revenue or minimal" },
  { key: "cash_reserves", label: "Cash reserves / runway", placeholder: "8 weeks runway" },
  ...QUICK_FIELDS.slice(5),
];

const DETAILED_FIELDS: FieldDef[] = [
  { key: "company_name", label: "Company name", placeholder: "Acme Corp" },
  { key: "industry", label: "Industry", placeholder: "B2B software" },
  ...GUIDED_FIELDS,
];

function getFields(mode: IntakeMode): FieldDef[] {
  if (mode === "quick") return QUICK_FIELDS;
  if (mode === "detailed") return DETAILED_FIELDS;
  return GUIDED_FIELDS;
}

function nextValue(mode: IntakeMode, key: keyof CaseInput, value: string): string {
  const normalized = normalizeCase(mode, { ...EMPTY_CASE, [key]: value });
  return normalized[key];
}

export function IntakePanel({ onResult, onLoading, onError }: Props) {
  const [mode, setMode] = useState<IntakeMode>("guided");
  const [form, setForm] = useState<CaseInput>(EMPTY_CASE);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [guidedIndex, setGuidedIndex] = useState(0);

  const fields = useMemo(() => getFields(mode), [mode]);

  function updateField(key: keyof CaseInput, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => ({ ...prev, [key]: undefined }));
  }

  async function submitCase() {
    const normalized = normalizeCase(mode, form);
    const allErrors = validateCase(mode, normalized);
    setErrors(allErrors);
    if (Object.keys(allErrors).length > 0) return;

    onLoading(true);
    onError(null);
    try {
      const response = await analyzeCase({ mode, case: normalized });
      onResult(response);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      onLoading(false);
    }
  }

  function renderField(field: FieldDef) {
    const value = form[field.key];
    return (
      <div key={field.key} style={{ marginBottom: "0.8rem" }}>
        <label style={{ display: "block", marginBottom: "0.3rem", fontWeight: 600 }}>{field.label}</label>
        {field.multiline ? (
          <textarea
            className="field"
            rows={3}
            placeholder={field.placeholder}
            value={value}
            onChange={(e) => updateField(field.key, e.target.value)}
          />
        ) : (
          <input
            className="field"
            placeholder={field.placeholder}
            value={value}
            onChange={(e) => updateField(field.key, e.target.value)}
          />
        )}
        {errors[field.key] && <div className="field-error">{errors[field.key]}</div>}
      </div>
    );
  }

  function renderGuidedStep() {
    const f = fields[guidedIndex];
    const total = fields.length;
    const value = form[f.key];

    async function onNext() {
      const err = validateField(mode, f.key, value);
      if (err) {
        setErrors((prev) => ({ ...prev, [f.key]: err }));
        return;
      }
      const nv = nextValue(mode, f.key, value);
      updateField(f.key, nv);
      setGuidedIndex((i) => Math.min(i + 1, total - 1));
    }

    return (
      <div className="card fade-in" style={{ padding: "1rem" }}>
        <div className="muted" style={{ marginBottom: "0.5rem" }}>Guided mode (recommended) • Step {guidedIndex + 1} of {total}</div>
        {renderField(f)}
        <div style={{ display: "flex", gap: "0.55rem", justifyContent: "space-between" }}>
          <button className="btn btn-soft" onClick={() => setGuidedIndex((i) => Math.max(i - 1, 0))} disabled={guidedIndex === 0}>Back</button>
          {guidedIndex < total - 1 ? (
            <button className="btn btn-primary" onClick={onNext}>Next</button>
          ) : (
            <button className="btn btn-primary" onClick={submitCase}>Review and run analysis</button>
          )}
        </div>
      </div>
    );
  }

  return (
    <section>
      <div className="card" style={{ padding: "1rem", marginBottom: "0.75rem" }}>
        <h3 style={{ marginTop: 0 }}>Case Intake</h3>
        <p className="muted" style={{ marginTop: "0.2rem" }}>Select intake mode, validate inputs, then run multi-agent analysis.</p>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          <button className={`btn ${mode === "quick" ? "btn-primary" : "btn-soft"}`} onClick={() => { setMode("quick"); setGuidedIndex(0); }}>Quick</button>
          <button className={`btn ${mode === "guided" ? "btn-primary" : "btn-soft"}`} onClick={() => { setMode("guided"); setGuidedIndex(0); }}>Guided (Recommended)</button>
          <button className={`btn ${mode === "detailed" ? "btn-primary" : "btn-soft"}`} onClick={() => { setMode("detailed"); setGuidedIndex(0); }}>Detailed</button>
        </div>
      </div>

      {mode === "guided" ? (
        renderGuidedStep()
      ) : (
        <div className="card fade-in" style={{ padding: "1rem" }}>
          {fields.map((f) => renderField(f))}
          <button className="btn btn-primary" onClick={submitCase}>Review and run analysis</button>
        </div>
      )}
    </section>
  );
}
