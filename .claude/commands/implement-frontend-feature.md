---
description: Plan and implement a Next.js frontend feature for the support assistant
argument-hint: <feature description, e.g. "question box with cited answers">
---

Implement this frontend feature: $ARGUMENTS

## Before writing code

1. Read `CLAUDE.md` and `ARCHITECTURE.md`, and skim `logs/dev_journal.md` for the current step and past decisions.
2. Check whether the Next.js app exists yet (look for a `package.json` and an `app/` or `pages/` directory). If it doesn't, say so and make scaffolding the first step of the plan.
3. Check what the backend currently exposes. `router.py` has `answer_question(question)`, which returns `{"answer", "tool_calls"}`; there is no FastAPI layer yet unless you find one. If the feature needs an endpoint that doesn't exist, include building it in the plan.
4. Give me a short numbered plan: files to create or change, what each does, and anything you're unsure about. Wait for my go-ahead before editing.

## Rules for this project

- The frontend talks only to our own backend API. Never query Supabase or Postgres from the browser, and never expose `DATABASE_URL`, the Anthropic key, or any Supabase key to client code. Secrets stay in environment variables and are never committed.
- Answers that use documents must show their source files as citations. Don't invent citation data the backend doesn't return.
- The lookup feature is for internal staff and shows customer and order data. Don't log names, contact details or order amounts, and don't put them in URLs or client-side analytics.
- Handle loading, empty, not-found and error states explicitly (a slow answer takes several seconds).
- Keep it simple: no extra abstractions, no libraries beyond what the feature needs.

## Verify

- Start the dev server and use the feature in a browser: the happy path plus at least one not-found case and one error case. If you can't run it, say so instead of claiming it works.
- Run any existing tests and add tests for new logic where it's worth it.

## Record it

- Append an entry to `logs/frontend_implementation_log.md` (Plan, Structure, Content, Result). Not `logs/implementation_log.md`, which is for backend and data work.
- Add only outline-level changes to `logs/dev_journal.md` (current step, decisions, problems).
- Don't commit or push unless I ask.
