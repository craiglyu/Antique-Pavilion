---
description: /brief — turn Craig's raw issue into a six-field task brief (goal / scope boundary / leave alone / evidence / autonomy / model+effort) and decide whether /grill is needed, before any tool call. Use when the request is a paragraph of intent rather than a ticket.
---

# /brief — issue intake (runs before /grill and before any code)

Craig's message is the intent; this command turns it into the brief the executing model
will work from. Current models perform best when task, intent and constraints arrive
complete in the first message; a brief that is revealed over several turns costs tokens
and, on Sonnet 5, quality. Do not start work until the brief is confirmed or Craig says
"go as is".

Produce exactly this block, in Craig's language (Chinese if he wrote Chinese):

```
目標        : one sentence, the observable outcome
範圍邊界    : files / modules / surfaces in scope; what "done" covers
不碰什麼    : adjacent things that stay untouched (report as follow-ups instead)
驗收證據    : the artifact that proves completion (test command + expected output, diff, read-back)
自主程度    : autonomous (no questions until done) / checkpoint at <fork> / interactive
模型+effort : Fable 5.1 high | Opus 5 high (xhigh only for long autonomous runs) | Sonnet 5 xhigh (or /model opusplan) | Haiku 4.5 low — with one line of why
需要 /grill : yes/no — yes if it touches signed semantics, has more than one plausible reading, or is hard to reverse
```

Rules:
- Facts you can grep, you fill in yourself; decisions are Craig's — list them as numbered
  questions under the block, each with a recommendation.
- If the model+effort field differs from the session you are in, say so; Craig may switch.
- Keep it under 25 lines. A brief longer than the task is a smell.
