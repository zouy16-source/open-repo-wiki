#!/usr/bin/env bash
# Process a single GitHub repository locally (against LocalStack).
#
# Usage: ./local/process-repo.sh <owner> <repo> [branch]
# Example: ./local/process-repo.sh tiangolo fastapi
#
# Requires `docker compose up -d` to be running first (LocalStack + API),
# and local/.env.local to contain GITHUB_TOKEN (and optionally LLM_* keys).
set -euo pipefail

OWNER="${1:?Usage: local/process-repo.sh <owner> <repo> [branch]}"
REPO="${2:?Usage: local/process-repo.sh <owner> <repo> [branch]}"
BRANCH="${3:-}"
JOB_ID="local-${OWNER}-${REPO}-$$"

RUN_ARGS=(-e "REPO_OWNER=${OWNER}" -e "REPO_NAME=${REPO}" -e "JOB_ID=${JOB_ID}")
if [ -n "${BRANCH}" ]; then
  RUN_ARGS+=(-e "BRANCH=${BRANCH}")
fi

echo ">> Processing ${OWNER}/${REPO}${BRANCH:+ (branch: ${BRANCH})} as job ${JOB_ID}"
docker compose run --rm "${RUN_ARGS[@]}" processor

echo
echo ">> Done. Browse the result via the local API, e.g.:"
echo "   curl 'http://localhost:8000/repos/${OWNER}/${REPO}/tree?branch=${BRANCH:-main}'"
echo "   curl 'http://localhost:8000/repos/${OWNER}/${REPO}/page?branch=${BRANCH:-main}&path='"
