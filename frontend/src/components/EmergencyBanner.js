import React from "react";
import { t } from "../i18n";

export default function EmergencyBanner() {
  return (
    <div className="banner-emergency" role="alert">
      <div>
        <strong>{t("emergency.title")}</strong>
        <p>{t("emergency.text")}</p>
      </div>
      <a className="btn btn-danger" href="tel:112">
        {t("emergency.call")}
      </a>
    </div>
  );
}
