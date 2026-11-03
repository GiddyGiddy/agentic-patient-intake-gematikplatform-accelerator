const API = process.env.REACT_APP_API_URL || "http://localhost:8000";

export async function sendChat(token, payload) {
  const res = await fetch(`${API}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Backend error ${res.status}`);
  return res.json();
}

// Dev only: fetches a token from the mock ID service.
export async function devLogin() {
  const res = await fetch("http://localhost:8081/token", { method: "POST" });
  if (!res.ok) throw new Error("Login failed");
  return (await res.json()).access_token;
}
