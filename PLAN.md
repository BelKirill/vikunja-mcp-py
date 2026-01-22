# vikunja-mcp-py Implementation Plan

> **Last Updated:** 2026-01-22
> **Total Open Tasks:** 43
> **Completed:** 7
> **Estimated Phases:** 6

---

## Executive Summary

This plan organizes 50 open tasks into 6 sequential phases based on dependencies, priority, and logical grouping. Each phase is designed for focused execution with clear completion criteria.

---

## Phase 1: Foundation & CI/CD (Priority: Critical)

**Goal:** Establish reliable build/deploy pipeline before feature work.

| Task ID | Title | Energy | Est. | Status |
|---------|-------|--------|------|--------|
| 92 | Test CI pipeline end-to-end | high | 20m | **DONE** |
| 93 | Add "How to use Claude" snippet to docs | low | 15m | **DONE** |
| 94 | PR template update (optional polish) | low | 10m | **DONE** |

**Completion Criteria:**
- [x] CI/CD pipeline runs green on draft PR
- [x] Docker image builds and pushes to GHCR
- [x] README updated with Claude configuration
- [x] PR template includes container build checklist

**Dependencies:** None - foundation work

---

## Phase 2: Core API Enhancements (Priority: High)

**Goal:** Improve core MCP tool reliability and functionality.

### 2A: Error Handling & Retry Logic

| Task ID | Title | Energy | Est. | Status |
|---------|-------|--------|------|--------|
| 149 | 400 error: get-filtered-tasks retry logic | medium | 45m | **DONE** |

### 2B: Bulk Operations

| Task ID | Title | Energy | Est. | Status |
|---------|-------|--------|------|--------|
| 112 | Implement bulk update tool | medium | 60m | **DONE** |

### 2C: Comment System (EPIC #150)

| Task ID | Title | Energy | Est. | Blocks |
|---------|-------|--------|------|--------|
| 153 | Integrate comments with MCP workflow | medium | 30m | **DONE** |
| 154 | Document comment system usage | low | 25m | **DONE** |

**Completion Criteria:**
- [x] get-filtered-tasks retries 3x before failing
- [x] bulk_update_tasks tool operational
- [x] Comments integrated with get-task-metadata
- [x] Comment system documented

**Dependencies:** Phase 1 complete

---

## Phase 3: Dependency Management System (Priority: High)

**Goal:** Implement intelligent task dependency tracking and blocking logic.

### Dependency Chain (Tasks 95-104)

| Order | Task ID | Title | Energy | Est. | Blocks |
|-------|---------|-------|--------|------|--------|
| 1 | 95 | Extract dependency data from Vikunja API | medium | 30m | 96-104 |
| 2 | 96 | Update MCP tool response schema | medium | 30m | 97 |
| 3 | 97 | Build dependency checker core logic | high | 45m | 98 |
| 4 | 98 | Integrate dependency filtering into focus engine | medium | 120m | 99 |
| 5 | 99 | Update daily focus tool with dependency awareness | medium | 120m | 100 |
| 6 | 100 | Add chain context metadata enhancement | medium | 120m | 101 |
| 7 | 101 | Enhance AI prompt with dependency context | medium | 120m | 102 |
| 8 | 102 | Write unit tests for dependency system | medium | 120m | 104 |
| 9 | 104 | Document dependency system usage | medium | 120m | - |

**Completion Criteria:**
- [ ] Dependency data extracted from Vikunja related_tasks API
- [ ] Blocked tasks excluded from daily-focus recommendations
- [ ] Chain context shown in task metadata
- [ ] AI prompts include dependency information
- [ ] Unit tests passing with >80% coverage
- [ ] System documented

**Dependencies:** Phase 2 complete

---

## Phase 4: Project Context & Intelligence (Priority: High)

**Goal:** Enable context-aware recommendations to minimize context switching.

### 4A: Project Context System (Tasks 86, 105-111)

| Order | Task ID | Title | Energy | Est. | Blocks |
|-------|---------|-------|--------|------|--------|
| 1 | 86 | Provide rich project details to AI | medium | 45m | 105-111 |
| 2 | 105 | Add project context metadata parsing | medium | 90m | 106 |
| 3 | 106 | Build context filtering algorithm | high | 120m | 107 |
| 4 | 107 | Enhance daily focus with context parameters | medium | 120m | 108 |
| 5 | 108 | Add context-aware focus engine integration | medium | 120m | 109 |
| 6 | 109 | Enhance AI prompt with context information | medium | 120m | 110 |
| 7 | 110 | Test context filtering end-to-end | medium | 90m | 111 |
| 8 | 111 | Configure project context metadata | medium | 90m | - |

### 4B: AI Task Rating System (EPIC #155)

| Order | Task ID | Title | Energy | Est. | Blocks |
|-------|---------|-------|--------|------|--------|
| 1 | 156 | Design AI task rating engine | medium | 45m | 157 |
| 2 | 157 | Integrate AI rating with task creation | medium | 30m | 158 |
| 3 | 158 | Validate and monitor AI rating accuracy | low | 30m | - |

**Completion Criteria:**
- [ ] Project context included in AI decision prompts
- [ ] Context switching costs calculated and minimized
- [ ] AI generates intelligent task metadata (energy, complexity, duration)
- [ ] Fallback to defaults when AI unavailable
- [ ] Rating accuracy validated

**Dependencies:** Phase 3 complete

---

## Phase 5: Session Management & Label System (Priority: High)

**Goal:** Implement persistent AI sessions and comprehensive label management.

### 5A: Session Persistence (Tasks 114-125)

| Order | Task ID | Title | Energy | Est. | Blocks |
|-------|---------|-------|--------|------|--------|
| 1 | 115 | Enhance recommendation engine with session context | medium | 75m | 116, 149 |
| 2 | 116 | Add session control MCP tools | medium | 60m | 117 |
| 3 | 117 | Build session analytics for workflow insights | low | 45m | - |
| 4 | 124 | Integrate session persistence with MCP server | high | 40m | 125, 114 |
| 5 | 125 | Create integration tests for session persistence | high | 180m | 114 |
| 6 | 114 | Implement OpenAI conversation session persistence (META) | high | 180m | - |

### 5B: Label Management System (EPIC #159, Tasks 127-131, 160-162)

| Order | Task ID | Title | Energy | Est. | Blocks |
|-------|---------|-------|--------|------|--------|
| 1 | 160 | Implement Vikunja label API integration | medium | 40m | 161, 162, 163 |
| 2 | 127 | Design comprehensive label management tool system | high | 180m | 128-131 |
| 3 | 128 | Implement core label data structures | high | 180m | 129-131 |
| 4 | 129 | Build individual label management MCP tools | high | 180m | 130 |
| 5 | 130 | Implement bulk label operations | high | 180m | 131 |
| 6 | 131 | Integrate advanced label-based filtering | high | 180m | - |
| 7 | 162 | Create MCP label management tools | medium | 35m | 163 |

**Completion Criteria:**
- [ ] Session persists across MCP server restarts
- [ ] Session control tools (start/end/status/summary) working
- [ ] Session analytics tracking effectiveness
- [ ] Label CRUD operations via MCP tools
- [ ] Bulk label operations for efficiency
- [ ] Label-based filtering in get-filtered-tasks

**Dependencies:** Phase 4 complete

---

## Phase 6: Analytics, Testing & Documentation (Priority: Medium)

**Goal:** Polish, test coverage, and portfolio-ready documentation.

### 6A: Analytics Dashboard

| Task ID | Title | Energy | Est. | Status |
|---------|-------|--------|------|--------|
| 81 | Build focus session analytics dashboard | high | 60m | pending |

### 6B: Test Coverage (Task 74, 77)

| Task ID | Title | Energy | Est. | Blocks |
|---------|-------|--------|------|--------|
| 74 | VIK-012: Test Coverage & Quality Assurance | medium | 90m | 77 |
| 77 | VIK-003: Add comprehensive tests for Go client | medium | 75m | - |

### 6C: Documentation & Portfolio (Tasks 72, 78, 80)

| Task ID | Title | Energy | Est. | Blocks |
|---------|-------|--------|------|--------|
| 72 | Documentation & Portfolio Presentation | medium | 90m | 78, 80 |
| 78 | Documentation and deployment guide updates | medium | 60m | - |
| 80 | Prepare portfolio demo presentation | social | 90m | - |

### 6D: Infrastructure Optimization

| Task ID | Title | Energy | Est. | Status |
|---------|-------|--------|------|--------|
| 45 | Reduce block storage costs | high | 60m | pending |

**Completion Criteria:**
- [ ] Analytics dashboard showing session metrics
- [ ] Test coverage >85% overall
- [ ] Go client tests >80% coverage
- [ ] README with professional value proposition
- [ ] Demo materials and presentation ready
- [ ] Deployment guide complete
- [ ] Block storage costs reduced 20-30%

**Dependencies:** Phase 5 complete

---

## Quick Reference: Tasks by Energy Level

### Low Energy (Good for foggy days)
| Task ID | Title | Est. |
|---------|-------|------|
| 93 | Add "How to use Claude" snippet | 15m |
| 94 | PR template update | 10m |
| 117 | Build session analytics | 45m |
| 154 | Document comment system | 25m |
| 158 | Validate AI rating accuracy | 30m |

### Medium Energy (Steady focus)
| Task ID | Title | Est. |
|---------|-------|------|
| 72 | Documentation & Portfolio | 90m |
| 78 | Deployment guide updates | 60m |
| 95 | Extract dependency data | 30m |
| 96 | Update MCP response schema | 30m |
| 112 | Bulk update tool | 60m |
| 149 | 400 error retry logic | 45m |
| 153 | Integrate comments with workflow | 30m |
| 156 | Design AI task rating engine | 45m |
| 157 | Integrate AI rating | 30m |

### High Energy (Peak focus required)
| Task ID | Title | Est. |
|---------|-------|------|
| 45 | Reduce block storage costs | 60m |
| 81 | Focus session analytics dashboard | 60m |
| 92 | Test CI pipeline | 20m |
| 97 | Build dependency checker core | 45m |
| 106 | Build context filtering algorithm | 120m |
| 124 | Integrate session persistence | 40m |
| 125 | Integration tests for sessions | 180m |
| 127-131 | Label management system | varies |

### Social Energy (Presentation mode)
| Task ID | Title | Est. |
|---------|-------|------|
| 80 | Prepare portfolio demo | 90m |

---

## Task Dependency Graph

```
Phase 1: CI/CD Foundation
    92 (CI pipeline) ─┬─> 93 (docs snippet)
                      └─> 94 (PR template)

Phase 2: Core Enhancements
    149 (error handling)
    112 (bulk update)
    153 ──> 154 (comments)

Phase 3: Dependency Management
    95 ──> 96 ──> 97 ──> 98 ──> 99 ──> 100 ──> 101 ──> 102 ──> 104

Phase 4: Project Context & AI Rating
    86 ──> 105 ──> 106 ──> 107 ──> 108 ──> 109 ──> 110 ──> 111
    156 ──> 157 ──> 158

Phase 5: Sessions & Labels
    115 ──> 116 ──> 117
         └──> 149 (already done in Phase 2)
    124 ──> 125 ──> 114 (meta-task)

    160 ──┬──> 127 ──> 128 ──> 129 ──> 130 ──> 131
          └──> 162

Phase 6: Polish & Portfolio
    74 ──> 77 (testing)
    72 ──┬──> 78 (deployment docs)
         └──> 80 (demo presentation)
    81 (analytics)
    45 (storage optimization)
```

---

## Daily Focus Session Recommendations

**Quick Wins (15-30 min, any energy):**
- Task 93: Add Claude config to docs
- Task 94: PR template update
- Task 154: Document comment system

**Deep Work Sessions (60-120 min, high energy):**
- Task 97: Dependency checker core logic
- Task 106: Context filtering algorithm
- Task 127: Label management design

**Steady Progress (30-60 min, medium energy):**
- Task 95: Extract dependency data
- Task 112: Bulk update tool
- Task 156: AI task rating engine

---

## Notes

1. **Python Rewrite Context:** This is vikunja-mcp-py, a Python rewrite. Some tasks reference Go code from the original - adapt accordingly.

2. **EPIC Tasks:** Tasks 150, 155, 159 are EPICs (meta-tasks). They complete when their child tasks are done.

3. **Blocked Tasks:** Several tasks have complex dependency chains. Always verify blockers before starting.

4. **Session Persistence:** Task 114 is a meta-task blocked by 119-125. Tasks 119-123 are not in current open list - may already be complete or need creation.

5. **Portfolio Focus:** Tasks 72, 78, 80 are critical for Australian job market positioning.
