# PostHog post-wizard report

The wizard has completed a deep integration of PostHog analytics into the Calypr FastAPI backend. New files created: `posthog_client.py` (shared SDK instance), `middleware.py` (per-request ASGI context). Modified files: `config.py` (added PostHog settings), `main.py` (registered middleware), `routers/agents.py`, `routers/runs.py`, and `routers/assist.py` (11 capture calls). The PostHog `posthog` SDK (v7.22.0) was added to `apps/api/pyproject.toml`. Environment variables `CALYPR_POSTHOG_PROJECT_TOKEN` and `CALYPR_POSTHOG_HOST` were written to `.env`.

| Event name | Description | File |
|---|---|---|
| `agent_created` | A user saved a new agent (name + graph spec) to their workspace. | `apps/api/src/calypr_api/routers/agents.py` |
| `agent_updated` | A user updated the name or graph spec of an existing saved agent. | `apps/api/src/calypr_api/routers/agents.py` |
| `agent_deleted` | A user deleted a saved agent from their workspace. | `apps/api/src/calypr_api/routers/agents.py` |
| `graph_compiled` | A user compiled a graph spec to check it for validation errors. | `apps/api/src/calypr_api/routers/agents.py` |
| `graph_codegen_requested` | A user requested Python code generation from a graph spec. | `apps/api/src/calypr_api/routers/agents.py` |
| `workspace_renamed` | A user renamed their workspace. | `apps/api/src/calypr_api/routers/agents.py` |
| `agent_run_started` | A user started an agent run by submitting a message to the engine. | `apps/api/src/calypr_api/routers/runs.py` |
| `agent_run_completed` | An agent run finished and emitted its final output event. | `apps/api/src/calypr_api/routers/runs.py` |
| `agent_run_failed` | An agent run encountered an unhandled error and returned an error event. | `apps/api/src/calypr_api/routers/runs.py` |
| `assist_requested` | A user sent a prompt to the AI assistant to draft or refine a graph. | `apps/api/src/calypr_api/routers/assist.py` |
| `assist_daily_cap_reached` | A user's assist request was blocked because they hit the daily workspace cap. | `apps/api/src/calypr_api/routers/assist.py` |

## Next steps

We've built some insights and a dashboard for you to keep an eye on user behavior, based on the events we just instrumented:

- [Analytics basics (wizard) — Dashboard](https://us.posthog.com/project/501592/dashboard/1810219)
- [Active agent builders (weekly)](https://us.posthog.com/project/501592/insights/UEy9vBPJ)
- [AI assistant requests](https://us.posthog.com/project/501592/insights/3fO4Zo3A)
- [Daily cap hit — churn risk](https://us.posthog.com/project/501592/insights/mKk85CgO)
- [Agent run health: completed vs failed](https://us.posthog.com/project/501592/insights/bkK1fnH6)
- [Compile → codegen → save funnel](https://us.posthog.com/project/501592/insights/nfBGaxw7)

## Verify before merging

- [ ] Run a full production build (the wizard only verified the files it touched) and fix any lint or type errors introduced by the generated code.
- [ ] Run the test suite — call sites that were rewritten or instrumented may need updated mocks or fixtures.
- [ ] Add `CALYPR_POSTHOG_PROJECT_TOKEN` and `CALYPR_POSTHOG_HOST` to `.env.example` and any monorepo bootstrap scripts so collaborators know what to set.

### Agent skill

We've left an agent skill folder in your project. You can use this context for further agent development when using Claude Code. This will help ensure the model provides the most up-to-date approaches for integrating PostHog.
