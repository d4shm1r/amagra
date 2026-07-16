// Test setup — runs before every suite (wired in vite.config.js `test.setupFiles`).
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Unmount between tests. Without this, a dialog left open by one test is still
// in the document for the next one, and the failure surfaces somewhere unrelated.
afterEach(cleanup);
