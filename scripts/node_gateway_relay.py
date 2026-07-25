#!/usr/bin/env python3
"""IronPanel transparent node gateway relay.

This relay is intentionally small and dependency-free. iptables REDIRECT sends
client traffic that arrived on the main server public protocol port to a local
relay port; the relay then opens an outbound connection to the selected node.
That makes the return path deterministic: node -> main relay -> client.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
import signal
import socket
import time
from pathlib import Path

LOG = Path('/var/log/ironpanel-node-gateway-relay.log')


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"[relay] {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}"
    print(line, flush=True)
    try:
        with LOG.open('a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, label: str) -> None:
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception as exc:
        log(f"tcp pipe {label} closed: {exc}")
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def handle_tcp(mapping: dict, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter) -> None:
    peer = client_writer.get_extra_info('peername')
    target_host = mapping['target_host']
    target_port = int(mapping['target_port'])
    name = mapping.get('name', 'tcp')
    try:
        upstream_reader, upstream_writer = await asyncio.open_connection(target_host, target_port)
    except Exception as exc:
        log(f"tcp {name} connect failed {peer} -> {target_host}:{target_port}: {exc}")
        try:
            client_writer.close(); await client_writer.wait_closed()
        except Exception:
            pass
        return
    log(f"tcp {name} {peer} -> {target_host}:{target_port}")
    await asyncio.gather(
        pipe(client_reader, upstream_writer, f"client->{name}"),
        pipe(upstream_reader, client_writer, f"{name}->client"),
        return_exceptions=True,
    )


class UDPRelay(asyncio.DatagramProtocol):
    def __init__(self, mapping: dict):
        self.mapping = mapping
        self.transport = None
        self.sessions: dict[tuple[str, int], tuple[socket.socket, float]] = {}
        self.loop = asyncio.get_running_loop()
        self.target = (mapping['target_host'], int(mapping['target_port']))
        self.name = mapping.get('name', 'udp')

    def connection_made(self, transport):
        self.transport = transport
        log(f"udp {self.name} listening on {self.mapping.get('listen_port')} -> {self.target[0]}:{self.target[1]}")

    def datagram_received(self, data: bytes, addr):
        now = time.time()
        self._cleanup(now)
        sess = self.sessions.get(addr)
        if sess is None:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setblocking(False)
            try:
                s.connect(self.target)
            except Exception as exc:
                log(f"udp {self.name} connect failed {addr} -> {self.target}: {exc}")
                s.close(); return
            self.sessions[addr] = (s, now)
            self.loop.add_reader(s.fileno(), self._upstream_ready, addr, s)
            log(f"udp {self.name} session {addr} -> {self.target[0]}:{self.target[1]}")
        else:
            s, _ = sess
            self.sessions[addr] = (s, now)
        try:
            s.send(data)
        except Exception as exc:
            log(f"udp {self.name} send upstream failed {addr}: {exc}")

    def _upstream_ready(self, addr, sock: socket.socket):
        try:
            data = sock.recv(65536)
        except Exception:
            data = b''
        if not data:
            return
        if self.transport:
            self.transport.sendto(data, addr)
        if addr in self.sessions:
            self.sessions[addr] = (sock, time.time())

    def _cleanup(self, now: float) -> None:
        ttl = int(os.environ.get('IRONPANEL_NODE_RELAY_UDP_TTL', '180'))
        for addr, (sock, ts) in list(self.sessions.items()):
            if now - ts > ttl:
                try:
                    self.loop.remove_reader(sock.fileno())
                except Exception:
                    pass
                try:
                    sock.close()
                except Exception:
                    pass
                self.sessions.pop(addr, None)


async def start_mapping(mapping: dict):
    proto = str(mapping.get('proto', 'tcp')).lower()
    listen_host = mapping.get('listen_host') or '0.0.0.0'
    listen_port = int(mapping['listen_port'])
    name = mapping.get('name', proto)
    if proto == 'tcp':
        server = await asyncio.start_server(lambda r, w: handle_tcp(mapping, r, w), listen_host, listen_port, reuse_address=True)
        log(f"tcp {name} listening on {listen_host}:{listen_port} -> {mapping['target_host']}:{mapping['target_port']} public={mapping.get('public_port')}")
        return server
    if proto == 'udp':
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.create_datagram_endpoint(lambda: UDPRelay(mapping), local_addr=(listen_host, listen_port), reuse_address=True)
        return transport
    return None


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='/etc/ironpanel/node-gateway-relay.json')
    args = ap.parse_args()
    data = json.loads(Path(args.config).read_text(encoding='utf-8'))
    mappings = data.get('mappings') or []
    if not mappings:
        log('no mappings in config; exiting')
        return
    servers = []
    for m in mappings:
        try:
            srv = await start_mapping(m)
            if srv is not None:
                servers.append(srv)
        except Exception as exc:
            log(f"mapping failed {m}: {exc}")
    if not servers:
        log('no relay listeners started; exiting with error')
        raise SystemExit(1)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass
    await stop.wait()
    for srv in servers:
        try:
            if hasattr(srv, 'close'):
                srv.close()
            if hasattr(srv, 'wait_closed'):
                await srv.wait_closed()
        except Exception:
            pass


if __name__ == '__main__':
    asyncio.run(main())
