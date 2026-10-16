const { EventEmitter } = require('events');
module.exports = class extends EventEmitter {
  constructor(url, options) {
    super();
    if (url !== 'ws://127.0.0.1:1981/control' || options.headers.Authorization !== 'Bearer test-secret') throw new Error('invalid transport contract');
    setImmediate(() => this.emit('open'));
  }
  send(raw) {
    const data = JSON.parse(raw);
    if (data.method !== 'conversations.send' || data.params.text !== 'binding done') throw new Error('invalid request');
    const mode = process.env.SM_KIMI_TRANSPORT_CASE;
    if (mode === 'disconnect') return this.emit('close');
    if (mode === 'rejected') return this.emit('message', JSON.stringify({id:data.id,error:{code:-1}}));
    this.emit('message', JSON.stringify({id:data.id,result:{accepted:true,agentId:data.params.agentId,
      conversationKey:mode === 'wrong-target' ? 'other-chat' : data.params.conversationKey,turnId:'test-turn'}}));
  }
  terminate() { this.emit('close'); }
};
