/**
 * api.ts
 *
 * Single entry point the views import from. Re-exports every type from
 * liveApi.ts (the canonical shape) and picks which implementation backs
 * `api` at build time:
 *   - default / dev: liveApi, talks to the real FastAPI backend on :8000
 *   - VITE_STATIC=true (production build for GitHub Pages): staticApi, runs
 *     entirely client-side against a precomputed bundle + the ported engine
 *     in staticEngine.ts. See staticApi.ts for why this exists.
 */
export * from "./liveApi";
import { liveApi } from "./liveApi";
import { staticApi } from "./staticApi";

const isStatic = (import.meta as any).env?.VITE_STATIC === "true";

export const api = isStatic ? staticApi : liveApi;
