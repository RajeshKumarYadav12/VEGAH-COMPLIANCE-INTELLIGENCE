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

export async function GET() {
  const response = await fetch(
    `${normalizeBackendUrl(BACKEND_API_URL)}/health`,
    {
      cache: "no-store",
    },
  );

  return new Response(await response.text(), {
    status: response.status,
    headers: {
      "content-type":
        response.headers.get("content-type") || "application/json",
      "cache-control": "no-store",
    },
  });
}
