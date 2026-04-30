import Link from "next/link";
import { AGENT_VISUALS } from "@/lib/agentVisuals";

export default function HomePage() {
  const workflow = [
    "Founder describes the current business situation and objectives in chat.",
    "Intake orchestration extracts structured facts and normalizes key fields.",
    "Follow-up questions close critical data gaps before analysis starts.",
    "Finance, Operations, and Strategy agents run specialized analysis.",
    "Reviewer resolves trade-offs with one controlled clarification round when needed.",
    "Founder report outputs a ranked decision brief with execution plan.",
  ];

  return (
    <main className="container fade-in home-grid">
      <section className="home-hero">
        <div className="surface-elevated home-section">
          <p className="muted" style={{ margin: 0 }}>
            AI-powered multi-agent management consulting platform
          </p>
          <h1 className="home-title">Move from founder context to operator-grade decisions in one workspace.</h1>
          <p className="muted home-subtitle">
            Structured intake, specialist analysis, reviewer synthesis, and a founder-ready decision brief in a clean
            executive interface.
          </p>
          <div className="home-actions">
            <Link className="btn btn-primary" href="/dashboard">Start Analysis</Link>
            <Link className="btn btn-soft" href="/dashboard">Open Dashboard</Link>
          </div>
        </div>
      </section>

      <section className="card home-section">
        <h2 className="section-heading">What the platform does</h2>
        <div className="info-grid three">
          <div className="soft-block">
            <strong>Intake</strong>
            <p className="muted" style={{ marginBottom: 0 }}>Converts open-ended context into structured consulting facts.</p>
          </div>
          <div className="soft-block">
            <strong>Analysis</strong>
            <p className="muted" style={{ marginBottom: 0 }}>Runs finance, operations, and strategy specialists with reviewer control.</p>
          </div>
          <div className="soft-block">
            <strong>Decision Brief</strong>
            <p className="muted" style={{ marginBottom: 0 }}>Delivers ranked root causes, risk calls, priorities, and a 30/60/90 plan.</p>
          </div>
        </div>
      </section>

      <section className="card home-section">
        <h2 className="section-heading">Meet the agents</h2>
        <div className="info-grid three">
          {Object.values(AGENT_VISUALS).map((agent) => (
            <article key={agent.id} className="soft-block">
              <div className="panel-title-row">
                <strong>{agent.icon} {agent.name}</strong>
                <span className="tag">{agent.roleTag}</span>
              </div>
              <p className="muted" style={{ margin: 0 }}>{agent.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="card home-section">
        <h2 className="section-heading">How orchestration works</h2>
        <div className="info-grid two">
          {workflow.map((step, idx) => (
            <div className="soft-block" key={step}>
              <strong>Step {idx + 1}</strong>
              <p className="muted" style={{ marginBottom: 0 }}>{step}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="surface-elevated home-section" style={{ marginBottom: "1.2rem" }}>
        <h2 className="section-heading">Why founders and operators use this</h2>
        <div className="info-grid two">
          <div>
            <p className="muted">Get a report that prioritizes what to cut, where to invest, and what not to change.</p>
            <p className="muted" style={{ marginBottom: 0 }}>
              Outputs include ranked root causes, major risks, weekly metrics, and a concrete 30/60/90 execution plan.
            </p>
          </div>
          <div className="home-actions" style={{ marginTop: 0 }}>
          <Link className="btn btn-primary" href="/dashboard">Start Analysis</Link>
          <Link className="btn btn-soft" href="/dashboard">Open Dashboard</Link>
          </div>
        </div>
      </section>
    </main>
  );
}
