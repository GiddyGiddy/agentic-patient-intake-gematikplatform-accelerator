import React from "react";
import { devLogin } from "../services/api";

export default function AuthButton({ onToken }) {
  return (
    <button onClick={async () => onToken(await devLogin())}>
      Mit Gesundheits-ID anmelden (Mock)
    </button>
  );
}
