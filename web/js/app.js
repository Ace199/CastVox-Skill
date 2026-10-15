import { createStore } from './store.js';
import { createMockApi } from './api.js';
import { createController } from './controller.js';
import { eventLog } from './events.js';
import { mountStudio } from './view.js?v=config-editor-1';
import { mountDebug } from './debug.js';
import { fetchProviders } from './providers.js';
import { freshDraft } from './store.js';
import { createPreviewPlayer } from './preview-player.js';

const store = createStore();
let providers = [], configError = '';
try { providers = await fetchProviders(); } catch (error) { configError = error.message; }
const api = createMockApi(eventLog, providers);
providers = api.getProviders();
const draft = freshDraft(providers[0]?.id ?? 'minimax', providers[0]?.default_model ?? '');
store.update({ providers, draft });
const controller = createController(store, api, eventLog), player = createPreviewPlayer(store, eventLog);
mountStudio(document.querySelector('#workspace'), store, controller, eventLog, player);
if (['localhost', '127.0.0.1', '[::1]'].includes(location.hostname) && new URLSearchParams(location.search).get('dev') !== '0') mountDebug(document.querySelector('#debug-panel'), document.querySelector('#debug-toggle'), store, api, controller, eventLog);
await controller.load();
if (configError) store.update({ error: configError });

export { store, api, controller, player };
