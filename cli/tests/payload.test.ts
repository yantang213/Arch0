import { describe, expect, it } from "vitest";
import { buildInsertPayload, firstMarkdownH1 } from "../src/payload";

const system = {
  username: () => "alice",
  hostname: () => "vps-prod"
};

describe("payload", () => {
  it("extracts first Markdown H1", () => {
    expect(firstMarkdownH1("intro\n# Main Title\n## Child")).toBe("Main Title");
  });

  it("resolves title from explicit option", () => {
    const payload = buildInsertPayload({
      filePath: "work_summary.md",
      fileContent: "# H1\n\nbody",
      title: "Explicit Title",
      config: {},
      system
    });
    expect(payload.archive_title).toBe("Explicit Title");
  });

  it("resolves title from H1 then file stem", () => {
    expect(
      buildInsertPayload({ filePath: "work_summary.md", fileContent: "# H1 Title\n\nbody", config: {}, system })
        .archive_title
    ).toBe("H1 Title");
    expect(
      buildInsertPayload({ filePath: "work_summary.md", fileContent: "no heading", config: {}, system }).archive_title
    ).toBe("work_summary");
  });

  it("resolves sender and instruction from options/config/fallback", () => {
    const payload = buildInsertPayload({
      filePath: "a.md",
      fileContent: "# Title",
      from: "remote-agent:test",
      instruction: "Archive it",
      config: { send_from_who: "config-sender", default_instruction: "config instruction" },
      system
    });
    expect(payload.send_from_who).toBe("remote-agent:test");
    expect(payload.instruction).toBe("Archive it");

    const fallback = buildInsertPayload({ filePath: "a.md", fileContent: "# Title", config: {}, system });
    expect(fallback.send_from_who).toBe("cli:alice@vps-prod");
  });
});

