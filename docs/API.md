# API

All routes live under **`/api/v1`**, send and receive JSON, and need a **Firebase token** —
except the public Act, stats and sitemap routes, and the Razorpay webhook.

There are no `/auth/signup` or `/auth/login` routes: Firebase handles those in the browser.

## Streaming contract

Chat answers stream over **server-sent events (SSE)**:

1. Text arrives **word by word**.
2. Then **one** `citations` event, after verification — the full checked set, each with a
   tick or a warning mark, a link to `pdf_url` or `source_url`, the data-as-of date, the
   CC BY credit and the not-legal-advice notice.
3. Then a `done` event.

A user must **never** see a citation appear and then vanish. Nothing citation-shaped goes
out before step 2.

**As built (`api/schemas.py`):** `citations` carries `removed_count`, `data_as_of`, `credit`
and `notice`. A refusal is a single `done` with `refused: true`, a `reason`
(`out_of_scope` or `not_found`) and a `message_key`. A usage limit is a single `error` event
with code `quota_exceeded`. A citation's `status` is only `verified` or `partly`; the web
shows a tick for `verified` alone. Routes not yet built answer `501 feature_disabled` after
the login check. Judgment titles are never sent (they are party names).

## Routes

| Method and path | Purpose |
|---|---|
| `GET /me` | Profile, plan, answers left this month |
| `GET /search` | Direct search with filters, no AI answer (cheap) |
| `GET /cases/{id}` | Full judgment with paragraph anchors; backs every citation link |
| `GET /acts/{act}/sections/{n}` | One section. In-force status shown **only** when `act_status` is filled, otherwise labelled "in-force status not checked". **Public, no login** |
| `POST /conversations` | Start a research or document conversation |
| `GET /conversations` | List, with cursor pagination |
| `GET /conversations/{id}` | Full history with sources |
| `POST /conversations/{id}/messages` | Ask a question; streams the answer |
| `POST /documents/uploads` | Get a pre-signed upload link and a document ID |
| `GET /documents/{id}` | Upload status |
| `DELETE /documents/{id}` | **Hard delete**: file, text and vectors |
| `POST /feedback` | Thumbs up/down plus a comment |
| `POST /billing/webhook` | Razorpay events (**signature checked**, no Firebase token) |
| `GET /stats` | Public outcome counts by court, year and outcome label. **No login.** Supreme Court only until Phase 2 |
| `GET /sitemap.xml` | Every public Act and stats page, for Google (served by the website) |
| `POST /organisations` | Create a Chambers organisation (minimum 3 seats, one bill) |
| `POST`, `DELETE /organisations/{id}/members` | Invite or remove a member |
| `GET`, `POST /me/consents` | See or withdraw consent (DPDP) |
| `DELETE /me` | Delete the account and all its data, including the Firebase user; cancels the Razorpay subscription. Payment and invoice records kept as the law requires (Needs counsel) (DPDP) |
| `GET /me/export` | Download a copy of account data, chats and upload list (DPDP) |

## Rules every route follows

- **One error format.** Nothing else.
  ```json
  { "error": { "code": "quota_exceeded", "message": "...", "request_id": "..." } }
  ```
  The `code` is machine-readable so the website can show the right screen.
- **A request ID on every response**, also written into every log line and Langfuse trace,
  so one ID finds everything about a complaint.
- **Cursor pagination** on every list.
- **Limits in headers**: remaining answers and rate limits come back as response headers.
- **The usage check runs before any AI call**, inside the AI gateway module, and stops with
  a clear message at the limit instead of silently giving worse answers.
- Cache hits are free and do not count against the limit.

## Audit log

Logins, uploads, deletions, exports and any admin view of a user's data each write one row
to `audit_log` with the user, action, target, IP and request ID. **It never holds document
text.** Retention needs a decision with counsel.
