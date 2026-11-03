import React from "react";

export default function ConsentModal({ message, onDecision }) {
  return (
    <div role="dialog" style={{ border: "1px solid #888", padding: "1rem" }}>
      <h2>Zugriff auf die elektronische Patientenakte (ePA)</h2>
      <p>{message || "Bitte geben Sie den Zugriff über Ihre Gesundheits-ID frei."}</p>
      <button onClick={() => onDecision(true)}>Mit Gesundheits-ID freigeben</button>{" "}
      <button onClick={() => onDecision(false)}>Ablehnen</button>
    </div>
  );
}
