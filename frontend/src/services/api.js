import { config } from "../config";

export class ApiError extends Error {
  constructor(status) {
    super(`Backend error ${status}`);
    this.status = status;
  }
}

export async function sendChat(token, payload) {
  let res;
  try {
    res = await fetch(`${config.apiUrl}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new ApiError(0);
  }
  if (!res.ok) throw new ApiError(res.status);
  return res.json();
}
