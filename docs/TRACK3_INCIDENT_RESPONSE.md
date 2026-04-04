# 🚨 Quest: Incident Response

**Be the one who knows when it breaks.**

**The Mission:** If a tree falls in the forest and no one logs it, did it make a sound? Build the eyes and ears of your infrastructure.

**Difficulty:** ⭐⭐⭐ (Complex setup)

---

## 🥉 Tier 1: Bronze (The Watchtower)

**Objective:** Stop using print statements.

### ⚔️ Main Objectives

- **Structured Logging:** Configure JSON logs. Include timestamps and log levels (INFO, WARN, ERROR).
- **Metrics:** Expose a `/metrics` endpoint (or similar) showing CPU/RAM usage.
- **Manual Check:** Have a way to view logs without SSH-ing into the server.

### 💡 Intel

- **Structured Logs:** Computers can't read `print("it broke")`. They CAN read `{"level": "ERROR", "component": "DB"}`.
- **Metrics:** Logs tell you what happened. Metrics tell you how much is happening.

### ✅ Verification (Loot)

- Screenshot of clean JSON logs.
- Screenshot of a `/metrics` page with data.

---

## 🥈 Tier 2: Silver (The Alarm)

**Objective:** Wake up the on-call engineer.

### ⚔️ Main Objectives

- **Set Traps:** Configure alerts for "Service Down" and "High Error Rate."
- **Fire Drill:** Connect alerts to a channel (Slack, Discord, Email).
- **Speed:** Trigger must fire within 5 minutes of the failure.

### 💡 Intel

- **Alert Fatigue:** Don't alert on everything. Only alert if a human needs to wake up and fix it.
- **Thresholds:** "Alert if CPU > 90% for 2 minutes."

### ✅ Verification (Loot)

- **Live Demo:** Break the app → Phone/Laptop goes "Bing!" with a notification.
- Show the configuration (YAML/Code) for the alert logic.

---

## 🥇 Tier 3: Gold (The Command Center)

**Objective:** Total situational awareness.

### ⚔️ Main Objectives

- **The Dashboard:** Build a visual board (Grafana/Datadog) tracking 4+ metrics (Latency, Traffic, Errors, Saturation).
- **The Runbook:** Write a "In Case of Emergency" guide. What do we do when the alert fires?
- **Sherlock Mode:** Diagnose a fake issue using only your dashboard and logs.

### 💡 Intel

- **The Runbook:** At 3 AM, you are not functioning. The Runbook does not sleep. Write instructions for your nonfunctional 3 AM self.
- **Golden Signals:** Latency, Traffic, Errors, Saturation.

### ✅ Verification (Loot)

- Screenshot of a beautiful, data-filled Dashboard.
- Link to the Runbook.
- Explanation of how you found a root cause using the dashboard.

---

## 🧰 Recommended Loadout

- Prometheus
- Grafana
- Alertmanager
- Discord Webhooks
