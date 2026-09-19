/**
 * Conversations you can come back to.
 *
 * Before this, closing the tab lost the thread. The server kept every turn in a
 * table nothing read, so the transcript existed and could not be reached — the
 * worst of both, a write on every message and nothing to show for it.
 *
 * Threads are named after the first thing said in them, which is what makes
 * this list usable a week later: "why is labour up this week" finds itself, and
 * eleven rows called New chat do not.
 */

import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { Loading } from "./States";

function when(iso) {
  if (!iso) return "";
  const then = new Date(iso);
  const days = Math.floor((Date.now() - then.getTime()) / 86_400_000);
  if (days === 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 7) return `${days} days ago`;
  return then.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function ChatLibrary({ surface = "business", activeId, onOpen, onNew, refreshKey = 0 }) {
  const [threads, setThreads] = useState(null);
  const [renaming, setRenaming] = useState(null);
  const [draft, setDraft] = useState("");

  const load = useCallback(async () => {
    try {
      setThreads(await api(`/threads?surface=${encodeURIComponent(surface)}`));
    } catch {
      setThreads([]);
    }
  }, [surface]);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  async function rename(id) {
    const title = draft.trim();
    setRenaming(null);
    if (!title) return;
    // Optimistic: the name is already what they typed, and a round trip to
    // confirm what somebody just wrote is a round trip they can feel.
    setThreads((rows) => rows.map((row) => (row.id === id ? { ...row, title } : row)));
    try {
      await api(`/threads/${id}`, { method: "PATCH", body: JSON.stringify({ title }) });
    } catch {
      load();
    }
  }

  async function archive(id) {
    setThreads((rows) => rows.filter((row) => row.id !== id));
    try {
      await api(`/threads/${id}/archive`, { method: "POST" });
    } catch {
      load();
    }
    // Archiving the conversation you are reading has to move you somewhere.
    if (id === activeId) onNew?.();
  }

  return (
    <aside className="chat-library">
      <div className="chat-library-head">
        <span className="eyebrow">Conversations</span>
        <button className="eos-btn eos-btn-quiet eos-btn-sm" onClick={onNew}>
          New chat
        </button>
      </div>

      {threads === null ? (
        <Loading rows={4} label="Loading your conversations" />
      ) : threads.length === 0 ? (
        <p className="chat-library-empty">
          Nothing yet. Ask something and it will keep the thread.
        </p>
      ) : (
        <ul className="chat-library-list">
          {threads.map((thread) => (
            <li
              key={thread.id}
              className={`chat-library-item${thread.id === activeId ? " is-open" : ""}`}
            >
              {renaming === thread.id ? (
                <input
                  className="eos-input chat-rename"
                  value={draft}
                  autoFocus
                  onChange={(event) => setDraft(event.target.value)}
                  onBlur={() => rename(thread.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") rename(thread.id);
                    if (event.key === "Escape") setRenaming(null);
                  }}
                />
              ) : (
                <>
                  <button className="chat-library-open" onClick={() => onOpen?.(thread.id)}>
                    <strong>{thread.title}</strong>
                    <small>
                      {when(thread.updated_at)}
                      {thread.message_count > 0 && ` · ${thread.message_count} messages`}
                    </small>
                  </button>
                  <span className="chat-library-actions">
                    <button
                      className="chat-library-action"
                      title="Rename"
                      aria-label={`Rename ${thread.title}`}
                      onClick={() => {
                        setDraft(thread.title);
                        setRenaming(thread.id);
                      }}
                    >
                      ✎
                    </button>
                    <button
                      className="chat-library-action"
                      title="Archive"
                      aria-label={`Archive ${thread.title}`}
                      onClick={() => archive(thread.id)}
                    >
                      ⌫
                    </button>
                  </span>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
