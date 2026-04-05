# Incident Postmortem Template

> This template follows the [Google SRE](https://sre.google/sre-book/postmortem-culture/) incident postmortem model. Use it after every production incident (severity P1–P3). Aim to complete within 5 business days of resolution.

---

## Incident Metadata

<!-- Fill in the incident details below. Use the incident ID from your alert system. -->

| Field | Value |
|-------|-------|
| **Incident ID** | [FILL IN: e.g., INC-2026-001] |
| **Title** | [FILL IN: Clear, specific incident description] |
| **Date Started** | [FILL IN: YYYY-MM-DD HH:MM UTC] |
| **Date Resolved** | [FILL IN: YYYY-MM-DD HH:MM UTC] |
| **Duration** | [FILL IN: e.g., 45 minutes] |
| **Severity** | [FILL IN: P1/P2/P3] |
| **Status** | [FILL IN: Resolved / Mitigated] |
| **Incident Commander** | [FILL IN: Name of person who led response] |
| **Postmortem Author** | [FILL IN: Name and date of writing] |

---

## Summary

<!-- 2-3 sentences: What happened in plain English? What was the user-facing impact? -->

[FILL IN: Write a one-paragraph executive summary. Focus on *what* happened and *who* was affected, not *why* (that comes later). Include the primary symptom that customers noticed.]

---

## Impact Statement

<!-- Quantify the blast radius. Be specific — this drives priority and urgency. -->

### Users Affected

[FILL IN: How many users? Percentage of user base? Specific customer segments? Or "internal-only" if this was pre-production.]

### Service Degradation

| Metric | During Incident | Normal Baseline | SLO Target |
|--------|-----------------|-----------------|-----------|
| Availability | [FILL IN: %] | [FILL IN: %] | [FILL IN: %] |
| Error Rate (5xx) | [FILL IN: %] | [FILL IN: %] | [FILL IN: %] |
| Latency p95 | [FILL IN: ms] | [FILL IN: ms] | [FILL IN: ms] |
| [Service-specific metric] | [FILL IN] | [FILL IN] | [FILL IN] |

### SLO Burn

<!-- Did this incident consume part of the error budget? By how much? -->

[FILL IN: e.g., "This incident consumed 25% of the weekly error budget. We had 75% remaining as of the incident start."]

### Business Impact

[FILL IN: Quantify if possible — lost transactions, customers unable to complete workflows, revenue impact, reputation impact. Or "no customer impact" if this was caught before users noticed.]

---

## Timeline

<!-- Chronological list of what happened. Reference specific times, dashboards, logs, and people involved. -->

| Time (UTC) | Actor(s) | Event | Notes |
|---------|---------|-------|-------|
| [FILL IN: HH:MM] | [FILL IN: Name] | [FILL IN: What triggered the incident?] | [FILL IN: e.g., Deploy completed, alert fired, manual testing] |
| [FILL IN] | [FILL IN] | [FILL IN: First sign of problems (error spike, latency spike, etc.)] | [FILL IN: Which dashboard/alert? What metric breached?] |
| [FILL IN] | [FILL IN] | [FILL IN: Detection — alert fired or on-call noticed] | [FILL IN: How long after failure? Was MTTD acceptable?] |
| [FILL IN] | [FILL IN] | [FILL IN: Escalation — escalated to another team?] | [FILL IN: Which team? Why needed?] |
| [FILL IN] | [FILL IN] | [FILL IN: Investigation step — hypothesis tested] | [FILL IN: What dashboard/log was checked? What was ruled out?] |
| [FILL IN] | [FILL IN] | [FILL IN: Mitigation began] | [FILL IN: Temporary fix, rollback, scaling, etc.] |
| [FILL IN] | [FILL IN] | [FILL IN: Mitigation applied] | [FILL IN: Result — did traffic drop? Latency improve?] |
| [FILL IN] | [FILL IN] | [FILL IN: Full recovery confirmed] | [FILL IN: All metrics back to normal. Verified by whom?] |

---

## Root Cause Analysis

<!-- Use the "5 Whys" method. Each level should answer why the previous level happened. -->

### 5 Whys

**Level 1: What directly caused the outage?**

[FILL IN: e.g., "Database connection pool exhausted after new query pattern was deployed."]

**Level 2: Why did that happen?**

[FILL IN: e.g., "The new endpoint was making N queries per request without connection reuse."]

**Level 3: Why was this not caught?**

[FILL IN: e.g., "Load testing was only done with 50 concurrent users; production load was 500 users."]

**Level 4: Why didn't load testing match production?**

[FILL IN: e.g., "The load test harness was not configured with realistic request distributions. The new endpoint represents 5% of traffic in production but was 1% in the test."]

**Level 5: Why was the process insufficient?**

[FILL IN: e.g., "Load test configs are not validated against production traffic patterns. There is no automatic comparison of test vs. prod."]

### Root Cause Summary

[FILL IN: 1-2 sentences pulling together the 5 Whys into a single clear statement. This is what you prevent going forward.]

### Contributing Factors

<!-- Things that made the problem worse or delayed detection/recovery. -->

- [FILL IN: e.g., "Monitoring was not set up for the new endpoint."]
- [FILL IN: e.g., "On-call engineer did not have access to database metrics."]
- [FILL IN: e.g., "Circuit breaker timeout was too long, causing 60 seconds of degradation instead of 10."]

---

## Action Items

<!-- Tasks to prevent recurrence (prevent), detect faster (detect), or survive the failure (mitigate). -->

| Action | Type | Owner | Priority | Due Date | Status | Notes |
|--------|------|-------|----------|----------|--------|-------|
| [FILL IN: e.g., "Increase DB max_connections from 50 to 200"] | Prevent | [FILL IN: Name] | [FILL IN: P1/P2/P3] | [FILL IN: Date] | [FILL IN: Open/In Progress/Done] | [FILL IN: e.g., "Reduces queueing under peak load"] |
| [FILL IN: e.g., "Add per-endpoint query count monitoring"] | Detect | [FILL IN: Name] | [FILL IN: P1/P2/P3] | [FILL IN: Date] | [FILL IN: Open/In Progress/Done] | [FILL IN: e.g., "Alerts if a single endpoint makes >1000 queries/sec"] |
| [FILL IN: e.g., "Implement connection pool backpressure"] | Mitigate | [FILL IN: Name] | [FILL IN: P1/P2/P3] | [FILL IN: Date] | [FILL IN: Open/In Progress/Done] | [FILL IN: e.g., "Return 503 instead of queuing when pool is exhausted"] |
| [FILL IN: e.g., "Update runbook with recovery steps"] | Mitigate | [FILL IN: Name] | [FILL IN: P1/P2/P3] | [FILL IN: Date] | [FILL IN: Open/In Progress/Done] | [FILL IN: e.g., "Document which command to run and expected recovery time"] |
| [FILL IN: e.g., "Load test with realistic traffic distributions"] | Prevent | [FILL IN: Name] | [FILL IN: P1/P2/P3] | [FILL IN: Date] | [FILL IN: Open/In Progress/Done] | [FILL IN: e.g., "Before deploying any endpoint changes, run load test matching prod traffic patterns"] |

---

## Lessons Learned

### What Went Well

<!-- Things we did right. Reinforce these behaviors. -->

- [FILL IN: e.g., "Alerting on error rate fired within 30 seconds. No delay in detection."]
- [FILL IN: e.g., "On-call engineer correctly identified the connection pool as the bottleneck by checking the right dashboard first."]
- [FILL IN: e.g., "Playbook for scaling the database was up to date and took only 5 minutes to execute."]
- [FILL IN: e.g., "Multi-region setup meant the other region continued serving traffic while we mitigated the primary region."]

### What Went Poorly

<!-- Things we did wrong. Don't assign blame — focus on the process or system failure. -->

- [FILL IN: e.g., "Load test config was out of sync with production traffic patterns."]
- [FILL IN: e.g., "Monitoring for the new endpoint was not set up before deployment."]
- [FILL IN: e.g., "On-call engineer did not have write access to the database config, had to wait for an escalation."]
- [FILL IN: e.g., "Alerting threshold for latency p95 was too high — 2 second threshold when SLO is 500ms. We could have been alerted sooner."]

### Where We Got Lucky

<!-- Potential worse outcomes that didn't happen. These highlight risks and gaps. -->

- [FILL IN: e.g., "The incident happened during a low-traffic period (50 req/s). During peak traffic (500 req/s), the same failure would have caused dropped requests."]
- [FILL IN: e.g., "The cache was still warm, so even with DB latency increased, many reads were served from cache."]
- [FILL IN: e.g., "The bad deploy was to a single region — the other region was not affected, so 50% of users saw no impact."]
- [FILL IN: e.g., "A paying customer did not hit the bug. If they had, we would have had a high-urgency support case."]

---

## Supporting Information

### Links and References

- **Incident Tracker:** [FILL IN: Link to ticket or incident log]
- **Dashboards Consulted:**
  - [FILL IN: e.g., "Golden Signals — latency and error rate"]
  - [FILL IN: e.g., "Database Metrics — connection pool status"]
  - [FILL IN: e.g., "Deployment Timeline — what changed at 14:32?"]
- **Logs:**
  - [FILL IN: e.g., "Application logs from 14:30–15:00 UTC"]
  - [FILL IN: e.g., "Database slow query log"]
- **Runbooks:**
  - [FILL IN: e.g., "/wiki/runbooks/database-scale-up.md"]
- **On-Call Resources:**
  - [FILL IN: e.g., "Escalation tree: /wiki/oncall/escalation.md"]
  - [FILL IN: e.g., "Database on-call playbook: /wiki/runbooks/db-triage.md"]

### Relevant Code / Configuration

- **Deploy:** [FILL IN: Commit hash or deploy ID that triggered the incident]
- **Config Changes:** [FILL IN: If config was changed, link to the diff or change request]
- **Monitoring Config:** [FILL IN: Link to alert definition or dashboard JSON]

### Alert Definitions

[FILL IN: Copy the alert rule that fired. Include the PromQL query or threshold.]

```
# Example:
rule_name: HighDatabaseConnections
expr: (pg_stat_activity_count / pg_settings_max_connections) > 0.8
for: 2m
```

### Logs from Incident Window

[FILL IN: Paste key log entries (anonymized). Focus on errors, state changes, and timestamps.]

```
Example:
2026-04-04T14:32:00Z ERROR: Database pool exhausted (45/50 connections in use)
2026-04-04T14:32:03Z ERROR: Request timeout waiting for connection
2026-04-04T14:33:15Z INFO: Database scaled from 50 to 200 max_connections
2026-04-04T14:33:45Z INFO: Connection pool recovered, now 12/200 in use
```

---

## Appendix: Communication Log

<!-- Internal communication during the incident — for learning and context. -->

### Slack / Incident Channel

[FILL IN: Key messages from the incident channel. Timestamps. Who said what.]

```
14:32:00 @alice: Error rate spike in dashboard. Looking now.
14:32:15 @bob: Is this related to the deploy 30 min ago?
14:32:30 @alice: Checking. Let me review the load test results.
14:33:00 @carlos: I've started the scale-up playbook
14:33:45 @alice: Root cause identified. Bad query pattern in new endpoint. Issue #456.
14:34:00 @carlos: Scale-up complete. Latency recovering.
14:35:00 @alice: All clear. Metrics back to baseline. Opening postmortem.
```

### Public Communication

[FILL IN: If customers were notified, paste the communication (status page update, email, etc.). Include timestamps.]

```
2026-04-04 14:35 UTC
Status update: A brief service degradation occurred from 14:32–14:35 UTC.
Affected: [X]% of requests experienced elevated latency.
Cause: Database connection pool exhaustion.
Resolution: Scaled up connection limits. Service is now fully recovered.
Postmortem coming soon.
```

---

## Document History

| Version | Author | Date | Changes |
|---------|--------|------|---------|
| 1.0 | [FILL IN: Name] | [FILL IN: Date] | Initial postmortem |
| [FILL IN] | [FILL IN] | [FILL IN] | [FILL IN: Any edits after publication] |

---

## Sign-Off

<!-- Indicates postmortem is complete and consensus has been reached on action items. -->

- **Incident Commander:** _________________________ Date: _________
- **Engineering Lead:** _________________________ Date: _________
- **On-Call Manager:** _________________________ Date: _________

---

## Notes for Future Postmortems

- **Blameless:** This postmortem focuses on process and system failures, not individual mistakes. No blame is assigned.
- **Action Items Tracked:** All action items are tracked in [FILL IN: Your issue tracker]. Progress is reviewed weekly until complete.
- **Feedback:** Questions or additions? Comment on the incident ticket or email [FILL IN: DL or person responsible].
- **Confidentiality:** This postmortem is internal. Do not share outside the team without approval from [FILL IN: Manager or public communications lead].
