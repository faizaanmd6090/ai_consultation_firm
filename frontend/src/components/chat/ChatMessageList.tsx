"use client";

import type { ChatMessage } from "@/lib/types";

type Props = {
  messages: ChatMessage[];
  isThinking: boolean;
};

export function ChatMessageList({ messages, isThinking }: Props) {
  return (
    <div className="card" style={{ padding: "0.95rem", minHeight: 420, maxHeight: 560, overflowY: "auto" }}>
      {messages.length === 0 ? (
        <div className="soft-block">
          <strong>Start your case intake</strong>
          <p className="muted" style={{ marginBottom: 0 }}>
            Describe your company situation in plain language. The orchestrator will ask focused follow-ups and build your structured draft automatically.
          </p>
        </div>
      ) : (
        messages.map((m, idx) => (
          <div
            key={`${m.role}-${idx}`}
            style={{
              marginBottom: "0.7rem",
              display: "flex",
              justifyContent: m.role === "user" ? "flex-end" : "flex-start",
            }}
          >
            <div
              style={{
                maxWidth: "86%",
                borderRadius: 14,
                padding: "0.75rem 0.85rem",
                border: "1px solid var(--line)",
                background: m.role === "user" ? "#e7f0ff" : "#f8fafc",
              }}
            >
              <div style={{ fontSize: "0.75rem", color: "#64748b", marginBottom: "0.2rem" }}>
                {m.role === "user" ? "You" : "Consulting Assistant"}
              </div>
              <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.45 }}>{m.content}</div>
            </div>
          </div>
        ))
      )}
      {isThinking && <div className="status-chip running" style={{ marginTop: "0.5rem" }}>Running intake reasoning...</div>}
    </div>
  );
}
