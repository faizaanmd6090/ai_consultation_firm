"use client";

type Props = {
  steps: string[];
};

export function OrchestrationPanel({ steps }: Props) {
  return (
    <div className="card" style={{ padding: "0.95rem" }}>
      <h4 className="section-heading">How It Works</h4>
      <ol style={{ margin: 0, paddingLeft: "1rem" }}>
        {steps.map((step, idx) => (
          <li key={idx} className="soft-block muted" style={{ marginBottom: "0.45rem" }}>
            {step}
          </li>
        ))}
      </ol>
      <div className="soft-block" style={{ marginTop: "0.7rem" }}>
        <strong style={{ fontSize: "0.9rem" }}>What You Receive</strong>
        <ul style={{ margin: "0.35rem 0 0", paddingLeft: "1rem" }}>
          <li className="muted">Ranked root causes with evidence strength and urgency.</li>
          <li className="muted">Biggest risks plus explicit cut vs invest calls.</li>
          <li className="muted">30/60/90 execution plan with weekly operating metrics.</li>
        </ul>
      </div>
    </div>
  );
}
