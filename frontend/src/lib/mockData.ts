import type { AnalyzeCaseResponse } from "@/lib/types";

export const MOCK_RESPONSE: AnalyzeCaseResponse = {
  founder_report: `Executive Summary
Your business shows promising demand, but weak unit economics and retention pressure are constraining cash efficiency.

Core Problems
- Customer churn is elevated in two customer cohorts.
- Acquisition spend is outpacing contribution margin.
- Forecasting discipline is inconsistent across teams.

Immediate Priorities
- Stabilize retention in top-value segments.
- Tighten CAC controls and channel attribution.
- Build a 13-week cash visibility cadence.

Biggest Risks
- Runway compression if churn trend continues.
- Margin deterioration from discounting pressure.
- Slower execution due to unclear ownership.

Missing Critical Data
- Channel-level CAC/LTV by cohort.
- Product-level gross margin breakdown.
- Weekly leading indicators for pipeline quality.

30/60/90 Day Action Plan
- 30: Launch retention taskforce and stop-loss spend rules.
- 60: Reprice low-margin segments and optimize offers.
- 90: Institutionalize operating cadence with owner-level scorecards.

Key Metrics to Watch
- Net revenue retention
- CAC payback period
- Gross margin by segment
- Weekly cash burn`,
  agents: {
    intake: {
      agent_name: "intake",
      summary: "Problem frame and key context gathered.",
      findings: ["Demand signal exists", "Primary stress point is retention"],
      risks: ["Unclear prioritization"],
      recommendations: ["Define one north-star objective"],
      assumptions: ["Inputs provided are directionally correct"],
    },
    finance: {
      agent_name: "finance",
      summary: "Cash and unit economics show pressure.",
      findings: ["CAC payback too long", "Margin instability across channels"],
      risks: ["Runway compression"],
      recommendations: ["Cut low-ROI campaigns", "Renegotiate variable costs"],
      assumptions: ["Revenue timing remains stable"],
    },
    operations: {
      agent_name: "operations",
      summary: "Execution bottlenecks reduce delivery confidence.",
      findings: ["Decision latency", "Process variance"],
      risks: ["Delivery quality drift"],
      recommendations: ["Define weekly operating cadence"],
      assumptions: ["Team capacity can be reallocated"],
    },
    strategy: {
      agent_name: "strategy",
      summary: "Focus strategy should narrow target segments.",
      findings: ["Over-broad segment targeting"],
      risks: ["Marketing waste"],
      recommendations: ["Concentrate on highest-LTV segment"],
      assumptions: ["Segment demand remains durable"],
    },
    review: {
      agent_name: "reviewer",
      summary: "Integrated priority stack prepared.",
      findings: ["Retention + CAC are highest-leverage levers"],
      risks: ["Execution slippage on cross-functional items"],
      recommendations: ["Assign owners and weekly targets"],
      assumptions: ["Leadership alignment can be achieved quickly"],
      priority_order: ["Retention stabilization", "CAC discipline", "Forecast cadence"],
    },
  },
};
