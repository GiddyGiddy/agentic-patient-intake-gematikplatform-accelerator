import React, { useEffect, useRef, useState } from "react";
import { sendChat } from "../services/api";
import { t } from "../i18n";
import { useTypewriter } from "../hooks/useTypewriter";
import ConsentDialog from "./ConsentDialog";
import EmergencyBanner from "./EmergencyBanner";
import ResultCard from "./ResultCard";

const KEY = "intake.chat";
const EMPTY = { messages: [], result: null, consent: false, pending: null, declined: false };

function load() {
  try {
    return { ...EMPTY, ...JSON.parse(sessionStorage.getItem(KEY) || "{}") };
  } catch {
    return EMPTY;
  }
}

function Message({ msg }) {
  const shown = useTypewriter(msg.text, Boolean(msg.fresh));
  const typing = shown.length < msg.text.length;
  const who = msg.from === "patient" ? "you" : msg.from;
  return (
    <li className={`msg msg-${msg.from}`}>
      <span className="who">{t(`chat.${who}`)}</span>
      {typing ? (
        <>
          <span aria-hidden="true">{shown}</span>
          <span className="sr-only">{msg.text}</span>
        </>
      ) : (
        <span>{msg.text}</span>
      )}
    </li>
  );
}

export default function Chat({ token, onUnauthorized }) {
  const [state, setState] = useState(load);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const logEnd = useRef(null);
  const { messages, result, consent, pending, declined } = state;

  useEffect(() => {
    const saved = { ...state, messages: state.messages.map((m) => ({ ...m, fresh: false })) };
    sessionStorage.setItem(KEY, JSON.stringify(saved));
  }, [state]);

  useEffect(() => {
    logEnd.current?.scrollIntoView?.({ block: "end" });
  }, [messages, loading]);

  async function call(payload) {
    setLoading(true);
    setError(null);
    try {
      const r = await sendChat(token, payload);
      setState((s) => ({
        ...s,
        messages: r.reply
          ? [...s.messages, { from: "agent", text: r.reply, fresh: true }]
          : s.messages,
        result: r,
        pending: r.iam_required
          ? { ...payload, triage_score: r.triage_score, anamnesis_summary: r.anamnesis_summary }
          : null,
        declined: false,
      }));
    } catch (err) {
      if (err.status === 401) {
        onUnauthorized();
        return;
      }
      setError({
        payload,
        text: err.status === 0 ? t("chat.error.network") : t("chat.error.server", { status: err.status }),
      });
    } finally {
      setLoading(false);
    }
  }

  function submit(e) {
    e.preventDefault();
    const message = input.trim();
    if (!message || loading) return;
    const history = messages.filter((m) => m.from === "patient").map((m) => m.text);
    setInput("");
    setState((s) => ({ ...s, messages: [...s.messages, { from: "patient", text: message }] }));
    call({ message, history, consent_granted: consent });
  }

  function decide(granted) {
    if (!granted) {
      setState((s) => ({ ...s, declined: true }));
      return;
    }
    const payload = { ...pending, consent_granted: true };
    setState((s) => ({ ...s, consent: true, declined: false, pending: null }));
    call(payload);
  }

  function revoke() {
    setState((s) => ({
      ...s,
      consent: false,
      messages: [...s.messages, { from: "system", text: t("consent.revoked") }],
    }));
  }

  function restart() {
    setState(EMPTY);
    setInput("");
    setError(null);
  }

  const done = Boolean(result?.kim_sent);
  const showInput = !pending && !declined && !done;

  return (
    <div className="chat">
      {result?.triage_score === "Rot" && <EmergencyBanner />}

      {consent && (
        <div className="consent-status">
          <span>{t("consent.status.granted")}</span>
          <button className="btn btn-link" onClick={revoke}>
            {t("consent.revoke")}
          </button>
        </div>
      )}

      {messages.length === 0 && <p className="muted">{t("chat.intro")}</p>}
      <ol className="log" role="log" aria-label={t("chat.log")}>
        {messages.map((m, i) => (
          <Message key={i} msg={m} />
        ))}
      </ol>
      <p className="muted status" role="status">
        {loading ? t("chat.sending") : ""}
      </p>
      <div ref={logEnd} />

      {error && (
        <div className="error" role="alert">
          <span>{error.text}</span>
          <button className="btn" onClick={() => call(error.payload)} disabled={loading}>
            {t("chat.retry")}
          </button>
        </div>
      )}

      {pending && declined && (
        <section className="card" aria-labelledby="declined-title">
          <h2 id="declined-title">{t("consent.declined.title")}</h2>
          <p>{t("consent.declined.text")}</p>
          <div className="actions">
            <button className="btn btn-primary" onClick={() => setState((s) => ({ ...s, declined: false }))}>
              {t("consent.declined.reconsider")}
            </button>
            <button className="btn" onClick={restart}>
              {t("chat.restart")}
            </button>
          </div>
        </section>
      )}

      {pending && !declined && <ConsentDialog message={result?.iam_message} onDecision={decide} />}

      {done && <ResultCard result={result} onRestart={restart} />}

      {showInput && (
        <form className="composer" onSubmit={submit}>
          <label htmlFor="chat-input">{t("chat.inputLabel")}</label>
          <div className="row">
            <input
              id="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
              autoComplete="off"
            />
            <button className="btn btn-primary" type="submit" disabled={loading || !input.trim()}>
              {t("chat.send")}
            </button>
          </div>
        </form>
      )}

      {messages.length > 0 && !done && !pending && (
        <button className="btn btn-link" onClick={restart}>
          {t("chat.restart")}
        </button>
      )}
    </div>
  );
}
