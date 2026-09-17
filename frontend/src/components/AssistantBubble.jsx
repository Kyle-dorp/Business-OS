import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";

/**
 * The assistant, on every page.
 *
 * Both AI surfaces were whole pages, which meant asking a question required
 * leaving whatever you were doing — and a question you have to navigate away
 * to ask is a question nobody asks. The two pages remain for long sessions.
 * This is for the ninety percent that are one line.
 *
 * It changes with the page. On the rota it is the scheduling assistant, which
 * can regenerate a week or move a shift; everywhere else it is the agent,
 * which reads across the whole business and proposes changes for approval.
 * Same bubble, the right brain, and the person using it never has to know
 * there are two.
 *
 * It arrives knowing where you are. Opened on the rota for the week of the
 * 14th, it is handed that week rather than asking which one you mean — and the
 * starter questions are the ones worth asking from the screen you are on.
 *
 * A panel, not a modal: the page stays visible behind it, because the whole
 * point is asking about what you are looking at.
 */

// Which brain answers, per page. The scheduling assistant is the only one that
// can act on a rota; the agent is the only one that can see the books. Sending
// "regenerate Tuesday" to the agent would get a polite paragraph and no rota.
const SCHEDULING_PAGES = new Set(["manager", "availability", "preflight", "compliance"]);

const STARTERS = {
  manager: [
    "Who is short this week?",
    "Regenerate Tuesday with one fewer person",
    "Is anyone over their hours?",
  ],
  preflight: ["What is blocking this week?", "Why is labor so high?"],
  compliance: ["What would this week cost me in penalties?", "Is anyone under 18 scheduled late?"],
  availability: ["Who is unavailable on Friday?", "Who can cover a morning?"],
  home: ["How did last month go?", "What is outstanding, and how late?", "Is anything running low?"],
  sales: ["Who owes me money?", "What did I invoice this month?"],
  purchasing: ["What do I owe, and when is it due?"],
  accounting: ["What did I spend the most on?", "How does this month compare to last?"],
  reports: ["Explain my profit and loss", "Where is my money going?"],
  inventory: ["What is running low?", "What is worth reordering?"],
  "inventory-intel": ["Where is my shrinkage?", "Which items lose me money?"],
  bookings: ["How busy is next week?", "Who has not turned up recently?"],
  billing: ["What am I paying for?", "Which modules am I not using?"],
};

const DEFAULT_STARTERS = [
  "How did last month go?",
  "What needs my attention today?",
  "Is anything running low?",
];

export default function AssistantBubble({ page, pageLabel, weekStart, scheduleId, attention = 0 }) {
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [threadId, setThreadId] = useState(null);
  const [error, setError] = useState("");

  const inputRef = useRef(null);
  const bodyRef = useRef(null);

  const scheduling = SCHEDULING_PAGES.has(page);
  const starters = useMemo(() => STARTERS[page] || DEFAULT_STARTERS, [page]);

  // A different brain is a different conversation. Carrying the rota thread
  // into a question about invoices would give the model a transcript about
  // shifts and a question about money.
  useEffect(() => {
    setTurns([]);
    setThreadId(null);
    setError("");
  }, [scheduling]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [turns, busy]);

  // Escape closes it, because a panel that traps you is a modal.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  async function send(text) {
    const message = (text ?? draft).trim();
    if (!message || busy) return;

    setDraft("");
    setError("");
    setBusy(true);
    setTurns((prev) => [...prev, { role: "user", content: message }]);

    try {
      const reply = scheduling
        ? await api("/assistant/chat", {
            method: "POST",
            // The week and the schedule travel with the question, so "make
            // Tuesday lighter" does not need a follow-up asking which Tuesday.
            body: JSON.stringify({
              message,
              thread_id: threadId,
              week_start: weekStart || null,
              schedule_id: scheduleId || null,
            }),
          })
        : await api("/agent/chat", {
            method: "POST",
            body: JSON.stringify({
              message,
              thread_id: threadId,
              history: turns
                .filter((t) => t.role === "user" || t.role === "assistant")
                .map((t) => ({ role: t.role, content: t.content })),
            }),
          });

      setThreadId(reply.thread_id ?? threadId);
      setTurns((prev) => [
        ...prev,
        {
          role: "assistant",
          content: reply.reply,
          proposals: reply.proposals || [],
          actions: reply.actions || [],
        },
      ]);
    } catch (err) {
      setError(err?.message || "The assistant couldn't be reached.");
      // Put the question back in the box rather than losing what they typed.
      setTurns((prev) => prev.slice(0, -1));
      setDraft(message);
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <>
      <button
        type="button"
        className={`eos-bubble${open ? " is-open" : ""}${attention > 0 && !open ? " has-attention" : ""}`}
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={open ? "Close the assistant" : "Ask the assistant"}
      >
        <span className="eos-bubble-mark" aria-hidden="true">{open ? "×" : "✦"}</span>
        {attention > 0 && !open && <span className="eos-bubble-dot" aria-hidden="true" />}
      </button>

      <aside className={`eos-panel${open ? " is-open" : ""}`} aria-hidden={!open}>
        <header className="eos-panel-head">
          <div>
            <span className="eyebrow">{scheduling ? "SCHEDULING ASSISTANT" : "ASSISTANT"}</span>
            <h2>{scheduling ? "Ask about this rota" : "Ask your business anything"}</h2>
            <p>
              {scheduling
                ? weekStart
                  ? `Week of ${weekStart} — it can change shifts for your approval.`
                  : "It can regenerate a week or move a shift, for your approval."
                : `Reading your records. You are on ${pageLabel || "your workspace"}.`}
            </p>
          </div>
        </header>

        <div className="eos-panel-body" ref={bodyRef}>
          {turns.length === 0 && (
            <div className="eos-panel-starters">
              <span>Try</span>
              {starters.map((s) => (
                <button key={s} type="button" className="eos-starter" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          )}

          {turns.map((turn, i) => (
            <div key={i} className={`eos-turn is-${turn.role}`}>
              <p>{turn.content}</p>

              {turn.proposals?.length > 0 && (
                <p className="eos-turn-note">
                  {turn.proposals.length} change{turn.proposals.length === 1 ? "" : "s"} proposed —
                  open Ask to review and approve.
                </p>
              )}
              {turn.actions?.length > 0 && (
                <p className="eos-turn-note">
                  {turn.actions.length} change{turn.actions.length === 1 ? "" : "s"} suggested —
                  open Scheduling AI to apply.
                </p>
              )}
            </div>
          ))}

          {busy && (
            <div className="eos-turn is-assistant is-thinking" role="status" aria-label="Thinking">
              <span /><span /><span />
            </div>
          )}

          {error && <div className="alert error eos-panel-error">{error}</div>}
        </div>

        <div className="eos-panel-foot">
          <textarea
            ref={inputRef}
            rows={1}
            value={draft}
            placeholder={scheduling ? "Ask about this week…" : "Ask about takings, stock, staff…"}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
          />
          <button
            type="button"
            className="primary-btn"
            onClick={() => send()}
            disabled={busy || !draft.trim()}
          >
            {busy ? "…" : "Ask"}
          </button>
        </div>
      </aside>
    </>
  );
}
