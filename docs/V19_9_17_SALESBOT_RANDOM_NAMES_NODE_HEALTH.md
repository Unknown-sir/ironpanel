# IronPanel v19.9.19

- Sales bot generated VPN usernames no longer use Telegram chat IDs.
- New sales-bot config-name mode: five-digit random usernames by default, or optional `prefix-12345` when enabled in the panel.
- Admin free-config command now accepts optional custom prefix: `TelegramID PlanID Count Name`.
- Node direct-port JSON is canonicalized across bootstrap, install_node, node_agent and core installer to remove malformed trailing braces such as `{"telegram_proxy":6974}}`.
- Telegram Proxy node health check now waits for the listener and treats the active service with correct direct-port runtime as a valid post-sync state.
- Cisco/Ocserv CSTP hook removal remains enforced.
