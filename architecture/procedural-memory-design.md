# Research: Procedural + Episodic Memory for llm_memory

**Date:** 2026-03-12  
**Author:** Codex  
**Purpose:** Evaluate how llm_memory should represent "what happened" and "how to do X" without over-designing v1.

---

## Executive Take

Auggie is right that the system lacks first-class procedural memory, but his recommended "ship now with imported docs" path is weaker than it sounds.

**Why his outcome is off:**
- `import-documents.md` does **not** give us reliable procedural recall by itself.
- Imported document text is saved to `tmp/{uuid}_content.txt`, while normal query paths search **entity name + summary**, not full document body.
- The repo itself documents document import as **experimental** with "advanced queries limited."

**Best near-term move:**
- Do **not** add a brand-new graph shape first.
- Reuse the existing `Entity.attributes` JSON field and add a first-class `Procedure` entity label/type.
- Store structured procedure payloads in `attributes`, then update retrieval/UI paths to surface them.

That gets us procedural memory with minimal schema churn and without pretending document import solves the retrieval problem.

---

## What The Codebase Actually Supports Today

### 1. Episodic memory exists, but mostly in SQL

Current split:
- **SQL** stores raw interactions and timestamps
- **Graph** stores extracted entities/facts

This matches the docs:
- `docs/STATUS.md`: Episodic nodes are **not implemented**
- `docs/database-schema.md`: episode/provenance lives in SQLite interactions and in relationship provenance fields

So today the system has:
- **good episodic storage**
- **good semantic graph retrieval**
- **weak procedural representation**

### 2. The graph already has a place for structured procedure metadata

The graph schema already includes:
- `Entity.labels`
- `Entity.summary`
- `Entity.attributes` as JSON

Relevant implementation reality:
- `tools/graph_db.py` already persists `attributes`
- `scripts/validate_extraction.py` does **not** reject extra entity fields
- but `scripts/store_extraction.py` currently creates entities with `attributes={}`, so extra structure is discarded

That means the missing piece is not a database capability problem first. It is a **pipeline and retrieval problem**.

### 2b. The existing provenance model must be preserved

This repo is not just trying to remember procedures. It is trying to preserve:
- attribution
- auditability
- cryptographic provenance
- the ability to later assign or clear responsibility

That means procedural memory cannot be allowed to bypass the existing graph proof model.

If an agent extracts a bad procedure, stores the wrong step order, or records a misleading execution result, the system should still allow later review to answer:
- who created it
- when
- from which source interactions or workflow invocation
- under which extraction/execution batch

### 3. Document import is not a procedural-memory solution

`import-documents.md` currently:
- imports documents as `Entity` nodes with labels like `ExternalSource` and `Document`
- saves extracted body text to `tmp/{uuid}_content.txt`
- optionally runs AI extraction later

But query behavior today is limited:
- `query_memory.py` search uses entity `name` and `summary`
- `GraphDatabase.search_entities()` searches `name` and `summary`, then aliases
- repo status says document import has **limited query support**

So "import sync.md and search it" is not a robust answer to:
- "How do I run sync?"
- "What procedure should I use when extraction fails?"
- "What steps apply to Codex vs Auggie?"

It only helps if extraction converts the document into structured entities/facts, and even then we still do not have a first-class procedure model.

---

## External Research

### 1. Procedural vs episodic is a real distinction, not taxonomy fluff

Classic cognitive architecture literature distinguishes:
- **episodic memory** as stored experience/events
- **procedural memory** as knowledge of what actions to take under conditions

That distinction maps cleanly to this repo:
- SQL interactions = episodes / provenance
- graph entities + facts = semantic memory
- missing = condition-to-action workflows

Source:
- arXiv review of cognitive architectures: procedural memory stores what actions should be taken under certain conditions; episodic stores the agent's experience.  
  https://arxiv.org/pdf/1610.08602

### 2. MIRIX is the clearest current reference point

MIRIX frames agent memory as six dedicated components:
- Core
- Episodic
- Semantic
- Procedural
- Resource
- Knowledge Vault

Two useful takeaways:
- procedural memory is separated because "how to act" behaves differently from facts/events
- retrieval is field-specific, not just generic blob search

Sources:
- MIRIX paper listing six memory types  
  https://arxiv.org/abs/2507.07957
- MIRIX docs showing procedural memory as a dedicated workflow memory and field-specific search support  
  https://docs.mirix.io/

### 3. Graphiti supports the direction, but not the exact answer

Graphiti is relevant because it explicitly models:
- temporal context
- episodes as provenance
- custom node/edge types

That supports the architectural direction of:
- keep episodic provenance distinct
- allow domain-specific entities like procedures

But Graphiti does **not** imply we should immediately build step nodes and branching workflow graphs.

Source:
- Graphiti repo docs: temporal context graph, episodes as provenance, developer-defined custom entity and edge types  
  https://github.com/getzep/graphiti

---

## Where Auggie Is Right

He is right about:
- the current system covering **semantic + episodic-ish provenance**
- the absence of first-class procedural memory
- MIRIX being a strong recent signal that procedural memory deserves a dedicated representation

He is also right that:
- step-level workflow graphs are heavier than we need for first ship

---

## Where Auggie Is Wrong

### 1. "Import docs now" is not the fastest path to useful procedural memory

It is the fastest path to **storing** workflows, not to **using** them.

Current limitations:
- no full-text retrieval across document body in normal memory query flow
- no trigger-based retrieval
- no pretty rendering of procedure steps
- no distinction between a procedure and a descriptive document

### 2. Adding `steps` as a new top-level entity field is not the cleanest MVP

Why not:
- schema docs currently define entities as `name/type/summary`
- the graph already has `attributes` for structured JSON
- adding top-level fields everywhere creates more spec and display churn than necessary

If we want low-risk MVP, use:
- `type: "Procedure"`
- `attributes.steps`
- `attributes.trigger_phrases`
- `attributes.prerequisites`

### 3. "Not queryable" is only true if we leave it opaque

If steps live in `attributes` and retrieval code learns to inspect/print them, they are queryable enough for v1.

We do **not** need explicit `Step` nodes to support:
- keyword retrieval
- exact procedure display
- trigger-based recall
- agent-specific filtering

---

## Recommended Design

## v1: Procedure-as-Entity with Structured Attributes

Add a first-class procedure convention:

```json
{
  "name": "Sync Workflow",
  "type": "Procedure",
  "summary": "Full workflow for storing and extracting conversation memory.",
  "attributes": {
    "goal": "Save a conversation and extract knowledge into memory",
    "trigger_phrases": [
      "follow sync.md",
      "save this conversation to memory",
      "run memory sync"
    ],
    "applies_to_agent": ["codex", "auggie"],
    "prerequisites": [
      "Read COMMANDS.md first",
      "Ensure tmp/ exists",
      "Read mem.config.json for python_path and project_name"
    ],
    "steps": [
      {"order": 1, "action": "Read sync.md and mem.config.json"},
      {"order": 2, "action": "Prepare conversation or extraction inputs"},
      {"order": 3, "action": "Run the sync pipeline with the configured python path"},
      {"order": 4, "action": "Verify completion and report results"}
    ],
    "source_kind": "workflow_file",
    "source_ref": "sync.md"
  }
}
```

### Why this is the right MVP

- uses existing graph schema
- keeps provenance model intact
- keeps extraction JSON simple
- avoids exploding node count
- supports procedural recall now

### Required code changes

1. **Preserve entity attributes during storage**
- `scripts/store_extraction.py` currently drops them

2. **Document optional `attributes` on entities**
- `docs/EXTRACTION-FORMAT-SPEC.md` should explicitly allow structured entity metadata

3. **Retrieval must search/display procedures**
- search `attributes.goal`, `attributes.trigger_phrases`, and maybe serialized `steps`
- pretty-print procedure steps in `query_memory.py` / `remember.md` flow

4. **Extraction prompts should identify procedures**
- when source text is a workflow, create `Procedure` entities instead of only generic `File` or `Concept` entities

5. **Procedural memory must preserve auditability**
- `Procedure` and `ProcedureStep` must carry the same provenance/proof fields as other extracted entities
- procedural relationships must carry the same derivation/proof fields as other extracted facts
- no procedural feature should bypass attribution or verification

---

## v1 Retrieval Requirement: Reverse Lookup by Step Content

The base `Procedure`-in-`attributes` design is not enough by itself.

If procedure data only lives in:
- `attributes.steps`
- `attributes.prerequisites`
- `attributes.trigger_phrases`

then v1 retrieval will still be weak for questions like:
- "Which procedure calls `store_extraction.py`?"
- "What workflow mentions quality review?"
- "I remember one step about `validate_extraction.py`"

### Why this matters

Current retrieval paths search:
- entity name
- entity summary
- aliases

They do **not** currently support robust reverse lookup into arbitrary JSON procedure payloads.

So a procedure can exist in memory and still be hard to find from:
- one remembered script name
- one remembered phrase
- one prerequisite or exception

### Recommended fix

Add a **denormalized retrieval index** at both the procedure and step levels.

Keep the full structure:

```json
"steps": [
  {"order": 1, "action": "Run import_conversation.py"},
  {"order": 2, "action": "Run store_extraction.py with quality review"}
]
```

But also store flattened retrieval helpers:

```json
"step_keywords": [
  "import_conversation.py",
  "store_extraction.py",
  "quality review",
  "validate_extraction.py"
],
"search_text": "import_conversation.py store_extraction.py quality review validate_extraction.py"
```

At the **procedure** level, `search_text` should aggregate:
- goal text
- trigger phrases
- prerequisite text
- step keywords
- important script/tool/file references

At the **step** level, `search_text` should capture:
- action text
- script/tool/file references
- condition text
- exception text
- memorable phrases a user is likely to recall

### Why this is the right initial compromise

- low complexity
- no graph explosion
- supports reverse lookup by script/phrase
- supports partial recall from one remembered step
- preserves the richer structured steps for display

### What v1 should support

With this addition, v1 should be able to answer:

- "How do I sync?"  
  by matching procedure name or trigger phrase

- "Which procedure uses `store_extraction.py`?"  
  by matching `step_keywords` or `search_text`

- "I remember something about quality review"  
  by matching a phrase from a step or prerequisite

### What still belongs in later phases

If later we need:
- shared reusable sub-steps
- richer branching conditions
- advanced execution analytics across many runs
- adaptive optimization from procedure history

then the model can expand further.

But reverse lookup by step content and script reference should be considered part of the initial useful design, not deferred.

---

## Capture Strategy: Preserve Recent Procedural Turns

The storage model alone is not enough. We also need a better **capture-to-extraction path**.

### Problem

Anthropic-style agents often still have the last **3-5 full turns** available even when older context has been compressed or paraphrased.

Today, the repo already supports conversation fidelity levels:
- `full`
- `paraphrased`
- `reconstructed`
- `summary`

That is useful, but current workflow guidance does not explicitly tell the dumping agent to preserve recent procedures with higher fidelity than the rest of the conversation.

### Recommendation

When running `dump.md` or `sync.md`, the agent should be instructed to:

- preserve the last **3-5 exchanges verbatim** whenever possible
- preserve **any recent exchange that defines, corrects, or refines a workflow** verbatim, even if other nearby context is compressed
- if exact text is unavailable, create a **procedure-focused paraphrase** instead of a generic summary
- mark that reconstruction honestly with `fidelity` and `source_note`

This is the right place to exploit the "recent turns still available" capability instead of letting it disappear into broad summarization.

### Why this matters

Procedures degrade badly under generic paraphrase.

What gets lost first:
- exact step order
- prerequisites
- trigger conditions
- exceptions
- agent/tool-specific differences

If the dump stage preserves those turns at high fidelity, the extraction stage has a much better chance of producing a real structured procedure instead of a vague concept summary.

### Minimal workflow guidance to add

The dump/sync instructions should effectively say:

- If a recent exchange contains step-by-step instructions, decision rules, prerequisites, or "when to use X", preserve it as `fidelity: "full"` whenever possible.
- If only the gist is available, reconstruct it as a procedure-focused exchange and mark it `paraphrased` or `reconstructed`.
- Do not collapse a recent workflow discussion into a one-line summary if the step sequence is still recoverable.

### Resulting pipeline

That gives us a clearer end-to-end path:

1. **Capture**
   - keep recent procedural turns at highest available fidelity

2. **Extraction**
   - detect workflows from those turns
   - emit `Procedure` entities with structured fields

3. **Storage**
   - keep procedure structure in `Entity.attributes`

4. **Retrieval**
   - search by trigger/goal and render ordered steps back to the agent

This is the missing link between "models remember recent turns" and "the memory system stores usable procedures."

---

## Durable Schema Recommendation

If the goal is to avoid later redesign and reduce migration risk, the system should **not** stop at `Procedure` plus JSON steps.

The more durable first model is:

- `Procedure`
- `ProcedureStep`
- `ProcedureRun`
- `StepRun`

This separates:
- what the workflow **is**
- what its ordered steps **are**
- what happened when an agent **ran** it

### Why this is safer

If execution history is deferred too hard, later support for:
- "which procedures fail most often?"
- "what step broke last time?"
- "which workflow actually succeeded for Codex?"

will push the system toward schema additions anyway.

That is manageable if the design already anticipates those concepts.
It is riskier if the system starts from an opaque procedure blob and only later discovers it needs execution objects.

### Recommended first-class concepts

**Procedure**
- workflow identity
- goal
- trigger phrases
- agent applicability
- lifecycle status
- recommendation/ranking signals
- high-level search text

**ProcedureStep**
- ordered action
- script/tool/file references
- conditions
- exceptions
- step-level search text

**ProcedureRun**
- one execution instance of a procedure
- who ran it
- when it started/finished
- overall outcome

**StepRun**
- one execution record for one step in one procedure run
- status
- timestamps
- optional error/result note

### Deprecation vs Promotion

Procedural memory needs to distinguish between:

- **deprecation / invalidation**
  - the procedure definition is no longer correct, safe, or applicable
  - example: script changed, workflow is obsolete, step order is wrong

- **evaluation / promotion**
  - the procedure still exists, but execution history suggests it should rank higher or lower than alternatives
  - example: one workflow succeeds 20 times, another frequently fails at step 3

These must not be conflated.

The correct model is:
- **truth/lifecycle changes** -> supersede or deprecate the procedure definition
- **performance/reliability changes** -> adjust recommendation/ranking signals derived from `ProcedureRun` / `StepRun`

A procedure can therefore be:
- active but low-performing
- active and promoted
- deprecated but historically successful
- superseded because a newer definition replaced it

Frozen defaults:
- newly extracted procedures should default to `lifecycle_status = "active"`
- retrieval should treat missing lifecycle state as `active` for backward compatibility

### Graph shape

Recommended relationships:

- `Procedure -[:CONTAINS]-> ProcedureStep`
- `ProcedureStep -[:PRECEDES]-> ProcedureStep`
- `ProcedureRun -[:RUNS]-> Procedure`
- `StepRun -[:EXECUTES]-> ProcedureStep`
- `ProcedureRun -[:HAS_STEP_RUN]-> StepRun`

Optional relationships when identifiable:

- `ProcedureStep -[:USES]-> File`
- `ProcedureStep -[:USES]-> Technology`
- `ProcedureStep -[:REFERENCES]-> Document`

### Practical implication

Execution telemetry is part of the intended design from the start.

That does **not** mean every runtime automation feature must be implemented immediately.
It does mean the schema direction should reserve first-class concepts for:
- procedure executions
- step executions
- outcomes

### Auditability Requirement

The durable schema must preserve the same verification properties already expected elsewhere in the graph.

For extracted procedural entities such as `Procedure` and `ProcedureStep`, this means preserving:
- `source_interactions`
- `source_hashes`
- `source_chain`
- `extraction_proof`
- `timestamp_proof`
- `extraction_batch_uuid`

For procedural relationships such as `CONTAINS`, `PRECEDES`, and `EXTRACTED_FROM`, this means preserving:
- `episode_hashes`
- `derivation_proof`
- `timestamp_proof`
- `extraction_batch_uuid`

For execution records such as `ProcedureRun` and `StepRun`, this means they must be:
- attributable to agent/model
- timestamped
- reviewable in a way that supports later blame assignment or exoneration

The exact proof mechanism for execution records can be implementation-defined, but execution telemetry must not become an unaudited side channel.

### Retrieval Safety Requirement

Broken procedures must not remain on hot retrieval paths just because they still exist historically.

Default retrieval should:
- prefer active, non-deprecated procedures
- demote procedures with poor run outcomes when enough evidence exists
- avoid recommending clearly deprecated/invalid workflows unless the user is explicitly asking for history or audit

Phase 1 behavior:
- filter by lifecycle first
- treat `deprecated`, `superseded`, and `invalid` as excluded from default recall
- defer outcome-based promotion/demotion until `ProcedureRun` / `StepRun` exist

Source of truth for evaluation:
- execution-derived signals such as success count, failure count, last success, last failure, and common failure step should come from `ProcedureRun` / `StepRun`
- cached ranking fields on the `Procedure` entity are optional later optimizations, not the initial source of truth

Historical retrieval should still allow:
- querying deprecated procedures
- reviewing why they were superseded
- inspecting who created or ran them

### Recommended phasing

To make the phasing explicit:

**Phase 1: Foundational procedural memory**
- `Procedure`
- `ProcedureStep`
- `CONTAINS` / `PRECEDES`
- denormalized retrieval fields:
  - procedure-level `search_text`
  - step-level `search_text`
  - step keywords / script references

**Phase 2: Execution records**
- `ProcedureRun`
- `StepRun`
- manual or semi-manual capture of procedure execution outcomes
- enough tracking to answer:
  - what ran
  - who ran it
  - whether it succeeded
  - where it failed

**Phase 3: Rich telemetry and automation**
- automatic run capture
- richer outcome payloads
- branching/sub-procedure support
- analytics across many runs

This means:
- telemetry is **not optional in the architecture**
- but automated telemetry is **not required in the first implementation slice**

---

## Agent-Specific or Shared?

**Default:** shared procedures  
**Override:** agent-specific applicability in attributes

Reason:
- most workflows in this repo are shared operational knowledge
- some procedures differ by agent/tooling wrapper
- shared-by-default avoids duplication

Recommended field:

```json
"applies_to_agent": ["codex", "auggie"]
```

If omitted:
- procedure is assumed generic/shared

---

## Procedural vs Episodic in This Repo

The clean model for llm_memory is:

- **Episodic memory**
  - raw interactions in SQL
  - timestamps, provenance, chain integrity
  - "what happened"

- **Semantic memory**
  - graph entities and facts
  - "what is true / what exists"

- **Procedural memory**
  - structured `Procedure` entities
  - triggers, prerequisites, steps, agent applicability
  - "how to do X"

This is a better fit than trying to force all three into one entity shape with no retrieval specialization.

---

## Concrete Recommendation

### Immediate

Do **not** treat imported workflow docs as the answer.

First implementation slice:
- add `Procedure` and `ProcedureStep`
- preserve `entity.attributes`
- add procedure-level and step-level retrieval text
- teach retrieval to surface procedures cleanly

### Next

Import workflow docs like `sync.md`, `recall.md`, and `import-documents.md` as **sources** for procedural extraction, not as the final procedural memory itself.

### Later

Expand execution analytics and automation:
- automatic run capture
- richer step outcomes
- reusable sub-procedures
- branching execution logic
- success/failure pattern analysis

---

## Answers to Auggie's Questions

### 1. Does MIRIX's 6-type model map well to our architecture?

Yes, mostly.

Clean mapping:
- Core: not really implemented
- Episodic: SQL interactions
- Semantic: graph entities/facts
- Procedural: missing
- Resource: external documents
- Knowledge Vault: not implemented

So MIRIX maps well as a **directional model**, not as a literal schema to copy.

### 2. Is Procedure Entity enough or do we need step-level granularity?

No. For a durable design, step-level granularity should be included from the start.

The useful baseline is:
- `Procedure` for workflow identity
- `ProcedureStep` for ordered executable content

That supports:
- reverse lookup by script or remembered step fragment
- cleaner execution workflows
- future telemetry without forcing a conceptual rewrite

### 3. Should procedures be agent-specific or shared?

Shared by default, agent-scoped when needed.

That matches this repo's operational docs better than fully per-agent procedure silos.

---

## Bottom Line

The strongest path is:

1. Keep episodic memory where it already works: SQL + provenance
2. Add first-class procedural structures: `Procedure` and `ProcedureStep`
3. Treat execution telemetry as part of the design via `ProcedureRun` and `StepRun`
4. Upgrade retrieval so procedures are actually usable from step fragments, script names, and trigger phrases
5. Distinguish deprecated/superseded procedures from promoted/recommended ones
6. Preserve the same audit/provenance guarantees for procedural memory that already exist for the rest of the graph
7. Use imported docs as **sources for extraction**, not as the procedural memory product

That is a more durable path that reduces the chance of a later procedural-memory redesign.

---

## Sources

- Cognitive architecture review on semantic/procedural/episodic memory distinctions: https://arxiv.org/pdf/1610.08602
- MIRIX paper: https://arxiv.org/abs/2507.07957
- MIRIX docs: https://docs.mirix.io/
- Graphiti repo/docs: https://github.com/getzep/graphiti
