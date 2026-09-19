import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { ErrorState } from "../components/States";
import ChatLibrary from "../components/ChatLibrary";
import CreditMeter from "../components/CreditMeter";

/**
 * The conversational data agent.
 *
 * Two things make this different from a support chatbot and both are visible
 * in the UI: answers are computed from the workspace's real records, and any
 * change it wants to make arrives as a card you approve. Nothing it says it
 * will do has happened yet.
 */

const STARTERS = [
  "How did last month go?",
  "What's outstanding, and how late?",
  "Is anything running low?",
  "Who's working this week?",
];

function Proposal({ proposal, onResolved }) {
  const [state, setState] = useState("pending");
  const [error, setError] = useState("");

  async function act(decision) {
    setState(decision === "confirm" ? "applying" : "rejecting");
    setError("");
    try {
      await api(`/agent/proposals/${proposal.id}/${decision}`, { method: "POST" });
      setState(decision === "confirm" ? "applied" : "rejected");
      onResolved?.(proposal.id, decision);
    } catch (err) {
      setError(err?.message || "That didn't go through.");
      setState("pending");
    }
  }

  const entries = Object.entries(proposal.changes || {});

  return (
    <div className={`agent-proposal is-${state}`}>
      <div className="agent-proposal-head">
        <span className="agent-proposal-kind">{proposal.action} {proposal.entity_type.replace(/_/g, " ")}</span>
        {state === "applied" && <span className="agent-proposal-done">Applied</span>}
        {state === "rejected" && <span className="agent-proposal-dismissed">Discarded</span>}
      </div>

      <p className="agent-proposal-summary">{proposal.summary}</p>

      {entries.length > 0 && (
        <dl className="agent-proposal-changes">
          {entries.map(([field, value]) => (
            <div key={field}>
              <dt>{field.replace(/_/g, " ")}</dt>
              <dd>{typeof value === "object" ? JSON.stringify(value) : String(value)}</dd>
            </div>
          ))}
        </dl>
      )}

      {error && <p className="agent-proposal-error">{error}</p>}

      {state === "pending" && (
        <div className="agent-proposal-actions">
          <button className="primary-btn" onClick={() => act("confirm")}>Approve</button>
          <button className="ghost-btn" onClick={() => act("reject")}>Discard</button>
        </div>
      )}
      {(state === "applying" || state === "rejecting") && (
        <p className="agent-proposal-working">Working…</p>
      )}
    </div>
  );
}

export default function AgentPage() {
  const [turns, setTurns] = useState([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [threadId, setThreadId] = useState(null);
  const [error, setError] = useState("");
  // Bumped after every exchange so the meter and the library reload without
  // either of them needing to know what the other did.
  const [changed, setChanged] = useState(0);
  const endRef = useRef(null);
  const inputRef = useRef(null);

  /** Open a stored conversation. */
  const openThread = useCallback(async (id) => {
    setError("");
    try {
      const thread = await api(`/threads/${id}`);
      setThreadId(String(thread.id));
      setTurns(
        thread.messages
          .filter((m) => ["user", "assistant", "summary"].includes(m.role))
          .map((m) => ({ role: m.role, content: m.content })),
      );
    } catch (problem) {
      setError(problem?.message || "That conversation could not be opened.");
    }
  }, []);

  /** Start fresh. The thread is created on the server by the first message. */
  const newChat = useCallback(() => {
    setThreadId(null);
    setTurns([]);
    setDraft("");
    setError("");
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, busy]);

  async function send(text) {
    const message = (text ?? draft).trim();
    if (!message || busy) return;

    setDraft("");
    setError("");
    setBusy(true);
    setTurns((prev) => [...prev, { role: "user", content: message }]);

    try {
      // No history is sent any more. The server reads the transcript from the
      // thread, which is what lets a conversation survive closing the tab and
      // lets long ones be compacted — neither is possible while the browser is
      // the only place the conversation exists.
      const reply = await api("/agent/chat", {
        method: "POST",
        body: JSON.stringify({ message, thread_id: threadId }),
      });

      setThreadId(reply.thread_id);
      setChanged((n) => n + 1);
      setTurns((prev) => [
        ...prev,
        {
          role: "assistant",
          content: reply.reply,
          proposals: reply.proposals || [],
          escalated: reply.escalated,
        },
      ]);
    } catch (err) {
      setError(err?.message || "The assistant couldn't be reached.");
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
    <div className="page agent-page">
      <div className="os-heading">
        <div>
          <span className="eyebrow">ASSISTANT</span>
          <h1>Ask your business anything</h1>
          <p>Answers come from your actual records. Changes wait for your approval.</p>
        </div>
        <CreditMeter refreshKey={changed} />
      </div>

      <div className="agent-layout">
      <ChatLibrary
        surface="business"
        activeId={threadId ? Number(threadId) : null}
        onOpen={openThread}
        onNew={newChat}
        refreshKey={changed}
      />

      <div className="agent-main">
      <section className="card agent-thread">
        {turns.length === 0 && (
          <div className="agent-empty">
            <p>I can read your invoices, stock, customers, schedule and books — and propose changes for you to approve.</p>
            <div className="agent-starters">
              {STARTERS.map((s) => (
                <button key={s} className="ghost-btn" onClick={() => send(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}

        {turns.map((turn, i) => (
          <div key={i} className={`agent-turn is-${turn.role}`}>
            {turn.role === "summary" ? (
              <p className="agent-summary">
                <strong>Earlier in this conversation:</strong> {turn.content}
              </p>
            ) : (
            <div className="agent-bubble">
              {turn.content.split("\n").filter(Boolean).map((line, j) => <p key={j}>{line}</p>)}
            </div>
            )}

            {turn.proposals?.map((p) => (
              <Proposal key={p.id} proposal={p} />
            ))}

            {turn.escalated && (
              <p className="agent-escalated">A person has been notified and will follow up.</p>
            )}
          </div>
        ))}

        {busy && (
          <div className="agent-turn is-assistant">
            <div className="agent-bubble agent-thinking">
              <span /><span /><span />
            </div>
          </div>
        )}

        <div ref={endRef} />
      </section>

      {error && (
        <ErrorState
          title="The assistant didn't answer"
          error={error}
          onRetry={() => { setError(""); send(draft); }}
        />
      )}

      <div className="agent-composer">
        <textarea
          ref={inputRef}
          rows={1}
          value={draft}
          placeholder="Ask about takings, stock, staff, anything…"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={busy}
        />
        <button className="primary-btn" onClick={() => send()} disabled={busy || !draft.trim()}>
          {busy ? "Thinking…" : "Ask"}
        </button>
      </div>
      </div>
      </div>
    </div>
  );
}
