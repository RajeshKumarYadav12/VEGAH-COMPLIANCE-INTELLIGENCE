// VEGAH Compliance Intelligence — API Client

const API_BASE = "/api";

export async function uploadCapabilities(file: File): Promise<{
  success: boolean;
  capabilities_parsed: number;
  chunks_embedded: number;
  message: string;
}> {
  try {
    const formData = new FormData();
    formData.append("file", file);

    console.log(
      "Uploading file:",
      file.name,
      "to",
      `${API_BASE}/upload-capabilities`,
    );
    const response = await fetch(`${API_BASE}/upload-capabilities`, {
      method: "POST",
      body: formData,
    });

    console.log("Upload response status:", response.status);

    if (!response.ok) {
      const errorText = await response.text();
      console.error("Backend error:", errorText);
      let detail = "Upload failed";
      try {
        const err = JSON.parse(errorText);
        detail = err.detail || detail;
      } catch (e) {
        detail = errorText || detail;
      }
      throw new Error(detail);
    }

    return response.json();
  } catch (error) {
    console.error("Upload capabilities error:", error);
    throw error;
  }
}

export async function checkHealth(): Promise<{
  status: string;
  qdrant_connected: boolean;
  capabilities_stored: number;
  app: string;
  version: string;
}> {
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) throw new Error("Backend unavailable");
  return response.json();
}

export function createRFPStream(
  rfpFile: File,
  capabilityFile: File | null,
  reasoningModel: "claude" | "openai",
): { stream: ReadableStream<string>; abort: () => void } {
  const controller = new AbortController();

  const formData = new FormData();
  formData.append("rfp_file", rfpFile);
  if (capabilityFile) {
    formData.append("capability_file", capabilityFile);
  }
  formData.append("reasoning_model", reasoningModel);

  const stream = new ReadableStream<string>({
    async start(controller_stream) {
      try {
        console.log("Fetching:", `${API_BASE}/process-rfp`);
        const response = await fetch(`${API_BASE}/process-rfp`, {
          method: "POST",
          body: formData,
          signal: controller.signal,
        });

        if (!response.ok) {
          const errorText = await response.text();
          console.error("Backend error:", response.status, errorText);
          let detail = "Processing failed";
          try {
            const err = JSON.parse(errorText);
            detail = err.detail || detail;
          } catch (e) {
            detail = errorText || detail;
          }
          controller_stream.error(new Error(`Backend error: ${detail}`));
          return;
        }

        const reader = response.body?.getReader();
        if (!reader) {
          controller_stream.error(new Error("No response body"));
          return;
        }

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              controller_stream.enqueue(line.slice(6));
            }
          }
        }

        controller_stream.close();
      } catch (error) {
        console.error("Stream fetch error:", error);
        if (error instanceof Error) {
          controller_stream.error(error);
        } else {
          controller_stream.error(new Error("Unknown error occurred"));
        }
      }
    },
  });

  return {
    stream,
    abort: () => controller.abort(),
  };
}
