import { useEffect, useState } from "react";

const canAnimate = () =>
  typeof window.matchMedia === "function" &&
  !window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Reveals `text` progressively when `animate` is set (and motion is allowed). */
export function useTypewriter(text, animate) {
  const active = animate && canAnimate();
  const [count, setCount] = useState(active ? 0 : text.length);

  useEffect(() => {
    if (!active) {
      setCount(text.length);
      return undefined;
    }
    setCount(0);
    const id = setInterval(() => {
      setCount((c) => {
        if (c >= text.length) {
          clearInterval(id);
          return c;
        }
        return c + 2;
      });
    }, 20);
    return () => clearInterval(id);
  }, [text, active]);

  return text.slice(0, count);
}
