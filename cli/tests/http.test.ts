import { describe, expect, it, vi } from "vitest";
import { buildHeaders, healthCheck, insertArchive } from "../src/http";
import type { InsertPayload } from "../src/types";

const payload: InsertPayload = {
  cmd_type: "insert",
  archive_title: "Title",
  archive_content: "# Title\n\nBody",
  send_from_who: "cli:test"
};

describe("http", () => {
  it("adds authorization only when token exists", () => {
    expect(buildHeaders()).not.toHaveProperty("Authorization");
    expect(buildHeaders("token").Authorization).toBe("Bearer token");
  });

  it("checks health", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ status: "ok" }), { status: 200 }));
    const result = await healthCheck("http://server", "token", fetchMock as typeof fetch);
    expect(result.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://server/healthz",
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: "Bearer token" }) })
    );
  });

  it("inserts archive and parses response", async () => {
    const archiveResponse = {
      status: "accepted",
      project_name: "Project",
      decision_detail: { confidence: "high", reason: "ok", abstract: "summary" },
      stored_path: "arch-vault/Project/archives/title.md",
      index_updated: true,
      audit_logged: true,
      warnings: []
    };
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(archiveResponse), { status: 200 }));
    const result = await insertArchive("http://server", payload, undefined, fetchMock as typeof fetch);
    expect(result.project_name).toBe("Project");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://server/v0.1/archives",
      expect.objectContaining({ method: "POST", body: JSON.stringify(payload) })
    );
  });

  it("maps network errors", async () => {
    const fetchMock = vi.fn(async () => {
      throw new Error("connection timed out");
    });
    await expect(insertArchive("http://server", payload, undefined, fetchMock as typeof fetch)).rejects.toMatchObject({
      exitCode: 2
    });
  });
});

