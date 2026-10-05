# Frontend Implementation Log

Record of frontend (Next.js) features as they are built: plan, structure, content, result. One entry per concrete implementation, appended in order. Backend and data work goes in [implementation_log.md](implementation_log.md); the outline (current step, decisions, problems) goes in [dev_journal.md](dev_journal.md).

Entry template: **Plan** (what and why) · **Structure** (files, components, routes, API calls) · **Content** (how it works, notable details) · **Result** (what was verified in the browser, known gaps).

---

## Reference: key Next.js concepts, compared to React

Not an implementation entry. The concepts needed for this project, written for someone who knows React but not Next.js. The file is `logs/frontend_implementation_log.md`.

| Concept | Plain React | Next.js (App Router) | Used here for |
| --- | --- | --- | --- |
| Routing | Pick a router (React Router) and declare routes in code | The folder structure under `app/` is the router: `app/page.tsx` is `/`, `app/lookup/page.tsx` is `/lookup` | Home page plus a `/lookup` page |
| Shared shell | A wrapper component you compose yourself | `app/layout.tsx` wraps every page; the matched `page.tsx` is inserted as `children`. It also owns `<html>` and `<body>` (which live in `index.html` in React) | Nav bar, page title, fonts |
| Navigation | `<a>` (full reload) or the router's link | `<Link>` from `next/link`: client-side navigation, no full page reload | Nav between the two features |
| Components | All run in the browser | **Server Components by default**: run only on the server, can be `async` and `await` data, ship no JS to the browser, cannot use hooks or event handlers. Add `"use client"` at the top of a file to make it a Client Component | Pages stay server components; the question box is a client component |
| Data fetching | `useEffect` + `fetch` + loading state, or React Query | Server components `await fetch(...)` directly. Client-side fetching is still right for user-triggered actions | Question box fetches on submit (client side) |
| Loading, error, not-found | Suspense, error boundaries and conditionals you wire up | Special files next to a page: `loading.tsx`, `error.tsx`, `not-found.tsx` | Slow answers, failed calls, missing orders |
| Backend endpoints | A separate Node/Express server | Route Handlers: `app/api/.../route.ts` run server-side inside Next.js | `app/api/ask/route.ts` proxies to FastAPI |
| Mutations | `fetch` POST from an event handler | Same, or Server Actions (functions marked `"use server"` that a form or client component calls like a function) | Plain fetch first; Server Actions are an optional comparison |
| Env vars | Build-time `VITE_`/`REACT_APP_` vars are all public | Unprefixed vars are **server-only**; `NEXT_PUBLIC_` vars are bundled into browser code and visible to everyone | Backend URL stays server-only |
| Rendering | Client-side rendering only | Per route: build time, per request, or streamed. Client components are also server-rendered on first load | Mostly background knowledge for now |

**How to tell server from client.** A file is a client component only if its first line is `"use client"`. Without it, it is a server component. Hooks (`useState`, `useEffect`) and handlers (`onClick`) are only allowed in client components, so seeing them without the marker is an error. In the scaffold, no file under `app/` has the marker, so `layout.tsx` and `page.tsx` are both server components. `layout.tsx` can also `export const metadata`, which only server components can do.

**Pattern to follow.** Keep pages as server components and push `"use client"` down to small interactive leaves, so most of the tree ships no JS.

**Easy mistakes to watch for.**
- A `NEXT_PUBLIC_` prefix on a secret or backend URL leaks it to every visitor.
- `window` or `localStorage` is undefined during server rendering, so touch them only in client components, inside effects or handlers.
- Adding `"use client"` to a layout or page "to make the error go away" pulls the whole subtree into the client bundle.

**Open questions for myself.**
- What is serialized when a server component passes props to a client component?
- When would a Server Action beat a Route Handler for this project?
- Which of `loading.tsx` / `error.tsx` replaces my own component-level states, and which do not?

---

## Reference: how CORS works, and why the proxy design avoids it

Not an implementation entry. Written for review, since the direct-fetch approach (React + Node backend) is familiar and this project deliberately takes the proxy route instead.

**Origin.** An origin is scheme + host + port. `http://localhost:3000` (Next.js) and `http://localhost:8000` (FastAPI) are different origins because the port differs.

**Same-origin policy.** A browser lets a page read responses only from its own origin. Without this, any site you visit could call your bank's API with your cookies and read the result.

**CORS is the opt-in relaxation of that policy.** The _server_ declares which other origins may read its responses. The browser enforces it. Key points:

1. **The browser enforces, not the server.** The request usually still reaches the server and runs. The browser then refuses to hand the response to your JS if the headers don't allow it. curl, Postman and server-to-server calls are never subject to CORS, which is why "it works in Postman but not in the browser" is the classic symptom.
2. **Simple requests** (GET, or POST with a form-type content type) are sent directly. The response must include `Access-Control-Allow-Origin: <your origin>` or the browser blocks JS from reading it.
3. **Preflight.** A request with `Content-Type: application/json` (our `POST /ask`) or custom headers is not "simple". The browser first sends an `OPTIONS` request asking "may origin X send method Y with headers Z?". The server must answer with `Access-Control-Allow-Origin`, `-Methods` and `-Headers`. Only then does the real POST go out. Server frameworks' CORS middleware (Express `cors`, FastAPI `CORSMiddleware`) exist mainly to answer this preflight.
4. **Credentials.** Cookies and auth headers are only sent cross-origin if the frontend sets `credentials: "include"` and the server replies `Access-Control-Allow-Credentials: true` with an explicit origin. `*` is not allowed in that case.
5. **Typical fix in the direct-fetch design:** add CORS middleware on the backend allowing the frontend origin (dev: `http://localhost:3000`; prod: the real domain, never `*` for anything with auth).

**Why the proxy design (chosen here) sidesteps it:**

```
Direct:  Browser (:3000) ──cross-origin──> FastAPI (:8000)      needs CORS config
Proxy:   Browser (:3000) ──same-origin──>  Next.js route handler ──server-to-server──> FastAPI
```

- Browser to `/api/ask` is same-origin, so no CORS applies.
- Next.js server to FastAPI is not a browser request, so CORS never applies.
- FastAPI can then reject browser origins entirely (or bind to localhost / a private network), so it is not directly callable from a web page.
- The backend URL and any future backend credential live in server-only env vars (no `NEXT_PUBLIC_` prefix) and never reach client code. This is the main reason for the proxy here, and it matches the rule that the frontend talks only to our own backend.

**Trade-off.** The proxy adds one hop and one more file to maintain (`app/api/ask/route.ts`). Direct fetch is simpler when the backend is public by design and you are happy managing CORS.

**Review questions to answer myself later:**

- What exactly does the browser send in a preflight, and who answers it?
- Why does `Access-Control-Allow-Origin: *` conflict with cookies?
- If FastAPI has no CORS middleware and I call it from the browser, does the request still execute? (Yes; the response is just unreadable to JS.)

---

## 2026-10-03: Scaffold, two routes and shared nav (steps 1–2)

**Plan.** Create the Next.js app in `frontend/`, add the two entry points (document Q&A at `/`, customer/order lookup at `/lookup`) and a shared nav, and confirm navigation is client-side. Placeholders only; no backend calls yet.

**Structure.**
- `frontend/`: scaffolded with `create-next-app` (Next.js 16.3.8, TypeScript, App Router, Tailwind, ESLint, no `src/`).
- `app/layout.tsx`: root layout. Metadata title/description updated; `<nav>` with two `<Link>`s above `{children}`.
- `app/page.tsx`: placeholder "Ask a question" (route `/`).
- `app/lookup/page.tsx`: placeholder "Customer & order lookup" (route `/lookup`).

**Content.**
- The scaffold's `AGENTS.md` warns this Next.js version differs from older docs and says to read `node_modules/next/dist/docs/` first. The layouts/pages and `Link` docs there match what was used.
- No file under `app/` has `"use client"`, so `layout.tsx` and every page are server components. The nav needs no client JS.
- The layout stays mounted across navigation; only the `page.tsx` content swaps.

**Result.** Checked in the browser (dev server on port 3001; 3000 was already taken).
- `/` and `/lookup` both render. Navigation triggers no full "Doc" request, only small `fetch` requests (`?_rsc=...`, about 1.6–1.8 kB, about 40 ms). `_rsc` is the React Server Components payload that Next.js fetches and patches into the page.
- Problem hit: `/` returned the built-in 404 because `app/page.tsx` had been deleted. A route exists only if its `page.tsx` exists. Also, the first `lookup/page.tsx` was a copy of the scaffold home page and had to be replaced.
- Known gaps: the nav has no active-link styling; nothing talks to the backend yet (no FastAPI layer exists). Next: step 3, the server/client boundary with a question-box component.

---

## 2026-10-03: Server/client boundary with QuestionBox (step 3)

**Plan.** Build a small interactive component (`useState` + input) and deliberately render it without `"use client"` to see the server/client boundary fail, then fix it. Goal: understand where the boundary goes, not just make the error disappear.

**Structure.**
- `app/components/QuestionBox.tsx`: input bound to `useState`, echoes "You typed: ...". Starts with `"use client"` after the fix.
- `app/page.tsx`: stays a server component; imports `QuestionBox` via the `@/` path alias (rooted at `frontend/`) and renders it under the heading.

**Content.**
- Why the error: every component in the App Router is a server component unless marked otherwise. Server components render once on the server and ship no JS to the browser, so they cannot hold state or handle events. `useState` without `"use client"` therefore fails.
- The fix is the `"use client"` directive at the top of the file that needs the hook. It marks a **boundary**: that file and everything it imports are bundled for the browser, while its parent stays on the server.
- **Rule: keep the boundary as low in the tree as possible.** Put `"use client"` on the smallest interactive leaf (the question box), not on `page.tsx` or `layout.tsx`. Everything above the boundary stays server-rendered and sends no JS; everything below it goes into the client bundle. Marking a page or layout "to make the error go away" would pull its whole subtree into the bundle.
- Server components can import and render client components, and can pass them serializable props. A client component cannot import a server component, but it can receive one as `children`.
- Why this matters for the project: the question box needs state (typed text, loading, answer, error), so it is a client component. The headings, nav and layout do not, so they stay on the server.

**Result.** The error appeared without the directive and went away with it, and `QuestionBox` works under a server-component page. Known gaps: it is only an input with an echo line so far (no submit, no backend call); the comment on line 1 of `QuestionBox.tsx` says `components/QuestionBox.tsx` but the file is at `app/components/QuestionBox.tsx`. Next: step 4, a FastAPI `POST /ask` endpoint wrapping `answer_question()`, then wiring the box to it through a proxy route handler.

---

## 2026-10-05: Proxy route handler and wired question box (steps 4–6)

**Plan.** The browser must not call FastAPI directly (see the CORS reference above). Add a Next.js route handler that validates the question, forwards it to FastAPI server-side and returns the result, then wire `QuestionBox` to it with loading, error and answer states.

**Structure.**
- `app/api/ask/route.ts`: `POST /api/ask`, the proxy to FastAPI `POST /ask`.
- `frontend/.env.local` (git-ignored by the scaffold's `.env*` rule): `BACKEND_URL=http://127.0.0.1:8000`, server-only (no `NEXT_PUBLIC_` prefix).
- `app/components/QuestionBox.tsx`: client component; form, loading message, error, answer and sources.

**Content.**
- Route handler order: check `BACKEND_URL` is set (500 "Server is not configured." if not), parse the JSON body (400 if invalid), validate `question` (non-blank string, at most 2000 chars, matching the FastAPI limit; 400 otherwise), forward the trimmed question, return the backend JSON.
- `request.json()` throws on a bad body, so it sits in `try/catch`. The body is typed `unknown` and narrowed by hand; `typeof null === "object"` is why `body !== null` is checked.
- Backend failures: non-OK response gives 502 ("could not answer"); unreachable backend or non-JSON body gives 502 ("unavailable"); `AbortSignal.timeout(60_000)` aborts a hung call with a `TimeoutError` and returns 504 ("took too long"). The backend's error body and the caught exception are never forwarded or logged (they can contain request details). Neither questions nor answers are logged.
- 60 s timeout chosen because compound questions took about 18 s on Haiku; it is one constant (`BACKEND_TIMEOUT_MS`).
- **Double submit.** Decision: block a second submit while one is in flight (button disabled, and the handler returns early if `loading`, because Enter in the input bypasses a disabled button). Cancel-and-replace suits typeahead, not an explicit button on a slow, paid LLM call: aborting in the browser does not stop the FastAPI work, so both requests would still be paid for. `AbortController` is the tool if a Cancel button is wanted later.
- `QuestionBox`: submit clears the previous answer and error first so a stale result never sits beside a new question; `finally` always resets `loading`; the loading text and the button label change while waiting; `role="status"` and `role="alert"` for screen readers; sources shown only when the list is non-empty.

**Result.**
- Route tested with curl: valid question 200 (doc question returned `sources`; order question returned `sources: []`); blank, missing field, wrong type, non-JSON, `null` and over-length all 400; FastAPI stopped 502 in 0.01 s; fake backend returning 200 with non-JSON 502; fake backend that never answers 504 after 60.03 s.
- Checked in the browser: loading message appears, answer and sources render, stopping FastAPI shows the error message, and pressing Enter twice sends one request.
- Gotcha: a different app was already listening on port 3000 (`Cannot POST /api/ask`, Express-style). This project's server is on 3001; test against the right port.
- Known gaps: the answer is Markdown but is shown as plain text with literal `**`; `sources` are the documents retrieved, not necessarily the ones the answer used; no authorization on the backend (see dev journal); the `/lookup` page is still a placeholder.

---

## 2026-10-05: Render answers as Markdown

**Plan.** The backend answer is Markdown but was shown in a `whitespace-pre-wrap` paragraph, so `**bold**` appeared literally. Render it with `react-markdown`, and treat the text as untrusted because it is LLM output built from documents and customer data.

**Structure.**
- `app/components/MarkdownAnswer.tsx` (new): wraps `ReactMarkdown` with `remark-gfm` and a `components` map of Tailwind classes. No `"use client"` needed (no state); it renders under the `QuestionBox` client boundary.
- `app/components/QuestionBox.tsx`: the answer paragraph is replaced by `<MarkdownAnswer>`. Loading, error and sources are unchanged.
- `package.json`: added `react-markdown` and `remark-gfm` (tables).

**Content.**
- Tailwind's preflight strips default styles, so headings, lists, code, tables and links are restyled in the `components` map instead of adding the typography plugin.
- Safety: no `rehype-raw`, so raw HTML shows as inert text; `img` renders nothing (a markdown image makes the browser fetch any URL, a data-exfiltration route if a document contains an injection); links open with `target="_blank" rel="noopener noreferrer"`; react-markdown's URL sanitising drops `javascript:` hrefs.
- Model headings (`#`, `##`) are rendered at h3/h4 size so the page's own h1 stays the top level.

**Result.**
- Browser (port 3002): a policy question rendered bold headings, bullets and italic source text with the Sources list; `ORD-9999` returned "no order with that ID" and no sources; an unreachable backend showed the red "assistant is unavailable" message.
- A temporary `/mdtest` page confirmed tables, ordered lists and inline code; `<script>` and `<b>` appeared as literal text, the image did not render, and the `javascript:` link had no href.
- `npm run lint` and `npm run build` pass. No automated tests: the frontend has no test setup.
- Gotcha: a browser tool's form fill set the DOM value without updating React state, so the button stayed disabled; typing with the keyboard works.
- Known gaps: `sources` are still the documents retrieved, not necessarily the ones used; no backend authorization (see dev journal); `/lookup` is still a placeholder. `npx tsc --noEmit` reports `LayoutProps` not found in `layout.tsx` (a Next-generated type, not from this change).

---

No further implementation entries yet.
