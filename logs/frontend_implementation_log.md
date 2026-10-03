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

No further implementation entries yet.
