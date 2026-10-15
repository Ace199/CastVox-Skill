import { store } from './store.js';
import { api } from './api.js';
import { eventLog } from './events.js';
import { mountWorkspace } from './modules/workspace.js';
import { mountDebugPanel } from './modules/debug-panel.js';
import { createCatalogLoader } from './catalog-loader.js';

// Development is explicit and local: ?dev=0 hides all debug controls.
const development = ['127.0.0.1', 'localhost', '[::1]'].includes(location.hostname) && new URLSearchParams(location.search).get('dev') !== '0';
store.subscribe((_state, action) => eventLog.record({ name: 'state.changed', objectId: action, result: '已更新' }));
const loadCatalog = createCatalogLoader(store, api);
mountWorkspace(document.querySelector('#workspace'), store, eventLog, loadCatalog, api);
if (development) mountDebugPanel(document.querySelector('#debug-panel'), document.querySelector('#debug-toggle'), store, eventLog, api, loadCatalog);
store.dispatch({ type: 'LOAD_START' });
try {
  const data = await api.loadWorkspace();
  store.dispatch({ type: 'LOAD_SUCCESS', data });
} catch (error) {
  store.dispatch({ type: 'LOAD_FAILURE', error: error.message });
}
await loadCatalog();
