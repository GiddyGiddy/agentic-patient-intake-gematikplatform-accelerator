import React from "react";
import { t } from "../i18n";

function formatTime(iso) {
  const d = new Date(iso);
  if (!iso || Number.isNaN(d.getTime())) return t("result.noTime");
  return d.toLocaleString("de-DE", { dateStyle: "full", timeStyle: "short" });
}

export default function ResultCard({ result, onRestart }) {
  const score = result.triage_score;
  return (
    <section className="card result" aria-labelledby="result-title">
      <h2 id="result-title">{t("result.title")}</h2>
      <dl>
        <dt>{t("result.triage")}</dt>
        <dd>
          <span className={`badge badge-${score}`}>
            {score} – {t(`triage.${score}`)}
          </span>
        </dd>
        <dt>{t("result.appointment")}</dt>
        <dd>{formatTime(result.slot_start)}</dd>
        {result.appointment_id && (
          <>
            <dt>{t("result.appointmentId")}</dt>
            <dd>{result.appointment_id}</dd>
          </>
        )}
      </dl>
      <p>{t("result.kim")}</p>
      <button className="btn" onClick={onRestart}>
        {t("chat.restart")}
      </button>
    </section>
  );
}
