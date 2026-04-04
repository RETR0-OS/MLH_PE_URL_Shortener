import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:80";

// ---------- Tier 1: 50 concurrent users ----------
// Run: k6 run --env SCENARIO=tier1 loadtests/k6_test.js
//
// ---------- Tier 2: 200 concurrent users ----------
// Run: k6 run --env SCENARIO=tier2 loadtests/k6_test.js

const scenarios = {
  tier1: {
    executor: "constant-vus",
    vus: 50,
    duration: "30s",
  },
  tier2: {
    executor: "ramping-vus",
    startVUs: 0,
    stages: [
      { duration: "30s", target: 200 },
      { duration: "1m", target: 200 },
      { duration: "15s", target: 0 },
    ],
  },
};

const chosen = __ENV.SCENARIO || "tier1";

export const options = {
  scenarios: {
    load: scenarios[chosen],
  },
  thresholds: {
    http_req_duration: ["p(95)<3000"],
    http_req_failed: ["rate<0.05"],
  },
};

export default function () {
  // Health check
  const healthRes = http.get(`${BASE_URL}/health`);
  check(healthRes, {
    "health status 200": (r) => r.status === 200,
    "health body ok": (r) => r.json("status") === "ok",
  });

  // List users
  const usersRes = http.get(`${BASE_URL}/users?page=1&per_page=10`);
  check(usersRes, {
    "users status 200": (r) => r.status === 200,
  });

  // List URLs
  const urlsRes = http.get(`${BASE_URL}/urls`);
  check(urlsRes, {
    "urls status 200": (r) => r.status === 200,
  });

  // Create a user (write pressure)
  const tag = `k6_${__VU}_${__ITER}`;
  const createRes = http.post(
    `${BASE_URL}/users`,
    JSON.stringify({ username: tag, email: `${tag}@loadtest.io` }),
    { headers: { "Content-Type": "application/json" } }
  );
  check(createRes, {
    "create user 201 or 409": (r) => r.status === 201 || r.status === 409,
  });

  sleep(0.3);
}
