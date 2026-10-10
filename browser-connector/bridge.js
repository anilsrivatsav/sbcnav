// Only the configured SBC NAV page may initiate this connector.
const origin = window.location.origin;
window.addEventListener('message', async event => {
  if (event.source !== window || event.origin !== origin || event.data?.channel !== 'sbcnav-mcdo-request') return;
  const {nonce, action, config} = event.data;
  if (!/^[a-f0-9-]{36}$/.test(nonce || '') || !['ping','operator-auth','open','session','collect','pause','resume'].includes(action)) return;
  try {
    const response = await chrome.runtime.sendMessage({action, nonce, config});
    window.postMessage({channel:'sbcnav-mcdo-response', nonce, ...response}, origin);
  } catch (error) {
    window.postMessage({channel:'sbcnav-mcdo-response', nonce, error:String(error.message || error)}, origin);
  }
});
chrome.runtime.onMessage.addListener(message => {
  if (message.channel === 'sbcnav-mcdo-response') window.postMessage(message, origin);
});
