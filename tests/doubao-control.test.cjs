const test=require('node:test');
const assert=require('node:assert/strict');
let control;
try {control=require('../scripts/doubao_control.cjs');} catch(e) {if(e.code!=='MODULE_NOT_FOUND')throw e;}
test('local continuation cannot omit Windows sandbox, project or original permission',()=>{
  assert.ok(control,'Doubao control module is missing');
  const ctx={conversation_id:'38447362655653122',workspace:'C:\\project',project_id:'p',runtime_type:2,app_id:'582478',sandbox_auth_type:1};
  const native={workspace:ctx.workspace,agent_workspace:{agent_workspace:'C:\\skills',local_skill_paths:['C:\\skills']},client_env_id:'env'};
  const prepared={sandboxId:'sandbox',resolvedSharedFolders:[ctx.workspace]};
  const b=control.buildRequest(ctx,native,prepared,'message-one','binding saved');
  assert.equal(b.client_meta.conversation_id,ctx.conversation_id);
  assert.equal(b.option.need_create_conversation,false);
  assert.equal(b.option.general_task_param.runtime_type,2);
  assert.equal(b.option.general_task_param.client_option.enable_sandbox,true);
  assert.equal(b.option.general_task_param.client_option.sandbox_auth_type,1);
  assert.equal(b.option.general_task_param.client_option.sandbox_id,'sandbox');
  assert.equal(JSON.parse(b.ext.general_task_param).project_id,'p');
  assert.equal(b.option.model_config,undefined);
  assert.equal(b.option.general_task_param.client_option.os,undefined);
});
test('missing local instance and cloud runtime fail before request construction',()=>{
  assert.ok(control,'Doubao control module is missing');
  assert.throws(()=>control.buildRequest({runtime_type:1},{},{},'id','message'));
  assert.throws(()=>control.buildRequest({runtime_type:2},{},{},'id','message'));
});
test('controller accepts only loopback endpoints and exact browser generation',()=>{
  assert.ok(control,'Doubao control module is missing');
  for(const endpoint of ['http://example.com:1234','http://127.0.0.1:1234/path','http://u:p@127.0.0.1:1234','https://127.0.0.1:1234'])assert.throws(()=>control.validateBridge({endpoint,browser_path:'/devtools/browser/x'}));
  assert.doesNotThrow(()=>control.validateBridge({endpoint:'http://127.0.0.1:19349',browser_path:'/devtools/browser/x'}));
});
test('a forwarding export cannot make the real native task module ambiguous',()=>{
  assert.equal(typeof control.resolveNativeModules,'function');
  const implementation={buildGeneralAgentCompletionTaskParam:async()=>({})};
  const sandbox={H:async()=>({})};
  const req=id=>({2:implementation,3:sandbox})[id];
  req.m={1:function(){return 'buildGeneralAgentCompletionTaskParam:';},
    2:function(){return 'buildGeneralAgentCompletionTaskParam: general-agent:client-env-id sandboxEnvironmentController.query';},
    3:function(){return 'H: resolvedSharedFolders: projectFolders:';}};
  const resolved=control.resolveNativeModules(req);
  assert.equal(resolved.nativeModule,implementation);
  assert.equal(resolved.sandboxModule,sandbox);
});

test('real renderer flow verifies metadata, preserves local context and checks ACK target',async t=>{
  const originalLocation=globalThis.location,originalWindow=globalThis.window;
  t.after(()=>{globalThis.location=originalLocation;globalThis.window=originalWindow;});
  globalThis.location={protocol:'chrome:',hostname:'doubao-chat'};
  t.mock.method(performance,'getEntriesByType',()=>[{name:'https://www.doubao.com/im/chain/recent_conv?aid=582478&device_id=device-one&pc_version=2.32.5'}]);
  const target={conversation_id:'38447362655653122',workspace:'C:\\project',project_id:'p',runtime_type:2,app_id:'582478',sandbox_auth_type:1};
  const agent={workspace:target.workspace,runtime_type:2,local_app_id:'582478',local_device_id:'device-one',sandbox_auth_type:1};
  const metadata={downlink_body:{batch_get_conv_info_downlink_body:{conversation_info_list:[{conversation_id:target.conversation_id,project_reference:{project_id:'p'},extra:{agent_task_param:agent}}]}}};
  let prepareCalls=0,sent=[];
  const native={buildGeneralAgentCompletionTaskParam:async()=>({workspace:target.workspace,sandbox_id:'env',client_env_id:'env',agent_workspace:{agent_workspace:'C:\\skills'}})};
  const sandbox={H:async args=>{prepareCalls++;assert.equal(args.sandboxAuthType,1);return {sandboxId:'sandbox-one',resolvedSharedFolders:[target.workspace]};}};
  const req=id=>({2:native,3:sandbox})[id];
  req.m={2:function(){return 'buildGeneralAgentCompletionTaskParam: general-agent:client-env-id sandboxEnvironmentController.query';},3:function(){return 'H: resolvedSharedFolders: projectFolders:';}};
  globalThis.window={'@flow-web/desktop:stable':{push:([,,callback])=>callback(req)}};
  let ackTarget=target.conversation_id;
  t.mock.method(globalThis,'fetch',async(url,options)=>{
    if(String(url).includes('/conversation/batch_get'))return Response.json(metadata);
    assert.ok(String(url).startsWith('https://api5-normal-gl.doubao.com/chat/completion?'));
    sent.push(JSON.parse(options.body));
    return new Response('event: SSE_ACK\ndata: '+JSON.stringify({ack_client_meta:{conversation_id:ackTarget},query_list:[{question_id:'123456'}]})+'\n\n');
  });
  assert.deepEqual(await control.rendererOperation({op:'send',target,message:'binding saved'},control.buildRequest,control.resolveNativeModules),{status:'queued',run_id:'123456'});
  assert.equal(sent[0].option.general_task_param.runtime_type,2);
  assert.equal(prepareCalls,1);
  ackTarget='38447362655653123';
  assert.deepEqual(await control.rendererOperation({op:'send',target,message:'binding saved'},control.buildRequest,control.resolveNativeModules),{status:'unknown'});
  const count=sent.length;
  metadata.downlink_body.batch_get_conv_info_downlink_body.conversation_info_list[0].extra.running_messages=['active'];
  assert.deepEqual(await control.rendererOperation({op:'send',target,message:'binding saved'},control.buildRequest,control.resolveNativeModules),{status:'busy'});
  assert.equal(sent.length,count);
  agent.runtime_type=1;
  await assert.rejects(control.rendererOperation({op:'send',target,message:'binding saved'},control.buildRequest,control.resolveNativeModules),/not_original_local_context/);
  assert.equal(sent.length,count);
});
