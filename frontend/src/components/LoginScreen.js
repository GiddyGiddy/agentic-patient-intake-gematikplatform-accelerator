import React from "react";
import { t } from "../i18n";

export default function LoginScreen({ onLogin, busy }) {
  return (
    <section className="card" aria-labelledby="login-title">
      <h2 id="login-title">{t("auth.heading")}</h2>
      <p>{t("auth.intro")}</p>
      <button className="btn btn-primary" onClick={onLogin} disabled={busy}>
        {busy ? t("auth.processing") : t("auth.login")}
      </button>
    </section>
  );
}
