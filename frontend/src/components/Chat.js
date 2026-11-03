import React, { useState } from "react";
import { sendChat } from "../services/api";
import ConsentModal from "./ConsentModal";

export default function Chat({ token }) {
  const [log, setLog] = useState([]);
  const [input, setInput] = useState("");
  const [status, setStatus] = useState(null);
  const [pending, setPending] = useState(null); // last request, replayed after consent

  async function call(payload) {
    try {
      const r = await sendChat(token, payload);
      if (r.reply) setLog((l) => [...l, { from: "agent", text: r.reply }]);
      setStatus(r);
      setPending(
        r.iam_required
          ? { ...payload, triage_score: r.triage_score, anamnesis_summary: r.anamnesis_summary }
          : null
      );
    } catch (err) {
      setLog((l) => [...l, { from: "agent", text: `Fehler: ${err.message}` }]);
    }
  }

  function submit(e) {
    e.preventDefault();
    const history = log.filter((m) => m.from === "patient").map((m) => m.text);
    const message = input;
    setInput("");
    setLog((l) => [...l, { from: "patient", text: message }]);
    call({ message, history, consent_granted: false });
  }

  function decide(granted) {
    const request = pending;
    setPending(null);
    if (granted) call({ ...request, consent_granted: true });
  }

  return (
    <div>
      {log.map((m, i) => (
        <p key={i}>
          <b>{m.from === "patient" ? "Sie" : "Assistent"}:</b> {m.text}
        </p>
      ))}
      {pending ? (
        <ConsentModal message={status?.iam_message} onDecision={decide} />
      ) : (
        <form onSubmit={submit}>
          <input value={input} onChange={(e) => setInput(e.target.value)} style={{ width: "80%" }} />
          <button type="submit">Senden</button>
        </form>
      )}
      {status && (
        <small>
          Triage: {status.triage_score}
          {status.appointment_id && ` | Termin: ${status.appointment_id}`}
          {status.kim_sent && " | Arztbrief per KIM gesendet"}
        </small>
      )}
    </div>
  );
}
