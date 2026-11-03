import React, { useEffect, useRef } from "react";
import { t } from "../i18n";

const DATA = ["anamnesis", "triage", "medication", "booking", "letter"];

export default function ConsentDialog({ message, onDecision }) {
  const grantRef = useRef(null);

  useEffect(() => {
    grantRef.current?.focus();
  }, []);

  function onKeyDown(e) {
    if (e.key === "Escape") onDecision(false);
  }

  return (
    <div className="overlay" onKeyDown={onKeyDown}>
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="consent-title"
        aria-describedby="consent-purpose"
      >
        <h2 id="consent-title">{t("consent.title")}</h2>
        {message && <p>{message}</p>}
        <p id="consent-purpose">{t("consent.purpose")}</p>
        <p className="strong">{t("consent.dataHeading")}</p>
        <ul>
          {DATA.map((k) => (
            <li key={k}>{t(`consent.data.${k}`)}</li>
          ))}
        </ul>
        <p>{t("consent.duration")}</p>
        <p className="muted">{t("consent.revokeInfo")}</p>
        <div className="actions">
          <button ref={grantRef} className="btn btn-primary" onClick={() => onDecision(true)}>
            {t("consent.grant")}
          </button>
          <button className="btn" onClick={() => onDecision(false)}>
            {t("consent.decline")}
          </button>
        </div>
      </div>
    </div>
  );
}
