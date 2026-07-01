---
name: audit-to-plan
description: >
  End-to-end pipeline that turns a systemic audit into an approved correction
  plan through five phases: systemic audit, issue identification,
  classification/prioritization, a prioritized index report, one-by-one
  human-in-the-loop decision resolution, and a canonical implementation plan.
  Use when the user asks to audit or review a project, revisar or auditar un
  proyecto, auditoría sistémica, systemic review, find/classify/prioritize
  issues, incidencias, hallazgos, deuda técnica, riesgos de compatibilidad, or
  to investigate a concrete problem and drive it to a fix — even if they do not
  name this skill. Orchestrates resolve-open-decisions (phase 4) and create-plan
  (phase 5); do not duplicate their rules. Also triggers on índice de
  incidencias, PROJECT-REVIEW, resolver decisiones 1 por 1, human on the loop.
when_to_use: >
  Invoke with /audit-to-plan [scope] or when the user wants to go from "there may
  be problems here" to "an approved plan to fix them": auditing a codebase,
  reviewing for bugs/compat/UX/debt, or investigating one concrete issue and
  planning its correction. Scales from a single-problem investigation to a full
  multi-platform systemic audit.
---

# Workflow: Audit to plan

<!-- <user_communication> -->
Ask, confirm, and respond to the user in **Spanish** (native Spanish-speaking
audience). Keep this artifact's instructions in **English** for token efficiency.
Canonical policy: `<language_policy>` in
[artifact-structuring](../artifact-structuring/SKILL.md). User-facing rules:
[AGENTS.md](../../../AGENTS.md) §0. Keep standard technical terms and code
identifiers in their original form (e.g. `file:line`, API names, flags).
<!-- </user_communication> -->

<!-- <overview> -->
## Overview

This skill codifies the complete meta-workflow that takes a project (or one
concrete problem) from **unknown state** to an **approved correction plan**,
keeping the human in the loop at the decision boundary. It is agnostic to the
domain audited (compatibility, security, UX, performance, tech debt, a single
bug — anything).

Five phases, in order:

| # | Phase | Owner | Deliverable |
|---|-------|-------|-------------|
| 1 | **Systemic audit** | this skill | Raw observations from directed inspection |
| 2 | **Identify issues** | this skill | Discrete findings with evidence |
| 3 | **Classify, prioritize & document** | this skill | Prioritized **index report** (the review) |
| 4 | **Resolve decisions 1×1** | `resolve-open-decisions` | Chosen approach per finding |
| 5 | **Define the plan** | `create-plan` | Canonical, approved correction plan |

Phases 1–3 are **owned here**. Phases 4–5 **delegate** to sibling skills
([resolve-open-decisions](../resolve-open-decisions/SKILL.md) and
[create-plan](../create-plan/SKILL.md)); this skill provides them the findings
and index as input and never restates their internal rules (shared canonical
reference, not duplication).

The index report from phase 3 is the **hinge**: it is the durable artifact that
survives session boundaries and feeds the interactive resolution of phase 4.
<!-- </overview> -->

<!-- <when_to_apply> -->
## When it applies

- The user asks to audit, review, or assess a project or module.
- The user reports symptoms ("something is off", "is this production-ready?",
  "check compatibility across platforms") without a fixed list of fixes yet.
- The user wants to investigate **one** concrete problem and drive it to a
  correction plan.
- A prior audit produced raw findings and the user wants them classified,
  resolved, and planned.

If the user already has a finished index/review and only wants the interactive
resolution or the plan, **skip to phase 4 or 5** and delegate directly — do not
redo phases 1–3.
<!-- </when_to_apply> -->

<!-- <scope_calibration> -->
## Scope calibration (first step, always)

Before auditing, size the effort with the user. The same five phases apply at
any scale; only their depth changes.

- **Concrete-problem mode**: one symptom or module. Phase 1 is a focused root-cause
  investigation; the index may hold a handful of findings; phase 4 may be a single
  decision batch. Do not inflate a one-bug investigation into a full report.
- **Systemic-audit mode**: whole project or a broad concern (e.g. multi-platform
  compatibility + UX before a release). Phase 1 is a directed sweep across the
  relevant surface; the index is a full report with many findings across areas.

If the intended scope, target surface, or the audit lens (what class of problems
to look for) is unclear, ask **in Spanish** before starting. Never invent scope.
<!-- </scope_calibration> -->

<!-- <operation> -->
## How to operate this workflow

**Harness tooling (reflective, not mechanical)**: this skill targets Claude Code
first but runs in any agentic harness. Map each capability to its local
equivalent: read-only code exploration for the audit (Claude Code: `Grep`,
`Glob`, `Read`, and `Agent` with `subagent_type: "Explore"` for parallel
fan-out); structured user questions for decisions (via `resolve-open-decisions`
→ `AskUserQuestion`); a read-only planning/approval mode for the plan (via
`create-plan` → `EnterPlanMode`/`ExitPlanMode`); and task-list tracking
(`TaskCreate`/`TaskUpdate`) to trace findings and phase progress. Where a
capability is absent, achieve its intent by other means rather than skipping it.

This workflow is **interactive by design**: stopping to confirm scope (phase 0),
to resolve decisions (phase 4), and to approve the plan (phase 5) is success, not
failure. Do not audit-resolve-plan in one silent pass.

**Do not mutate code in this workflow.** Phases 1–3 are read-only inspection and
documentation; phase 5 produces a *plan*, not the fix. Execution of the plan is a
separate flow the user starts after approval.

**Composition.** Phases 4 and 5 sub-invoke sibling skills following Pattern A
(invocation with result consumption) of the `<sub_invocation_protocol>` in
[artifact-structuring](../artifact-structuring/SKILL.md): pass explicit input,
let the sub-skill deliver its canonical output as a hand-off, and surface its
approval gates to the user through this outer flow.
<!-- </operation> -->

<!-- <phase_1_audit> -->
## Phase 1 — Systemic audit

Directed, read-only inspection of the target surface under the chosen lens.

1. Resolve the target surface from the scope: entry points, platform-specific
   branches, build/CI config, dependency manifests, docs — whatever the lens
   demands. Use `Glob`/`Grep` to map, `Read` to inspect, and delegate independent
   sweeps to `Explore` subagents in parallel when the surface is broad.
2. Inspect against the lens. For compatibility: per-OS code paths, subprocess
   calls, path handling. For UX: user-facing messages, first-run behavior,
   error paths. For debt/security/perf: adapt the lens accordingly.
3. Record raw observations with **evidence** (`file:line`) as you go — do not yet
   classify. Track them with the task list so none is dropped.

Output of this phase is raw material for phase 2, not a report.
<!-- </phase_1_audit> -->

<!-- <phase_2_identify> -->
## Phase 2 — Identify issues

Turn raw observations into discrete, well-formed **findings**. Each finding is
atomic (one problem) and carries the fields below. Assign a short stable **ID**
with a domain prefix and a number (e.g. `CP-01` for a compatibility review,
`SEC-01`, `UX-01`) so later phases and sessions can reference it unambiguously.

Finding schema:

| Field | Content |
|-------|---------|
| **ID** | Stable prefix+number (e.g. `CP-01`) |
| **Título** | One-line statement of the problem |
| **Severidad** | Blocking / high / medium / low (define the ladder for the domain) |
| **Área/plataforma** | Where it applies (module, OS, layer) |
| **Evidencia** | `file:line` (or config/doc locator) proving it |
| **Causa** | Why it happens |
| **Impacto** | What breaks or degrades, and for whom |
| **Corrección(es) propuesta(s)** | One or more candidate fixes |
| **Decisión requerida** | Flag when the fix needs an owner choice (feeds phase 4) |

Deduplicate and merge overlapping observations. A finding with no owner decision
and a single obvious fix still gets recorded — it becomes a direct plan task.
<!-- </phase_2_identify> -->

<!-- <phase_3_document> -->
## Phase 3 — Classify, prioritize & document the index

Assemble the findings into the **index report** — the hinge artifact. Use the
template in `<review_template>`. Prioritize by severity and dependency (a
blocking finding that gates others ranks first). Group the recommended fix order
into phases so phase 5 can map them to ordered tasks.

**Persist the report to disk.** Default path: `docs/PROJECT-REVIEW.md` (or a
scope-specific name). Confirm the path with the user if ambiguous. This file is
what makes the workflow resumable across sessions and is the direct input to
phase 4.

After writing it, present a short Spanish summary (counts by severity, the
recommended-order phases) and confirm with the user before entering resolution.
<!-- </phase_3_document> -->

<!-- <phase_4_resolve> -->
## Phase 4 — Resolve decisions 1×1 (human in the loop)

Delegate to [resolve-open-decisions](../resolve-open-decisions/SKILL.md). Do
**not** restate its form rules, batching, or gate here — follow that skill.

Sub-invocation input this skill provides:

- The list of findings that carry a **Decisión requerida** flag (and any whose
  chosen approach is not self-evident), each with its candidate corrections from
  the index as the option set.
- The active review name and, if the user declared one, a maintenance profile.

Contract:

- **One question per finding**, options ordered most-to-least recommended with
  explicit trade-offs, batched ≤4 per call (see that skill's `<batching>`).
- **Emergent escalations (key insight):** when a human answer reveals a deeper
  design problem than the finding captured, **pause and open new decisions**
  before continuing — do not silently absorb it. Reflect the escalation back into
  the index (add/adjust findings) so the report stays the source of truth. This
  really happens (a "how does X relate to Y?" answer can trigger a redesign).
- The gate belongs to the user: resume only after every batch is answered.

Record each resolved approach against its finding ID in the index (or a
decisions log) so phase 5 consumes concrete, closed choices.
<!-- </phase_4_resolve> -->

<!-- <phase_5_plan> -->
## Phase 5 — Define the correction plan

Delegate to [create-plan](../create-plan/SKILL.md) in sub-invoked mode. Do not
restate its template or rules here.

Sub-invocation input this skill provides:

- The resolved approach for every finding (from phase 4) as the requirements.
- The index report as context and the source-of-truth for evidence and ordering.

Mapping guidance for the plan:

- Each finding maps to one execution task, or several cohesive findings that
  touch the same surface collapse into one task.
- The recommended-order phases from the index inform the task numbering and the
  dependency graph create-plan builds.

The plan-approval gate (`ExitPlanMode` or its equivalent) is surfaced to the
user by create-plan. This skill delivers the audit-to-plan pipeline **up to an
approved plan**; executing the plan is a separate flow.
<!-- </phase_5_plan> -->

<!-- <review_template> -->
## Index report template (phase 3 deliverable)

Spanish prose; keep `file:line` and identifiers verbatim. Adapt severity labels
and the ID prefix to the domain.

```markdown
# Revisión: {{título del alcance auditado}}

## Resumen ejecutivo

{{Una o dos frases: qué se auditó, bajo qué lente, y el veredicto global.}}

| ID | Título | Severidad | Área/plataforma | Decisión requerida |
|----|--------|-----------|-----------------|--------------------|
| {{CP-01}} | {{...}} | {{Bloqueante}} | {{...}} | {{Sí/No}} |

## Hallazgos por severidad

### {{Bloqueantes}}

#### {{CP-01}} — {{título}}
- **Área/plataforma**: {{...}}
- **Evidencia**: `{{archivo:línea}}`
- **Causa**: {{...}}
- **Impacto**: {{...}}
- **Corrección(es) propuesta(s)**: {{una o más; marcar cuál se recomienda}}
- **Decisión requerida**: {{Sí — describir la elección | No}}

{{...repetir por hallazgo, agrupado por nivel de severidad descendente...}}

## Orden de corrección recomendado

{{Fases ordenadas (Fase 1, Fase 2, ...) que agrupan los IDs por prioridad y
dependencia; alimentan la numeración de tareas del plan.}}

## Decisiones pendientes del propietario

{{Lista de los IDs con «Decisión requerida: Sí» y la elección concreta que se
resolverá en la fase interactiva.}}

## Notas de verificación pendiente

{{Hallazgos detectados por análisis estático que aún deben confirmarse en
ejecución/CI, con dónde verificarlos.}}
```
<!-- </review_template> -->

<!-- <constraints> -->
## Constraints

- **Read-only until the plan**: never edit source code in this workflow. Phases
  1–3 inspect and document; phase 5 outputs a plan, not a fix.
- **Do not duplicate sibling skills**: phase 4 and phase 5 follow
  `resolve-open-decisions` and `create-plan` respectively; provide input and
  consume output, never restate their rules.
- **Persist the index** before phase 4 so the workflow is resumable.
- **Evidence is mandatory**: every finding cites a concrete `file:line` or
  locator; no evidence-free findings.
- **Human owns the decisions and the plan approval**: never resolve a flagged
  decision unilaterally, never skip the plan-approval gate.
- All user-facing questions, summaries, and the index report are in **Spanish**;
  identifiers, paths, and API names stay in their original form.
<!-- </constraints> -->

<!-- <verification> -->
## Verification before delivery

1. Was the scope calibrated with the user (concrete-problem vs systemic-audit)
   before auditing?
2. Does every finding carry an ID, severity, evidence (`file:line`), cause,
   impact, and at least one proposed correction?
3. Was the index report persisted to disk and summarized to the user before
   entering resolution?
4. Were all findings flagged **Decisión requerida** resolved via
   `resolve-open-decisions` (one question each, trade-offs, ≤4 per batch), and
   were emergent escalations surfaced rather than absorbed?
5. Was the plan produced via `create-plan` from the resolved approaches, with the
   approval gate surfaced to the user?
6. Did the workflow stay read-only (no code mutations) through to plan approval?
7. Is all user-facing output in Spanish, with identifiers and paths verbatim, and
   no internal XML block names leaked?
<!-- </verification> -->

<!-- <example> -->
## Example

**Input:** «Audita la compatibilidad multiplataforma de tts-sidecar antes de los
builds de CI.»

**Flow:**
1. **Scope**: systemic-audit mode, lens = compatibilidad Windows/Linux/macOS + UX.
2. **Audit**: sweep per-OS branches in `cli.py`, `audio.py`, `daemon/`, the build
   scripts and `.circleci/config.yml`.
3. **Identify**: findings `CP-01`…`CP-13` with `file:line` evidence.
4. **Document**: write `docs/PROJECT-REVIEW.md` (summary table, findings by
   severity, recommended-order phases, owner decisions).
5. **Resolve**: `resolve-open-decisions` batches — one question per finding; a
   "¿cómo se relaciona CP-13 con CP-08?" answer escalates into a voice-model
   redesign, so new decisions are opened before continuing.
6. **Plan**: `create-plan` turns the resolved approaches into a canonical plan,
   grouping findings into ordered tasks; the user approves it.

**Output:** an approved correction plan; no code changed by this workflow.
<!-- </example> -->
