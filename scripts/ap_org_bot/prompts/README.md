# Prompts directory

Each agent's system prompt lives here as a `.md` file with YAML frontmatter.
**Do not** put prompts back inside `.py` files — that is the anti-pattern this
directory exists to prevent (legacy `ap_org_bot.py` had 8 prompts hardcoded as
Python f-strings, requiring a full bot restart + 1288-line `.bak` to change one).

## Layer convention

| Layer       | Path                          | Forkable to other projects? |
|-------------|-------------------------------|------------------------------|
| `_core/`    | Framework-shared (PM, Feedback PM) | Yes — keep as-is when forking |
| `_domain/ap/` | Antique Pavilion–specific       | No — replace with `_domain/<new>/` |

## Frontmatter schema

```yaml
schema_version: 1                      # bump when frontmatter shape changes
agent: <agent_name>                    # matches key in config/agents.yaml
layer: core | domain
loaded_by: [<class_name>, ...]         # which Agent class loads this prompt
prompt_version: vX.Y                   # bump when prompt body changes
last_updated: YYYY-MM-DD
notion_page_title: "<exact title in Notion Agent Prompts DB>"
```

## Body templating

Bodies are loaded by `prompts/__init__.py:load_prompt()` and consumed via
`str.format(**kwargs)` in agent classes. Use `{placeholder}` for runtime
variables (e.g. `{ticket_id}`, `{topic}`). Use `{{`/`}}` to emit a literal `{`/`}`
(important for JSON examples in `feedback_pm.md`).

## Workflow when changing a prompt

1. Edit the `.md` file. Bump `prompt_version`.
2. Update `config/prompts_versioning.yaml` `current_version` + `last_changed`
   + `change_notes` for that agent.
3. (Optional) Push the new prompt body to the Notion *Agent Prompts* DB so the
   versioning metadata stays in sync with content of record.
4. Restart the bot — `ap_org_bot/main.py` reloads prompts on startup.

No `.py` edit, no `.bak` of the bot, no full deploy.
