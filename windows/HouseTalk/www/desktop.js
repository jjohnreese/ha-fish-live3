import './house-talk.js';
let sequence=0;const pending=new Map();
function host(action,payload={}){return new Promise((resolve,reject)=>{const id=++sequence;const timer=setTimeout(()=>{pending.delete(id);reject(Error('This operation timed out. Please try again.'));},action==='connect'?310000:100000);pending.set(id,{resolve,reject,timer});window.chrome.webview.postMessage({id,action,payload});});}
window.chrome.webview.addEventListener('message',event=>{const message=event.data;if(message.event){if(message.event==='wake'||message.event==='start')window.houseTalk.start();else if(message.event==='toggleMic')window.houseTalk.toggleMicrophone();else if(message.event==='settingsChanged')window.houseTalk.applyDesktopSettings(message.settings).catch(error=>window.houseTalk.fail(error));return;}const waiter=pending.get(message.id);if(!waiter)return;pending.delete(message.id);clearTimeout(waiter.timer);message.error?waiter.reject(Error(message.error)):waiter.resolve(message.result);});
window.houseTalk=document.querySelector('house-talk-card');
window.houseTalk.bridge={call:(type,params={})=>host('rpc',{type,params}),host};
