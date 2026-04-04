# 🚀 Quest: Scalability Engineering

**Make it handle the entire internet.**

**The Mission:** Your app works for one user. What happens when 500 people hit it at once? Find the breaking point and push past it.

**Difficulty:** ⭐⭐⭐ (Requires system resources)

---

## 🥉 Tier 1: Bronze (The Baseline)

**Objective:** Stress test your system.

### ⚔️ Main Objectives

- **Load Test:** Install k6 or Locust.
- **The Crowd:** Simulate 50 concurrent users hitting your service.
- **Record Stats:** Document your Response Time (Latency) and Error Rate.

### 💡 Intel

- **Concurrent Users:** This isn't total hits. This is 50 people clicking at the exact same second.
- **Baseline:** You can't improve what you don't measure.

### ✅ Verification (Loot)

- Screenshot of terminal output showing 50 concurrent users.
- Documented baseline p95 response time.

---

## 🥈 Tier 2: Silver (The Scale-Out)

**Objective:** One server isn't enough. Build a fleet.

### ⚔️ Main Objectives

- **The Horde:** Ramp up to 200 concurrent users.
- **Clone Army:** Run 2+ instances of your app (containers) using Docker Compose.
- **Traffic Cop:** Put a Load Balancer (Nginx) in front to split traffic between instances.
- **Speed Limit:** Keep response times under 3 seconds.

### 💡 Intel

- **Horizontal Scaling:** Don't make the server stronger (Vertical). Just add more servers (Horizontal).
- **Load Balancer:** The entry point. It decides which container does the work.

### ✅ Verification (Loot)

- `docker ps` showing multiple app containers + 1 Nginx container.
- Load test results showing success with 200 users.

---

## 🥇 Tier 3: Gold (The Speed of Light)

**Objective:** Optimization and Caching.

### ⚔️ Main Objectives

- **The Tsunami:** Handle 500+ concurrent users (or 100 req/sec).
- **Cache It:** Implement Redis. Store results in memory so you don't hit the DB every time.
- **Bottleneck Analysis:** Find out what was slow before, and explain how you fixed it.
- **Stability:** Error rate must stay under 5% during the tsunami.

### 💡 Intel

- **Caching:** The fastest query is the one you don't have to make.
- **Bottlenecks:** Is it the CPU? The Database? The Network? Find the weak link.

### ✅ Verification (Loot)

- Evidence of Caching (headers, logs, or speed comparison).
- Load test results: 500 users with <5% errors.
- "Bottleneck Report" (2-3 sentences on what you fixed).

---

## 🧰 Recommended Loadout

- k6 (or Locust)
- Nginx
- Docker Compose
- Redis
