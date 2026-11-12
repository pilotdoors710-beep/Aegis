#!/usr/bin/env bash
# One-command deployment check (DEV_PLAN A-D1-03). Exits non-zero on the first failure.
#   SERVER=https://<backend> WEB=https://<vercel-app> deploy/smoke.sh
# Needs only curl and python3.
set -uo pipefail

: "${SERVER:?set SERVER, e.g. https://xyz.trycloudflare.com}"
: "${WEB:?set WEB, e.g. https://aegis-mu-sepia-91.vercel.app}"
SERVER="${SERVER%/}"
WEB="${WEB%/}"

pass() { printf '  \033[32mPASS\033[0m %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; exit 1; }
json() { python3 -c "import json,sys; d=json.load(sys.stdin); print($1)" 2>/dev/null; }

echo "server: $SERVER"
echo "web:    $WEB"

body=$(curl -sf -m 15 "$SERVER/healthz") || fail "GET /healthz unreachable"
[ "$(echo "$body" | json 'd.get("status")')" = "ok" ] || fail "/healthz said: $body"
pass "/healthz ok"

body=$(curl -sf -m 60 "$SERVER/healthz/browser") || fail "GET /healthz/browser failed"
title=$(echo "$body" | json 'd["title"]')
[ "$title" = "Aegis OK" ] || fail "/healthz/browser title was '$title'"
pass "/healthz/browser: Chromium $(echo "$body" | json 'd["version"]') in $(echo "$body" | json 'd["elapsed_ms"]') ms"

body=$(curl -s -m 90 "$SERVER/healthz/llm")
provider=$(echo "$body" | json 'd["provider"]+":"+d["model"]+" in "+str(d["latency_ms"])+" ms"') \
  || fail "/healthz/llm: $body"
pass "/healthz/llm: $provider"

body=$(curl -s -m 60 "$SERVER/healthz/arena")
arena=$(echo "$body" | json 'd["title"]+" <- "+d["url"]') || fail "/healthz/arena: $body"
pass "/healthz/arena: $arena"

first=$(curl -sN -m 5 "$SERVER/runs/sample/stream" 2>/dev/null | tr -d '\r' | grep -m1 '^event:') || true
[ "$first" = "event: run" ] || fail "sample stream: no 'event: run' frame within 5 s (got '$first')"
pass "SSE /runs/sample/stream first frame within 5 s"

acao=$(curl -s -m 15 -o /dev/null -D - -H "Origin: $WEB" "$SERVER/presets" \
  | tr -d '\r' | awk -F': ' 'tolower($1)=="access-control-allow-origin"{print $2}')
[ "$acao" = "$WEB" ] || fail "CORS: allow-origin was '$acao', expected '$WEB' (add it to CORS_ORIGINS and restart)"
pass "CORS allows $WEB"

code=$(curl -s -o /dev/null -w '%{http_code}' -m 15 "$WEB/arena/index.html")
[ "$code" = "200" ] || fail "$WEB/arena/index.html returned $code"
pass "arena on the web host: 200"

code=$(curl -s -o /dev/null -w '%{http_code}' -m 15 "$WEB/")
[ "$code" = "200" ] || fail "$WEB/ returned $code"
pass "console on the web host: 200"

# Real paired run (A-D2-08): both sides must finish within RUN_TIMEOUT s, with no cached decision.
PRESET="${PRESET:-clean}"
RUN_TIMEOUT="${RUN_TIMEOUT:-180}"
body=$(curl -s -m 15 -X POST "$SERVER/runs" -H 'content-type: application/json' \
  -d "{\"preset_id\":\"$PRESET\",\"auto_approve\":true}")
run_id=$(echo "$body" | json 'd["run_id"]') || fail "POST /runs: $body"
pass "POST /runs ($PRESET): run $run_id, $(echo "$body" | json 'd["status"]')"
started=$(date +%s)
summary=$(curl -sN -m "$RUN_TIMEOUT" "$SERVER/runs/$run_id/stream" 2>/dev/null | tr -d '\r' | python3 -c '
import json, sys
dones, cached, errors = {}, 0, []
for line in sys.stdin:
    if not line.startswith("data:"):
        continue
    d = json.loads(line[5:])
    k = d.get("kind")
    if k == "decision" and d["payload"]["cached"]:
        cached += 1
    elif k == "error":
        errors.append(d["mode"] + ":" + d["payload"]["code"])
    elif k == "done":
        o = d["payload"]["outcome"]
        dones[d["mode"]] = d["payload"]["reason"] + " total=" + str(o.get("total"))
print(len(dones), cached, "; ".join(f"{m} {r}" for m, r in sorted(dones.items())) or "-", errors or "")
')
elapsed=$(( $(date +%s) - started ))
read -r ndone ncached rest <<< "$summary"
[ "$ndone" = "2" ] || fail "paired run: $ndone/2 sides finished within ${RUN_TIMEOUT} s ($rest)"
[ "$ncached" = "0" ] || fail "paired run used $ncached cached decisions; the duration would be meaningless"
pass "paired run finished in ${elapsed} s: $rest"

n=$(curl -s -m 30 "$SERVER/runs/$run_id/events" | json 'len(d)') || fail "GET /runs/$run_id/events failed"
[ "${n:-0}" -gt 0 ] || fail "replay: no events for $run_id"
pass "replay: $n events for $run_id"

echo "all checks passed (paired run ${elapsed} s)"
