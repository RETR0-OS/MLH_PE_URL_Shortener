# Automated Submission Tests

> By Hugo Castro · Apr 3, 2026

Once you send your submission for evaluation, your app is tested against a suite of automated tests to ensure it complies with the features of a basic URL shortener. These tests **do not replace** tests your team writes, but they can help you work towards the reliability quest.

> **Note:** Some tests have hidden input/output. If your app handles edge cases well, you may pass them. Hints will be shared as the hackathon progresses.

---

## 1. Health

Ensure the API is running and ready to accept requests.

| Detail | Value |
|---|---|
| **Endpoint** | `GET /health` |
| **Input** | None |
| **Expected Status** | `200 OK` |

**Response Format:**

```json
{
  "status": "ok"
}
```

---

## 2. Users

### 2.1 Bulk Load Users (CSV Import)

| Detail | Value |
|---|---|
| **Endpoint** | `POST /users/bulk` |
| **Input** | `multipart/form-data` with a `file` field containing `users.csv` |
| **Expected Status** | `200 OK` or `201 Created` |

**Response Format** — must indicate the number of imported users. Acceptable formats:

```json
{ "count": 2 }
```

```json
{ "imported": 2 }
```

Or simply returning an array of imported objects.

### 2.2 List Users

| Detail | Value |
|---|---|
| **Endpoint** | `GET /users` |
| **Input** | None (query params `?page=x&per_page=y` should optionally paginate) |
| **Expected Status** | `200 OK` |

**Response Format** — a JSON array of users (or a paginated envelope like `{"users": [...]}`):

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

### 2.3 Get User by ID

| Detail | Value |
|---|---|
| **Endpoint** | `GET /users/<id>` |
| **Input** | None |
| **Expected Status** | `200 OK` |

**Response Format:**

```json
{
  "id": 1,
  "username": "silvertrail15",
  "email": "silvertrail15@hackstack.io",
  "created_at": "2025-09-19T22:25:05"
}
```

### 2.4 Create User

| Detail | Value |
|---|---|
| **Endpoint** | `POST /users` |
| **Input** | `{"username": "testuser", "email": "testuser@example.com"}` |
| **Expected Status** | `201 Created` |

Must reject invalid data schemas (e.g. integer for username) and return `400 Bad Request` or `422 Unprocessable Entity` with an error dictionary.

**Response Format:**

```json
{
  "id": 3,
  "username": "testuser",
  "email": "testuser@example.com",
  "created_at": "2026-04-03T12:00:00"
}
```

### 2.5 Update User

| Detail | Value |
|---|---|
| **Endpoint** | `PUT /users/<id>` |
| **Input** | `{"username": "updated_username"}` |
| **Expected Status** | `200 OK` |

**Response Format:**

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

### 3.1 Create URL

| Detail | Value |
|---|---|
| **Endpoint** | `POST /urls` |
| **Input** | `{"user_id": 1, "original_url": "https://example.com/test", "title": "Test URL"}` |
| **Expected Status** | `201 Created` |

Should handle a missing user gracefully and throw errors for invalid constraints.

**Response Format:**

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

### 3.2 List URLs

| Detail | Value |
|---|---|
| **Endpoint** | `GET /urls` |
| **Input** | None (should accept filtering queries like `?user_id=1`) |
| **Expected Status** | `200 OK` |

**Response Format:**

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

### 3.3 Get URL by ID

| Detail | Value |
|---|---|
| **Endpoint** | `GET /urls/<id>` |
| **Input** | None |
| **Expected Status** | `200 OK` |

**Response Format:**

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

### 3.4 Update URL Details

| Detail | Value |
|---|---|
| **Endpoint** | `PUT /urls/<id>` |
| **Input** | `{"title": "Updated Title", "is_active": false}` |
| **Expected Status** | `200 OK` |

**Response Format:**

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

### 4.1 List Events

| Detail | Value |
|---|---|
| **Endpoint** | `GET /events` |
| **Input** | None |
| **Expected Status** | `200 OK` |

**Response Format:**

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

## Quick Checklist

- [ ] `GET /health` returns `{"status": "ok"}` with 200
- [ ] `POST /users/bulk` imports CSV and returns count
- [ ] `GET /users` lists all users (with optional pagination)
- [ ] `GET /users/<id>` returns a single user
- [ ] `POST /users` creates a user and validates input (400/422 on bad data)
- [ ] `PUT /users/<id>` updates a user
- [ ] `POST /urls` creates a short URL with a generated `short_code`
- [ ] `GET /urls` lists URLs (with optional `?user_id=` filter)
- [ ] `GET /urls/<id>` returns a single URL
- [ ] `PUT /urls/<id>` updates URL details
- [ ] `GET /events` lists analytics events
- [ ] Edge cases are handled gracefully (hidden tests)
