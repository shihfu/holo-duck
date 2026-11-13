#!/bin/sh
# Copilot fires no hook when you answer a permission prompt, so follow the
# session log until the prompt resolves: cancelled -> idle, approved -> working.
sid=$(grep -o '"sessionId":"[^"]*"' | head -1 | cut -d'"' -f4)
f="${COPILOT_HOME:-$HOME/.copilot}/session-state/$sid/events.jsonl"
[ -f "$f" ] || exit 0
n=$(wc -c < "$f")
p=$PPID # the Copilot process
(
  for _ in $(seq 1800); do
    sleep 1
    kill -0 "$p" || exit
    r=$(tail -c +$((n + 1)) "$f" | sed -n '/"type":"permission.completed"/,$p')
    [ -n "$r" ] && break
  done
  case $r in
    *'"kind":"cancelled"'*) s=idle ;;
    # The tool already finished, so postToolUse sent working. Don't overwrite a later state.
    *'"hookType":"postToolUse"'*) exit ;;
    *'"kind":"approved'*) s=working ;;
    *) exit ;;
  esac
  curl -4 -s -m 1 -d state=$s http://duck.local/state
) >/dev/null 2>&1 &
