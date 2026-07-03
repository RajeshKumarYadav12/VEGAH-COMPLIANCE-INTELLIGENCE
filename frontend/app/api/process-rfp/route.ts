const BACKEND_API_URL =
  process.env.BACKEND_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8001";

function normalizeBackendUrl(value: string) {
  let url = value;
  if (!url.startsWith("http://") && !url.startsWith("https://")) {
    url = `http://${url}`;
  }
  return url.replace("localhost", "127.0.0.1");
}

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const bodyBuffer = await request.arrayBuffer();
  const response = await fetch(
    `${normalizeBackendUrl(BACKEND_API_URL)}/process-rfp`,
    {
      method: "POST",
      headers: {
        "content-type": request.headers.get("content-type") || "",
        "content-length": request.headers.get("content-length") || "",
      },
      body: bodyBuffer,
    },
  );

  const headers = new Headers();
  const contentType = response.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  headers.set("cache-control", "no-cache, no-transform");
  headers.set("connection", "keep-alive");
  headers.set("x-accel-buffering", "no");

  return new Response(response.body, {
    status: response.status,
    headers,
  });
}
