const BACKEND_TIMEOUT_MS = 15_000;

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ customerId: string }> },
) {
  const backendUrl = process.env.BACKEND_URL;

  if (!backendUrl) {
    return Response.json({ error: "Server is not configured." }, { status: 500 });
  }

  const { customerId } = await params;
  if (!/^CUST-\d+$/.test(customerId)) {
    return Response.json({ error: "Invalid customer ID." }, { status: 400 });
  }

  try {
    const backendResponse = await fetch(`${backendUrl}/lookup/customers/${customerId}`, {
      signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS),
    });

    if (backendResponse.status === 404) {
      return Response.json({ error: "Customer not found." }, { status: 404 });
    }
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
