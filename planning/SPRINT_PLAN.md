# Sprint Plan & Execution Framework

## Sprint Planning Overview

This document defines the sprint structure, ceremonies, and execution framework for the 72-week PostgreSQL migration program.

---

## Sprint Structure

### Sprint Duration & Cadence

- **Sprint Length**: 2 weeks (10 working days)
- **Total Sprints**: 36 sprints (72 weeks / 2 weeks per sprint)
- **Sprint Cycle**: Monday-Friday per week (10 days)
- **Review/Planning Gap**: Friday afternoon - Monday morning

### Sprint Types

**Type A: Development Sprints** (Phases 4-5)
- Focus: Building ETL, validation engine, dashboards
- Ceremonies: Daily standup, mid-sprint check-in, sprint review, retrospective
- Story points: 40-50 points/sprint

**Type B: Execution Sprints** (Phases 6-8)
- Focus: Testing, validation, parallel run
- Ceremonies: Daily standup, testing status, sprint review, retrospective
- Story points: 30-40 points/sprint

**Type C: Gate Sprints** (After each phase)
- Focus: Phase gate review, approval, stakeholder sign-off
- Ceremonies: Gate review meeting, steering committee review
- Deliverable: Gate approval or reschedule

---

## Sprint Ceremonies

### Daily Standup (9:00 AM UTC)

**Duration**: 15 minutes
**Attendees**: Core team + current phase lead
**Format**:
- What did I complete yesterday?
- What will I work on today?
- What blockers or risks do I have?
- Any escalations needed?

**Output**: 
- Updated task board
- Blocker tracking log
- Escalation queue

### Mid-Sprint Check-In (Wednesday 10:00 AM UTC)

**Duration**: 30 minutes
**Attendees**: Phase lead, engineering leads, project manager
**Focus**:
- Are we on track to meet sprint goals?
- Top 3 risks identified
- Resource needs / blockers
- Budget burn vs. forecast

**Output**:
- Mid-sprint status report
- Risk log update
- Escalation if needed

### Sprint Review (Friday 2:00 PM UTC)

**Duration**: 60 minutes
**Attendees**: Core team, stakeholders, steering committee (phase gates)
**Agenda**:
1. Demo completed work (20 min)
2. Discuss challenges & learnings (20 min)
3. Next sprint planning preview (15 min)
4. Feedback & questions (5 min)

**Output**:
- Sprint acceptance/approval
- Demo recording for stakeholders
- Next sprint preview

### Sprint Retrospective (Friday 3:00 PM UTC)

**Duration**: 45 minutes
**Attendees**: Core team only (psychological safety)
**Format**: Start/Stop/Continue
- What should we START doing?
- What should we STOP doing?
- What should we CONTINUE doing?

**Output**:
- Action items for next sprint
- Process improvements
- Lessons learned log

### Phase Gate Review (On Phase Completion)

**Duration**: 120 minutes
**Attendees**: Steering Committee, phase leads, executive sponsor
**Agenda**:
1. Phase completion summary (15 min)
2. Deliverables review (30 min)
3. Gate criteria validation (30 min)
4. Risk & issue review (20 min)
5. Go/No-Go decision (15 min)

**Output**:
- Gate approval / conditional approval / defer decision
- Conditions (if conditional)
- Next phase authorization
- Budget release for next phase

---

## Sprint Board Structure

### Backlog Prioritization

**P0 (Critical)**: Must complete this sprint
- Blocking other teams
- Deadline-driven (gate criteria)
- High business impact

**P1 (High)**: Should complete this sprint
- Important functionality
- Stakeholder visibility
- Medium business impact

**P2 (Medium)**: Nice to have
- Optimization work
- Documentation
- Technical debt

**P3 (Low)**: Deferred
- Future phases
- Nice-to-have enhancements
- Non-critical bugs

### Story Status Workflow

```
Backlog → In Progress → In Review → Testing → Done

Stories move through stages:
├─ Backlog: Estimated, prioritized, waiting for sprint assignment
├─ In Progress: Assigned to engineer, active work
├─ In Review: Code/design review in progress
├─ Testing: QA or validation in progress
└─ Done: Meets definition of done, accepted
```

### Definition of Done (DoD)

Story is "Done" when:
- ✅ Code written & peer-reviewed
- ✅ Unit tests (>80% code coverage)
- ✅ Documentation updated
- ✅ QA testing complete (if applicable)
- ✅ Performance validated (if applicable)
- ✅ Security review passed (if applicable)
- ✅ Deployed to staging environment
- ✅ Stakeholder acceptance obtained

---

## Sprint Planning Template

### Phase 4 Example: Migration Development Sprint 1 (Weeks 15-16)

**Sprint Goal**: Schema migration & database initialization complete

**Sprint Capacity**: 50 story points / 3 engineers

**Backlog Items**:

| ID | Task | Type | Owner | Points | Status |
|---|------|------|-------|--------|--------|
| SCHEMA-01 | Export source schema with pg_dump | Task | Senior DBA | 5 | In Progress |
| SCHEMA-02 | Analyze compatibility issues (100+ mappings) | Analysis | DBA | 8 | In Progress |
| SCHEMA-03 | Create auto-conversion Python scripts | Development | Data Engineer | 13 | Backlog |
| SCHEMA-04 | Test conversion on sample data | QA | QA Engineer | 8 | Backlog |
| SCHEMA-05 | Deploy target schema to Azure | Deployment | DBA | 5 | Backlog |
| SCHEMA-06 | Create supporting/validation tables | Development | Data Engineer | 8 | Backlog |
| SCHEMA-07 | Document all data type mappings | Documentation | Technical Writer | 3 | Backlog |
| **TOTAL** | | | | **50** | |

**Sprint Risks**:
- Risk: Unexpected data type incompatibilities
  - Probability: Medium | Impact: High
  - Mitigation: Early analysis, fallback to manual conversion
  
- Risk: Conversion script performance issues
  - Probability: Low | Impact: High
  - Mitigation: Test on large dataset in staging

**Sprint Dependencies**:
- Upstream: Phase 3 (Infrastructure) must be complete
- Downstream: Phase 4 Sprint 2 depends on SCHEMA-05 completion

---

## Resource Allocation by Phase

### Phase 4: Migration Development (10 weeks)

**Team Composition**:
- Senior DBA (1.0 FTE)
- Data Engineer (1.0 FTE)
- ADF Specialist (1.0 FTE)
- QA Engineer (0.5 FTE)
- Performance Tuning Engineer (0.6 FTE)
- **Total**: 4.1 FTE

**Weekly Breakdown**:
```
Week 15-17 (Schema Migration): DBA 100%, Data Eng 100%
Week 18-20 (ETL Dev): Data Eng 100%, ADF Spec 100%
Week 21-24 (Full Load): All hands, 4.1 FTE combined
```

### Phase 7: Business Validation (12 weeks)

**Team Composition**:
- UAT Coordinator (1.0 FTE)
- Data Support (3.0 FTE)
- Business Users (rotating, 40 FTE total)
- QA Lead (0.5 FTE)

**Weekly Breakdown**:
```
Week 39-42: UAT coordination, 3 FTE support, 40 business users
Week 43-46: Issue remediation, 2 FTE support, 20 business users (validation)
Week 47-50: Extended validation, 2 FTE support, 10 business users
```

---

## Risk Management in Sprints

### Sprint Risk Review Process

**Each Sprint**:
1. Identify new risks
2. Review existing risk status
3. Update risk log with:
   - Description
   - Probability (Low/Medium/High)
   - Impact (Low/Medium/High)
   - Mitigation strategy
   - Owner
   - Status (Open/Mitigated/Closed)

### Top 5 Enterprise Risks

**Risk 1: Stakeholder Misalignment on Requirements**
- Probability: Medium
- Impact: High (could delay by 2-4 weeks)
- Mitigation: Weekly stakeholder sync, requirements sign-off gate
- Owner: Project Manager

**Risk 2: Data Quality Issues in Source**
- Probability: Medium
- Impact: High (delays validation, extends timeline)
- Mitigation: Comprehensive data profiling (Phase 1), early issue identification
- Owner: Senior DBA

**Risk 3: Performance Bottlenecks Under Load**
- Probability: Medium
- Impact: High (could require re-architecture)
- Mitigation: Load testing in Phase 6, performance tuning buffer in plan
- Owner: Performance Engineer

**Risk 4: Parallel Run Discrepancies**
- Probability: Medium
- Impact: Medium (adds 1-2 weeks to Phase 8)
- Mitigation: Daily reconciliation, early issue detection
- Owner: Data Engineer

**Risk 5: Network Connectivity Issues**
- Probability: Low
- Impact: High (could affect entire program)
- Mitigation: VPN + ExpressRoute redundancy, SHIR auto-restart
- Owner: Network Engineer

### Risk Escalation Criteria

| Severity | Criteria | Action | Escalate To |
|----------|----------|--------|-------------|
| Critical | Blocks go-live, data loss risk | Immediate | Steering Committee |
| High | Delays phase by > 1 week | Daily standup | Phase Lead |
| Medium | Delays sprint by > 2 days | Mid-sprint review | PM |
| Low | Minor delay, workaround exists | Backlog | Team |

---

## Metrics & Tracking

### Sprint Metrics (Weekly Reporting)

**Velocity**
- Story points completed / planned
- Trend analysis (3-sprint moving average)
- Target: ±5% variance from plan

**Burndown Chart**
- Remaining story points vs. days
- Tracks sprint progress toward goal
- Flag if more than 30% points remain on last 2 days

**Defect Metrics**
- Critical defects: < 1 per sprint
- High defects: < 5 per sprint
- Escape rate: < 5% (bugs found post-testing)

**Resource Metrics**
- Actual FTE vs. planned
- Time tracking accuracy (> 95% logged)
- Overtime hours (alert if > 10% overrun)

**Budget Metrics**
- Actual spend vs. budgeted
- Variance from plan (target: ±5%)
- Forecast at completion (Phase vs. Program)

### Phase-Level Metrics (Gate Reviews)

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Schedule variance | ±5% | ? | |
| Budget variance | ±5% | ? | |
| Defect escape rate | <5% | ? | |
| Stakeholder satisfaction | >90% | ? | |
| Risk items open | <3 critical | ? | |

---

## Communication Plan During Sprints

### Weekly Communications

**Monday 9:30 AM**: Executive briefing (5 min)
- Week overview
- Critical blockers/risks
- Steering committee alert (if needed)

**Wednesday 5:00 PM**: Mid-sprint status email
- Progress toward sprint goal
- Blockers & resolutions
- Forecast (will we complete sprint goal?)

**Friday 4:00 PM**: Sprint summary report
- Sprint completion status
- Accepted vs. deferred stories
- Next sprint preview
- Retrospective insights

### Escalation Communication

**Blocker Identified**:
- Logged in 15 minutes
- Daily standup escalation
- PM notification within 1 hour
- Phase lead decision by end of day

**Critical Risk**:
- Logged immediately
- Phase lead + PM notified within 30 min
- Steering Committee alert within 2 hours
- Emergency meeting if needed

---

## Sprint Retrospective Template

### Retrospective Output Log

**Date**: [Week XX, Day]
**Phase**: [Phase name]
**Sprint**: [Sprint #]

**What went well?** (Start doing / Continue)
- Item 1
- Item 2
- Item 3

**What didn't go well?** (Stop doing)
- Item 1
- Item 2

**What should we improve?** (Action items)
- Action 1: Owner, Target date
- Action 2: Owner, Target date

**Metrics**:
- Velocity: X points
- Burn rate: X points/day
- Defects found: X
- Blockers: X

**Knowledge Transfer**:
- Key learnings for future sprints
- Improvements implemented

---

## Sprint Execution Best Practices

### During Sprint

✅ **DO**:
- Commit only to realistic capacity
- Break large stories into smaller pieces
- Flag blockers immediately
- Update board daily
- Communicate early about delays
- Focus on sprint goal

❌ **DON'T**:
- Add stories mid-sprint without removing others
- Overcommit beyond capacity
- Wait until end-of-sprint to flag issues
- Leave board stale
- Hold onto blockers without escalation
- Multitask (focus on sprint goal)

### Sprint Ceremonies

✅ **DO**:
- Start on time
- Keep time-boxes (no running over)
- Include necessary people only
- Have clear agenda
- Document outcomes

❌ **DON'T**:
- Run ceremonies late
- Let meetings drift over time
- Include uninvolved people
- Skip ceremonies to "save time"
- Forget to document results

---

## Tools & Systems

### Recommended Tools

- **Backlog Management**: Azure DevOps, Jira, Asana
- **Sprint Board**: Same tool (Kanban board)
- **Time Tracking**: Toggl, Harvest, Azure DevOps
- **Metrics/Dashboards**: PowerBI, Tableau
- **Communication**: Teams, Slack, Confluence
- **Documentation**: Confluence, Sharepoint

### Template Repository

All sprint templates available in:
`/planning/templates/`

- Sprint planning template
- Risk assessment template
- Sprint retrospective template
- Metrics reporting template
- Communication templates

---

**Sprint Plan Version**: 1.0
**Last Updated**: Q1 2024
