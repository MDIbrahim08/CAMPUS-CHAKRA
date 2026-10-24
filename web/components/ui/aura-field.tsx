"use client";

import { useRef, useState, type CSSProperties } from "react";
import "./aura-field-utils/aura-field.css";

export type Tool = {
  id: string;
  label: string;
  icon: string;
  rewrite: (t: string) => string;
};

export type Props = {
  initial?: string;
  tools?: Tool[];
  theme?: "light" | "dark";
  className?: string;
  onSend?: (text: string) => void;
};

export const DEFAULT_TOOLS: Tool[] = [
  {
    id: "proofread",
    label: "Proofread",
    icon: "✓",
    rewrite: () =>
      "Campus Facilities: Scheduled peak shaving protocol initiated for Block A & B to offset midday grid draw.",
  },
  {
    id: "action-plan",
    label: "Action Plan",
    icon: "⚡",
    rewrite: () =>
      "Deploy automated inspection for Girls Hostel water pump. Throttle secondary inverter and notify BMS team.",
  },
  {
    id: "concise",
    label: "Concise",
    icon: "≡",
    rewrite: () =>
      "Surge detected in Academic Block A. 120 kW solar active. Work order staged.",
  },
];

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

export function AuraField({
  initial = "Ask facilities copilot: What caused the 48 kL water spike in Girls Hostel and what is the current solar offset?",
  tools = DEFAULT_TOOLS,
  theme = "dark",
  className = "",
  onSend,
}: Props) {
  const [text, setText] = useState(initial);
  const [words, setWords] = useState<string[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [history, setHistory] = useState<string[]>([]);
  const run = useRef(0);

  const apply = async (tool: Tool) => {
    if (busy) return;
    const id = ++run.current;
    setBusy(tool.id);
    setHistory((h) => [...h, text]);
    await wait(700);
    const next = tool.rewrite(text).split(/(\s+)/);
    const reduce = typeof window !== "undefined" && window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    for (let i = 1; i <= next.length; i += 2) {
      if (run.current !== id) return;
      setWords(next.slice(0, i));
      if (!reduce) await wait(38);
    }
    await wait(250);
    const newText = next.join("");
    setText(newText);
    setWords(null);
    setBusy(null);
  };

  const undo = () => {
    if (busy || !history.length) return;
    setText(history[history.length - 1]);
    setHistory((h) => h.slice(0, -1));
  };

  return (
    <div
      className={`aura-field aura-field--${theme} ${className}`}
      data-busy={busy || undefined}
    >
      <div className="aura-field__frame">
        <span className="aura-field__aura" aria-hidden="true" />
        <span className="aura-field__glow" aria-hidden="true" />
        <div className="aura-field__surface">
          {words ? (
            <p className="aura-field__text" aria-hidden="true">
              {words.map((w, i) => (
                <span
                  key={i}
                  className="aura-field__word"
                  style={{ "--i": i } as CSSProperties}
                >
                  {w}
                </span>
              ))}
              <span className="aura-field__caret" />
            </p>
          ) : (
            <textarea
              className="aura-field__text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              aria-label="Message draft"
              rows={4}
              disabled={!!busy}
            />
          )}
        </div>
      </div>

      <div
        className="aura-field__tools"
        role="toolbar"
        aria-label="Writing tools"
      >
        {tools.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => apply(t)}
            disabled={!!busy}
            data-active={busy === t.id || undefined}
          >
            <span aria-hidden="true">{t.icon}</span>
            {t.label}
          </button>
        ))}
        <span className="aura-field__spacer" />
        <button
          type="button"
          className="aura-field__undo"
          onClick={undo}
          disabled={!!busy || !history.length}
          aria-label="Undo rewrite"
        >
          <svg viewBox="0 0 16 16" aria-hidden="true">
            <path d="M5 4L2.5 6.5 5 9M3 6.5h6.5a3.5 3.5 0 0 1 0 7H7" />
          </svg>
        </button>
        {onSend && (
          <button
            type="button"
            className="aura-field__send"
            onClick={() => onSend(text)}
            disabled={!!busy}
            style={{
              background: "#10B981",
              color: "#FFFFFF",
              fontWeight: 700,
              padding: "5px 14px",
              borderRadius: "9999px",
            }}
          >
            Send ✦
          </button>
        )}
      </div>
      <p className="aura-field__sr" aria-live="polite">
        {busy
          ? "Rewriting…"
          : history.length
            ? "Rewrite applied. Undo is available."
            : ""}
      </p>
    </div>
  );
}

export default AuraField;
