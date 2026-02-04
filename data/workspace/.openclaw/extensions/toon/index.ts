type ToonPluginConfig = {
  enabled?: boolean;
  includeStatistics?: boolean;
  logConversions?: boolean;
  minJsonChars?: number;
  /**
   * Roles to consider for in-memory prompt compaction (before sending to the LLM).
   * Defaults to ["user","tool"] to avoid rewriting assistant history by surprise.
   */
  roles?: string[];
};

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function serializeToToon(obj: unknown, path = ""): string {
  if (obj === null || obj === undefined) {
    return "";
  }

  if (Array.isArray(obj)) {
    return serializeList(obj, path);
  }
  if (isPlainObject(obj)) {
    return serializeDict(obj, path);
  }
  return String(obj);
}

function serializeDict(obj: Record<string, unknown>, path: string): string {
  const parts: string[] = [];
  for (const [key, value] of Object.entries(obj)) {
    const currentPath = path ? `${path}.${key}` : key;

    if (
      Array.isArray(value) &&
      value.length > 0 &&
      isPlainObject(value[0])
    ) {
      parts.push(serializeObjectArray(key, value as Record<string, unknown>[], currentPath));
      continue;
    }

    if (isPlainObject(value)) {
      const nested = serializeDict(value, currentPath);
      if (nested) parts.push(nested);
      continue;
    }

    if (Array.isArray(value)) {
      parts.push(`${key}: ${value.map((v) => String(v)).join(",")}`);
      continue;
    }

    parts.push(`${key}: ${String(value)}`);
  }
  return parts.join("\n");
}

function serializeList(list: unknown[], path: string): string {
  if (list.length === 0) return "";
  if (list.every((item) => isPlainObject(item))) {
    const objects = list as Record<string, unknown>[];
    const keys = Object.keys(objects[0] ?? {});
    return serializeObjectArray(path || "items", objects, path || "items", keys);
  }
  return list.map((item) => String(item)).join(",");
}

function serializeObjectArray(
  arrayName: string,
  objects: Record<string, unknown>[],
  _path: string,
  keys?: string[],
): string {
  if (objects.length === 0) return "";
  const props = keys && keys.length > 0 ? keys : Object.keys(objects[0] ?? {});
  const header = `${arrayName}[${objects.length}]{${props.join(",")}}:`;
  const lines = objects.map((obj) => props.map((k) => String(obj[k] ?? "")).join(","));
  return `${header}\n${lines.join("\n")}`;
}

function toToonWithStats(obj: unknown): { toon: string; stats?: string } {
  const toon = serializeToToon(obj);
  // "token" estimate here is just character count (like the Langflow component).
  const tokenCount = toon.length;
  const jsonStr = JSON.stringify(obj);
  const originalTokens = jsonStr.length;
  const compressionRatio = originalTokens > 0 ? ((originalTokens - tokenCount) / originalTokens) * 100 : 0;
  const stats = `TOON stats: ${originalTokens} -> ${tokenCount} chars (${compressionRatio.toFixed(1)}% reduction)`;
  return { toon, stats };
}

function replaceJsonFences(prompt: string, cfg: ToonPluginConfig): string {
  const includeStats = cfg.includeStatistics === true;
  const minChars = Number.isFinite(cfg.minJsonChars) ? Math.max(0, Math.floor(cfg.minJsonChars as number)) : 300;

  // Replace ```json ...``` (case-insensitive) blocks.
  const re = /```json\s*([\s\S]*?)```/gi;
  return prompt.replace(re, (full, body: string) => {
    const trimmed = String(body ?? "").trim();
    if (!trimmed || trimmed.length < minChars) {
      return full;
    }
    try {
      const parsed = JSON.parse(trimmed);
      const { toon, stats } = includeStats ? toToonWithStats(parsed) : { toon: serializeToToon(parsed) };
      const header = includeStats && stats ? `${stats}\n\n` : "";
      return "```toon\n" + header + toon + "\n```";
    } catch {
      return full;
    }
  });
}

function tryParseJson(text: string): unknown | null {
  const trimmed = text.trim();
  if (!trimmed) return null;
  // Fast guard: only attempt parse on plausible JSON payloads.
  const first = trimmed[0];
  const last = trimmed[trimmed.length - 1];
  const looksLikeObject = first === "{" && last === "}";
  const looksLikeArray = first === "[" && last === "]";
  if (!looksLikeObject && !looksLikeArray) return null;
  try {
    return JSON.parse(trimmed);
  } catch {
    return null;
  }
}

function convertRawJsonIfWholePrompt(prompt: string, cfg: ToonPluginConfig): string {
  const includeStats = cfg.includeStatistics === true;
  const minChars = Number.isFinite(cfg.minJsonChars) ? Math.max(0, Math.floor(cfg.minJsonChars as number)) : 300;

  const trimmed = prompt.trim();
  if (trimmed.length < minChars) return prompt;

  const parsed = tryParseJson(trimmed);
  if (parsed === null) return prompt;

  const { toon, stats } = includeStats ? toToonWithStats(parsed) : { toon: serializeToToon(parsed) };
  const header = includeStats && stats ? `${stats}\n\n` : "";
  return "```toon\n" + header + toon + "\n```";
}

function compressAgentMessage(message: any, cfg: ToonPluginConfig): any {
  if (!message || typeof message !== "object") return message;
  const content = message.content;
  if (!Array.isArray(content)) return message;

  let changed = false;
  const nextContent = content.map((part: any) => {
    if (!part || typeof part !== "object") return part;
    if (part.type !== "text" || typeof part.text !== "string") return part;
    // 1) Convert fenced JSON blocks inside text
    // 2) If the whole text is valid JSON, convert the entire text
    let nextText = replaceJsonFences(part.text, cfg);
    if (nextText === part.text) {
      nextText = convertRawJsonIfWholePrompt(part.text, cfg);
    }
    if (nextText !== part.text) {
      changed = true;
      return { ...part, text: nextText };
    }
    return part;
  });

  if (!changed) return message;
  return { ...message, content: nextContent };
}

function shouldProcessRole(role: unknown, cfg: ToonPluginConfig): boolean {
  const r = typeof role === "string" ? role : "";
  const roles = Array.isArray(cfg.roles) && cfg.roles.length > 0 ? cfg.roles : ["user", "tool"];
  return roles.includes(r);
}

function compressConversationMessages(messages: any[], cfg: ToonPluginConfig): { changed: number; blocks: number } {
  let changed = 0;
  let blocks = 0;

  for (let i = 0; i < messages.length; i++) {
    const msg = messages[i];
    if (!msg || typeof msg !== "object") continue;
    if (!shouldProcessRole(msg.role, cfg)) continue;

    const beforeStr = JSON.stringify(msg);
    const next = compressAgentMessage(msg, cfg);
    if (next !== msg) {
      messages[i] = next;
      const afterStr = JSON.stringify(next);
      // Track changes even when size doesn't shrink (e.g., formatting differences).
      changed += 1;
      // Count TOON fences added by this conversion step.
      const beforeCount = (beforeStr.match(/```toon/g) ?? []).length;
      const afterCount = (afterStr.match(/```toon/g) ?? []).length;
      if (afterCount > beforeCount) {
        blocks += afterCount - beforeCount;
      }
    }
  }

  return { changed, blocks };
}

export default function register(api: any) {
  api.on("before_agent_start", (event) => {
    const pluginCfg = (api.pluginConfig ?? {}) as ToonPluginConfig;
    if (pluginCfg.enabled === false) {
      return;
    }

    // Mutate the in-memory message history before the run, so *any* provider
    // (Gemini/Claude/Codex/...) sees the compact TOON representation.
    if (Array.isArray(event?.messages)) {
      const { changed, blocks } = compressConversationMessages(event.messages, pluginCfg);
      if (pluginCfg.logConversions && (changed > 0 || blocks > 0)) {
        try {
          api.logger?.info?.(`[toon] compacted message history: changed=${changed} blocks=${blocks}`);
        } catch {
          // ignore logger errors
        }
      }
    }
  });

  // Persist compressed versions of tool results in session transcripts, so future turns
  // carry TOON instead of large JSON blocks.
  api.on("tool_result_persist", (event: any) => {
    const pluginCfg = (api.pluginConfig ?? {}) as ToonPluginConfig;
    if (pluginCfg.enabled === false) return;

    const msg = event?.message;
    if (!msg || typeof msg !== "object") return;
    if (msg.role !== "tool") return;

    const next = compressAgentMessage(msg, pluginCfg);
    if (next !== msg) {
      if (pluginCfg.logConversions) {
        try {
          api.logger?.info?.(`[toon] converted fenced JSON blocks in tool result (${String(event?.toolName ?? "unknown")})`);
        } catch {
          // ignore logger errors
        }
      }
      return { message: next };
    }
  });
}
