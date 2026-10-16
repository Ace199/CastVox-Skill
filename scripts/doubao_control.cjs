// Native Windows continuation, verified with Doubao 2.32.5. No DOM typing or copied cookies.
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');

function validateBridge(t) {
  const u=new URL(t.endpoint);
  if(u.protocol!=='http:'||u.hostname!=='127.0.0.1'||!u.port||u.pathname!=='/'||u.search||u.hash||u.username||u.password
     ||!/^\/devtools\/browser\/[a-zA-Z0-9-]+$/.test(t.browser_path))throw new Error('invalid_bridge');
  return u;
}

function buildRequest(ctx,native,prepared,localMessageId,message) {
  if(ctx.runtime_type!==2||ctx.app_id!=='582478'||!/^\d{12,24}$/.test(ctx.conversation_id)
     ||!ctx.project_id||!ctx.workspace||native.workspace!==ctx.workspace||!native.client_env_id
     ||!prepared.sandboxId||!Array.isArray(prepared.resolvedSharedFolders)
     ||!Number.isInteger(ctx.sandbox_auth_type)||typeof message!=='string'||!message.trim()||message.length>16000)throw new Error('invalid_local_context');
  const general={runtime_type:2,project_id:ctx.project_id,
    client_option:{...native,enable_sandbox:true,sandbox_id:prepared.sandboxId,
      shared_folder_path:prepared.resolvedSharedFolders,sandbox_auth_type:ctx.sandbox_auth_type},
    agent_task_param:{runtime_type:2,local_app_id:ctx.app_id,local_device_id:ctx.device_id,
      workspace:ctx.workspace,sandbox_auth_type:ctx.sandbox_auth_type},
    agent_task_param_change:{runtime_changed:false,device_changed:false,sandbox_auth_type_changed:false},
    need_modify_conversation:false,
    task_input_json:JSON.stringify({schema_version:1,project_context:{project_id:ctx.project_id,
      folders:[{path:ctx.workspace,folder_name:path.win32.basename(ctx.workspace),is_primary:true}]}})};
  return {client_meta:{local_conversation_id:ctx.local_conversation_id||('local_'+Date.now()),
      conversation_id:ctx.conversation_id,bot_id:'7338286299411103781',last_section_id:ctx.last_section_id||'',last_message_index:null},
    messages:[{local_message_id:localMessageId,message_status:0,content_block:[{block_type:10000,
      content:{text_block:{text:message}},block_id:crypto.randomUUID()}]}],
    option:{create_time_ms:Date.now(),agent_mode:1,need_deep_think:9,unique_key:crypto.randomUUID(),
      recovery_option:{is_recovery:false,req_create_time_sec:Math.floor(Date.now()/1000),append_sse_event_scene:0},
      need_create_conversation:false,is_old_user:true,message_from:0,sse_recv_event_options:{support_chunk_delta:true},general_task_param:general},
    ext:{general_task_param:JSON.stringify(general),agent_mode:'1',is_finish:'1'},user_context:[]};
}

class Cdp {
  constructor(url){this.socket=new WebSocket(url);this.pending=new Map();this.sequence=0;
    this.socket.onmessage=e=>{const d=JSON.parse(e.data),p=this.pending.get(d.id);if(p){clearTimeout(p.timer);this.pending.delete(d.id);d.error?p.reject(new Error('cdp_error')):p.resolve(d.result);}};
    this.socket.onclose=()=>{for(const p of this.pending.values()){clearTimeout(p.timer);p.reject(new Error('connection_closed'));}this.pending.clear();};}
  async ready(){await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('connect_timeout')),4000);this.socket.onopen=()=>{clearTimeout(timer);resolve();};this.socket.onerror=()=>{clearTimeout(timer);reject(new Error('connect_failed'));};});return this;}
  async evaluate(expression){const result=await new Promise((resolve,reject)=>{const id=++this.sequence;
    const timer=setTimeout(()=>{this.pending.delete(id);reject(new Error('evaluation_timeout'));},25000);
    this.pending.set(id,{resolve,reject,timer});this.socket.send(JSON.stringify({id,method:'Runtime.evaluate',params:{expression,awaitPromise:true,returnByValue:true}}));});
    if(result.exceptionDetails){
      const description=result.exceptionDetails.exception?.description||'';
      const known=['invalid_operation','wrong_renderer','missing_runtime_identity','unverified_client_version','metadata_failed','metadata_rejected','origin_missing','not_original_local_context','origin_changed','native_contract_changed','local_environment_not_ready','invalid_local_context'];
      const reason=known.find(code=>description.includes(code))||(/ReferenceError: (\w+) is not defined/.exec(description)?.[1] ? 'missing_runtime_dependency' : 'renderer_rejected');
      throw new Error(reason);
    }return result.result?.value;}
  close(){this.socket.close();}
}

function resolveNativeModules(req) {
  const unique=match=>{const matches=Object.entries(req.m).filter(([,f])=>match(f.toString()));if(matches.length!==1)throw new Error('native_contract_changed');return req(Number(matches[0][0]));};
  const nativeModule=unique(s=>s.includes('buildGeneralAgentCompletionTaskParam:')&&s.includes('general-agent:client-env-id')&&s.includes('sandboxEnvironmentController.query'));
  const sandboxModule=unique(s=>s.includes('H:')&&s.includes('resolvedSharedFolders:')&&s.includes('projectFolders:')&&s.length<1500);
  if(typeof nativeModule.buildGeneralAgentCompletionTaskParam!=='function'||typeof sandboxModule.H!=='function')throw new Error('native_contract_changed');
  return {nativeModule,sandboxModule};
}

async function rendererOperation(input,build,resolveModules) {
  const t=input.target,op=input.op;
  if(!['probe','send'].includes(op)||!/^\d{12,24}$/.test(t.conversation_id))throw new Error('invalid_operation');
  if(!['chrome:','doubao:'].includes(location.protocol)||location.hostname!=='doubao-chat')throw new Error('wrong_renderer');
  const entry=performance.getEntriesByType('resource').slice().reverse().find(e=>{try{const u=new URL(e.name);return u.origin==='https://www.doubao.com'&&u.pathname.startsWith('/im/')&&u.searchParams.has('device_id')&&u.searchParams.get('aid')==='582478';}catch{return false;}});
  if(!entry)throw new Error('missing_runtime_identity');
  const source=new URL(entry.name).searchParams;
  if(source.get('pc_version')!=='2.32.5')throw new Error('unverified_client_version');
  const params=new URLSearchParams();
  for(const k of ['aid','real_aid','channel','chromium_version','client_platform','device_id','device_platform','doubao_device_platform','doubao_pc_version','fp','language','pc_version','pkg_type','region','runtime','runtime_version','samantha_web','sys_region','tea_uuid','tz_name','use-olympus-account','version_code','web_id','web_platform','web_tab_id'])if(source.has(k))params.set(k,source.get(k));
  const response=await fetch('https://www.doubao.com/im/conversation/batch_get?'+params,{method:'POST',credentials:'include',headers:{'content-type':'application/json; encoding=utf-8'},signal:AbortSignal.timeout(6000),body:JSON.stringify({cmd:1111,uplink_body:{batch_get_conv_info_uplink_body:{conversation_id:[t.conversation_id],option:{recent_message_count_per_conv:0},ext:{}}},sequence_id:crypto.randomUUID(),channel:2,version:'1'})});
  if(!response.ok)throw new Error('metadata_failed');const data=await response.json();
  if(data.status_code)throw new Error('metadata_rejected');
  const c=data.downlink_body?.batch_get_conv_info_downlink_body?.conversation_info_list?.find(c=>c.conversation_id===t.conversation_id);
  if(!c)throw new Error('origin_missing');
  let extra=c.extra||{};if(typeof extra==='string')extra=JSON.parse(extra);
  let agent=extra.agent_task_param||{};if(typeof agent==='string')agent=JSON.parse(agent);
  const ctx={conversation_id:c.conversation_id,workspace:agent.workspace,project_id:c.project_reference?.project_id,
    runtime_type:agent.runtime_type,app_id:String(agent.local_app_id||''),sandbox_auth_type:agent.sandbox_auth_type,
    device_id:agent.local_device_id,last_section_id:c.last_section_id,local_conversation_id:extra.local_conversation_id};
  if(ctx.runtime_type!==2||ctx.app_id!=='582478'||ctx.device_id!==source.get('device_id')||!ctx.workspace||!ctx.project_id||!Number.isInteger(ctx.sandbox_auth_type))throw new Error('not_original_local_context');
  if(op==='probe')return Object.fromEntries(Object.entries(ctx).filter(([k])=>!['device_id','last_section_id','local_conversation_id'].includes(k)));
  for(const k of ['conversation_id','workspace','project_id','runtime_type','app_id','sandbox_auth_type'])if(t[k]!==ctx[k])throw new Error('origin_changed');
  let running=extra.running_messages;try{if(typeof running==='string')running=JSON.parse(running);}catch{}
  if((Array.isArray(running)&&running.length)||extra.is_loading===true||extra.is_loading==='true')return {status:'busy'};
  const req=await new Promise(resolve=>window['@flow-web/desktop:stable'].push([['soundmaker_resume_'+crypto.randomUUID()],{},resolve]));
  const {nativeModule,sandboxModule}=resolveModules(req);
  const native=await nativeModule.buildGeneralAgentCompletionTaskParam(ctx.conversation_id,ctx.workspace,{conversationId:ctx.conversation_id});
  if(!native.sandbox_id)throw new Error('local_environment_not_ready');
  const localMessageId=crypto.randomUUID();
  const prepared=await sandboxModule.H({cwd:ctx.workspace,envId:native.sandbox_id,from:'main',globalSkillPath:native.agent_workspace?.agent_workspace,projectFolders:[ctx.workspace],sandboxAuthType:ctx.sandbox_auth_type,sendContext:{conversationId:ctx.conversation_id,localMessageId}});
  // Only the tested serializer builds requests; no dynamic user-supplied code.
  const body=build(ctx,native,prepared,localMessageId,input.message);
  const resp=await fetch('https://api5-normal-gl.doubao.com/chat/completion?'+params,{method:'POST',credentials:'include',headers:{'content-type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(12000)});
  if(!resp.ok)return {status:'failed'};
  const reader=resp.body.getReader(),decoder=new TextDecoder();let buffer='';
  try{for(;;){const {done,value}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});let at;
    while((at=buffer.indexOf('\n\n'))>=0){const chunk=buffer.slice(0,at);buffer=buffer.slice(at+2);
      const event=chunk.split('\n').find(l=>l.startsWith('event:'))?.slice(6).trim();
      const raw=chunk.split('\n').filter(l=>l.startsWith('data:')).map(l=>l.slice(5).trim()).join('');if(!raw)continue;
      let d;try{d=JSON.parse(raw);}catch{continue;}
      if(event==='SSE_ACK'){const run=String(d.query_list?.[0]?.question_id||'');return d.ack_client_meta?.conversation_id===ctx.conversation_id&&/^\d+$/.test(run)?{status:'queued',run_id:run}:{status:'unknown'};}
      if(event==='STREAM_ERROR')return {status:'failed'};
    }
  }}catch{return {status:'unknown'};}finally{try{await reader.cancel();}catch{}}
  return {status:'unknown'};
}

async function control(input) {
  const t=input.target,url=validateBridge(t);
  if(typeof t.profile_path!=='string'||!path.isAbsolute(t.profile_path))throw new Error('invalid_profile');
  const state=JSON.parse(fs.readFileSync(path.join(path.dirname(t.profile_path),'Local State'),'utf8'));
  if(state.profile?.last_used!==path.basename(t.profile_path))throw new Error('profile_changed');
  const version=await (await fetch(new URL('/json/version',url),{signal:AbortSignal.timeout(3000)})).json();
  const browser=new URL(version.webSocketDebuggerUrl);
  if(browser.hostname!=='127.0.0.1'||browser.port!==url.port||browser.pathname!==t.browser_path)throw new Error('instance_changed');
  const targets=await (await fetch(new URL('/json/list',url),{signal:AbortSignal.timeout(3000)})).json();
  const matches=targets.filter(v=>v.type==='page'&&/^(?:chrome|doubao):\/\/doubao-chat\/chat(?:[/?#]|$)/.test(v.url));
  if(matches.length!==1)throw new Error('ambiguous_renderer');
  const ws=new URL(matches[0].webSocketDebuggerUrl);
  if(ws.protocol!=='ws:'||ws.hostname!=='127.0.0.1'||ws.port!==url.port||!ws.pathname.startsWith('/devtools/page/'))throw new Error('invalid_renderer_address');
  const client=await new Cdp(ws).ready();
  try {
    // The page has crypto but not Node's path module; use a portable basename expression.
    const source=buildRequest.toString().replace('path.win32.basename(ctx.workspace)',"ctx.workspace.split(/[\\\\/]/).pop()");
    return await client.evaluate('('+rendererOperation.toString()+')('+JSON.stringify(input)+',('+source+'),('+resolveNativeModules.toString()+'))');
  } finally {client.close();}
}

module.exports={validateBridge,buildRequest,resolveNativeModules,rendererOperation,control};
if(require.main===module){
  let text='';process.stdin.setEncoding('utf8');process.stdin.on('data',chunk=>{text+=chunk;if(text.length>32768)process.exit(2);});
  process.stdin.on('end',async()=>{let input;try{input=JSON.parse(text);const result=await control(input);console.log(JSON.stringify(result));}
    catch(error){const codes=['invalid_bridge','invalid_profile','profile_changed','instance_changed','ambiguous_renderer','invalid_renderer_address','cdp_error','connection_closed','evaluation_timeout','connect_timeout','connect_failed','invalid_operation','wrong_renderer','missing_runtime_identity','unverified_client_version','metadata_failed','metadata_rejected','origin_missing','not_original_local_context','origin_changed','native_contract_changed','local_environment_not_ready','invalid_local_context','missing_runtime_dependency','renderer_rejected'];const reason=codes.includes(error.message)?error.message:'doubao_unavailable';console.log(JSON.stringify(input?.op==='send'?{status:'unknown',reason}:{error:reason}));process.exitCode=input?.op==='send'?0:1;}});
}
