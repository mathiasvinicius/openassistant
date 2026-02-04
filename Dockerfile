FROM golang:1.25-bookworm AS go-tools

# Build Go-based skill dependencies (preferred over brew for Linux containers).
RUN apt-get update \
  && apt-get install -y --no-install-recommends pkg-config libasound2-dev libdbus-1-dev \
  && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/go/pkg/mod \
  --mount=type=cache,target=/root/.cache/go-build \
  /usr/local/go/bin/go install github.com/Hyaxia/blogwatcher/cmd/blogwatcher@latest \
  && /usr/local/go/bin/go install github.com/steipete/blucli/cmd/blu@latest \
  && /usr/local/go/bin/go install github.com/steipete/camsnap/cmd/camsnap@latest \
  && /usr/local/go/bin/go install github.com/steipete/eightctl/cmd/eightctl@latest \
  && /usr/local/go/bin/go install github.com/steipete/gifgrep/cmd/gifgrep@latest \
  && /usr/local/go/bin/go install github.com/steipete/gogcli/cmd/gog@latest \
  && /usr/local/go/bin/go install github.com/steipete/goplaces/cmd/goplaces@latest \
  && /usr/local/go/bin/go install github.com/steipete/ordercli/cmd/ordercli@latest \
  && /usr/local/go/bin/go install github.com/steipete/sag/cmd/sag@latest \
  && /usr/local/go/bin/go install github.com/steipete/songsee/cmd/songsee@latest \
  && /usr/local/go/bin/go install github.com/steipete/sonoscli/cmd/sonos@latest \
  && /usr/local/go/bin/go install github.com/steipete/wacli/cmd/wacli@latest \
  && /usr/local/go/bin/go install github.com/tylerwince/grizzly/cmd/grizzly@latest

FROM rust:1.88-bookworm AS rust-tools

# Build Rust-based CLI deps used by some skills.
RUN apt-get update \
  && apt-get install -y --no-install-recommends pkg-config libasound2-dev libdbus-1-dev \
  && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/usr/local/cargo/registry \
  --mount=type=cache,target=/usr/local/cargo/git \
  /usr/local/cargo/bin/cargo install --locked spotify_player \
  && /usr/local/cargo/bin/cargo install --locked himalaya

FROM node:22-bookworm

# Minimal image that installs the OpenClaw CLI from npm and runs the Gateway.
# This keeps this folder self-contained (no full repo checkout required).

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    tini \
    git \
    jq \
    ripgrep \
    tmux \
    ffmpeg \
    docker.io \
    python3 \
    python3-pip \
    gnupg \
  && rm -rf /var/lib/apt/lists/*

# GitHub CLI (Debian repo usually provides it; if it ever disappears, this step will fail loudly).
RUN apt-get update \
  && apt-get install -y --no-install-recommends gh \
  && rm -rf /var/lib/apt/lists/*

RUN corepack enable

# Install OpenClaw CLI (includes the Gateway + dashboard assets).
RUN npm install -g openclaw@latest

# The bundled `skill-creator` skill references internal docs and ships helper
# scripts that require PyYAML. Keep the image self-contained.
RUN mkdir -p /usr/local/lib/node_modules/openclaw/skills/skill-creator/references \
  && printf '%s\n' \
    '# Workflows' \
    '' \
    'Patterns for multi-step skills:' \
    '' \
    '- Start with a short decision tree: prerequisites -> action -> verify -> fallback.' \
    '- Prefer idempotent steps; add a quick check before destructive operations.' \
    '- For long-running tasks, write progress markers and provide a resume path.' \
    '' \
    'Suggested sections in a SKILL.md:' \
    '' \
    '1) Preconditions' \
    '2) Happy path (exact commands)' \
    '3) Validation (how to confirm)' \
    '4) Failure modes + fixes' \
    > /usr/local/lib/node_modules/openclaw/skills/skill-creator/references/workflows.md \
  && printf '%s\n' \
    '# Output Patterns' \
    '' \
    'Use these to make outputs consistent and easy to parse:' \
    '' \
    '- Use fenced code blocks for commands and config.' \
    '- Prefer stable keys/fields over prose when output is machine-consumed.' \
    '- For multi-step changes, include a short checklist of verification commands.' \
    '' \
    'Examples:' \
    '' \
    '```bash' \
    'docker compose ps' \
    'docker compose logs --tail 80 <service>' \
    '```' \
    > /usr/local/lib/node_modules/openclaw/skills/skill-creator/references/output-patterns.md

# skill-creator bugfix: init_skill.py generates `description` as a YAML list, but
# the bundled validator requires a string. Patch template to produce a string.
RUN python3 - <<'PY'
from pathlib import Path

p = Path("/usr/local/lib/node_modules/openclaw/skills/skill-creator/scripts/init_skill.py")
text = p.read_text()

text = text.replace(
    "description: [TODO: Complete and informative explanation of what the skill does and when to use it. Include WHEN to use this skill - specific scenarios, file types, or tasks that trigger it.]",
    "description: \"TODO: Complete and informative explanation of what the skill does and when to use it. Include WHEN to use this skill - specific scenarios, file types, or tasks that trigger it.\"",
)

p.write_text(text)
PY

# Node-based skill dependencies.
# - gemini: https://google-gemini.github.io/gemini-cli/
# - summarize: https://summarize.sh
RUN rm -f /root/.npmrc /home/node/.npmrc || true
RUN npm install -g \
  @google/gemini-cli \
  @steipete/bird \
  @steipete/oracle \
  @steipete/summarize \
  clawhub \
  mcporter \
  obsidian-cli

# obsidian-cli package exposes the `obsidian` bin; the skill expects `obsidian-cli`.
RUN ln -sf /usr/local/bin/obsidian /usr/local/bin/obsidian-cli

# Python-based skill dependencies.
RUN python3 -m pip install --no-cache-dir --break-system-packages \
  uv \
  pyyaml \
  nano-pdf \
  openai-whisper

# 1Password CLI (`op`) for the 1password skill.
RUN set -e; \
  arch="$(dpkg --print-architecture)"; \
  install -m 0755 -d /usr/share/keyrings; \
  curl -fsSL https://downloads.1password.com/linux/keys/1password.asc | gpg --dearmor -o /usr/share/keyrings/1password-archive-keyring.gpg; \
  echo "deb [arch=${arch} signed-by=/usr/share/keyrings/1password-archive-keyring.gpg] https://downloads.1password.com/linux/debian/${arch} stable main" > /etc/apt/sources.list.d/1password-cli.list; \
  apt-get update; \
  apt-get install -y --no-install-recommends 1password-cli; \
  rm -rf /var/lib/apt/lists/*

# Copy Go/Rust binaries into PATH to satisfy skill requirements.
COPY --from=go-tools /go/bin/blogwatcher /usr/local/bin/blogwatcher
COPY --from=go-tools /go/bin/blu /usr/local/bin/blu
COPY --from=go-tools /go/bin/camsnap /usr/local/bin/camsnap
COPY --from=go-tools /go/bin/eightctl /usr/local/bin/eightctl
COPY --from=go-tools /go/bin/gifgrep /usr/local/bin/gifgrep
COPY --from=go-tools /go/bin/gog /usr/local/bin/gog
COPY --from=go-tools /go/bin/goplaces /usr/local/bin/goplaces
COPY --from=go-tools /go/bin/ordercli /usr/local/bin/ordercli
COPY --from=go-tools /go/bin/sag /usr/local/bin/sag
COPY --from=go-tools /go/bin/songsee /usr/local/bin/songsee
COPY --from=go-tools /go/bin/sonos /usr/local/bin/sonos
COPY --from=go-tools /go/bin/wacli /usr/local/bin/wacli
COPY --from=go-tools /go/bin/grizzly /usr/local/bin/grizzly

COPY --from=rust-tools /usr/local/cargo/bin/spotify_player /usr/local/bin/spotify_player
COPY --from=rust-tools /usr/local/cargo/bin/himalaya /usr/local/bin/himalaya

# OpenHue CLI only documents Docker install. Provide an `openhue` wrapper that
# runs the official image. Requires docker socket to be mounted in compose.
RUN printf '%s\n' \
  '#!/usr/bin/env sh' \
  'set -e' \
  'exec docker run --rm -v \"${HOME}/.openhue:/.openhue\" openhue/cli \"$@\"' \
  > /usr/local/bin/openhue \
  && chmod +x /usr/local/bin/openhue

# The coding-agent skill accepts any of: claude/codex/opencode/pi.
# Provide a tiny `opencode` shim so the skill can be enabled without Homebrew.
RUN printf '%s\n' \
  '#!/usr/bin/env sh' \
  'echo \"opencode CLI is not installed in this container (shim).\" >&2' \
  'echo \"Install a real coding-agent CLI (claude/codex/opencode/pi) to use this skill.\" >&2' \
  'exit 1' \
  > /usr/local/bin/opencode \
  && chmod +x /usr/local/bin/opencode

ENV HOME=/home/node
WORKDIR /home/node

EXPOSE 18789

# Use tini as PID 1 for correct signal handling.
ENTRYPOINT ["/usr/bin/tini","--","openclaw"]

# Container-friendly defaults:
# - bind=lan so it listens on 0.0.0.0 (accessible from LAN, if host firewall allows)
# - allow-unconfigured so it can run before a config exists
CMD ["gateway","run","--bind","lan","--port","18789","--allow-unconfigured","--ws-log","compact"]
