# IronPanel v16.7 Outbound Routing

The Outbound Manager allows the main admin to route selected IronPanel protocol traffic through an upstream OpenVPN or V2Ray/Xray configuration.

## Supported upstream configs

- OpenVPN client config (`.ovpn`)
- VLESS URI
- VMess URI
- Trojan URI
- Shadowsocks URI

## Workflow

1. Go to `VPN و زیرساخت → Outbound Routing`.
2. Select OpenVPN or V2Ray/Xray.
3. Paste the upstream config.
4. Click `تست اتصال`.
5. Select which protocols should use the outbound.
6. Click `تست و اعمال`.

## Runtime behavior

- OpenVPN outbound starts a managed service named `ironpanel-outbound-openvpn.service`.
- Selected classic VPN protocol subnets are routed with Linux policy routing.
- V2Ray/Xray outbound is converted into an Xray outbound object.
- If Xray is selected, Xray inbound traffic is routed to the upstream outbound.
- If classic protocols are selected with V2Ray/Xray outbound, a TProxy inbound is added to Xray and policy rules are prepared.

## Troubleshooting

```bash
sudo systemctl status ironpanel-outbound-openvpn --no-pager
sudo journalctl -u ironpanel-outbound-openvpn -n 100 --no-pager
sudo bash /opt/ironpanel/scripts/apply_outbound.sh disable
sudo systemctl restart xray
```
