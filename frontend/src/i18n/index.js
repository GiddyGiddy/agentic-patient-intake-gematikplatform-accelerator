import de from "./de";

/** Looks up a German UI string; `{name}` placeholders are filled from `vars`. */
export function t(key, vars = {}) {
  const text = de[key] ?? key;
  return text.replace(/\{(\w+)\}/g, (_, name) => vars[name] ?? "");
}
