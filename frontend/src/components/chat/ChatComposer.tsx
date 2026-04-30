"use client";

import { useState } from "react";

type Props = {
  onSend: (message: string) => Promise<void>;
  disabled?: boolean;
};

export function ChatComposer({ onSend, disabled }: Props) {
  const [text, setText] = useState("");

  async function submit() {
    const t = text.trim();
    if (!t || disabled) return;
    setText("");
    await onSend(t);
  }

  return (
    <div className="surface-elevated" style={{ padding: "0.75rem", marginTop: "0.75rem" }}>
      <textarea
        className="field"
        rows={3}
        placeholder="Describe your business context, constraints, and goals..."
        value={text}
        disabled={disabled}
        onChange={(e) => setText(e.target.value)}
      />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "0.55rem" }}>
        <span className="muted" style={{ fontSize: "0.82rem" }}>
          Shift+Enter for newline • Send to continue intake
        </span>
        <button className="btn btn-primary" onClick={submit} disabled={disabled || !text.trim()}>
          Send Message
        </button>
      </div>
    </div>
  );
}
