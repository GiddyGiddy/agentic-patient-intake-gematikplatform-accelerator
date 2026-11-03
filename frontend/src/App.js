import React, { useCallback, useEffect, useState } from "react";
import Chat from "./components/Chat";
import LoginScreen from "./components/LoginScreen";
import {
  clearSession,
  completeLogin,
  getSession,
  hasCallbackParams,
  login,
  logout,
} from "./auth/oidc";
import { t } from "./i18n";

export default function App() {
  const [session, setSession] = useState(getSession);
  const [processing, setProcessing] = useState(hasCallbackParams);
  const [notice, setNotice] = useState(null);

  useEffect(() => {
    if (!hasCallbackParams()) return;
    completeLogin()
      .then(setSession)
      .catch(() => setNotice({ type: "error", text: t("auth.failed") }))
      .finally(() => {
        window.history.replaceState({}, "", window.location.pathname);
        setProcessing(false);
      });
  }, []);

  const expire = useCallback(() => {
    clearSession();
    setSession(null);
    setNotice({ type: "info", text: t("auth.expired") });
  }, []);

  const expiresAt = session?.expiresAt;
  useEffect(() => {
    if (!expiresAt) return undefined;
    const id = setTimeout(expire, Math.max(expiresAt - Date.now(), 0));
    return () => clearTimeout(id);
  }, [expiresAt, expire]);

  return (
    <div className="app">
      <a className="skip" href="#main">
        {t("app.skip")}
      </a>
      <header className="header">
        <h1>{t("app.title")}</h1>
        {session && (
          <div className="user">
            <span>{t("auth.loggedInAs", { sub: session.sub || "" })}</span>
            <button className="btn btn-link" onClick={logout}>
              {t("auth.logout")}
            </button>
          </div>
        )}
      </header>
      <main id="main">
        {notice && (
          <p className={`notice notice-${notice.type}`} role={notice.type === "error" ? "alert" : "status"}>
            {notice.text}
          </p>
        )}
        {session ? (
          <Chat token={session.accessToken} onUnauthorized={expire} />
        ) : (
          <LoginScreen onLogin={login} busy={processing} />
        )}
      </main>
      <footer className="footer">{t("app.demoNote")}</footer>
    </div>
  );
}
