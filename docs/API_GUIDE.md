# IronPanel API Guide / راهنمای API آیرون‌پنل

> Version: **13.2**  
> Repository: `https://github.com/Unknown-sir/ironpanel`  
> Support / License: `https://t.me/unknown_eng`

---

## 🇮🇷 فارسی

این فایل راهنمای کامل استفاده از API های IronPanel است. API برای اتصال سایت فروش، ربات تلگرام، سیستم نمایندگی، اتوماسیون ساخت کاربر، تمدید سرویس، مشاهده مصرف، مانیتورینگ و Health Check استفاده می‌شود.

IronPanel دو نوع API دارد:

| نسخه | مسیر پایه | روش احراز هویت | کاربرد |
|---|---|---|---|
| API v1 | `/api` | `X-API-KEY` | سازگاری با نسخه‌های قبلی و عملیات پایه |
| API v2 | `/api/v2` | `Bearer Token` یا `X-API-TOKEN` | API جدیدتر برای سایت فروش، ربات، مانیتورینگ، فاکتور و Health |

### Base URL

```text
http://YOUR_PANEL_DOMAIN_OR_IP
```

نمونه:

```text
http://example.com
http://1.2.3.4
```

---

## 1. احراز هویت

### 1.1 API v1 با `X-API-KEY`

کلید API مدیر از داخل پنل یا فایل تنظیمات ساخته می‌شود.

```bash
curl -H "X-API-KEY: YOUR_API_KEY" \
  http://YOUR_PANEL/api/status
```

### 1.2 API v2 با `X-API-TOKEN`

توکن API v2 از بخش **Security & API → API Tokens** ساخته می‌شود.

```bash
curl -H "X-API-TOKEN: YOUR_API_TOKEN" \
  http://YOUR_PANEL/api/v2/users
```

### 1.3 API v2 با Bearer Token

```bash
curl -H "Authorization: Bearer YOUR_API_TOKEN" \
  http://YOUR_PANEL/api/v2/monitoring
```

### 1.4 دریافت توکن با یوزر/پسورد مدیر

```http
POST /api/v2/auth/token
Content-Type: application/json
```

Request:

```json
{
  "username": "admin",
  "password": "admin_password"
}
```

Response:

```json
{
  "success": true,
  "token": "TOKEN_VALUE",
  "token_type": "Bearer"
}
```

---

## 2. استاندارد پاسخ‌ها

### پاسخ موفق

```json
{
  "success": true,
  "data": {}
}
```

### پاسخ خطا

```json
{
  "success": false,
  "error": "invalid token"
}
```

### کدهای رایج HTTP

| کد | معنی |
|---|---|
| 200 | موفق |
| 201 | ساخته شد |
| 400 | درخواست نامعتبر |
| 401 | احراز هویت نامعتبر |
| 403 | دسترسی غیرمجاز |
| 404 | پیدا نشد |
| 500 | خطای داخلی سرور |

---

## 3. API v1 Endpoints

### 3.1 وضعیت پنل و سرویس‌ها

```http
GET /api/status
X-API-KEY: YOUR_API_KEY
```

Response:

```json
{
  "success": true,
  "message": "Ironpanel is online",
  "services": {
    "openvpn": "active",
    "wg-quick@wg0": "active",
    "ocserv": "active",
    "strongswan-starter": "active",
    "xl2tpd": "active"
  },
  "timestamp": "2026-07-06T00:00:00"
}
```

### 3.2 لیست کاربران

```http
GET /api/users/list_all
X-API-KEY: YOUR_API_KEY
```

Response:

```json
{
  "success": true,
  "users": [
    {
      "id": 1,
      "username": "ali",
      "enabled": true,
      "access_ok": true,
      "access_reason": "ok",
      "protocols": ["openvpn", "wireguard", "ocserv", "l2tp"],
      "data_limit_mb": 0,
      "used_total_mb": 120,
      "connection_limit": 1,
      "expires_at": null,
      "subscription_url": "/s/TOKEN"
    }
  ]
}
```

> نکته: مقدار `0` برای حجم و تاریخ به معنی نامحدود است. در خروجی تاریخ نامحدود به صورت `null` نمایش داده می‌شود.

### 3.3 ساخت کاربر

```http
POST /api/users/create
X-API-KEY: YOUR_API_KEY
Content-Type: application/json
```

Request:

```json
{
  "username": "ali",
  "password": "StrongPassword",
  "days": 30,
  "data_limit_mb": 10240,
  "connection_limit": 2,
  "protocols": ["openvpn", "wireguard", "ocserv", "l2tp"],
  "l2tp_password": "optional_l2tp_password",
  "cisco_password": "optional_ocserv_password"
}
```

Response:

```json
{
  "success": true,
  "user": {
    "id": 1,
    "username": "ali"
  },
  "password": "StrongPassword"
}
```

### 3.4 فعال/غیرفعال کردن کاربر

```http
POST /api/users/{user_id}/toggle
X-API-KEY: YOUR_API_KEY
```

### 3.5 حذف کاربر

```http
DELETE /api/users/{user_id}
X-API-KEY: YOUR_API_KEY
```

Response:

```json
{
  "success": true,
  "deleted": "ali"
}
```

### 3.6 لیست سرورها / نودها

```http
GET /api/nodes
X-API-KEY: YOUR_API_KEY
```

### 3.7 ساخت تیکت

```http
POST /api/tickets
X-API-KEY: YOUR_API_KEY
Content-Type: application/json
```

Request:

```json
{
  "subject": "Connection problem",
  "body": "User cannot connect to WireGuard",
  "priority": "normal",
  "department": "support",
  "user_id": 1
}
```

### 3.8 لاگ‌های فعالیت

```http
GET /api/logs
X-API-KEY: YOUR_API_KEY
```

---

## 4. API v2 Endpoints

### 4.1 OpenAPI Schema

```http
GET /api/v2/openapi.json
```

### 4.2 مانیتورینگ سرور

```http
GET /api/v2/monitoring
Authorization: Bearer YOUR_API_TOKEN
```

Response:

```json
{
  "success": true,
  "metrics": {
    "cpu": 12.5,
    "ram": 48.2,
    "swap": 0,
    "disk": 35.1,
    "uptime": "10 days"
  },
  "services": {
    "openvpn": "active",
    "wg-quick@wg0": "active",
    "ocserv": "active"
  }
}
```

### 4.3 نشست‌های آنلاین

```http
GET /api/v2/sessions
Authorization: Bearer YOUR_API_TOKEN
```

Response:

```json
{
  "success": true,
  "sessions": [
    {
      "id": 1,
      "username": "ali",
      "protocol": "wireguard",
      "remote_ip": "8.8.8.8",
      "country": "Germany",
      "last_seen": "2026-07-06T00:00:00"
    }
  ]
}
```

### 4.4 لیست کاربران

```http
GET /api/v2/users
Authorization: Bearer YOUR_API_TOKEN
```

### 4.5 ساخت کاربر

```http
POST /api/v2/users
Authorization: Bearer YOUR_API_TOKEN
Content-Type: application/json
```

Request:

```json
{
  "username": "reza",
  "password": "StrongPassword",
  "days": 0,
  "data_limit_mb": 0,
  "connection_limit": 3,
  "protocols": ["openvpn", "wireguard", "ocserv", "l2tp"]
}
```

> `days: 0` یعنی تاریخ انقضا نامحدود.  
> `data_limit_mb: 0` یعنی حجم نامحدود.

Response:

```json
{
  "success": true,
  "user": {
    "id": 2,
    "username": "reza",
    "expires_at": null,
    "data_limit_mb": 0
  },
  "password": "StrongPassword"
}
```

### 4.6 ویرایش کاربر

```http
PATCH /api/v2/users/{user_id}
Authorization: Bearer YOUR_API_TOKEN
Content-Type: application/json
```

Request examples:

```json
{
  "enabled": true,
  "days": 60,
  "data_limit_mb": 20480,
  "connection_limit": 2,
  "allowed_devices": 2,
  "password": "NewPassword"
}
```

نامحدود کردن تاریخ و حجم:

```json
{
  "days": 0,
  "data_limit_mb": 0
}
```

### 4.7 حذف کاربر

```http
DELETE /api/v2/users/{user_id}
Authorization: Bearer YOUR_API_TOKEN
```

### 4.8 لیست نودها

```http
GET /api/v2/nodes
Authorization: Bearer YOUR_API_TOKEN
```

### 4.9 پلن‌ها

```http
GET /api/v2/plans
Authorization: Bearer YOUR_API_TOKEN
```

Response:

```json
{
  "success": true,
  "plans": [
    {
      "id": 1,
      "name": "Monthly 100GB",
      "days": 30,
      "traffic_gb": 100,
      "price": 10,
      "currency": "USD",
      "protocols": "openvpn,wireguard,ocserv,l2tp"
    }
  ]
}
```

### 4.10 ساخت فاکتور

```http
POST /api/v2/invoices
Authorization: Bearer YOUR_API_TOKEN
Content-Type: application/json
```

Request:

```json
{
  "user_id": 1,
  "amount": 10,
  "currency": "USD",
  "description": "Monthly renewal"
}
```

Response:

```json
{
  "success": true,
  "invoice_id": 1001,
  "status": "unpaid"
}
```

### 4.11 جزئیات Health Check / Repair

```http
GET /api/v2/health/details
Authorization: Bearer YOUR_API_TOKEN
```

Response:

```json
{
  "success": true,
  "health": {
    "openvpn": {
      "ok": true,
      "status": "active",
      "error": ""
    },
    "ocserv": {
      "ok": false,
      "status": "failed",
      "error": "journalctl output here"
    }
  }
}
```

در پنل گرافیکی هم اگر هر بخش خطا داشته باشد، کنار همان بخش دکمه **مشاهده خطا** نمایش داده می‌شود.

---

## 5. نمونه اتصال با Python

```python
import requests

BASE_URL = "http://YOUR_PANEL"
TOKEN = "YOUR_API_TOKEN"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

payload = {
    "username": "api_user",
    "password": "StrongPassword",
    "days": 30,
    "data_limit_mb": 10240,
    "protocols": ["openvpn", "wireguard", "ocserv", "l2tp"],
}

r = requests.post(f"{BASE_URL}/api/v2/users", json=payload, headers=headers, timeout=30)
print(r.status_code)
print(r.json())
```

---

## 6. نمونه اتصال با JavaScript / Node.js

```js
const BASE_URL = "http://YOUR_PANEL";
const TOKEN = "YOUR_API_TOKEN";

async function createUser() {
  const res = await fetch(`${BASE_URL}/api/v2/users`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${TOKEN}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      username: "api_user",
      password: "StrongPassword",
      days: 30,
      data_limit_mb: 10240,
      protocols: ["openvpn", "wireguard", "ocserv", "l2tp"]
    })
  });

  console.log(await res.json());
}

createUser();
```

---

## 7. نکات امنیتی API

- همیشه API را پشت HTTPS استفاده کنید.
- برای هر سیستم خارجی یک API Token جدا بسازید.
- Token سایت فروش، ربات تلگرام و سیستم نماینده‌ها را یکی نکنید.
- در صورت لو رفتن Token، سریعاً آن را غیرفعال کنید.
- از IP Whitelist برای API استفاده کنید.
- سطح دسترسی توکن‌ها را محدود کنید.
- لاگ‌های API را مرتب بررسی کنید.

---

# 🇺🇸 English

This document explains how to use IronPanel APIs for external websites, Telegram bots, reseller systems, automation, user provisioning, renewals, monitoring, billing, and Health Check integrations.

IronPanel provides two API layers:

| Version | Base Path | Authentication | Purpose |
|---|---|---|---|
| API v1 | `/api` | `X-API-KEY` | Backward-compatible basic operations |
| API v2 | `/api/v2` | `Bearer Token` or `X-API-TOKEN` | Modern API for billing, bots, monitoring, users, and health |

## Base URL

```text
http://YOUR_PANEL_DOMAIN_OR_IP
```

---

## Authentication

### API v1

```bash
curl -H "X-API-KEY: YOUR_API_KEY" \
  http://YOUR_PANEL/api/status
```

### API v2

```bash
curl -H "Authorization: Bearer YOUR_API_TOKEN" \
  http://YOUR_PANEL/api/v2/users
```

or:

```bash
curl -H "X-API-TOKEN: YOUR_API_TOKEN" \
  http://YOUR_PANEL/api/v2/users
```

### Issue a token using admin credentials

```http
POST /api/v2/auth/token
Content-Type: application/json
```

Request:

```json
{
  "username": "admin",
  "password": "admin_password"
}
```

Response:

```json
{
  "success": true,
  "token": "TOKEN_VALUE",
  "token_type": "Bearer"
}
```

---

## API v1 Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/status` | Panel and VPN service status |
| GET | `/api/users/list_all` | List users |
| POST | `/api/users/create` | Create user |
| POST | `/api/users/{user_id}/toggle` | Enable/disable user |
| DELETE | `/api/users/{user_id}` | Delete user |
| GET | `/api/nodes` | List nodes |
| POST | `/api/tickets` | Create ticket |
| GET | `/api/logs` | Activity logs |

## API v2 Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v2/openapi.json` | OpenAPI schema |
| POST | `/api/v2/auth/token` | Issue token |
| GET | `/api/v2/monitoring` | Realtime server metrics and services |
| GET | `/api/v2/sessions` | Online sessions |
| GET | `/api/v2/users` | List users |
| POST | `/api/v2/users` | Create user |
| PATCH | `/api/v2/users/{user_id}` | Edit user |
| DELETE | `/api/v2/users/{user_id}` | Delete user |
| GET | `/api/v2/nodes` | List nodes |
| GET | `/api/v2/plans` | List active service plans |
| POST | `/api/v2/invoices` | Create invoice |
| GET | `/api/v2/health/details` | Detailed Health Check result and errors |

---

## Create User Example

```bash
curl -X POST http://YOUR_PANEL/api/v2/users \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john",
    "password": "StrongPassword",
    "days": 30,
    "data_limit_mb": 10240,
    "connection_limit": 2,
    "protocols": ["openvpn", "wireguard", "ocserv", "l2tp"]
  }'
```

## Create Unlimited User

```bash
curl -X POST http://YOUR_PANEL/api/v2/users \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "unlimited_user",
    "password": "StrongPassword",
    "days": 0,
    "data_limit_mb": 0,
    "protocols": ["openvpn", "wireguard", "ocserv", "l2tp"]
  }'
```

`days: 0` means unlimited expiration.  
`data_limit_mb: 0` means unlimited traffic.

## Edit User Example

```bash
curl -X PATCH http://YOUR_PANEL/api/v2/users/1 \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "days": 60,
    "data_limit_mb": 20480,
    "connection_limit": 3,
    "enabled": true
  }'
```

## Health Details Example

```bash
curl http://YOUR_PANEL/api/v2/health/details \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

---

## Security Recommendations

- Use HTTPS for all API calls.
- Create separate tokens for each integration.
- Rotate tokens periodically.
- Disable leaked tokens immediately.
- Use API IP whitelist where possible.
- Review API and admin activity logs regularly.
- Never publish API tokens in GitHub repositories.

---

## Support / License

For license purchase, renewal, or API support, contact:

Telegram: `https://t.me/unknown_eng`
