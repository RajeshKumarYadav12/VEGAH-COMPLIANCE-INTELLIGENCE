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

export async function POST(request: Request) {
  try {
    const bodyBuffer = await request.arrayBuffer();
    const response = await fetch(
      `${normalizeBackendUrl(BACKEND_API_URL)}/upload-capabilities`,
      {
        method: "POST",
        headers: {
          "content-type": request.headers.get("content-type") || "",
          "content-length": request.headers.get("content-length") || "",
        },
        body: bodyBuffer,
      },
    );

    return new Response(await response.text(), {
      status: response.status,
      headers: {
        "content-type":
          response.headers.get("content-type") || "application/json",
      },
    });
  } catch (error: any) {
    return new Response(JSON.stringify({ detail: error.message, stack: error.stack }), {
      status: 500,
      headers: { "content-type": "application/json" }
    });
  }
}
