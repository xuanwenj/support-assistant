const MAX_QUESTION_LENGTH = 2000;
const BACKEND_TIMEOUT_MS = 60_000;

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

  const question =
    typeof body === "object" && body !== null && "question" in body
      ? (body as { question: unknown }).question
      : undefined;

  if (typeof question !== "string" || question.trim() === "") {
    return Response.json({ error: "Please enter a question." }, { status: 400 });
  }

  if (question.length > MAX_QUESTION_LENGTH) {
    return Response.json(
      { error: `Question must be at most ${MAX_QUESTION_LENGTH} characters.` },
      { status: 400 },
    );
  }

  try {
    const backendResponse = await fetch(`${backendUrl}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question.trim() }),
      signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS),
    });

    if (!backendResponse.ok) {
      return Response.json(
        { error: "The assistant could not answer. Please try again." },
        { status: 502 },
      );
    }

    const data = await backendResponse.json();
    return Response.json(data);
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") {
      return Response.json(
        { error: "The assistant took too long to answer. Please try again." },
        { status: 504 },
      );
    }
    return Response.json(
      { error: "The assistant is unavailable. Please try again." },
      { status: 502 },
    );
  }
}
