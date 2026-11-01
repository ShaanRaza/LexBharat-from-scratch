# Agent Teams: Master Reference

How to build effective agent teams in this repo. Agent teams are for **building** KanoonBuddy,
never for **running** it (see `CLAUDE.md` §7: the product is a fixed pipeline, not an agent).

**Evidence labels.** Facts marked **Checked** come from the official page,
<https://code.claude.com/docs/en/agent-teams>, fetched 1 Nov 2026. The feature is experimental,
so re-check that page if something behaves differently. Anything marked **Our rule** is a
choice made for this repo, not a Claude Code fact.

---

## 1. What an agent team is

One Claude Code session is the **lead**. It spawns **teammates**: separate Claude Code
sessions, each with its own context window. Teammates message each other directly and share a
task list. You can also talk to any teammate yourself. (**Checked**)

| Part | Role |
|---|---|
| **Lead** | The main session. Spawns teammates, assigns tasks, pulls the results together. Fixed for the session's life; you cannot hand leadership to a teammate |
| **Teammates** | Separate Claude Code instances, each working on assigned tasks |
| **Task list** | Shared list of work. Tasks are `pending`, `in progress` or `completed`, and can depend on other tasks (shown as blocked until those finish) |
| **Mailbox** | How agents message each other. One JSON file per agent at `~/.claude/teams/{team-name}/inboxes/{agent-name}.json` |

```
                you
                 |
            [ LEAD ]  ---- creates tasks ---->  [ shared task list ]
           /    |    \                                  ^
          /     |     \                                 | claim / complete
   [mate A] [mate B] [mate C]  <----- messages ------>  (any mate to any mate)
```

Where the data lives (**Checked**):

- Team config: `~/.claude/teams/{team-name}/config.json`. Removed when the session ends.
  Holds runtime state. **Do not edit it by hand**; changes are overwritten.
- Task list: `~/.claude/tasks/{team-name}/`. **Stays on disk** after the session. Retention is
  set by `cleanupPeriodDays`.
- The team name is `session-` plus the first 8 characters of the session ID.
- There is no project-level team config. A `.claude/teams/teams.json` in this repo would be
  treated as an ordinary file. To define reusable roles, use subagent definitions (§6).

---

## 2. Agent team, subagent, or one session?

Pick the lightest tool that does the job. (**Checked**)

| | Single session | Subagent | Agent team |
|---|---|---|---|
| Context | One | Own window; result returns to caller | Own window; fully independent |
| Talking to each other | n/a | Return a result to the caller | Direct messages between teammates |
| Coordination | You | Main agent | Shared task list plus messages |
| Token cost | Lowest | Lower (results summarised back) | **Highest**: each teammate is a full Claude instance |
| Use when | Sequential work, same-file edits, many dependencies | Quick focused helper where only the result matters | Parallel work where teammates need to share findings, challenge each other, or own separate pieces |

### Decision test

Use a team only if **all three** are true:

1. The work splits into pieces that **do not need each other's output** while running.
2. Each piece can be owned by **a different set of files** (or is read-only).
3. Having the workers **talk to each other** adds value. If they would only report back to the
   lead, use subagents.

If any is false, use one session or subagents. A team on sequential or same-file work costs
more and goes slower.

### Strongest use cases (**Checked**)

- **Research and review**: several lenses on one thing at once.
- **New modules or features**: each teammate owns a separate piece.
- **Debugging with competing hypotheses**: teammates try to disprove each other, which beats
  the single agent that finds one plausible cause and stops.
- **Cross-layer work**: frontend, backend and tests, each owned by someone different.

---

## 3. Setup

### Enable (done in this repo)

`.claude/settings.local.json` (gitignored, so personal to this machine):

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

Without this variable no team is set up and Claude will not spawn or propose teammates.
(**Checked**)

### Three things that surprise people (**Checked**)

1. **Named subagents become teammates.** With the flag on, any subagent Claude *names* launches
   as a teammate, with no confirmation. Teams can form when you did not ask for one.
2. **It needs an interactive session.** With `-p` (non-interactive) and in Agent SDK sessions,
   Claude does not spawn teammates; named subagents run as ordinary subagents.
3. **Claude may use subagents when you wanted a team.** The agent panel shows both, so the
   panel alone does not prove a team formed. If you got subagents, ask again and say
   "agent team" explicitly.

### Turn it off

Set the variable to `"0"` in `settings.json`. It takes effect on save, no restart. Higher
precedence sources can still turn it on: project settings, local settings, a `--settings`
payload, and managed settings. A `0` in user settings overrides a shell export.

### Display modes (**Checked**)

| Mode | How it works | Works where |
|---|---|---|
| `in-process` (default) | All teammates inside your main terminal | Any terminal |
| split panes | Each teammate gets its own pane | **tmux or iTerm2 (with `it2` CLI) only** |

Set with `"teammateMode"` in `~/.claude/settings.json` (`"in-process"`, `"auto"`, `"tmux"`,
`"iterm2"`), or per session with `claude --teammate-mode auto` (experimental flag, not in
`--help`). `"auto"` uses split panes only when already inside tmux or iTerm2 with `it2`.

> **For this repo:** the owner uses VS Code on macOS. Split panes are **not supported in VS
> Code's integrated terminal**. Use `in-process`, or run Claude Code from iTerm2/tmux if you
> want to watch all teammates side by side. For iTerm2: install `it2` and enable
> *Settings → General → Magic → Enable Python API*.

---

## 4. Running a team

### Start one

Describe the task, the roles and ideally the names. Claude spawns and coordinates.

```text
Spawn three teammates to review PR #142, named security, perf and tests:
- security: security implications
- perf: performance impact
- tests: test coverage
Each reviews and reports findings. Wait for all three before summarising.
```

Name teammates in the prompt. The lead names them otherwise, and you need predictable names to
message them later. (**Checked**)

### Controls (in-process mode, **Checked**)

| Key | Action |
|---|---|
| Up / Down | Select a teammate in the agent panel (below the prompt) |
| Enter | Open that teammate's transcript and message it directly |
| Escape | Clear selection. While viewing a teammate, interrupts its current turn |
| `x` | Stop the selected teammate |
| Ctrl+T | Toggle the task list |
| Shift+Tab (while viewing a teammate) | Put that teammate in plan mode |

Idle rows hide 30 s after the whole panel goes idle and return on the teammate's next turn
(it is hidden, not stopped). More than three idle teammates collapse into an `N idle agents`
row; Enter expands it.

While viewing a teammate: plain text and skills go to the teammate. `/compact`, `/clear`,
`/rewind` act on the **lead** (you are asked to confirm). `/model` and `/fast` change the
**lead** and do not run from this view. A teammate's model is fixed when it spawns.

### Choosing models (**Checked**)

Each teammate's model comes from the first of these that applies:

1. The model your spawn prompt names for it.
2. The model in its subagent definition (`inherit` = the lead's model).
3. `CLAUDE_CODE_SUBAGENT_MODEL`, if set to anything but `inherit`.
4. The lead's current model.

`CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` makes the env var win over (1) and (2) (needs Claude Code
v2.1.257+). `teammateDefaultModel` was removed in v2.1.234; name the model in the prompt.
Teammates inherit the lead's effort level. The organisation's `availableModels` allowlist is
checked and a blocked model is swapped for another.

```text
Spawn 4 teammates to refactor these modules in parallel. Use Sonnet for each.
```

### Tasks (**Checked**)

- The lead creates tasks; teammates work through them.
- **Lead assigns** ("give task X to `perf`") or teammates **self-claim** the next unassigned,
  unblocked task when they finish. Claims use file locking, so two teammates cannot grab the
  same task.
- Teammates do not self-claim a *blocked* task. You or the lead can still assign it.
- Finishing a task automatically unblocks tasks that depended on it.
- Agents without the Task tools coordinate by messages only.
- Sizing: **5 to 6 tasks per teammate** keeps everyone busy and lets the lead reassign if
  someone is stuck. If the lead makes too few, tell it to split the work smaller.

### Plan before building (**Checked**)

Put the **lead in plan mode first**, then ask for the teammate. That teammate works read-only
until its plan is ready, then sends a plan-approval request.

- By default, if you have not changed that teammate's permission mode, Claude Code
  **approves the plan automatically** without the lead reading it. Edits and commands still
  hit the normal permission prompts.
- To make the lead actually review it, put the teammate in plan mode yourself with Shift+Tab
  while viewing its session.

### Shut down

```text
Ask the security teammate to shut down
```

The lead sends a shutdown request; the teammate may approve or refuse with a reason. It
finishes its current request or tool call first, so it can be slow. Team directories clean up
when the session ends (the task list stays; see §1).

### Hooks as quality gates (**Checked**)

Exit code 2 sends feedback and blocks the action.

| Hook | Fires when | Exit 2 does |
|---|---|---|
| `TeammateIdle` | A teammate is about to go idle | Keeps it working, with feedback |
| `TaskCreated` | A task is being created | Prevents creation |
| `TaskCompleted` | A task is being marked complete | Prevents completion |

> **Our rule:** `TaskCompleted` is the place to enforce "run the tests before a task counts as
> done" (`CLAUDE.md` §9.1, §2 rule 6). Not set up yet; add it when the first real team runs.

---

## 5. Context, communication and permissions

### What a teammate knows (**Checked**)

- It loads the same project context as any session: **CLAUDE.md, MCP servers and skills**.
  So every teammate here reads `CLAUDE.md` and the repo skills (`citation-verifier`,
  `pipeline-step`, and so on) by itself.
- It gets the **spawn prompt** from the lead.
- It does **not** get the lead's conversation history. Anything it needs must be in the spawn
  prompt or in a file it can read.
- If the lead started with `--setting-sources`, teammates use the same restricted list.

### How they talk (**Checked**)

- Messages are delivered automatically; the lead does not poll.
- When a teammate stops, it notifies the lead with its final answer. If its turn ends on an
  API error, the notice includes the error text.
- Messaging goes to **one named teammate at a time**. To reach everyone, one message each.
- A message from the lead or another teammate wakes a teammate that is waiting to retry a
  failed API call.

### Permissions (**Checked**)

- Teammates start with the **lead's permission mode**, except `dontAsk`, which is not
  inherited. If the lead uses `--dangerously-skip-permissions`, so do all teammates.
- You **cannot set per-teammate modes at spawn**. You can change one afterwards.
- Teammate permission prompts **appear in the lead's session**. Approve them there.
- To cut prompts, pre-approve common safe commands in permission settings **before** spawning.
- `--allowedTools` is **not passed to split-pane teammates**. Use `permissions.allow` under
  `--settings` instead. In-process teammates obey the lead's live allow and deny rules.
- A message from another agent is never *you*. A teammate cannot approve a prompt on your
  behalf, and a denied teammate cannot relay the request to another to get around the check.
  In auto mode, relayed approval claims are treated as untrusted and each message is reviewed
  before delivery.

> **Our rule:** never spawn a team under `--dangerously-skip-permissions` in this repo. The
> privacy and secrets rules (`CLAUDE.md` §6) assume permission prompts exist. Remember also
> that no teammate may print `.env`; every teammate inherits that rule from `CLAUDE.md`.

---

## 6. Reusable roles: subagent definitions

Define a role once in `.claude/agents/<name>.md`, then name it when spawning:

```text
Spawn a teammate using the security-reviewer agent type to audit the auth module.
```

What carries over from the definition (**Checked**; "in-process" vs "split-pane" matters):

| Field | Effect on the teammate |
|---|---|
| `tools` | Limits tools to that list. `SendMessage` (and the Task tools, where available) are added automatically |
| `disallowedTools` | In-process only. Removed from the set. `SendMessage` and Task tools stay even if listed |
| `model` | Used if the spawn prompt names none |
| `effort` | In-process only |
| `autoCompactWindow` | In-process only (v2.1.296+) |
| Body | In-process: **appended** to the default system prompt. Split-pane: **replaces** it |
| `skills` | **Ignored** in both modes. The teammate loads skills from project and user settings |
| `mcpServers` | Split-pane only. In-process teammates ignore it |

Trust note: a definition from the project's `.claude/agents/` is re-applied to a revived
teammate only if you have **trusted that exact folder** (a trusted parent does not count).
Otherwise the teammate returns without the definition's tools or instructions.

Repo status: **no `.claude/agents/` folder exists yet** (checked 1 Nov 2026). §8 proposes
starter roles.

---

## 7. Design rules for good teams

### Principles (**Checked** unless marked)

1. **Start small: 3 to 5 teammates.** Three focused beat five scattered. No hard cap, but cost
   grows linearly and returns diminish. With 15 independent tasks, start at 3.
2. **One owner per file.** Two teammates editing one file means overwrites. Split by file set.
3. **Size tasks as clear deliverables**: a function, a test file, a review. Too small and
   coordination costs more than it saves. Too large and a teammate runs long with no check-in.
4. **Put context in the spawn prompt.** Include paths, the constraint that matters, and what
   "done" looks like (see the template in §9).
5. **Make the lead wait.** The lead sometimes starts doing the work itself. Say:
   `Wait for your teammates to complete their tasks before proceeding.`
6. **Steer.** Check in, redirect, and do not leave a team running unattended for long.
7. **Learn on read-only work first**: PR review, library research, bug investigation. Move to
   parallel implementation once the habit is there.
8. **Make debate explicit when you want it.** For root-cause hunts, tell teammates to try to
   disprove each other's theories. This beats anchoring on the first plausible cause.
9. **Our rule: no team for work the docs say is sequential.** Verifier changes, migrations
   and pipeline-order changes are one-session jobs.

### Cost (**Checked**)

Teams use significantly more tokens than one session. Each teammate is a full instance.
An in-process teammate's prompt cache lasts 5 minutes by default; set
`subagentPromptCacheTtl` to `1h` to keep it longer (1-hour cache writes cost more).

---

## 8. How this maps onto KanoonBuddy

### Match teammates to the existing lanes (**Our rule**)

`team/README.md` already gives each lane its own folders so "nobody edits the same files".
That is exactly the file-ownership rule a team needs. Use the lanes as teammate boundaries.

| Teammate role | Owns (may edit) | Never edits |
|---|---|---|
| core | `core/` `adapters/` `data/` `knowledge/` `evals/` scripts | `api/` `web/` `migrations/` |
| platform | `api/` `infra/` `migrations/` `workers/` `pyproject.toml` | `core/` `web/` |
| web | `web/` and the question files in `evals/` | `core/` `api/` |
| tests | `tests/` only | Everything else |
| reviewer | Nothing (read-only) | Everything |

Cross-lane changes go through the lead, not a teammate reaching into someone's folder.

### Starter use cases that fit (**Our rule**)

| Good fit | Why |
|---|---|
| Parallel review of one PR against `CLAUDE.md` §2 (the seven rules), §5 (verifier) and §6 (privacy) | Read-only; three lenses |
| `/trust-check`-style audit split into verifier / user isolation / secrets | Independent, read-only |
| Debugging a retrieval-quality drop with competing hypotheses (query rewrite vs rerank vs gate threshold) | Real debate value |
| Building `web/` screens and the matching `api/` routes against an agreed OpenAPI shape | Two lanes, agreed contract |

### Poor fit (**Our rule**)

| Bad fit | Why |
|---|---|
| Anything in `core/verify.py` or the verifier logic | Must stay in one head; `CLAUDE.md` §8 says the owner leads here |
| Reordering or changing the 11 pipeline steps or the 50 → 10 → 8 counts | Sequential, and needs a `docs/DECISIONS.md` entry |
| Database migrations | Numbered and sequential; parallel teammates collide on numbers |
| Anything touching upload text or `user_id` filtering | Privacy-critical; review serially |

### Rules this repo's existing process puts on teams (**Our rule**)

- **One task = one issue = one branch = one PR = one session** (`CLAUDE.md` §9.7). A team is
  still one session, so a team works on **one issue, one branch, one PR**. Teammates do not
  open their own PRs.
- **The owner leads design** on `core/`, the verifier, adapters, the data model and legal or
  product decisions (`CLAUDE.md` §8). A team may *research and propose options* there. It does
  not decide. The lead must stop and ask before building.
- **Say which pipeline steps a change touches**, every time (`CLAUDE.md` §8). Put that in every
  spawn prompt that touches `core/`.
- **Tests before "done"** (`CLAUDE.md` §9.1). "Tests pass" means the output was shown.
- **Never push to `main`**; Shaan merges. No teammate pushes, deploys or touches the server.
- **Secrets**: no teammate prints `.env` or credentials, and none writes a key into a doc.

---

## 9. Templates

### Spawn prompt (copy and fill in)

```text
Spawn <N> teammates for issue #<n> (<title>), branch <name>. One PR, opened by the lead only.

Teammate <name>:
  Goal:        <one sentence, a clear deliverable>
  Owns:        <folders/files it may edit, and only these>
  Reads first: <CLAUDE.md sections, docs files, skills that apply>
  Pipeline steps touched: <list, or "none">
  Done means:  <what output proves it, e.g. test run output>
  Do not:      <files it must not touch; no pushes; no printing .env>

Rules for all: explain changes in plain words first and name file:line (CLAUDE.md §8);
report what you could not verify as "not verified".
Wait for all teammates to finish before you summarise. Do not do their work yourself.
```

### Parallel review

```text
Spawn three read-only reviewers for PR #<n>, named trust, privacy and arch:
- trust:   citation verifier integrity (CLAUDE.md §5) and the "Data you must not trust" rules
- privacy: user_id filtering, upload text never reaching Jev/Langfuse/Sentry, secrets
- arch:    the seven rules in CLAUDE.md §2 and the 11-step pipeline order
No edits. Each reports findings with file:line and severity.
```

### Competing-hypotheses debugging

```text
<symptom>. Spawn 4 teammates, one hypothesis each: <h1>, <h2>, <h3>, <h4>.
Have them message each other to try to disprove one another's theory. Read-only.
Write the surviving explanation, with evidence, to <findings file>.
```

---

## 10. Troubleshooting (**Checked**)

| Symptom | What to do |
|---|---|
| No teammates appear | Check the agent panel (arrows + Enter). A hidden idle row is not a stopped teammate: message it by name. The task may have been too simple for Claude to split. For split panes, check `which tmux` or that `it2` and its Python API are set up |
| Got subagents, not a team | Ask again and say "agent team". The panel shows both |
| Teammates appear when you did not ask | Flag is on and Claude named a subagent. Set the variable to `"0"` to get plain subagents back |
| Too many permission prompts | Pre-approve safe commands in permission settings before spawning |
| A teammate stopped on an error | Open its transcript and give instructions, or spawn a replacement. A message wakes one waiting to retry an API call |
| The lead declared the team done too early | Tell it to keep going |
| A task looks stuck | Task status can lag: teammates sometimes forget to mark it done, which blocks dependants. Check the work, then update the task or tell the lead to nudge |
| Lead messages a teammate that no longer exists after `/resume` | `/resume` and `/rewind` do **not** restore in-process teammates. Tell the lead to spawn new ones |
| Orphaned tmux session | `tmux ls`, then `tmux kill-session -t <session-name>` |
| "Failed to write to a teammate's inbox" | Usually disk full or the mailbox directory not writable. See the Claude Code errors page |

---

## 11. Limitations to plan around (**Checked**)

- **No session resumption** with in-process teammates (`/resume`, `/rewind`).
- **Task status can lag**, blocking dependent tasks.
- **Shutdown can be slow** (finishes the current call first).
- **One team per session.** No extra named teams, none shared across sessions.
- **No nested teams.** Teammates cannot spawn teammates.
- **No background subagents from in-process teammates.** A teammate's own subagents run in the
  foreground; `background: true` definitions error.
- **Lead is fixed** for the session.
- **Permissions are set at spawn** (changeable afterwards, per teammate).
- **Split panes** do not work in VS Code's terminal, Windows Terminal or Ghostty.
- **Experimental**: behaviour and flags can change between releases.

---

## 12. Related settings, and teams vs workflows

**Source note:** this section comes from a research pass over *other* pages of the official
docs (env-vars, settings-reference, tools-reference, costs, workflows). I did not re-fetch
them myself, so treat the details as **second-hand: re-check before relying on them**.

| Name | What it does |
|---|---|
| `teammateMode` | Display mode (§3). Full settings-reference entry not seen |
| `CLAUDE_CODE_SUBAGENT_MODEL` / `_FORCE` | Teammate model sources (§4) |
| `subagentPromptCacheTtl` | `5m` or `1h` cache for teammate prompts (v2.1.242+). Env override `CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL` |
| `cleanupPeriodDays` | How long `~/.claude/tasks/` is kept (costs page says the default is 30 days) |
| `CLAUDE_CODE_ENABLE_TODO_TOOLS=1` | The Task tools are on by default only for some models (reported: Opus 4.7, Sonnet 4.6, Haiku 4.5 and earlier). Newer models may need this set, or the shared task list may be missing and teammates fall back to messages only |
| `CLAUDE_CODE_ENABLE_TASKS=0` | Switches back to the older `TodoWrite` |

**Cost** (costs page, reported): use Sonnet for teammates, keep teams small, keep spawn
prompts focused, shut teammates down when done (an active teammate keeps spending until it
exits). The page also states teams run about **7x** the tokens of a normal session when
teammates run in plan mode. That figure is the docs' claim with no method given; treat it as
an **Estimate**.

**Teams vs workflows** (workflows page, reported). Workflows are a separate feature (a script
that runs many subagents) and the session's `Workflow` tool is only used when you ask for it.

| | Agent team | Workflow |
|---|---|---|
| Who holds the plan | A lead agent, deciding turn by turn | A script the runtime executes |
| Intermediate results | Shared task list | Script variables |
| Scale | A handful of long-running peers | Dozens to hundreds of agents per run |
| Pick it for | Peers who must discuss and adapt | Repeatable fan-out/fan-in jobs with a fixed shape |

Given `CLAUDE.md` §7 (fixed pipelines over agents that choose their own steps), a **workflow
is often the better build tool** for repeatable jobs such as "review every file in a diff".
Keep teams for open-ended work.

### Not verified anywhere (do not assume)

- The minimum Claude Code version for agent teams (the page gives per-feature versions only).
- Whether `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` (default 20) and the spawn-depth cap apply
  to teammates.
- Whether `CLAUDE_CODE_TASK_LIST_ID` applies to team task lists.
- The on-disk JSON format of inbox and task files (only the paths are documented).
- Input fields for the `TeammateIdle`, `TaskCreated` and `TaskCompleted` hooks. Read
  `hooks` in the docs before writing one.

---

## 13. Open items

- [ ] Create `.claude/agents/` with the roles in §8 (core, platform, web, tests, reviewer)
- [ ] Add a `TaskCompleted` hook that runs the tests and blocks completion on failure
- [ ] Run a first read-only team (parallel PR review) and record what worked in this file
- [ ] Decide whether to commit a shared `teammateMode` / team permission baseline, or keep
      teams local-only in `settings.local.json`
- [ ] Add this file to the `CLAUDE.md` §11 lookup table (not done: needs the owner's yes)

## 14. Source

<https://code.claude.com/docs/en/agent-teams>, fetched 1 Nov 2026. Related pages it links:
subagents, cross-session messaging, hooks, permission modes, settings, costs, worktrees.
The page links an index of all docs at <https://code.claude.com/docs/llms.txt>.
