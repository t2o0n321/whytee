#!/bin/bash
# SessionStart hook: install the transcription microservice (with dev deps) so
# `ruff` and `pytest` work in Claude Code on the web sessions.
set -euo pipefail

# Only run in the remote (web) environment; local users manage their own venvs.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}/transcription-service"

# ffmpeg backs the audio tier; install if the package manager is available and
# it isn't already present. Best-effort — unit tests don't require it.
if ! command -v ffmpeg >/dev/null 2>&1 && command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg || true
fi

# Editable install is idempotent and lets the container cache the result.
pip install -e ".[dev]"
