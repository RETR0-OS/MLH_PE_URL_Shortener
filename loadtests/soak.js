import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 50,
  duration: "5m",
  thresholds: {
    http_req_duration: ["p(95)<2000"],
    http_req_failed: ["rate<0.01"],
  },
};

const BASE = __ENV.BASE_URL || "http://localhost";
const HEADERS = { headers: { "Content-Type": "application/json" } };

export function setup() {
  const userIds = [];
  for (let i = 0; i < 20; i++) {
    const tag = `soak_${Date.now()}_${i}`;
    const res = http.post(
      `${BASE}/users`,
      JSON.stringify({ username: tag, email: `${tag}@loadtest.local` }),
      HEADERS
    );
    if (res.status === 201) {
      userIds.push(JSON.parse(res.body).id);
    }
  }
  if (userIds.length === 0) {
    throw new Error("setup failed: could not create any test users");
  }
  return { userIds };
}

export default function (data) {
  const userId = data.userIds[Math.floor(Math.random() * data.userIds.length)];

  let res = http.get(`${BASE}/health/ready`);
  check(res, { "ready": (r) => r.status === 200 });

  res = http.get(`${BASE}/users?page=1&per_page=10`);
  check(res, { "users": (r) => r.status === 200 });

  const payload = JSON.stringify({
    user_id: userId,
    original_url: `https://example.com/soak/${Date.now()}/${__VU}/${__ITER}`,
    title: "Soak test",
  });
  res = http.post(`${BASE}/urls`, payload, HEADERS);
  check(res, { "create": (r) => r.status === 201 });

  sleep(1);
}
