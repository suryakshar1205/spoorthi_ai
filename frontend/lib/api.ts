import { AskResponse, KnowledgeDocument, StreamEvent } from "@/lib/types";


const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  (typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : "http://localhost:8000");


function extractErrorMessage(raw: string, fallback: string): string {
  try {
    const payload = JSON.parse(raw) as { detail?: string };
    return payload.detail || raw || fallback;
  } catch {
    return raw || fallback;
  }
}


async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const raw = await response.text();
    throw new Error(extractErrorMessage(raw, "Request failed"));
  }
  return (await response.json()) as T;
}


export async function askQuestion(query: string, sessionId?: string): Promise<AskResponse> {
  const response = await fetch(`${API_URL}/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ query, session_id: sessionId })
  });
  return parseJson<AskResponse>(response);
}


export async function streamQuestion(
  query: string,
  sessionId: string | undefined,
  onEvent: (event: StreamEvent) => void
): Promise<void> {
  const response = await fetch(`${API_URL}/ask/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ query, session_id: sessionId })
  });

  if (!response.ok || !response.body) {
    const raw = await response.text();
    throw new Error(extractErrorMessage(raw, "Streaming connection failed."));
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const line = part
        .split("\n")
        .find((entry) => entry.startsWith("data: "));

      if (!line) {
        continue;
      }

      const payload = line.replace("data: ", "").trim();
      if (!payload) {
        continue;
      }

      onEvent(JSON.parse(payload) as StreamEvent);
    }
  }
}


export async function adminLogin(username: string, password: string): Promise<string> {
  const response = await fetch(`${API_URL}/admin/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ username, password })
  });
  const payload = await parseJson<{ access_token: string }>(response);
  return payload.access_token;
}


export async function fetchKnowledgeDocs(token: string): Promise<KnowledgeDocument[]> {
  const response = await fetch(`${API_URL}/admin/docs`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  return parseJson<KnowledgeDocument[]>(response);
}


export async function addManualContext(
  token: string,
  title: string,
  content: string
): Promise<void> {
  const response = await fetch(`${API_URL}/admin/add-context`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify({ title, content })
  });
  await parseJson<{ detail: string }>(response);
}


export async function deleteKnowledgeDoc(token: string, documentId: string): Promise<void> {
  const response = await fetch(`${API_URL}/admin/delete/${documentId}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  await parseJson<{ detail: string }>(response);
}


export async function rebuildKnowledge(token: string): Promise<void> {
  const response = await fetch(`${API_URL}/admin/reindex`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  await parseJson<{ detail: string }>(response);
}


export function uploadKnowledge(
  token: string,
  files: File[],
  onProgress: (percent: number) => void
): Promise<void> {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/admin/upload`);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);

    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable) {
        return;
      }
      onProgress(Math.round((event.loaded / event.total) * 100));
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress(100);
        resolve();
        return;
      }
      reject(new Error(extractErrorMessage(xhr.responseText, "Upload failed")));
    };

    xhr.onerror = () => reject(new Error("Upload failed"));
    xhr.send(formData);
  });
}
