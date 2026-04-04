import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "30s", target: 100 },
    { duration: "30s", target: 500 },
    { duration: "60s", target: 500 },
    { duration: "10s", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.10"],
  },
};

const BASE = __ENV.BASE_URL || "http://localhost";
const HEADERS = { headers: { "Content-Type": "application/json" } };

export function setup() {
  const userIds = [];
  for (let i = 0; i < 50; i++) {
    const tag = `stress_${Date.now()}_${i}`;
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

  let res = http.get(`${BASE}/health`);
  check(res, { "health ok": (r) => r.status === 200 });

  res = http.get(`${BASE}/urls?user_id=${userId}`);
  check(res, { "urls filtered": (r) => r.status === 200 });

  const payload = JSON.stringify({
    user_id: userId,
    original_url: `https://example.com/stress/${Date.now()}/${__VU}/${__ITER}`,
    title: "Stress test URL",
  });
  res = http.post(`${BASE}/urls`, payload, HEADERS);
  check(res, { "create url": (r) => r.status === 201 });

  if (res.status === 201) {
    const urlId = JSON.parse(res.body).id;
    res = http.get(`${BASE}/urls/${urlId}`);
    check(res, { "get url cached": (r) => r.status === 200 });

    res = http.get(`${BASE}/urls/${urlId}`);
    check(res, { "get url cache hit": (r) => r.status === 200 });
  }

  sleep(0.3);
}
