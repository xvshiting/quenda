# ADR-030: Product Strategy Positioning

## Status

Proposed

## Context

Quenda has been in development for 6+ months with v0.3.0 released. Current state:

- **GitHub Stars**: 2 (including author)
- **Competitors**: LangChain (90k+), LlamaIndex (35k+), AutoGPT (160k+), CrewAI (25k+), PydanticAI (5k+), SmolAgents (3k+)
- **Pain points**: Low visibility, no adoption, crowded market
- **Differentiation attempts**: Lightweight, 26 providers, skills system, layered architecture

After extensive grilling sessions, we identified:

1. **Model is not our advantage** — We can't compete with Claude/OpenAI on model quality
2. **Feature parity with competitors** — Most features (screenshot, multimodal, tools) exist in other frameworks
3. **Real differentiation possibilities**:
   - Zero dependencies
   - Testable layered architecture
   - Skills system
   - AGENT.md configuration
   - Input-driven model adaptation

## Decision

Quenda adopts a **dual-track strategy**:

### Track 1: Quenda Code (Developer-Focused)

> **The minimal, testable agent framework for developers.**

- **Audience**: Python developers, AI engineers
- **Value proposition**: 5 lines to start, zero dependencies, testable architecture
- **Competitors**: Claude Code, Cursor, LangChain, PydanticAI
- **Success metric**: Developers choose Quenda for simplicity and testability

### Track 2: Legal Agent Product (Legal Industry-Focused)

> **The trusted agent for legal teams.**

- **Audience**: Law firms, corporate legal departments
- **Value proposition**: Legal skills, enterprise trust (permission, isolation, private deployment)
- **Competitors**: Legal tech tools (Casetext, LexisNexis AI)
- **Success metric**: Legal teams adopt and pay for the product
- **Note**: Product TBD. Lawnet is a prototype, not the final product.

### Core Positioning (Framework Layer)

| Layer | Focus | What It Means |
|-------|-------|---------------|
| **Core** | Minimal | 5 lines to start, zero dependencies |
| **Enterprise** | Pluggable | Permission control, data isolation, private deployment |
| **Industry** | Legal-first | Pre-built legal skills, legal toolkits |

### What We DO

1. **Extreme simplicity** — 5 lines of code to build an agent
2. **Testable architecture** — Every layer is unit-testable with fake models
3. **Legal industry focus** — Skills and tools for legal domain
4. **Enterprise trust** — Permission control, data isolation, private deployment
5. **Tool customization** — Legal teams can create custom tools without modifying framework

### What We DON'T Do

| Not Doing | Reason |
|-----------|--------|
| Multi-agent orchestration | Violates simplicity principle |
| Complex workflow engines | Violates simplicity principle |
| All-industry generic tools | Focus on legal first |
| All enterprise features | Only pluggable management modules |
| Competing on model quality | Framework, not model provider |

### Target Users

**Quenda Code:**
- Primary: Python developers, AI engineers
- Secondary: Teams building internal tools

**Legal Agent Product:**
- Primary: Law firms, corporate legal departments
- Secondary: Independent legal tech developers

### Success Metrics

| Metric | Current | 1-Year Target |
|--------|---------|---------------|
| GitHub Stars | 2 | 1,000+ |
| Real users | ~0 | 10+ legal teams |
| Commercial interest | 0 | 2+ paid pilots |

## Consequences

### Positive

- Clear differentiation from LangChain/LlamaIndex (they're general-purpose, we're legal-first)
- Focus on enterprise needs (permission, isolation, private deployment)
- Clear product roadmap (legal skills, legal tools, enterprise modules)

### Negative

- Smaller TAM (legal is narrower than general-purpose)
- Need domain expertise to build legal skills
- Enterprise sales cycle is long

### Risks

- Legal industry may not adopt open-source solutions
- Competitors may add legal-specific features
- Enterprise features add complexity (tension with "minimal" positioning)

## Implementation Path

### Track 1: Quenda Code (Ongoing)

**Phase 1: Instruction Improvement (Week 1-2)**

**Key Insight**: The framework works well. The problem is instructions are too abstract, lacking concrete methodology.

**Evidence**: grill-with-docs skill works great because it references specific methodology skills (/grilling, /domain-modeling).

- [ ] Create "core-coding" skill with concrete methodology
  - Study grill-with-docs structure
  - Define coding methodology (understand → plan → act → verify)
  - Create skill file: `skills/core-coding/SKILL.md`
- [ ] Improve `instructions/coding.md` to be more specific
- [ ] Test improved instructions on 3 real coding tasks

**Phase 2: Dogfooding (Week 3-4)**

- [ ] Author uses Quenda Code exclusively for all coding
- [ ] Compare experience before/after instruction improvement
- [ ] Identify remaining gaps

**Phase 3: Core Improvements (Week 5-12)**

- [ ] Address remaining pain points
- [ ] Improve documentation (5-minute quickstart)
- [ ] Add example gallery

### Track 2: Legal Agent Product (Exploration)

**Phase 1: Market Research (Week 1-4)**
- [ ] Interview 5+ lawyers/legal professionals
- [ ] Identify top 3 pain points in legal workflows
- [ ] Map competitor landscape (Casetext, LexisNexis, Harvey AI)

**Phase 2: Prototype Validation (Week 5-8)**
- [ ] Build minimal prototype for 1 pain point
- [ ] Test with 2-3 real users
- [ ] Iterate or pivot

**Phase 3: Product Definition (Week 9-12)**
- [ ] Define MVP scope
- [ ] Design enterprise features (permission, isolation, deployment)
- [ ] Plan legal skills package

### Shared: Enterprise Features (Week 13+)

- [ ] Permission control module
- [ ] Data isolation design
- [ ] Private deployment guide

## References

- Lawnet project: `/Users/xushiting/Workspace/lawnet`
- Quenda architecture: `docs/architecture/`
- Existing ADRs: `docs/decisions/`
