"use client";

import { useState } from "react";
import { askCopilot, CopilotAnswer } from "@/lib/api";
import { Send, Sparkles } from "lucide-react";

const QUICK_QUESTIONS = [
  "Why is the risk high?",
  "Why is this an emergency?",
  "Which agents contributed?",
  "What should we do now?",
  "What information is missing?",
];

interface Turn {
  question: string;
  answer: CopilotAnswer;
}

export default function SafetyCopilot({ zoneId }: { zoneId: string }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);

  async function ask(question: string) {
    if (!question.trim() || pending) return;
    setPending(true);
    setInput("");
    try {
      const answer = await askCopilot(zoneId, question);
      setTurns((t) => [...t, { question, answer }]);
    } catch {
      setTurns((t) => [
        ...t,
        { question, answer: { text: "The Safety Copilot is unreachable right now.", source: "deterministic", model: null } },
      ]);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="card" style={{ padding: 24 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
        <Sparkles size={16} color="var(--accent)" />
        <span style={{ fontSize: 13.5, fontWeight: 700 }}>Ask SENTINEL</span>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 14 }}>
        {QUICK_QUESTIONS.map((q) => (
          <button
            key={q}
            onClick={() => ask(q)}
            disabled={pending}
            style={{
              fontSize: 11.5,
              fontWeight: 600,
              padding: "6px 10px",
              borderRadius: 999,
              border: "1px solid var(--border)",
              background: "var(--surface)",
              color: "var(--text-secondary)",
              cursor: pending ? "default" : "pointer",
              opacity: pending ? 0.5 : 1,
            }}
          >
            {q}
          </button>
        ))}
      </div>

      {turns.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 14, marginBottom: 14 }}>
          {turns.map((t, i) => (
            <div key={i}>
              <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--text-secondary)" }}>{t.question}</div>
              <div style={{ fontSize: 13, lineHeight: 1.6, marginTop: 4 }}>{t.answer.text}</div>
              <div
                className="mono"
                style={{ fontSize: 10, color: "var(--text-tertiary)", marginTop: 4, textTransform: "uppercase" }}
              >
                {t.answer.source === "llm" ? `LLM (${t.answer.model})` : "Deterministic (verified data, no LLM)"}
              </div>
            </div>
          ))}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(input);
        }}
        style={{ display: "flex", gap: 8 }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about this assessment..."
          disabled={pending}
          style={{
            flex: 1,
            fontSize: 13,
            padding: "8px 12px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border)",
            background: "var(--surface-sunken)",
          }}
        />
        <button
          type="submit"
          disabled={pending || !input.trim()}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 36,
            borderRadius: "var(--radius-sm)",
            border: "none",
            background: "var(--accent)",
            color: "#fff",
            opacity: pending || !input.trim() ? 0.5 : 1,
          }}
        >
          <Send size={14} />
        </button>
      </form>
    </div>
  );
}
