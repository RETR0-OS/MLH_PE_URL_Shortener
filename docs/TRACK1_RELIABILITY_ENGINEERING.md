# 🛡️ Quest: Reliability Engineering

**Build a service that refuses to die easily.**

**The Mission:** In the real world, code breaks. Your job is to build a safety net so strong that even when things go wrong, the service keeps running.

**Difficulty:** ⭐⭐ (Good starting point)

> **Hidden Reliability Score (Bonus up to +50)**
> For this quest, some additional evaluator checks are intentionally not shown during development. These broadly reward resilient behavior under edge cases, such as rejecting bad input, preserving data consistency, enforcing uniqueness, handling invalid or inactive resources correctly, and maintaining expected behavior across core flows. Your hidden-check completion rate maps to a bonus tier of +10, +20, +35, or +50.

---

## 🥉 Tier 1: Bronze (The Shield)

**Objective:** Prove your code works before you ship it.

### ⚔️ Main Objectives

- **Write Unit Tests:** Create a test suite using pytest. Test individual functions in isolation.
- **Automate Defense:** Set up GitHub Actions (or similar CI) to run tests on every commit.
- **Pulse Check:** Create a `/health` endpoint that returns `200 OK`.

### 💡 Intel

- **Unit Tests?** Don't test the whole app. Just test that Input A leads to Output B.
- **Health Check?** Load balancers use this to know if your app is alive. If this fails, no traffic for you.

### ✅ Verification (Loot)

- CI Logs showing green/passing tests.
- A working `GET /health` endpoint.

---

## 🥈 Tier 2: Silver (The Fortress)

**Objective:** Stop bad code from ever reaching production.

### ⚔️ Main Objectives

- **50% Coverage:** Use `pytest-cov`. Ensure half your code lines are hit by tests.
- **Integration Testing:** Write tests that hit the API (e.g., `POST` to `/shorten` → Check DB).
- **The Gatekeeper:** Configure CI so deployment fails if tests fail.
- **Error Handling:** Document how your app handles 404s and 500s.

### 💡 Intel

- **Blocking Deploys:** This is the #1 rule of SRE. Never ship broken code.
- **Integration vs Unit:** Unit tests check the engine; integration tests check if the car drives.

### ✅ Verification (Loot)

- Coverage report showing >50%.
- A screenshot of a blocked deploy due to a failed test.

---

## 🥇 Tier 3: Gold (The Immortal)

**Objective:** Break it on purpose. Watch it survive.

### ⚔️ Main Objectives

- **70% Coverage:** High confidence in code stability.
- **Graceful Failure:** Send bad inputs. The app must return clean errors (JSON), not crash.
- **Chaos Mode:** Kill the app process or container while it's running. Show it restarts automatically (e.g., Docker restart policy).
- **Failure Manual:** Document exactly what happens when things break (Failure Modes).

### 💡 Intel

- **Chaos Engineering:** Don't wait for a crash at 3 AM. Cause the crash at 2 PM and fix it.
- **Graceful:** A user should see "Service Unavailable," not a Python stack trace.

### ✅ Verification (Loot)

- **Live Demo:** Kill the container → Watch it resurrect.
- **Live Demo:** Send garbage data → Get a polite error.
- Link to "Failure Mode" documentation.

---

## 🧰 Recommended Loadout

- `pytest`
- `pytest-cov`
- GitHub Actions
