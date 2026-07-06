# Ironpanel API

All API requests require:

```http
X-API-KEY: your_key
Content-Type: application/json
```

## GET /api/v1/status
Returns panel and service status.

## GET /api/v1/users/list_all
Returns users. Main admin sees all users; sub-admin sees owned users.

## POST /api/v1/users/create
```json
{
  "username": "ali",
  "password": "secret",
  "days": 30,
  "data_limit_mb": 10240,
  "connection_limit": 2,
  "protocols": ["openvpn", "ocserv", "l2tp", "wireguard"]
}
```

## POST /api/v1/users/{id}/toggle
Enable/disable user.

## GET /api/v1/nodes
List nodes.

## POST /api/v1/tickets
Create ticket.

## GET /api/v1/logs
Read recent logs.
