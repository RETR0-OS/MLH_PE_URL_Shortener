# MLH PE Hackathon — Automated Test Specification

> **Source:** Hugo Castro · Apr 3, 2026, 5:58 PM MST

Once you send your submission for evaluation, your app is tested against these tests to ensure it complies with the features of a basic URL shortener. This does **not** replace your own team's tests, but helps you work towards the **reliability quest**.

> **Note:** Some tests have hidden input/output. If your app handles edge cases correctly, you may pass them. Hints will be shared as the hackathon progresses.

---

## 1. Health

Ensure your API is running and ready to accept requests.

| Field | Value |
|-------|-------|
| Endpoint | `GET /health` |
| Input | None |
| Expected Response | `200 OK` |

```json
{
  "status": "ok"
}
```

---

## 2. Users

### Bulk Load Users (CSV Import)

| Field | Value |
|-------|-------|
| Endpoint | `POST /users/bulk` |
| Input | `multipart/form-data` with a `file` field containing `users.csv` |
| Expected Response | `200 OK` or `201 Created` |

Response must indicate the number of imported users. Acceptable formats:

```json
{ "count": 2 }
```
```json
{ "imported": 2 }
```
```json
[{ ... }, { ... }]
```

---

### List Users

| Field | Value |
|-------|-------|
| Endpoint | `GET /users` |
| Input | None (supports optional `?page=x&per_page=y` pagination) |
| Expected Response | `200 OK` |

```json
[
  {
    "id": 1,
    "username": "silvertrail15",
    "email": "silvertrail15@hackstack.io",
    "created_at": "2025-09-19T22:25:05"
  },
  {
    "id": 2,
    "username": "urbancanyon36",
    "email": "urbancanyon36@opswise.net",
    "created_at": "2024-04-09T02:51:03"
  }
]
```

A paginated envelope (`{"users": [...]}`) is also acceptable.

---

### Get User by ID

| Field | Value |
|-------|-------|
| Endpoint | `GET /users/<id>` |
| Input | None |
| Expected Response | `200 OK` |

```json
{
  "id": 1,
  "username": "silvertrail15",
  "email": "silvertrail15@hackstack.io",
  "created_at": "2025-09-19T22:25:05"
}
```

---

### Create User

| Field | Value |
|-------|-------|
| Endpoint | `POST /users` |
| Expected Response | `201 Created` |
| Validation errors | `400 Bad Request` or `422 Unprocessable Entity` with an error dictionary |

**Request:**
```json
{
  "username": "testuser",
  "email": "testuser@example.com"
}
```

**Response:**
```json
{
  "id": 3,
  "username": "testuser",
  "email": "testuser@example.com",
  "created_at": "2026-04-03T12:00:00"
}
```

> Invalid schemas (e.g. integer for `username`) must be rejected with a `400` or `422`.

---

### Update User

| Field | Value |
|-------|-------|
| Endpoint | `PUT /users/<id>` |
| Expected Response | `200 OK` |

**Request:**
```json
{
  "username": "updated_username"
}
```

**Response:**
```json
{
  "id": 1,
  "username": "updated_username",
  "email": "silvertrail15@hackstack.io",
  "created_at": "2025-09-19T22:25:05"
}
```

---

## 3. URLs

### Create URL

| Field | Value |
|-------|-------|
| Endpoint | `POST /urls` |
| Expected Response | `201 Created` |

**Request:**
```json
{
  "user_id": 1,
  "original_url": "https://example.com/test",
  "title": "Test URL"
}
```

**Response:**
```json
{
  "id": 3,
  "user_id": 1,
  "short_code": "k8Jd9s",
  "original_url": "https://example.com/test",
  "title": "Test URL",
  "is_active": true,
  "created_at": "2026-04-03T12:00:00",
  "updated_at": "2026-04-03T12:00:00"
}
```

> Must handle missing `user_id` gracefully and throw errors for invalid constraints.

---

### List URLs

| Field | Value |
|-------|-------|
| Endpoint | `GET /urls` |
| Input | None (supports optional `?user_id=1` filter) |
| Expected Response | `200 OK` |

```json
[
  {
    "id": 1,
    "user_id": 1,
    "short_code": "ALQRog",
    "original_url": "https://opswise.net/harbor/journey/1",
    "title": "Service guide lagoon",
    "is_active": true,
    "created_at": "2025-06-04T00:07:00",
    "updated_at": "2025-11-19T03:17:29"
  }
]
```

---

### Get URL by ID

| Field | Value |
|-------|-------|
| Endpoint | `GET /urls/<id>` |
| Input | None |
| Expected Response | `200 OK` |

```json
{
  "id": 1,
  "user_id": 1,
  "short_code": "ALQRog",
  "original_url": "https://opswise.net/harbor/journey/1",
  "title": "Service guide lagoon",
  "is_active": true,
  "created_at": "2025-06-04T00:07:00",
  "updated_at": "2025-11-19T03:17:29"
}
```

---

### Update URL Details

| Field | Value |
|-------|-------|
| Endpoint | `PUT /urls/<id>` |
| Expected Response | `200 OK` |

**Request:**
```json
{
  "title": "Updated Title",
  "is_active": false
}
```

**Response:**
```json
{
  "id": 1,
  "user_id": 1,
  "short_code": "ALQRog",
  "original_url": "https://opswise.net/harbor/journey/1",
  "title": "Updated Title",
  "is_active": false,
  "created_at": "2025-06-04T00:07:00",
  "updated_at": "2026-04-03T12:00:00"
}
```

---

## 4. Events / Analytics

### List Events

| Field | Value |
|-------|-------|
| Endpoint | `GET /events` |
| Input | None |
| Expected Response | `200 OK` |

```json
[
  {
    "id": 1,
    "url_id": 1,
    "user_id": 1,
    "event_type": "created",
    "timestamp": "2025-06-04T00:07:00",
    "details": {
      "short_code": "ALQRog",
      "original_url": "https://opswise.net/harbor/journey/1"
    }
  }
]
```

---

## Summary Table

| # | Category | Endpoint | Method | Status |
|---|----------|----------|--------|--------|
| 1 | Health | `/health` | GET | `200` |
| 2 | Users | `/users/bulk` | POST | `200/201` |
| 3 | Users | `/users` | GET | `200` |
| 4 | Users | `/users/<id>` | GET | `200` |
| 5 | Users | `/users` | POST | `201` |
| 6 | Users | `/users/<id>` | PUT | `200` |
| 7 | URLs | `/urls` | POST | `201` |
| 8 | URLs | `/urls` | GET | `200` |
| 9 | URLs | `/urls/<id>` | GET | `200` |
| 10 | URLs | `/urls/<id>` | PUT | `200` |
| 11 | Events | `/events` | GET | `200` |
