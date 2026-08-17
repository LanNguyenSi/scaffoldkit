#!/usr/bin/env bash
# notify-planforge.sh - Open (or supersede) a bump task in agent-planforge's
# agent-tasks project whenever scaffoldkit's default branch moves.
#
# Closes the drift window between scaffoldkit HEAD and agent-planforge's
# pinned SCAFFOLDKIT_REF (server/Dockerfile) by filing
# "chore(deps): bump scaffoldkit to <sha7>" every time master advances.
#
# Required env when PLANFORGE_BOT_TOKEN is set (a "real" run):
#   PLANFORGE_BOT_TOKEN    Bearer token for the agent-tasks API. If unset or
#                          empty, this script no-ops (exit 0) with a visible
#                          notice - the secret is provisioned by the operator
#                          after this workflow merges, see README.
#   PLANFORGE_BASE_URL     e.g. https://agent-tasks.opentriologue.ai
#   PLANFORGE_PROJECT_ID   agent-planforge's project id in agent-tasks.
#   GITHUB_REPOSITORY      "owner/repo" of this scaffoldkit checkout.
#   NEW_SHA                Full commit SHA of the new HEAD. Must be
#                          resolvable via `git log`/`git diff` in the
#                          current working directory.
#
# Optional env:
#   OLD_SHA                Full commit SHA of the previous HEAD. Empty or
#                          the all-zeros SHA (GitHub's "branch just
#                          created" sentinel) is treated as "no prior
#                          commit to diff against".
#   PLANFORGE_LOOKBACK_LIMIT  How many recent tasks to scan for an existing
#                          open bump task to dedupe/supersede. Default 100.
#
# Idempotency: the agent-tasks backend dedupes task creation on
# (projectId, externalRef); we set externalRef to
# "scaffoldkit-bump/<full sha>". The public API does not expose a
# lookup-by-externalRef endpoint (GET /api/projects/{id}/tasks has no such
# filter, and Task objects don't echo externalRef back), so before creating
# we list recent tasks and scan titles/descriptions client-side:
#   - if ANY open task matching the bump-task title pattern already has a
#     description containing the full new SHA -> already filed, skip
#     creation entirely (no further API calls this run).
#   - otherwise every OTHER open task matching the pattern (i.e. for an
#     OLDER sha) gets best-effort superseded, one at a time: we re-fetch
#     it via GET /api/tasks/{id} (the list response's description can be
#     truncated/stale) and respec its fresh description with a
#     "Superseded by <newer sha7>" note (requires this bot to be the
#     task's creator; failures here are logged and non-fatal). The new
#     task is created regardless of how the supersede attempts went.
set -euo pipefail

log() { printf '%s\n' "$*" >&2; }
notice() { printf '::notice::%s\n' "$*" >&2; }
warn() { printf '::warning::%s\n' "$*" >&2; }

if [ -z "${PLANFORGE_BOT_TOKEN:-}" ]; then
  notice "PLANFORGE_BOT_TOKEN is not set; skipping the agent-planforge bump-task notification. This is expected until the operator provisions the secret (see README)."
  exit 0
fi

: "${PLANFORGE_BASE_URL:?PLANFORGE_BASE_URL is required when PLANFORGE_BOT_TOKEN is set}"
: "${PLANFORGE_PROJECT_ID:?PLANFORGE_PROJECT_ID is required when PLANFORGE_BOT_TOKEN is set}"
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required when PLANFORGE_BOT_TOKEN is set}"
: "${NEW_SHA:?NEW_SHA is required when PLANFORGE_BOT_TOKEN is set}"

OLD_SHA="${OLD_SHA:-}"
if [ "$OLD_SHA" = "0000000000000000000000000000000000000000" ]; then
  OLD_SHA=""
fi
LOOKBACK_LIMIT="${PLANFORGE_LOOKBACK_LIMIT:-100}"

NEW_SHA7="${NEW_SHA:0:7}"
COMMIT_SUBJECT="$(git log -1 --pretty=%s "$NEW_SHA")"

TITLE="chore(deps): bump scaffoldkit to ${NEW_SHA7}"
case "$COMMIT_SUBJECT" in
  'Revert '*|Revert:*|revert:*|'revert('*)
    TITLE="revert: ${TITLE}"
    ;;
  "Merge pull request"*[Rr]evert*)
    TITLE="revert: ${TITLE}"
    ;;
esac

if [ -n "$OLD_SHA" ] && git cat-file -e "${OLD_SHA}^{commit}" 2>/dev/null; then
  COMPARE_LINE="Compare: https://github.com/${GITHUB_REPOSITORY}/compare/${OLD_SHA}...${NEW_SHA}"
  FILES_STAT="$(git diff --stat "${OLD_SHA}..${NEW_SHA}")"
else
  OLD_SHA=""
  COMPARE_LINE="Compare: https://github.com/${GITHUB_REPOSITORY}/commit/${NEW_SHA} (initial push to this branch; no prior commit to diff against)"
  FILES_STAT="(initial push; no prior commit to diff against)"
fi

# SC2016: single-quoted on purpose - the literal backticks around
# `from-planforge` below must not be treated as command substitution.
# shellcheck disable=SC2016
CHECKLIST='## Re-pickup checklist
- [ ] Pull latest scaffoldkit master and confirm the commit above is still HEAD (or note the newer one)
- [ ] Update SCAFFOLDKIT_REF in server/Dockerfile to the new SHA
- [ ] Skim the compare diff above for blueprint/schema changes that need matching changes here
- [ ] Rebuild the server image locally and smoke-test scaffoldkit-input.json generation / `from-planforge`
- [ ] Open a PR bumping the pin and link this task'

DESCRIPTION="$(printf 'Commit: %s (%s)\n%s\n\nFiles changed:\n%s\n\n%s\n' \
  "$NEW_SHA" "$NEW_SHA7" "$COMPARE_LINE" "$FILES_STAT" "$CHECKLIST")"

EXTERNAL_REF="scaffoldkit-bump/${NEW_SHA}"

# ---------------------------------------------------------------------------
# HTTP helper. Sets API_STATUS and writes the response body to API_BODY_FILE.
# Never logs the Authorization header or the token. The token is kept off
# argv entirely (it would otherwise be visible to anyone who can read this
# host's process list) by routing it through a 0600 curl config file instead
# of a -H flag.
# ---------------------------------------------------------------------------
API_BODY_FILE="$(mktemp)"
AUTH_CONFIG_FILE="$(mktemp)"
chmod 600 "$AUTH_CONFIG_FILE"
trap 'rm -f "$API_BODY_FILE" "$AUTH_CONFIG_FILE"' EXIT

# curl config-file quoting: backslash-escape backslashes, then quotes.
ESCAPED_TOKEN="${PLANFORGE_BOT_TOKEN//\\/\\\\}"
ESCAPED_TOKEN="${ESCAPED_TOKEN//\"/\\\"}"
printf 'header = "Authorization: Bearer %s"\n' "$ESCAPED_TOKEN" >"$AUTH_CONFIG_FILE"

api_call() {
  local method="$1" path="$2" body="${3:-}" status
  if [ -n "$body" ]; then
    if ! status="$(curl -sS -o "$API_BODY_FILE" -w '%{http_code}' \
      --max-time 30 --connect-timeout 10 \
      -K "$AUTH_CONFIG_FILE" \
      -X "$method" \
      -H "Content-Type: application/json" \
      --data "$body" \
      "${PLANFORGE_BASE_URL}${path}")"; then
      # curl itself failed (DNS, connection refused, --max-time firing,
      # etc.) rather than returning an HTTP response. Fall back to a
      # sentinel status instead of letting `set -e` kill the whole script
      # here - every caller already has a not-200/201 handling path (warn
      # + continue for supersede, loud failure for list/create).
      status='000'
    fi
  else
    if ! status="$(curl -sS -o "$API_BODY_FILE" -w '%{http_code}' \
      --max-time 30 --connect-timeout 10 \
      -K "$AUTH_CONFIG_FILE" \
      -X "$method" \
      "${PLANFORGE_BASE_URL}${path}")"; then
      status='000'
    fi
  fi
  API_STATUS="$status"
}

# ---------------------------------------------------------------------------
# 1. Look for an existing open bump task (idempotent-skip or supersede).
# ---------------------------------------------------------------------------
api_call GET "/api/projects/${PLANFORGE_PROJECT_ID}/tasks?limit=${LOOKBACK_LIMIT}"
if [ "$API_STATUS" != "200" ]; then
  log "Failed to list existing agent-planforge tasks (HTTP ${API_STATUS}):"
  cat "$API_BODY_FILE" >&2
  exit 1
fi

if ! EXISTING_JSON="$(jq -c '[.tasks[] | select(.status == "open") | select(.title | test("chore\\(deps\\): bump scaffoldkit to "))]' "$API_BODY_FILE" 2>/dev/null)"; then
  log "Failed to list existing agent-planforge tasks (HTTP ${API_STATUS}):"
  cat "$API_BODY_FILE" >&2
  exit 1
fi

# Scan the WHOLE filtered array for an already-filed task for this exact
# NEW_SHA before deciding to skip - it might not be the first element (the
# list can carry several open bump tasks, e.g. after a manual duplicate).
SAME_SHA_ID="$(jq -r --arg sha "$NEW_SHA" \
  '[.[] | select((.description // "") | contains($sha))][0].id // empty' \
  <<<"$EXISTING_JSON")"

if [ -n "$SAME_SHA_ID" ]; then
  notice "An open bump task for ${NEW_SHA7} already exists (task ${SAME_SHA_ID}); skipping duplicate creation."
  exit 0
fi

# No same-sha match: every remaining open bump task in the array is for an
# older sha. Best-effort supersede all of them, not just the first.
OLDER_IDS="$(jq -r '.[].id' <<<"$EXISTING_JSON")"
if [ -n "$OLDER_IDS" ]; then
  while IFS= read -r OLDER_ID; do
    [ -n "$OLDER_ID" ] || continue

    # Re-fetch right before respec so the base description is authoritative
    # (the list response's description may be stale or truncated).
    api_call GET "/api/tasks/${OLDER_ID}"
    if [ "$API_STATUS" != "200" ]; then
      warn "Could not fetch task ${OLDER_ID} to supersede it (HTTP ${API_STATUS}); skipping."
      continue
    fi
    FETCHED_DESCRIPTION="$(jq -r '.task.description // .description // empty' "$API_BODY_FILE")"
    if [ -z "$FETCHED_DESCRIPTION" ]; then
      warn "Task ${OLDER_ID}'s fetched description is empty; skipping supersede to avoid clobbering it."
      continue
    fi

    SUPERSEDE_NOTE="$(printf '\n\n---\nSuperseded by %s (a newer scaffoldkit commit landed on master; see the newer bump task for current status).\n' "$NEW_SHA7")"
    SUPERSEDE_DESCRIPTION="${FETCHED_DESCRIPTION}${SUPERSEDE_NOTE}"
    RESPEC_BODY="$(jq -n --arg description "$SUPERSEDE_DESCRIPTION" '{description: $description}')"

    api_call POST "/api/tasks/${OLDER_ID}/respec" "$RESPEC_BODY"
    if [ "$API_STATUS" = "200" ]; then
      notice "Marked older open bump task ${OLDER_ID} as superseded by ${NEW_SHA7}."
    else
      warn "Could not mark task ${OLDER_ID} as superseded (HTTP ${API_STATUS}); continuing to create the new task anyway. This is expected if this bot is not that task's creator and allowNonCreatorRespec is off."
    fi
  done <<<"$OLDER_IDS"
fi

# ---------------------------------------------------------------------------
# 2. Create the new bump task.
# ---------------------------------------------------------------------------
CREATE_BODY="$(jq -n \
  --arg title "$TITLE" \
  --arg description "$DESCRIPTION" \
  --arg externalRef "$EXTERNAL_REF" \
  '{title: $title, description: $description, externalRef: $externalRef}')"

api_call POST "/api/projects/${PLANFORGE_PROJECT_ID}/tasks" "$CREATE_BODY"

if [ "$API_STATUS" = "201" ]; then
  CREATED_ID="$(jq -r '.task.id // empty' "$API_BODY_FILE" 2>/dev/null || true)"
  notice "Opened agent-planforge bump task ${CREATED_ID} for ${NEW_SHA7}."
  exit 0
fi

# --- Everything below is UNVERIFIED against the live backend. The openapi
# spec for this create endpoint documents only 201 (created) and 403
# (forbidden) - no dedupe-on-create response shape is spec'd. The 200-with-
# task-id arm and the 409/422-with-matching-body arm are our best guess at
# what a dedupe response looks like; tighten (or drop) them once we've
# observed a real duplicate response from the live backend.
if [ "$API_STATUS" = "200" ]; then
  CREATED_ID="$(jq -r '.task.id // empty' "$API_BODY_FILE" 2>/dev/null || true)"
  if [ -n "$CREATED_ID" ]; then
    notice "agent-planforge returned HTTP 200 with an existing/created task ${CREATED_ID} for ${NEW_SHA7}; treating as success."
    exit 0
  fi
fi

if [ "$API_STATUS" = "409" ] || { [ "$API_STATUS" = "422" ] && grep -qi -e 'externalref' -e 'duplicate' "$API_BODY_FILE"; }; then
  notice "agent-planforge already has a task for externalRef ${EXTERNAL_REF} (HTTP ${API_STATUS}); treating as already notified."
  exit 0
fi

log "Failed to create agent-planforge bump task (HTTP ${API_STATUS}):"
cat "$API_BODY_FILE" >&2
exit 1
