# Error Handling

All error responses from the API are JSON objects. The server never returns HTML error pages or raw stack traces.

## Error Response Format

```json
{
  "error": "Human-readable error message",
  "details": { "field_name": "Field-specific error" }
}
```

The `details` key is optional and only present for validation errors.

## Status Codes

| Code | Meaning | When |
|------|---------|------|
| 200  | OK | Successful read or update |
| 201  | Created | Successful `POST /users` or `POST /urls` |
| 400  | Bad Request | Malformed JSON, missing required fields, structural errors (e.g., `user_id` is a string instead of integer) |
| 404  | Not Found | Resource ID does not exist, or unknown route |
| 405  | Method Not Allowed | HTTP method not supported on the endpoint |
| 422  | Unprocessable Entity | Well-formed request but fails business rules (e.g., duplicate username, duplicate email) |
| 500  | Internal Server Error | Unexpected server failure (details logged server-side, generic message returned to client) |

## Validation Rules

### Users
- `username`: required, must be a non-empty string (rejects integers, empty strings, whitespace-only)
- `email`: required, must match a valid email pattern
- Both `username` and `email` must be unique across all users

### URLs
- `user_id`: required, must be an integer, must reference an existing user
- `original_url`: required, must be a non-empty string
- `title`: required, must be a string

### Bulk Import
- Requires a `file` field in multipart form data
- CSV must have headers: `id,username,email,created_at`
- Duplicate IDs are silently skipped (`ON CONFLICT IGNORE`)

## Global Error Handlers

The app registers Flask `errorhandler` functions for 404, 405, and 500. These ensure:

1. All errors return `application/json` content type
2. No stack traces leak to the client
3. Unhandled exceptions are caught by the 500 handler
