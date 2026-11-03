import "@testing-library/jest-dom";
import { webcrypto } from "crypto";

// jsdom has no WebCrypto; PKCE needs getRandomValues and subtle.digest
Object.defineProperty(globalThis, "crypto", { value: webcrypto, configurable: true });
