import type { ArchiveResponse, HealthResult, InsertPayload } from "./types";

export type FetchLike = typeof fetch;

export class Arch0HttpError extends Error {
  constructor(
    message: string,
    readonly exitCode: number,
    readonly statusCode?: number
  ) {
    super(message);
  }
}

export async function healthCheck(
  serverUrl: string,
  apiToken?: string,
  fetchImpl: FetchLike = fetch
): Promise<HealthResult> {
  try {
    const response = await fetchImpl(`${serverUrl}/healthz`, {
      method: "GET",
      headers: buildHeaders(apiToken)
    });
    if (response.ok) {
      return { ok: true, statusCode: response.status, message: "ok" };
    }
    return {
      ok: false,
      statusCode: response.status,
      message: `HTTP ${response.status}`
    };
  } catch (error) {
    return { ok: false, message: networkMessage(error) };
  }
}

export async function insertArchive(
  serverUrl: string,
  payload: InsertPayload,
  apiToken?: string,
  fetchImpl: FetchLike = fetch
): Promise<ArchiveResponse> {
  let response: Response;
  try {
    response = await fetchImpl(`${serverUrl}/v0.1/archives`, {
      method: "POST",
      headers: buildHeaders(apiToken),
      body: JSON.stringify(payload)
    });
  } catch (error) {
    throw new Arch0HttpError(`Arch0 server is unreachable: ${networkMessage(error)}`, 2);
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new Arch0HttpError(`Arch0 returned non-JSON response: HTTP ${response.status}`, 2, response.status);
  }

  if (response.status === 401 || response.status === 403) {
    throw new Arch0HttpError("unauthorized. Check API token.", 2, response.status);
  }
  if (!response.ok) {
    throw new Arch0HttpError(`Arch0 request failed: HTTP ${response.status}`, 2, response.status);
  }
  return body as ArchiveResponse;
}

export function buildHeaders(apiToken?: string): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json"
  };
  if (apiToken) {
    headers.Authorization = `Bearer ${apiToken}`;
  }
  return headers;
}

function networkMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

