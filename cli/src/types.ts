export type Arch0Config = {
  server_url?: string;
  api_token?: string;
  send_from_who?: string;
  default_instruction?: string;
};

export type ConfigKey = keyof Arch0Config;

export type InsertPayload = {
  cmd_type: "insert";
  instruction?: string;
  archive_title: string;
  archive_content: string;
  send_from_who: string;
};

export type ArchiveResponse = {
  status: "accepted" | "needs_review" | "rejected";
  operation: "created_archive" | "updated_archive" | "needs_review" | "rejected";
  project_name: string | null;
  decision_detail: {
    confidence: "low" | "medium" | "high";
    reason: string;
    abstract?: string | null;
    target_archive_path?: string | null;
    change_summary?: string | null;
  };
  stored_path: string | null;
  index_updated: boolean;
  audit_logged: boolean;
  git_committed: boolean;
  git_commit?: string | null;
  warnings: string[];
};

export type HealthResult = {
  ok: boolean;
  statusCode?: number;
  message: string;
};

export type Output = {
  stdout: (message: string) => void;
  stderr: (message: string) => void;
};

export type CommandResult = {
  exitCode: number;
};

export type SystemInfo = {
  username: () => string;
  hostname: () => string;
};
