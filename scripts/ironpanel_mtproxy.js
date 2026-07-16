#!/usr/bin/env node
'use strict';
// IronPanel MTProto proxy wrapper for single-port, multi-secret Telegram Proxy.
// Based on the lightweight JSMTProxy flow, with IronPanel-specific multi-user
// secret matching and per-user byte counters written to usage.json.
const net = require('net');
const crypto = require('crypto');
const fs = require('fs');
const { exec } = require('child_process');

const CON_TIMEOUT = 5 * 60000;
const REPORT_CON_SEC = 10;
const MIN_IDLE_SERVERS = 4;
const configPath = process.env.IRONPANEL_TGPROXY_CONFIG || 'config.json';
const usagePath = process.env.IRONPANEL_TGPROXY_USAGE || 'usage.json';
exec('/usr/bin/prlimit --pid ' + process.pid + ' --nofile=81920:81920', () => {});

function readConfig() {
  const cfg = JSON.parse(fs.readFileSync(configPath, 'utf8'));
  const users = Array.isArray(cfg.users) ? cfg.users : [];
  const legacySecret = cfg.secret ? [{ id: 'legacy', username: 'legacy', secret: String(cfg.secret), enabled: true }] : [];
  const enabledUsers = users.concat(legacySecret).filter(u => u && u.enabled !== false && /^[a-fA-F0-9]{32}$/.test(String(u.secret || '')));
  return { port: Number(cfg.port || 6969), users: enabledUsers };
}

let configObj = readConfig();
const userSecrets = configObj.users.map(u => ({
  id: String(u.id),
  username: String(u.username || u.id),
  secret: String(u.secret).toLowerCase(),
  binSecret: Buffer.from(String(u.secret), 'hex')
}));

const usage = {};
for (const u of userSecrets) usage[u.id] = { username: u.username, rx: 0, tx: 0, connections: 0, last_seen: null };
function flushUsage() {
  try {
    const tmp = usagePath + '.tmp';
    fs.writeFileSync(tmp, JSON.stringify({ updated_at: new Date().toISOString(), users: usage }, null, 2));
    fs.renameSync(tmp, usagePath);
  } catch (e) {
    console.error('usage flush failed:', e.message);
  }
}
setInterval(flushUsage, 5000);
process.on('SIGTERM', () => { flushUsage(); process.exit(0); });
process.on('SIGINT', () => { flushUsage(); process.exit(0); });

function reverseInplace(buffer) {
  for (let i = 0, j = buffer.length - 1; i < j; ++i, --j) {
    const t = buffer[j]; buffer[j] = buffer[i]; buffer[i] = t;
  }
}

const telegram_servers = ['149.154.175.50', '149.154.167.51', '149.154.175.100', '149.154.167.91', '149.154.171.5'];
let telegram_idle_num = [MIN_IDLE_SERVERS, MIN_IDLE_SERVERS, MIN_IDLE_SERVERS, MIN_IDLE_SERVERS, MIN_IDLE_SERVERS];
const server_idle_cons = telegram_servers.map(() => []);
const con_count = telegram_servers.map(() => 0);

function create_idle_server(id, ip) {
  const client = new net.Socket();
  client.setKeepAlive(true);
  client.on('timeout', () => client.destroy());
  client.connect(443, ip, () => {
    let random_buf = crypto.randomBytes(64);
    while (true) {
      const val = (random_buf[3] << 24) | (random_buf[2] << 16) | (random_buf[1] << 8) | random_buf[0];
      const val2 = (random_buf[7] << 24) | (random_buf[6] << 16) | (random_buf[5] << 8) | random_buf[4];
      if (random_buf[0] !== 0xef && val !== 0x44414548 && val !== 0x54534f50 && val !== 0x20544547 && val !== 0x4954504f && val !== 0xeeeeeeee && val2 !== 0) {
        random_buf[56] = random_buf[57] = random_buf[58] = random_buf[59] = 0xef;
        break;
      }
      random_buf = crypto.randomBytes(64);
    }
    const keyIv = Buffer.allocUnsafe(48);
    random_buf.copy(keyIv, 0, 8);
    const encryptKey_server = Buffer.allocUnsafe(32); keyIv.copy(encryptKey_server, 0, 0);
    const encryptIv_server = Buffer.allocUnsafe(16); keyIv.copy(encryptIv_server, 0, 32);
    reverseInplace(keyIv);
    const decryptKey_server = Buffer.allocUnsafe(32); keyIv.copy(decryptKey_server, 0, 0);
    const decryptIv_server = Buffer.allocUnsafe(16); keyIv.copy(decryptIv_server, 0, 32);
    client.cipher_dec_server = crypto.createCipheriv('aes-256-ctr', decryptKey_server, decryptIv_server);
    client.cipher_enc_server = crypto.createCipheriv('aes-256-ctr', encryptKey_server, encryptIv_server);
    const packet_enc = client.cipher_enc_server.update(random_buf);
    random_buf.copy(packet_enc, 0, 0, 56);
    client.write(packet_enc, () => server_idle_cons[id].push(client));
  });
  client.on('error', () => client.destroy());
  client.on('data', (data) => {
    const sock = client.client_socket;
    if (sock && sock.writable) {
      if (sock.ironpanelUserId && usage[sock.ironpanelUserId]) {
        usage[sock.ironpanelUserId].tx += data.length;
        usage[sock.ironpanelUserId].last_seen = new Date().toISOString();
      }
      const dec_packet = client.cipher_dec_server.update(data);
      const enc_packet = sock.cipher_enc_client.update(dec_packet);
      sock.write(enc_packet, () => {});
    } else {
      client.destroy();
    }
  });
  client.on('end', () => {
    if (client.client_socket) client.client_socket.end();
  });
}

setInterval(() => {
  console.log('Connections per second:', Math.ceil(con_count.reduce((a,b)=>a+b,0) / REPORT_CON_SEC), 'users:', userSecrets.length, 'port:', configObj.port);
  for (let i = 0; i < telegram_servers.length; i++) {
    const n = Math.ceil(con_count[i] / REPORT_CON_SEC);
    telegram_idle_num[i] = n >= 4 ? n : 4;
    con_count[i] = 0;
  }
}, REPORT_CON_SEC * 1000);

setInterval(() => {
  for (let i = 0; i < telegram_servers.length; i++) {
    if (server_idle_cons[i].length < telegram_idle_num[i]) create_idle_server(i, telegram_servers[i]);
  }
}, 20);

function matchSecret(buf64) {
  const keyIvBase = Buffer.allocUnsafe(48);
  buf64.copy(keyIvBase, 0, 8);
  for (const user of userSecrets) {
    const keyIv = Buffer.from(keyIvBase);
    let decryptKey_client = Buffer.allocUnsafe(32); keyIv.copy(decryptKey_client, 0, 0);
    const decryptIv_client = Buffer.allocUnsafe(16); keyIv.copy(decryptIv_client, 0, 32);
    reverseInplace(keyIv);
    let encryptKey_client = Buffer.allocUnsafe(32); keyIv.copy(encryptKey_client, 0, 0);
    const encryptIv_client = Buffer.allocUnsafe(16); keyIv.copy(encryptIv_client, 0, 32);
    decryptKey_client = crypto.createHash('sha256').update(Buffer.concat([decryptKey_client, user.binSecret])).digest();
    encryptKey_client = crypto.createHash('sha256').update(Buffer.concat([encryptKey_client, user.binSecret])).digest();
    const cipher_dec_client = crypto.createCipheriv('aes-256-ctr', decryptKey_client, decryptIv_client);
    const dec_auth_packet = cipher_dec_client.update(buf64);
    let ok = true;
    for (let i = 0; i < 4; i++) {
      if (dec_auth_packet[56 + i] !== 0xef) { ok = false; break; }
    }
    if (!ok) continue;
    const dcId = Math.abs(dec_auth_packet.readInt16LE(60)) - 1;
    if (dcId > 4 || dcId < 0) continue;
    return {
      user,
      dcId,
      cipher_dec_client,
      cipher_enc_client: crypto.createCipheriv('aes-256-ctr', encryptKey_client, encryptIv_client)
    };
  }
  return null;
}

if (userSecrets.length === 0) {
  console.error('No enabled MTProto secrets in config.json');
}

net.createServer((socket) => {
  socket.setTimeout(CON_TIMEOUT);
  socket.on('error', () => socket.destroy());
  socket.on('timeout', () => socket.destroy());
  socket.on('end', () => { if (socket.server_socket) socket.server_socket.destroy(); });
  socket.on('data', (data) => {
    if (socket.init == null && (data.length === 41 || data.length === 56)) { socket.destroy(); return; }
    if (socket.init == null && data.length < 64) { socket.destroy(); return; }
    if (socket.init == null) {
      const buf64 = Buffer.allocUnsafe(64);
      data.copy(buf64);
      const matched = matchSecret(buf64);
      if (!matched) { socket.destroy(); return; }
      socket.cipher_dec_client = matched.cipher_dec_client;
      socket.cipher_enc_client = matched.cipher_enc_client;
      socket.dcId = matched.dcId;
      socket.ironpanelUserId = matched.user.id;
      socket.ironpanelUsername = matched.user.username;
      usage[socket.ironpanelUserId] = usage[socket.ironpanelUserId] || { username: matched.user.username, rx: 0, tx: 0, connections: 0, last_seen: null };
      usage[socket.ironpanelUserId].connections += 1;
      usage[socket.ironpanelUserId].rx += data.length;
      usage[socket.ironpanelUserId].last_seen = new Date().toISOString();
      data = data.slice(64);
      socket.init = true;
    } else if (socket.ironpanelUserId && usage[socket.ironpanelUserId]) {
      usage[socket.ironpanelUserId].rx += data.length;
      usage[socket.ironpanelUserId].last_seen = new Date().toISOString();
    }
    const payload = socket.cipher_dec_client.update(data);
    if (socket.server_socket == null) {
      if (server_idle_cons[socket.dcId].length > 0) {
        do {
          socket.server_socket = server_idle_cons[socket.dcId].shift();
          if (!socket.server_socket.writable) socket.server_socket.destroy();
        } while (!socket.server_socket.writable);
        con_count[socket.dcId]++;
        socket.server_socket.setTimeout(CON_TIMEOUT);
        socket.server_socket.setKeepAlive(false);
        socket.server_socket.client_socket = socket;
      } else {
        console.log('SHORT ON IDLE SERVER CONNECTIONS! dcId:', socket.dcId + 1);
        socket.destroy();
        return;
      }
    }
    const enc_payload = socket.server_socket.cipher_enc_server.update(payload);
    if (socket.server_socket.writable) socket.server_socket.write(enc_payload, () => {});
    else { socket.server_socket.destroy(); socket.destroy(); }
  });
}).listen(configObj.port, () => {
  console.log('IronPanel MTProto proxy listening on port', configObj.port, 'with', userSecrets.length, 'secrets');
});
