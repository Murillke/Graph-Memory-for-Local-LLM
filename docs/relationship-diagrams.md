# GML Memory System - Relationship Diagrams

This document visualizes the relationship-first design of the memory system.
The **relationships contain the real knowledge**, not the nodes!

## Scenario 1: The Path Correction Story 

```mermaid
graph LR
    C1[" Claim<br/>auth repo<br/>LOCATED_AT<br/>../auth-service<br/><br/>status: fact<br/>confidence: 1.0<br/>told at: interaction 42"]
    
    C2[" Claim<br/>auth repo<br/>LOCATED_AT<br/>./services/auth<br/><br/>status: refuted<br/>confidence: 0.3<br/>hallucinated at: interaction 847"]
    
    C1 -->|"[WARNING] CORRECTS<br/><br/>corrected_at: interaction 847<br/>my_wrong_guess: './services/auth'<br/>your_frustration: 'high'<br/>pattern_of_error: 'hallucinated path'<br/>why_wrong: 'made up ./services/ pattern'<br/>times_made_mistake: 3<br/>related_mistakes: ['./lib/', './components/']<br/>confidence_before: 0.6<br/>confidence_after: 1.0<br/>time_since_told: 805 interactions<br/>should_have_remembered: true"| C2
    
    style C1 fill:#90EE90,stroke:#2E8B57,stroke-width:3px
    style C2 fill:#FFB6C6,stroke:#DC143C,stroke-width:3px
```

**Key Insight**: The `CORRECTS` relationship captures:
- What I got wrong
- Why I was wrong (hallucinated pattern)
- How many times I've made this mistake (3!)
- Your frustration level
- How long it's been since you told me (805 interactions!)

## Scenario 2: Solution Pattern Evolution [TOOL]

```mermaid
graph TB
    Problem["[BUG] Claim<br/>Problem<br/>AttributeError: NoneType<br/>has no attribute 'amount'<br/><br/>status: resolved<br/>first_seen: interaction 450"]
    
    Solution["[OK] Claim<br/>Solution<br/>use dataclass with<br/>type hints<br/><br/>status: fact<br/>confidence: 0.95"]
    
    Alt1["[ERROR] Alternative<br/>use Any type<br/><br/>status: rejected"]
    
    Alt2["[ERROR] Alternative<br/>add manual checks<br/><br/>status: rejected"]
    
    App1["[PACKAGE] Application<br/>fixed order processor<br/><br/>interaction: 892<br/>outcome: success"]
    
    App2["[PACKAGE] Application<br/>fixed invoice handler<br/><br/>interaction: 1034<br/>outcome: success"]
    
    Solution -->|"[TARGET] SOLVED<br/><br/>problem_sig: 'type error payment'<br/>root_cause: 'missing null checks'<br/>why_worked: 'forces explicit Optional[T]'<br/>side_benefits: ['caught 3 bugs', 'better IDE']<br/>time_to_implement: 45min<br/>bugs_fixed: 4<br/>bugs_introduced: 0<br/>tests_before: 23<br/>tests_after: 27<br/>applicable_to: 'any Optional fields'<br/>pattern_name: 'dataclass-optional'<br/>would_use_again: true"| Problem
    
    Solution -.->|" REJECTED<br/><br/>why: 'loses type safety'<br/>considered_at: interaction 455<br/>confidence_if_chosen: 0.3"| Alt1
    
    Solution -.->|" REJECTED<br/><br/>why: 'too verbose, error-prone'<br/>considered_at: interaction 458<br/>confidence_if_chosen: 0.5"| Alt2
    
    Solution -->|" APPLIED_IN<br/><br/>task: 'fix order processor'<br/>adapted: 'used Decimal for money'<br/>outcome: success<br/>effectiveness: 0.9<br/>time_to_apply: 20min<br/>bugs_fixed: 1<br/>notes: 'works great for financial data'<br/>pattern_confidence_boost: +0.05"| App1
    
    Solution -->|" APPLIED_IN<br/><br/>task: 'fix invoice handler'<br/>adapted: 'added validation logic'<br/>outcome: success<br/>effectiveness: 0.85<br/>time_to_apply: 15min<br/>bugs_fixed: 2<br/>reuse_count: 2"| App2
    
    style Problem fill:#FFE4B5,stroke:#FF8C00,stroke-width:3px
    style Solution fill:#90EE90,stroke:#2E8B57,stroke-width:3px
    style Alt1 fill:#FFB6C6,stroke:#DC143C,stroke-width:2px,stroke-dasharray: 5 5
    style Alt2 fill:#FFB6C6,stroke:#DC143C,stroke-width:2px,stroke-dasharray: 5 5
    style App1 fill:#ADD8E6,stroke:#4169E1,stroke-width:2px
    style App2 fill:#ADD8E6,stroke:#4169E1,stroke-width:2px
```

**Key Insight**: The `SOLVED` relationship captures:
- WHY the solution worked (root cause analysis)
- What alternatives we rejected and WHY
- Side benefits we discovered
- Metrics (bugs fixed, tests passing)

The `APPLIED_IN` relationships track pattern reuse and effectiveness!

## Scenario 3: Evolving Understanding 

```mermaid
graph LR
    Old[" Claim<br/>test files<br/>LOCATED_AT<br/>src/__tests__/<br/><br/>status: superseded<br/>confidence: 0.6<br/>held_for: 2 days"]

    New[" Claim<br/>test files<br/>LOCATED_AT<br/>__tests__/ at root<br/><br/>status: fact<br/>confidence: 0.95"]

    Obs1[" Observation<br/>saw test in src/__tests__/<br/><br/>interaction: 234"]

    Obs2[" Observation<br/>you showed me 5 tests<br/>all at root __tests__/<br/><br/>interaction: 456"]

    New -->|"[SYNC] SUPERSEDES<br/><br/>what_changed: 'tests at root not src'<br/>trigger: 'you showed actual structure'<br/>old_confidence: 0.6<br/>new_confidence: 0.95<br/>evidence_type: 'direct observation'<br/>affects: ['where to create tests']<br/>invalidates: ['created test in src/__tests__/']<br/>why_wrong_before: 'inferred from 1 example'<br/>lesson: 'verify patterns across multiple examples'<br/>cognitive_error: 'hasty generalization'<br/>times_used_wrong: 3"| Old

    Old -.->|"[DATA] BASED_ON<br/><br/>sample_size: 1<br/>confidence: 0.6<br/>inference: 'hasty'"| Obs1

    New -->|"[DATA] BASED_ON<br/><br/>sample_size: 5<br/>confidence: 0.95<br/>evidence_strength: 0.9"| Obs2

    style Old fill:#FFE4B5,stroke:#FF8C00,stroke-width:3px,stroke-dasharray: 5 5
    style New fill:#90EE90,stroke:#2E8B57,stroke-width:3px
    style Obs1 fill:#E6E6FA,stroke:#9370DB,stroke-width:2px
    style Obs2 fill:#E6E6FA,stroke:#9370DB,stroke-width:2px
```

**Key Insight**: The `SUPERSEDES` relationship captures:
- How my understanding evolved
- What triggered the change
- The lesson learned ("verify patterns across multiple examples")
- The cognitive error I made ("hasty generalization")
- How many times I used the wrong belief (3 times!)

## Scenario 4: Inference Chain [LINK]

```mermaid
graph TB
    P1[" Premise 1<br/>auth repo<br/>LOCATED_AT<br/>../auth-service<br/><br/>status: fact<br/>confidence: 1.0<br/>source: user_told_me"]

    P2["[LIST] Premise 2<br/>test files<br/>LOCATED_AT<br/>__tests__/ at root<br/><br/>status: fact<br/>confidence: 0.95<br/>source: validated"]

    Inf[" Inference<br/>auth tests<br/>LOCATED_AT<br/>../auth-service/__tests__/<br/><br/>status: proposition<br/>confidence: 0.9<br/>needs_verification: true"]

    Val[" Validation<br/>directory exists<br/>at ../auth-service/__tests__/<br/><br/>verified: true<br/>method: file_system_check"]

    P1 -->|" DERIVES<br/><br/>inference_type: deductive<br/>reasoning: 'IF auth at X AND tests at Y<br/>THEN auth tests at X/Y'<br/>premise_confidence: 1.0<br/>conclusion_confidence: 0.9<br/>needs_verification: true<br/>depends_on: ['claim_auth_loc', 'claim_test_pattern']<br/>invalidated_if_premises_change: true"| Inf

    P2 -->|" DERIVES<br/><br/>premise_confidence: 0.95<br/>propagates_to_conclusion: true"| Inf

    Val -->|"[OK] VALIDATES<br/><br/>validation_type: empirical<br/>method: file_system_check<br/>validation_strength: 1.0<br/>confidence_boost: +0.05<br/>validates_aspect: 'path_exists'<br/>promotes_to_fact: true<br/>timestamp: now<br/>reproducible: true"| Inf

    style P1 fill:#90EE90,stroke:#2E8B57,stroke-width:3px
    style P2 fill:#90EE90,stroke:#2E8B57,stroke-width:3px
    style Inf fill:#FFFACD,stroke:#FFD700,stroke-width:3px
    style Val fill:#98FB98,stroke:#32CD32,stroke-width:2px
```

**Key Insight**: The `DERIVES` relationship captures:
- The reasoning chain (IF-THEN logic)
- Confidence propagation from premises to conclusion
- Dependencies (what claims this inference depends on)
- Validation needs

The `VALIDATES` relationship captures empirical verification!

## Scenario 5: Conflict Resolution 

```mermaid
graph TB
    OptA[" Option A<br/>use async/await<br/>for DB calls<br/><br/>status: proposition<br/>confidence: 0.7"]

    OptB["[SYNC] Option B<br/>use sync<br/>DB calls<br/><br/>status: proposition<br/>confidence: 0.6"]

    EvidA1["[DATA] Evidence<br/>performance benchmark<br/>async 3x faster<br/><br/>strength: 0.8"]

    EvidA2["[DATA] Evidence<br/>handles 1000 concurrent<br/>requests<br/><br/>strength: 0.9"]

    EvidB1["[DATA] Evidence<br/>easier to debug<br/>stack traces clearer<br/><br/>strength: 0.7"]

    EvidB2["[DATA] Evidence<br/>existing codebase<br/>is all sync<br/><br/>strength: 0.6"]

    Decision["[OK] Decision<br/>chose async/await<br/><br/>status: fact<br/>confidence: 0.85<br/>interaction: 923"]

    OptA <-->|" CONFLICTS_WITH<br/><br/>conflict_type: mutually_exclusive<br/>dimension: implementation_approach<br/>context: 'payment processing service'<br/>stakes: high (performance critical)<br/>resolution_needed: true<br/>resolution_criteria: ['performance', 'team skill', 'migration cost']<br/>why_conflict: 'trade-off perf vs simplicity'<br/>similar_conflicts: ['ORM vs raw SQL']"| OptB

    EvidA1 -.->|"supports"| OptA
    EvidA2 -.->|"supports"| OptA
    EvidB1 -.->|"supports"| OptB
    EvidB2 -.->|"supports"| OptB

    Decision -->|" RESOLVES<br/><br/>winner: Option A<br/>rationale: 'performance critical for payments'<br/>trade_offs_accepted: 'migration cost, learning curve'<br/>confidence_in_decision: 0.85<br/>will_revisit_if: 'team struggles with async'<br/>success_criteria: ['response time <100ms', 'no deadlocks']"| OptA

    Decision -->|"[ERROR] REJECTS<br/><br/>why_rejected: 'too slow for requirements'<br/>close_call: true<br/>margin: 0.1"| OptB

    style OptA fill:#ADD8E6,stroke:#4169E1,stroke-width:3px
    style OptB fill:#FFE4B5,stroke:#FF8C00,stroke-width:3px
    style EvidA1 fill:#E6E6FA,stroke:#9370DB,stroke-width:2px
    style EvidA2 fill:#E6E6FA,stroke:#9370DB,stroke-width:2px
    style EvidB1 fill:#E6E6FA,stroke:#9370DB,stroke-width:2px
    style EvidB2 fill:#E6E6FA,stroke:#9370DB,stroke-width:2px
    style Decision fill:#90EE90,stroke:#2E8B57,stroke-width:3px
```

**Key Insight**: The `CONFLICTS_WITH` relationship captures:
- The nature of the conflict (mutually exclusive)
- Evidence for BOTH sides
- Resolution criteria
- Trade-offs

The `RESOLVES` relationship captures the decision rationale and what trade-offs we accepted!

## Scenario 6: Pattern Similarity Network 

```mermaid
graph TB
    P1["[TARGET] Pattern<br/>dataclass-optional<br/>for null safety<br/><br/>success_rate: 0.95<br/>usage_count: 5"]

    P2["[TARGET] Pattern<br/>pydantic-model<br/>for validation<br/><br/>success_rate: 0.88<br/>usage_count: 3"]

    P3["[TARGET] Pattern<br/>attrs-frozen<br/>for immutability<br/><br/>success_rate: 0.92<br/>usage_count: 2"]

    P4["[TARGET] Pattern<br/>manual-null-checks<br/>if/else guards<br/><br/>success_rate: 0.65<br/>usage_count: 8"]

    P1 <-->|"[LINK] SIMILAR_TO<br/><br/>similarity: 0.8<br/>shared_context: ['type safety', 'Python']<br/>shared_problem: 'null handling'<br/>difference: 'pydantic adds runtime validation'<br/>when_to_use_p1: 'simple data classes'<br/>when_to_use_p2: 'API input validation'"| P2

    P1 <-->|"[LINK] SIMILAR_TO<br/><br/>similarity: 0.7<br/>shared_context: ['immutable data', 'Python']<br/>difference: 'attrs more features'<br/>when_to_use_p1: 'standard library preferred'<br/>when_to_use_p3: 'need advanced features'"| P3

    P1 -->|" BETTER_THAN<br/><br/>success_delta: +0.3<br/>why_better: 'less verbose, type-safe'<br/>contexts_where_better: ['new code', 'Python 3.7+']<br/>contexts_where_worse: ['Python 2', 'legacy code']<br/>migration_cost: 'medium'<br/>confidence: 0.9"| P4

    P2 -->|" BETTER_THAN<br/><br/>success_delta: +0.23<br/>why_better: 'runtime validation'<br/>contexts_where_better: ['API boundaries']"| P4

    style P1 fill:#90EE90,stroke:#2E8B57,stroke-width:3px
    style P2 fill:#90EE90,stroke:#2E8B57,stroke-width:3px
    style P3 fill:#90EE90,stroke:#2E8B57,stroke-width:3px
    style P4 fill:#FFE4B5,stroke:#FF8C00,stroke-width:2px
```

**Key Insight**: The `SIMILAR_TO` relationship captures:
- Similarity score
- Shared context and problems
- Key differences
- **When to use which pattern** (this is gold!)

The `BETTER_THAN` relationship captures comparative effectiveness!

## Scenario 7: My Recurring Mistakes [SYNC]

```mermaid
graph LR
    M1["[ERROR] Mistake<br/>hallucinated path<br/>./services/auth<br/><br/>interaction: 847"]

    M2["[ERROR] Mistake<br/>hallucinated path<br/>./lib/utils<br/><br/>interaction: 923"]

    M3["[ERROR] Mistake<br/>hallucinated path<br/>./components/Button<br/><br/>interaction: 1045"]

    Pattern["[RED] Error Pattern<br/>hallucinate ./folder/<br/>structure<br/><br/>occurrence_count: 3<br/>severity: high"]

    Root[" Root Cause<br/>assume standard<br/>project structure<br/>without verification<br/><br/>cognitive_error: assumption"]

    Fix["[IDEA] Solution<br/>always ask about<br/>project structure first<br/><br/>status: proposed<br/>applied: false"]

    M1 -->|"[LINK] INSTANCE_OF<br/><br/>pattern_match: 0.95<br/>your_frustration: 'high'<br/>should_have_known: true<br/>time_since_told_correct: 805 interactions"| Pattern

    M2 -->|"[LINK] INSTANCE_OF<br/><br/>pattern_match: 0.98<br/>your_frustration: 'medium'<br/>same_session: true"| Pattern

    M3 -->|"[LINK] INSTANCE_OF<br/><br/>pattern_match: 0.92<br/>your_frustration: 'very high'<br/>you_said: 'I keep telling you!'"| Pattern

    Pattern -->|" CAUSED_BY<br/><br/>confidence: 0.9<br/>analysis: 'I assume standard layouts'<br/>why_i_do_this: 'trained on common patterns'<br/>when_it_fails: 'non-standard repos'"| Root

    Root -->|"[IDEA] SUGGESTS<br/><br/>solution_type: 'behavioral change'<br/>confidence: 0.8<br/>implementation: 'query memory first'<br/>expected_reduction: 0.9"| Fix

    style M1 fill:#FFB6C6,stroke:#DC143C,stroke-width:2px
    style M2 fill:#FFB6C6,stroke:#DC143C,stroke-width:2px
    style M3 fill:#FFB6C6,stroke:#DC143C,stroke-width:2px
    style Pattern fill:#FF6B6B,stroke:#C92A2A,stroke-width:3px
    style Root fill:#FFE4B5,stroke:#FF8C00,stroke-width:3px
    style Fix fill:#98FB98,stroke:#32CD32,stroke-width:2px
```

**Key Insight**: The `INSTANCE_OF` relationship captures:
- Pattern matching (how similar is this mistake to the pattern)
- Your frustration level (important!)
- Whether I should have known better

The `CAUSED_BY` relationship captures root cause analysis!
The `SUGGESTS` relationship captures proposed solutions!

---

## Summary: The Relationships ARE The Knowledge [IDEA]

Look at what we capture in relationships:

| Relationship | What It Captures |
|-------------|------------------|
| `CORRECTS` | Why I was wrong, pattern of error, how many times, your frustration |
| `SOLVED` | Why it worked, alternatives rejected, side benefits, metrics |
| `SUPERSEDES` | How understanding evolved, lesson learned, cognitive error |
| `DERIVES` | Reasoning chain, confidence propagation, dependencies |
| `CONFLICTS_WITH` | Trade-offs, evidence for each side, resolution criteria |
| `VALIDATES` | Empirical evidence, confidence boost, verification method |
| `SIMILAR_TO` | When to use which pattern, key differences |
| `BETTER_THAN` | Comparative effectiveness, context-dependent |
| `INSTANCE_OF` | Pattern matching, frustration tracking |
| `CAUSED_BY` | Root cause analysis |
| `SUGGESTS` | Proposed solutions, expected effectiveness |

**The nodes are just anchors. The edges contain the wisdom!** 


