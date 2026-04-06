export const runtime = "edge";

const UPSTREAM_STREAM_URL =
  "https://aravind20-sre-bot-engine.hf.space/api/stream-logs";

export async function GET(request: Request) {
  const upstream = await fetch(UPSTREAM_STREAM_URL, {
    method: "GET",
    headers: {
      Accept: "text/event-stream",
      "Cache-Control": "no-cache",
      ...(request.headers.get("last-event-id")
        ? { "Last-Event-ID": request.headers.get("last-event-id") as string }
        : {}),
    },
  });

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
