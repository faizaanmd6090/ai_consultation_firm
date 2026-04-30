"use client";

import { useEffect, useMemo, useState } from "react";

import { ChatComposer } from "@/components/chat/ChatComposer";
import { ChatMessageList } from "@/components/chat/ChatMessageList";
import { ModeSelector } from "@/components/chat/ModeSelector";
import { CaseDraftCard } from "@/components/chat/CaseDraftCard";
import { AgentInfoPanel } from "@/components/chat/AgentInfoPanel";
import { OrchestrationPanel } from "@/components/chat/OrchestrationPanel";
import { ResultsPanel } from "@/components/results/ResultsPanel";
import { analyzeCase, getAgentInfo, intakeChat } from "@/lib/api";
import {
  EMPTY_CASE,
  type AgentInfoResponse,
  type AnalyzeCaseResponse,
  type ChatMessage,
  type IntakeChatResponse,
  type IntakeMode,
} from "@/lib/types";

export function ChatWorkspace() {
  const [mode, setMode] = useState<IntakeMode>("guided");
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState(EMPTY_CASE);
  const [missingFields, setMissingFields] = useState<string[]>([]);
  const [readinessScore, setReadinessScore] = useState(0);
  const [canRun, setCanRun] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [result, setResult] = useState<AnalyzeCaseResponse | null>(null);
  const [factsSummary, setFactsSummary] = useState<IntakeChatResponse["extracted_facts_summary"] | null>(null);
  const [activeResultTab, setActiveResultTab] = useState<"founder" | "facts" | "agents">("facts");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<AgentInfoResponse>({ agents: [], orchestration: [] });

  useEffect(() => {
    getAgentInfo().then(setInfo).catch(() => undefined);
  }, []);

  async function sendMessage(text: string) {
    setIsThinking(true);
    setError(null);
    try {
      const response = await intakeChat({ session_id: sessionId, mode, user_message: text });
      setSessionId(response.session_id);
      setMessages(response.messages);
      setDraft(response.structured_case_draft);
      setMissingFields(response.missing_fields);
      setReadinessScore(response.readiness_score);
      setCanRun(response.can_run_analysis);
      setFactsSummary(response.extracted_facts_summary);
      if (response.should_start_analysis) {
        await runAnalysis({
          sessionIdOverride: response.session_id,
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat request failed.");
    } finally {
      setIsThinking(false);
    }
  }

  async function runAnalysis(overrides?: { caseOverride?: typeof draft; sessionIdOverride?: string }) {
    setAnalysisLoading(true);
    setError(null);
    try {
      const requestSessionId = overrides?.sessionIdOverride ?? sessionId;
      const hasExplicitCaseOverride = !!overrides?.caseOverride;
      const requestPayload = requestSessionId && !hasExplicitCaseOverride
        ? {
            mode,
            session_id: requestSessionId,
          }
        : {
            mode,
            session_id: requestSessionId,
            case: overrides?.caseOverride ?? draft,
          };
      const response = await analyzeCase(requestPayload);
      setResult(response);
      setActiveResultTab("founder");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis request failed.");
    } finally {
      setAnalysisLoading(false);
    }
  }

  function resetForRerun() {
    setResult(null);
    setActiveResultTab("facts");
  }

  const canSend = !analysisLoading && !isThinking;
  const runButtonDisabled = analysisLoading || !canRun;
  const readinessText = useMemo(() => (canRun ? "Ready to analyze" : "Keep adding details"), [canRun]);
  const analysisStatus = analysisLoading ? "running" : result ? "complete" : canRun ? "ready" : "";
  const showCaseDraft = !result;

  return (
    <main className="container fade-in" style={{ paddingBottom: "1.2rem" }}>
      <section className="workspace-grid">
        <aside className="pane-scroll" style={{ minWidth: 0, maxHeight: "calc(100vh - 140px)" }}>
          <AgentInfoPanel agents={info.agents} />
          <OrchestrationPanel steps={info.orchestration} />
        </aside>

        <section className="chat-pane" style={{ minWidth: 0 }}>
          <ModeSelector
            mode={mode}
            onChange={(next) => {
              setMode(next);
              setSessionId(undefined);
              setMessages([]);
              setDraft(EMPTY_CASE);
              setMissingFields([]);
              setReadinessScore(0);
              setCanRun(false);
              setResult(null);
              setFactsSummary(null);
              setActiveResultTab("facts");
              setError(null);
            }}
          />
          <div className="pane-scroll">
            <ChatMessageList messages={messages} isThinking={isThinking} />
          </div>
          <div style={{ position: "sticky", bottom: 0, background: "var(--bg)", paddingTop: "0.4rem" }}>
            <ChatComposer onSend={sendMessage} disabled={!canSend} />
          </div>

          <div className="surface-elevated" style={{ padding: "0.75rem", marginTop: "0.75rem", display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.7rem", flexWrap: "wrap" }}>
            <div className="muted" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              {!!analysisStatus && <span className={`status-chip ${analysisStatus}`}>{analysisStatus}</span>}
              <strong>{readinessText}</strong> • {readinessScore}% complete
            </div>
            <button className="btn btn-primary" disabled={runButtonDisabled} onClick={() => void runAnalysis()}>
              {analysisLoading ? "Running analysis..." : "Run Analysis"}
            </button>
          </div>
          {error && (
            <div className="card" style={{ padding: "0.75rem", marginTop: "0.7rem", borderColor: "#fecaca" }}>
              <span style={{ color: "#b91c1c" }}>{error}</span>
            </div>
          )}
        </section>

        <section style={{ minWidth: 0 }} className="fade-in">
          {showCaseDraft && (
            <CaseDraftCard
              draft={draft}
              missingFields={missingFields}
              readinessScore={readinessScore}
              canRunAnalysis={canRun}
            />
          )}
          <ResultsPanel
            data={result}
            loading={analysisLoading}
            error={error}
            onReset={resetForRerun}
            extractedFacts={factsSummary}
            activeTab={activeResultTab}
            onTabChange={setActiveResultTab}
          />
        </section>
      </section>
    </main>
  );
}
