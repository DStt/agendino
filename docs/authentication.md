# Authentication

Optional single-user login system with session cookies and IP banning.

![Authentication](screenshots/authentication.png)

---

## Overview

Authentication is **enabled by default** (`AUTH_ENABLED=true` in code). Set `AUTH_ENABLED=false` to disable it. When enabled, all routes require a valid session cookie, and the first login creates the permanent account.

## Enabling Authentication

Set `AUTH_ENABLED=true` in your `.env` file:

```env
AUTH_ENABLED=true
```

## How It Works

### First Login (Account Creation)

1. Navigate to the dashboard - you'll be redirected to the **login page**.
2. Enter your desired **username** and **password**.
3. These credentials are stored as the permanent account:
   - Password is hashed with **PBKDF2-SHA256** (200,000 iterations).
   - Credentials are saved in `settings/auth.json`.

> **Important:** There is no built-in password reset. Choose your credentials carefully. To start over, delete `settings/auth.json`.

### Subsequent Logins

- Credentials are verified against the stored hash.
- On success, a session cookie (`agendino_session`) is issued, valid for **7 days**.
- Browser requests without a valid session are redirected to the login page.
- API requests without a valid session receive a `401` response.

### Failed Login Protection

- A failed login attempt **permanently bans** the client's IP address (by design).
- All future requests from that IP are blocked with `403 Forbidden`.
- Banned IPs are stored in `settings/banned_ips.json`.
- Set `TRUST_PROXY_HEADERS=true` when running behind a trusted reverse proxy so the ban
  applies to the real client IP (from `X-Forwarded-For` / `X-Real-IP`) rather than the proxy.
  Leave it `false` otherwise, or clients can spoof their address.
- Because a ban is permanent, never enable it on an address you do not control, and make sure
  the forwarded IP is correct before exposing the app publicly.

### Unbanning an IP

Edit or delete `settings/banned_ips.json` to remove a banned IP address.

### Logout

- Destroys the session server-side.
- Clears the session cookie.

## Security Notes

| Aspect | Implementation |
|--------|---------------|
| Password hashing | PBKDF2-SHA256, 200K iterations |
| Session storage | Server-side, cookie-based |
| Session expiry | 7 days |
| IP banning | Permanent on first failed attempt |
| Client IP | Socket address, or forwarded IP when `TRUST_PROXY_HEADERS=true` |
| Credential storage | `settings/auth.json` |

---

**Related:** [Getting Started](getting-started.md) · [AI Providers](ai-providers.md)
