const MAX_QUERY_LENGTH = 200;
const BACKEND_TIMEOUT_MS = 15_000;

// POST (not GET) so the search text, which can be a name, email or phone, never appears in a URL.
export async function POST(request: Request) {
  const backendUrl = process.env.BACKEND_URL;

  if (!backendUrl) {
    return Response.json({ error: "Server is not configured." }, { status: 500 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Request body must be valid JSON." }, { status: 400 });
  }

  const query =
    typeof body === "object" && body !== null && "query" in body
      ? (body as { query: unknown }).query
      : undefined;

  if (typeof query !== "string" || query.trim() === "") {
    return Response.json({ error: "Please enter something to search for." }, { status: 400 });
  }

  if (query.trim().length > MAX_QUERY_LENGTH) {
    return Response.json(
      { error: `Search must be at most ${MAX_QUERY_LENGTH} characters.` },
      { status: 400 },
    );
  }

  try {
    const backendResponse = await fetch(
      `${backendUrl}/lookup?${new URLSearchParams({ q: query.trim() })}`,
      { signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS) },
    );

    if (!backendResponse.ok) {
      return Response.json({ error: "The lookup failed. Please try again." }, { status: 502 });
    }

    return Response.json(await backendResponse.json());
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") {
      return Response.json(
        { error: "The lookup took too long. Please try again." },
        { status: 504 },
      );
    }
    return Response.json({ error: "The lookup is unavailable. Please try again." }, { status: 502 });
  }
}
