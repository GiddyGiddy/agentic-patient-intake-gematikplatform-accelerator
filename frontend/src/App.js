import React, { useState } from "react";
import AuthButton from "./components/AuthButton";
import Chat from "./components/Chat";

export default function App() {
  const [token, setToken] = useState(null);

  return (
    <main style={{ maxWidth: 640, margin: "2rem auto", fontFamily: "sans-serif" }}>
      <h1>Patientenaufnahme</h1>
      {token ? <Chat token={token} /> : <AuthButton onToken={setToken} />}
    </main>
  );
}
