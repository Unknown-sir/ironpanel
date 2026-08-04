# v19.10.12 Bulk Range Users

- Added bulk user creation from Users page.
- Admin enters username base, start/end number range, random password length and charset mode.
- Created usernames are base + number; passwords are generated randomly.
- Bulk users are single-connection by default, with optional IP limit and selected protocols.
- Traffic 0 means unlimited; days 0 means unlimited.
