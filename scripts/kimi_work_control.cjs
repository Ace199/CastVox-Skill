// Credentials arrive on stdin, never argv or logs. Uses Kimi's bundled transport.
'use strict';
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', () => {
  let sent = false, done = false, ws, timer;
  const finish = result => {
    if (done) return;
    done = true;
    clearTimeout(timer);
    process.stdout.write(JSON.stringify(result));
    if (ws) ws.terminate();
  };
  try {
    const data = JSON.parse(input);
    const WebSocket = require(data.ws_module);
    ws = new WebSocket(data.url, { headers: { Authorization: 'Bearer ' + data.token },
      maxPayload: 1024 * 1024, handshakeTimeout: 4000 });
    timer = setTimeout(() => finish({ status: sent ? 'unknown' : 'failed' }), 9000);
    const id = 'soundmaker-binding-complete';
    ws.on('open', () => {
      sent = true;
      ws.send(JSON.stringify({ jsonrpc: '2.0', id, method: 'conversations.send', params: {
        agentId: data.agent_id, conversationKey: data.conversation_key, text: data.message
      } }));
    });
    ws.on('message', raw => {
      let response;
      try { response = JSON.parse(raw); } catch { return; }
      if (response.id !== id) return;
      if (response.result?.accepted === true && response.result.conversationKey === data.conversation_key
          && response.result.agentId === data.agent_id && typeof response.result.turnId === 'string') {
        finish({ status: 'queued', turn_id: response.result.turnId });
      } else finish({ status: response.error ? 'failed' : 'unknown' });
    });
    ws.on('error', () => finish({ status: sent ? 'unknown' : 'failed' }));
    ws.on('close', () => finish({ status: sent ? 'unknown' : 'failed' }));
  } catch { finish({ status: sent ? 'unknown' : 'failed' }); }
});
