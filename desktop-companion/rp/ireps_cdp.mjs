// A loopback-only attachment filter for the dedicated IREPS reader.
// Browser navigation, cookies and source responses pass through unchanged.
import http from 'node:http';
import {createRequire} from 'node:module';
import {allowedTarget as allowed} from './ireps_cdp_policy.mjs';
const require=createRequire(import.meta.url);
const [chromePort,packagePath]=process.argv.slice(2);
if(!/^\d+$/.test(chromePort||'')||Number(chromePort)>65535)throw Error('Invalid app browser port');
const bundle=require(packagePath+'/lib/utilsBundle.js');
const WebSocket=bundle.ws,WebSocketServer=bundle.wsServer||WebSocket.Server;
const upstream=`http://127.0.0.1:${chromePort}`;
const version=await(await fetch(upstream+'/json/version')).json();
const server=http.createServer((req,res)=>{
  if(req.url!=='/json/version'&&req.url!=='/json/version/') {res.writeHead(404);res.end();return;}
  res.setHeader('Content-Type','application/json');res.end(JSON.stringify({...version,webSocketDebuggerUrl:`ws://127.0.0.1:${server.address().port}/ireps-reader`}));
});
const sockets=new Set();const websocket=new WebSocketServer({server});
websocket.on('connection',client=>{
  const remote=new WebSocket(version.webSocketDebuggerUrl);sockets.add(client);sockets.add(remote);
  const ready=[];const hidden=new Set();const accepted=new Set();let internal=1000000000;
  function sendRemote(message){const raw=JSON.stringify(message);if(remote.readyState===WebSocket.OPEN)remote.send(raw);else ready.push(raw);}
  function ignoreSession(sessionId,parent,waiting){
    hidden.add(sessionId);
    if(waiting)sendRemote({id:++internal,method:'Runtime.runIfWaitingForDebugger',sessionId});
    sendRemote({id:++internal,method:'Target.detachFromTarget',params:{sessionId},...(parent?{sessionId:parent}:{})});
  }
  remote.on('open',()=>{for(const raw of ready)remote.send(raw);ready.length=0;});
  client.on('message',data=>{try{sendRemote(JSON.parse(data.toString()));}catch{client.close();}});
  remote.on('message',data=>{
    let message;try{message=JSON.parse(data.toString());}catch{return;}
    if(message.id>=1000000000)return;
    if(message.result?.targetInfos)message.result.targetInfos=message.result.targetInfos.filter(allowed);
    if(message.method==='Target.attachedToTarget'){
      const p=message.params;
      if(!allowed(p.targetInfo)&&!accepted.has(message.sessionId)){ignoreSession(p.sessionId,message.sessionId,p.waitingForDebugger);return;}
      accepted.add(p.sessionId);
    }
    if(hidden.has(message.sessionId)||hidden.has(message.params?.sessionId))return;
    if(['Target.targetCreated','Target.targetInfoChanged'].includes(message.method)&&!allowed(message.params.targetInfo))return;
    if(client.readyState===WebSocket.OPEN)client.send(JSON.stringify(message));
  });
  const close=()=>{sockets.delete(client);sockets.delete(remote);if(client.readyState<2)client.close();if(remote.readyState<2)remote.close();};
  client.on('close',close);remote.on('close',close);client.on('error',close);remote.on('error',close);
});
server.listen(0,'127.0.0.1',()=>console.log(JSON.stringify({port:server.address().port})));
function stop(){for(const socket of sockets)socket.terminate();server.close(()=>process.exit(0));setTimeout(()=>process.exit(0),1000).unref();}
process.on('SIGTERM',stop);process.on('SIGINT',stop);
