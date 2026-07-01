---
name: audit-to-plan
description: >
  End-to-end orchestrator that turns a systemic audit into an approved
  correction plan through five phases: scope calibration, a delegated read-only
  investigation, a classified/prioritized index report, one-by-one
  human-in-the-loop decision resolution, and a canonical implementation plan.
  Use when the user asks to audit or review a project, revisar or auditar un
  proyecto, auditoría sistémica, systemic review, find/classify/prioritize
  issues, incidencias, hallazgos, deuda técnica, riesgos de compatibilidad, or
  to investigate a concrete problem and drive it to a fix — even if they do not
  name this skill. Orchestrates investigate (phase 2), resolve-open-decisions
  (phase 4) and create-plan (phase 5); do not duplicate their rules. Also
  triggers on índice de incidencias, PROJECT-REVIEW, resolver decisiones 1 por 1,
  human on the loop.
when_to_use: >
  Invoke with /audit-to-plan [scope] or when the user wants to go from "there may
  be problems here" to "an approved plan to fix them": auditing a codebase,
  reviewing for bugs/compat/UX/debt, or investigating one concrete issue and
  planning its correction. Scales from a single-problem investigation to a full
  multi-platform systemic audit. Routing: for read-only exploration that ends at
  findings (no plan), use investigate instead; audit-to-plan carries all the way
  to an approved correction plan.
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
bug — anything). It is an **orchestrator**: it owns only calibration and the
index, and delegates the investigation, the decisions, and the plan to sibling
skills without reimplementing their machinery.

Five phases, in order:

| # | Phase | Owner | Deliverable |
|---|-------|-------|-------------|
| 1 | **Scope calibration** | this skill (owned) | Mode, lens, target surface, maintenance profile |
| 2 | **Investigation** | `investigate` (delegated) | Proven findings with `file:line` evidence |
| 3 | **Classify, prioritize & index** | this skill (owned) | Prioritized **index report** (the review) |
| 4 | **Resolve decisions 1×1** | `resolve-open-decisions` (delegated) | Chosen approach per finding |
| 5 | **Define the plan** | `create-plan` (delegated) | Canonical, approved correction plan |

Phases 1 and 3 are **owned here** (calibration and the index). Phases 2, 4 and 5
**delegate** to sibling skills
([investigate](../investigate/SKILL.md),
[resolve-open-decisions](../resolve-open-decisions/SKILL.md) and
[create-plan](../create-plan/SKILL.md)); this skill provides each its input and
consumes its canonical output, and never restates their internal rules (shared
canonical reference, not duplication).

The index report from phase 3 is the **hinge**: it is the durable, persisted
artifact that survives session boundaries, feeds the interactive resolution of
phase 4, and lets the pipeline resume from a prior run.
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

**Routing.** If the user only wants a read-only exploration that ends at
findings (no correction plan), that is [investigate](../investigate/SKILL.md) —
this skill wraps it and continues to an approved plan. If the user already has a
finished index/review and only wants the interactive resolution or the plan,
**skip to phase 4 or 5** and delegate directly — do not redo phases 1–3.
<!-- </when_to_apply> -->

<!-- <scope_calibration> -->
## Phase 1 — Scope calibration (owned)

Before investigating, size the effort with the user. The same five phases apply
at any scale; only their depth changes. This phase produces the inputs the later
delegations consume: **mode**, **lens**, **target surface**, and **maintenance
profile**.

- **Concrete-problem mode**: one symptom or module. Phase 2 is a focused
  root-cause investigation; the index may hold a handful of findings; phase 4 may
  be a single decision batch. Do not inflate a one-bug investigation into a full
  report.
- **Systemic-audit mode**: whole project or a broad concern (e.g. multi-platform
  compatibility + UX before a release). Phase 2 is a directed sweep across the
  relevant surface; the index is a full report with many findings across areas.

Also determine the **maintenance profile** (correctivo / perfectivo / preventivo
/ adaptativo, or none) per the canonical table in
[investigate](../investigate/SKILL.md) `<maintenance_profiles>` — do not restate
it here. The profile is threaded into phases 2, 4 and 5 to modulate exploration
focus, decision weighting, and plan risk posture.

If the intended scope, target surface, the audit lens (what class of problems to
look for), or the profile is unclear, ask **in Spanish** before starting. Never
invent scope.
<!-- </scope_calibration> -->

<!-- <operation> -->
## How to operate this workflow

**Harness tooling (reflective, not mechanical)**: this skill targets Claude Code
first but runs in any agentic harness. Map each capability to its local
equivalent: the delegated investigation drives read-only exploration through
`investigate` (Claude Code: `Grep`, `Glob`, `Read`, and `Agent` with
`subagent_type: "Explore"` for parallel fan-out); structured user questions for
decisions (via `resolve-open-decisions` → `AskUserQuestion`); a read-only
planning/approval mode for the plan (via `create-plan` →
`EnterPlanMode`/`ExitPlanMode`); and task-list tracking
(`TaskCreate`/`TaskUpdate`) to trace findings and phase progress. Where a
capability is absent, achieve its intent by other means rather than skipping it.

This workflow is **interactive by design**: stopping to confirm scope (phase 1),
to resolve decisions (phase 4), and to approve the plan (phase 5) is success, not
failure. Do not audit-resolve-plan in one silent pass.

**Do not mutate code in this workflow.** Phases 1–3 are calibration, delegated
read-only investigation, and documentation; phase 5 produces a *plan*, not the
fix. Execution of the plan is a separate flow the user starts after approval.

**Composition.** Phases 2, 4 and 5 sub-invoke sibling skills following Pattern A
(invocation with result consumption) of the `<sub_invocation_protocol>` in
[artifact-structuring](../artifact-structuring/SKILL.md): pass explicit input,
let the sub-skill deliver its canonical output as a hand-off, and surface its
approval gates to the user through this outer flow. The **maintenance profile**
determined in phase 1 is the thread that runs
calibration → `investigate` → `resolve-open-decisions` → `create-plan`: pass it
to each delegation so exploration focus, decision weighting, and plan risk
posture stay aligned.
<!-- </operation> -->

<!-- <phase_2_investigate> -->
## Phase 2 — Investigation (delegated)

Delegate the read-only investigation to [investigate](../investigate/SKILL.md).
Do **not** reimplement its discovery, evidence discipline, or reporting here —
follow that skill (no duplication).

Sub-invocation input this skill provides (Pattern A):

- The **lens** (what class of problems to look for) and the **target surface**
  from phase 1, expressed as concrete sources (entry points, platform-specific
  branches, build/CI config, dependency manifests, docs — whatever the lens
  demands).
- The active **maintenance profile**, so `investigate` modulates each task's
  focus, required evidence, and depth per its `<maintenance_profiles>` table.

Consume as the hand-off the **proven findings** `investigate` reports (facts vs.
interpretations, each with its source), which become the raw material phase 3
classifies.

**Evidence rigor (gate on the consumed findings).** Every finding must cite a
concrete `file:line` (or config/doc locator); no evidence-free findings, no
unverified points passed off as fact, no false positives. Cross-platform or
runtime claims must be proven by reading the code and confirmed in CI — an
untested hypothesis is reported as such, never promoted to a finding.

**Coverage / stop criterion.** Stop the investigation when the target surface
under the lens has been swept and further reading yields no new distinct
findings — not before (gaps) and not by unbounded expansion (scope creep). If
the surface reveals a materially different scope than phase 1 assumed
(**re-scoping**), return to phase 1, recalibrate mode/lens/surface/profile with
the user, and re-enter phase 2.
<!-- </phase_2_investigate> -->

<!-- <phase_3_document> -->
## Phase 3 — Classify, prioritize & index (owned)

Assemble the findings from phase 2 into the **index report** — the hinge
artifact. Use the template in `<review_template>`.

**Classify** each finding into exactly one of three groups and derive its **ID**
from the group plus a number:

| Group | Meaning | ID form |
|-------|---------|---------|
| **CRITICAL** | Breaks correctness, blocks a platform, or ships a defect | `CRITICAL-01`, `CRITICAL-02`, … |
| **WARNING** | Degrades UX, reliability, or maintainability without breaking | `WARNING-01`, … |
| **SUGGESTION** | Improvement or hardening with no active harm | `SUGGESTION-01`, … |

**Prioritize** by **severity + dependency + effort/impact**: a CRITICAL finding
that gates others ranks first; among peers, prefer low-effort/high-impact fixes.
Group the recommended fix order into phases so phase 5 can map them to ordered
tasks.

**Persist the report to disk.** Default path: `docs/PROJECT-REVIEW.md` (or a
scope-specific name). Confirm the path with the user if ambiguous. This file is
what makes the workflow resumable across sessions and is the direct input to
phase 4.

**Resuming.** If a persisted index already exists for this scope, read it and
continue from where it left off (unresolved decisions → phase 4; resolved but
unplanned → phase 5) instead of re-running phase 2.

After writing it, present a short Spanish summary (counts per group, the
recommended-order phases) and confirm with the user before entering resolution.
<!-- </phase_3_document> -->

<!-- <phase_4_resolve> -->
## Phase 4 — Resolve decisions 1×1 (human in the loop)

Delegate to [resolve-open-decisions](../resolve-open-decisions/SKILL.md). Do
**not** restate its form rules, batching, or gate here — follow that skill.

**Skip branch.** If no finding in the index requires an owner decision (every fix
is self-evident), **omit phase 4 and proceed to phase 5** — record in the index
that resolution was not needed and carry the direct fixes as plan requirements.

Sub-invocation input this skill provides:

- The list of findings that carry a **Decisión requerida** flag (and any whose
  chosen approach is not self-evident), each with its candidate corrections from
  the index as the option set.
- The active review name and the **maintenance profile** from phase 1, which
  weights the option ordering per that skill's `<gate>` (profile definitions:
  [investigate](../investigate/SKILL.md) `<maintenance_profiles>`).

Contract:

- **One question per finding**, options ordered most-to-least recommended with
  explicit trade-offs, batched ≤4 per call (see that skill's `<batching>`).
- **Emergent escalations (key insight):** when a human answer reveals a deeper
  design problem than the finding captured, **pause and open new decisions**
  before continuing — do not silently absorb it. Reflect the escalation back into
  the index (add/adjust findings) so the report stays the source of truth. This
  really happens (a "how does X relate to Y?" answer can trigger a redesign).
- The gate belongs to the user: resume only after every batch is answered.

Record each resolved approach against its finding ID in a **single location — the
index** (a decisions section within it), so phase 5 consumes concrete, closed
choices from one source of truth.
<!-- </phase_4_resolve> -->

<!-- <phase_5_plan> -->
## Phase 5 — Define the correction plan (delegated)

Delegate to [create-plan](../create-plan/SKILL.md) in sub-invoked mode. Do not
restate its template or rules here.

Sub-invocation input this skill provides:

- The resolved approach for every finding (from phase 4, or the direct fixes when
  phase 4 was skipped) as the requirements.
- The index report as context and the source-of-truth for evidence and ordering.
- The **maintenance profile** from phase 1, to inform the plan's risk posture and
  reversal routes.

Mapping guidance for the plan:

- Each finding maps to one execution task, or several cohesive findings that
  touch the same surface collapse into one task.
- **Traceability**: every plan task cites the finding IDs it resolves (e.g.
  "resuelve `CRITICAL-01`, `WARNING-03`"), so the plan is auditable back to the
  index.
- The recommended-order phases from the index inform the task numbering and the
  dependency graph create-plan builds.

The plan-approval gate (`ExitPlanMode` or its equivalent) is surfaced to the
user by create-plan. This skill delivers the audit-to-plan pipeline **up to an
approved plan**; executing the plan is a separate flow.
<!-- </phase_5_plan> -->

<!-- <review_template> -->
## Index report template (phase 3 deliverable)

Spanish prose; keep `file:line` and identifiers verbatim. Findings are grouped
into `CRITICAL` / `WARNING` / `SUGGESTION`, IDs derived from the group.

```markdown
# Revisión: {{título del alcance auditado}}

## Resumen ejecutivo

{{Una o dos frases: qué se auditó, bajo qué lente y perfil, y el veredicto
global. Conteo por grupo: N críticos, M advertencias, K sugerencias.}}

| ID | Título | Grupo | Área/plataforma | Decisión requerida |
|----|--------|-------|-----------------|--------------------|
| {{CRITICAL-01}} | {{...}} | {{Crítico}} | {{...}} | {{Sí/No}} |

## Hallazgos por grupo

### Críticos

#### {{CRITICAL-01}} — {{título}}
- **Área/plataforma**: {{...}}
- **Evidencia**: `{{archivo:línea}}`
- **Causa**: {{...}}
- **Impacto**: {{...}}
- **Corrección(es) propuesta(s)**: {{una o más; marcar cuál se recomienda}}
- **Decisión requerida**: {{Sí — describir la elección | No}}

### Advertencias

{{...hallazgos WARNING-01, WARNING-02, ...}}

### Sugerencias

{{...hallazgos SUGGESTION-01, SUGGESTION-02, ...}}

## Orden de corrección recomendado

{{Fases ordenadas (Fase 1, Fase 2, ...) que agrupan los IDs por prioridad,
dependencia y esfuerzo/impacto; alimentan la numeración de tareas del plan.}}

## Decisiones del propietario

{{Registro único de las decisiones: cada ID con «Decisión requerida: Sí», la
elección concreta y, una vez resuelta en la fase 4, el enfoque elegido. Si ningún
hallazgo requirió decisión, dejar constancia de que la fase 4 se omitió.}}

## Confirmación en CI

{{Hallazgos ya probados por lectura de código cuya evidencia multiplataforma o de
runtime se confirmará al correr CI, con dónde confirmarla. No es una lista de
hipótesis sin comprobar: es la traza de verificación en ejecución de evidencia ya
establecida.}}
```
<!-- </review_template> -->

<!-- <constraints> -->
## Constraints

- **Read-only until the plan**: never edit source code in this workflow. Phases
  1–3 calibrate, investigate (delegated), and document; phase 5 outputs a plan,
  not a fix.
- **Do not duplicate sibling skills**: phases 2, 4 and 5 follow `investigate`,
  `resolve-open-decisions` and `create-plan` respectively; provide input and
  consume output, never restate their rules.
- **Evidence rigor**: every finding cites a concrete `file:line` or locator; no
  evidence-free findings, no unverified points, no false positives. Cross-platform
  claims are proven by code and confirmed in CI.
- **Persist the index** before phase 4 so the workflow is resumable.
- **Traceability**: every plan task cites the finding IDs it resolves.
- **Human owns the decisions and the plan approval**: never resolve a flagged
  decision unilaterally, never skip the plan-approval gate.
- All user-facing questions, summaries, and the index report are in **Spanish**;
  identifiers, paths, and API names stay in their original form.
<!-- </constraints> -->

<!-- <verification> -->
## Verification before delivery

1. Was the scope calibrated with the user in phase 1 (mode, lens, target surface,
   maintenance profile) before investigating?
2. Was the investigation delegated to `investigate` (Pattern A) with lens,
   surface and profile as input, and consumed as proven findings — not
   reimplemented here?
3. Does every finding carry a group-derived ID (`CRITICAL-`/`WARNING-`/
   `SUGGESTION-`), evidence (`file:line`), cause, impact, and at least one
   proposed correction, with no `CP-` prefix and no four-level severity ladder?
4. Was the index report persisted to disk and summarized to the user (counts per
   group) before entering resolution?
5. If any finding required a decision, were they resolved via
   `resolve-open-decisions` (one question each, trade-offs, ≤4 per batch) and
   emergent escalations surfaced rather than absorbed — or, if none required a
   decision, was phase 4 explicitly skipped?
6. Was the plan produced via `create-plan` from the resolved approaches, with each
   task citing the finding IDs it resolves, and the approval gate surfaced to the
   user?
7. Did the workflow stay read-only (no code mutations) through to plan approval?
8. Is all user-facing output in Spanish, with identifiers and paths verbatim, and
   no internal XML block names leaked?
<!-- </verification> -->

<!-- <example> -->
## Example

**Input:** «Audita la compatibilidad multiplataforma de tts-sidecar antes de los
builds de CI.»

**Flow:**
1. **Calibración (fase 1)**: modo auditoría sistémica, lente = compatibilidad
   Windows/Linux/macOS + UX, superficie = ramas por SO en `cli.py`, `audio.py`,
   `daemon/`, los scripts de build y `.circleci/config.yml`; perfil = preventivo.
2. **Investigación (fase 2, delegada)**: se sub-invoca `investigate` con esa
   lente, superficie y perfil; devuelve hallazgos probados con evidencia
   `file:line` (facts vs. interpretaciones), sin puntos sin comprobar.
3. **Índice (fase 3)**: se clasifican en `CRITICAL-01`…`CRITICAL-03`,
   `WARNING-01`…`WARNING-05`, `SUGGESTION-01`…; se prioriza por
   severidad+dependencia+esfuerzo/impacto y se persiste `docs/PROJECT-REVIEW.md`.
4. **Resolver (fase 4)**: `resolve-open-decisions` sobre los hallazgos con
   «Decisión requerida: Sí»; una respuesta a "¿cómo se relaciona `CRITICAL-03`
   con `WARNING-02`?" escala a un rediseño del modelo de voz, así que se abren
   nuevas decisiones y se reflejan en el índice antes de continuar.
5. **Plan (fase 5)**: `create-plan` convierte los enfoques resueltos en un plan
   canónico; cada tarea cita los IDs que resuelve (p. ej. «resuelve
   `CRITICAL-01`, `WARNING-03`»); el usuario lo aprueba.

**Output:** an approved correction plan; no code changed by this workflow.
<!-- </example> -->
