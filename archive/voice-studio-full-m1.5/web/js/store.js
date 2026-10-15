import { featureOptions } from './catalog.js';
import { activateEditor, updateEditor, defaultSaveBlocker } from './editor.js';
import { reduceFlow } from './assignment-flow.js';
import { voiceGender } from './voice-presentation.js';

export function createStore() {
  const parameters = value => ({ speed: 1, volume: 1, emotion: 'auto', ...structuredClone(value ?? {}) });
  let state = { status: 'idle', data: null, error: '', catalog: { status: 'idle', voices: [], filters: { query: '', source: 'all', feature: 'all' }, selectedId: null, error: '' }, task: { jobId: null, selections: {} },
    projectDefault: { saved: null, draft: null, revision: 0, confirmation: null }, editor: { activeKey: null, drafts: {} }, libraryRevision: 0,
    flow: { name: '', status: 'idle', error: '', message: '', confirmation: null, summary: null, lastSaveKey: null },
    ui: { tab: 'basic', poolPreview: { voiceId: null, status: 'idle', error: '' }, poolCollapsed: false, debugOpen: false, target: null, selectedVoiceId: null, detailVoiceId: null, detailKind: 'project', preview: { voiceId: null, status: 'idle', error: '' } } };
  const listeners = new Set();
  return {
    getState: () => structuredClone(state),
    dispatch(action) {
      switch (action.type) {
        case 'LOAD_START': state = { ...state, status: 'loading', error: '' }; break;
        case 'LOAD_SUCCESS': {
          const data = structuredClone(action.data);
          const portraits = ['narrator', 'reader', 'soft'];
          for (let n = portraits.length - 1; n > 0; n--) { const index = Math.floor(Math.random() * (n + 1)); [portraits[n], portraits[index]] = [portraits[index], portraits[n]]; }
          const avatars = Object.fromEntries((data.job ? data.roles ?? [] : []).map((role, index) => [role.id,
            state.task.jobId === data.job.id && state.task.avatars?.[role.id] ? state.task.avatars[role.id] : `assets/portrait-${portraits[index % portraits.length]}.svg`]));
          const saved = data.project.defaultVoice ? { ...structuredClone(data.project.defaultVoice), parameters: parameters(data.project.defaultVoice.parameters) } : null;
          state = { ...state, status: 'ready', data, error: '', editor: { activeKey: null, drafts: {} }, libraryRevision: data.libraryRevision ?? 0,
            flow: { name: '', status: 'idle', error: '', message: '', confirmation: null, summary: null, lastSaveKey: null },
            task: { jobId: data.job?.id ?? null, avatars, selections: Object.fromEntries((data.job ? data.roles ?? [] : []).map(role => [role.id, { voiceId: role.voiceId ?? null, voiceGender: voiceGender(data.voices.find(voice => voice.id === role.voiceId)), parameters: parameters(role.parameters) }])) },
            projectDefault: { saved, draft: structuredClone(saved), revision: 0, confirmation: null },
            ui: { ...state.ui, target: null, selectedVoiceId: null, detailVoiceId: null, detailKind: 'project', preview: { voiceId: null, status: 'idle', error: '' } } };
          break;
        }
        case 'LOAD_FAILURE': state = { ...state, status: 'error', error: String(action.error) }; break;
        case 'CATALOG_LOAD_START':
          state = { ...state, catalog: { ...state.catalog, status: 'loading', error: '' } }; break;
        case 'CATALOG_LOAD_SUCCESS':
          state = { ...state, catalog: { ...state.catalog, status: 'ready', voices: structuredClone(action.voices), selectedId: null, error: '' }, ui: state.ui.detailKind === 'pool' ? { ...state.ui, detailVoiceId: null } : state.ui }; break;
        case 'CATALOG_LOAD_FAILURE':
          state = { ...state, catalog: { ...state.catalog, status: 'error', voices: [], selectedId: null, error: String(action.error) }, ui: state.ui.detailKind === 'pool' ? { ...state.ui, detailVoiceId: null } : state.ui }; break;
        case 'SET_CATALOG_FILTER':
          if (!['query', 'source', 'feature'].includes(action.key) || typeof action.value !== 'string') throw new Error('无效筛选');
          if (action.key === 'source' && !['all', 'official', 'user'].includes(action.value)) throw new Error('无效来源');
          if (action.key === 'feature' && !featureOptions.some(([key]) => key === action.value)) throw new Error('无效特征');
          state = { ...state, catalog: { ...state.catalog, filters: { ...state.catalog.filters, [action.key]: action.value } } }; break;
        case 'SELECT_POOL_VOICE':
          if (state.catalog.status !== 'ready' || !state.catalog.voices.some(voice => voice.id === action.voiceId)) throw new Error('声音池候选不存在');
          state = { ...state, catalog: { ...state.catalog, selectedId: action.voiceId } }; break;
        case 'OPEN_POOL_SETTINGS':
          if (state.catalog.status !== 'ready' || !state.catalog.voices.some(voice => voice.id === action.voiceId)) throw new Error('声音池候选不存在');
          state = { ...state, catalog: { ...state.catalog, selectedId: action.voiceId }, ui: { ...state.ui, tab: 'basic', detailKind: 'pool', detailVoiceId: action.voiceId } }; break;
        case 'POOL_PREVIEW_STATE':
          if (!['loading', 'playing', 'ended', 'stopped', 'error'].includes(action.status)) throw new Error('无效播放状态');
          if (action.status === 'loading' && state.catalog.voices.find(voice => voice.id === action.voiceId)?.availability !== 'available') throw new Error('当前候选未确认可用');
          state = { ...state, ui: { ...state.ui, poolPreview: { voiceId: action.voiceId, status: action.status, error: action.error ?? '' } } }; break;
        case 'SET_POOL_COLLAPSED':
          if (typeof action.value !== 'boolean') throw new Error('无效声音池展开状态');
          state = { ...state, ui: { ...state.ui, poolCollapsed: action.value } }; break;
        case 'SET_TAB':
          if (!['basic', 'explore', 'create'].includes(action.tab)) throw new Error('未知 Tab');
          state = { ...state, ui: { ...state.ui, tab: action.tab } }; break;
        case 'TOGGLE_DEBUG': state = { ...state, ui: { ...state.ui, debugOpen: !state.ui.debugOpen } }; break;
        case 'SELECT_PROJECT_VOICE':
        case 'OPEN_VOICE_SETTINGS':
          if (!state.data?.voices.some(voice => voice.id === action.voiceId)) throw new Error('项目声音不存在');
          state = { ...state, ui: { ...state.ui, selectedVoiceId: action.voiceId,
            ...(action.type === 'OPEN_VOICE_SETTINGS' ? { tab: 'basic', poolCollapsed: true, detailVoiceId: action.voiceId, detailKind: 'project' } : {}) } }; break;
        case 'QUICK_DEFAULT_OPEN': {
          const voice = state.data?.voices.find(item => item.id === (state.projectDefault.saved?.voiceId ?? state.ui.selectedVoiceId)) ?? state.data?.voices[0];
          state = { ...state, projectDefault: { ...state.projectDefault, quick: { voiceId: voice?.id ?? null, expectedRevision: state.projectDefault.revision, libraryRevision: state.libraryRevision } } }; break;
        }
        case 'QUICK_DEFAULT_VOICE':
          if (!state.projectDefault.quick || !state.data.voices.some(item => item.id === action.voiceId)) throw new Error('默认声音候选不可用');
          state = { ...state, projectDefault: { ...state.projectDefault, quick: { ...state.projectDefault.quick, voiceId: action.voiceId } } }; break;
        case 'QUICK_DEFAULT_CANCEL':
          state = { ...state, projectDefault: { ...state.projectDefault, quick: null } }; break;
        case 'QUICK_DEFAULT_CONFIRM': {
          const quick = state.projectDefault.quick, voice = state.data?.voices.find(item => item.id === quick?.voiceId);
          if (!voice || voice.availability === 'unavailable') throw new Error('默认声音候选不可用');
          if (quick.expectedRevision !== state.projectDefault.revision || quick.libraryRevision !== state.libraryRevision) throw new Error('默认声音确认已失效，请关闭后重新选择');
          const saved = { voiceId: voice.id, voiceKey: `project:${voice.id}`, voiceRef: voice.originVoiceKey ?? `project:${voice.id}`, voiceName: voice.name, parameters: parameters(voice.parameters), ...(voice.studioSettings ? { studioSettings: structuredClone(voice.studioSettings) } : {}) };
          state = { ...state, projectDefault: { ...state.projectDefault, saved, draft: structuredClone(saved), quick: null, confirmation: null, revision: state.projectDefault.revision + 1 } }; break;
        }
        case 'SELECT_ROLE': {
          const selection = state.task.selections[action.roleId];
          if (!state.task.jobId || !Object.hasOwn(state.task.selections, action.roleId)) throw new Error('当前任务角色不存在');
          state = { ...state, ui: { ...state.ui, tab: 'basic', target: { kind: 'role', roleId: action.roleId }, selectedVoiceId: selection.voiceId, detailVoiceId: selection.voiceId, detailKind: 'project' } }; break;
        }
        case 'SELECT_DEFAULT':
          state = { ...state, ui: { ...state.ui, target: { kind: 'default' }, selectedVoiceId: state.projectDefault.draft?.voiceId ?? null, detailVoiceId: state.projectDefault.draft?.voiceId ?? null, detailKind: 'project' } }; break;
        case 'ASSIGN_TARGET_VOICE': {
          const voice = state.data?.voices.find(item => item.id === action.voiceId);
          if (!voice || !state.ui.target) throw new Error('请先选择角色或默认声音');
          if (state.ui.target.kind === 'role') {
            const id = state.ui.target.roleId;
            if (!state.task.jobId || !Object.hasOwn(state.task.selections, id)) throw new Error('当前任务角色不存在');
            state = { ...state, task: { ...state.task, selections: { ...state.task.selections, [id]: { ...state.task.selections[id], voiceId: voice.id, voiceKey: `project:${voice.id}`, voiceRef: voice.originVoiceKey ?? `project:${voice.id}`, voiceName: voice.name, voiceGender: voiceGender(voice) } } } };
          } else {
            state = { ...state, projectDefault: { ...state.projectDefault, draft: { voiceId: voice.id, parameters: parameters(state.projectDefault.draft?.parameters ?? voice.parameters) }, confirmation: null } };
          }
          state = { ...state, ui: { ...state.ui, selectedVoiceId: voice.id, detailVoiceId: voice.id, detailKind: 'project' } }; break;
        }
        case 'REQUEST_DEFAULT_SAVE':
          if (defaultSaveBlocker(state)) throw new Error(defaultSaveBlocker(state));
          if (!state.projectDefault.draft?.voiceId || JSON.stringify(state.projectDefault.draft) === JSON.stringify(state.projectDefault.saved)) throw new Error('没有可保存的默认声音修改');
          state = { ...state, projectDefault: { ...state.projectDefault, confirmation: { proposal: structuredClone(state.projectDefault.draft), expectedRevision: state.projectDefault.revision } } }; break;
        case 'CANCEL_DEFAULT_SAVE':
          state = { ...state, projectDefault: { ...state.projectDefault, confirmation: null } }; break;
        case 'CONFIRM_DEFAULT_SAVE': {
          const confirmation = state.projectDefault.confirmation;
          if (!confirmation || confirmation.expectedRevision !== state.projectDefault.revision || JSON.stringify(confirmation.proposal) !== JSON.stringify(state.projectDefault.draft)) throw new Error('默认声音确认已失效，请重新预览');
          state = { ...state, projectDefault: { ...state.projectDefault, saved: structuredClone(confirmation.proposal), revision: state.projectDefault.revision + 1, confirmation: null } }; break;
        }
        case 'DISCARD_DEFAULT_DRAFT':
          state = { ...state, projectDefault: { ...state.projectDefault, draft: structuredClone(state.projectDefault.saved), confirmation: null },
            ui: state.ui.target?.kind === 'default' ? { ...state.ui, selectedVoiceId: state.projectDefault.saved?.voiceId ?? null, detailVoiceId: state.projectDefault.saved?.voiceId ?? null, detailKind: 'project' } : state.ui }; break;
        case 'PREVIEW_STATE':
          if (!['loading', 'playing', 'ended', 'stopped', 'error'].includes(action.status)) throw new Error('无效试听状态');
          if (!state.data?.voices.some(voice => voice.id === action.voiceId)) throw new Error('项目声音不存在');
          state = { ...state, ui: { ...state.ui, preview: { voiceId: action.voiceId, status: action.status, error: action.error ?? '' } } }; break;
        case 'EDIT_FIELD':
        case 'EDITOR_PREVIEW_START':
        case 'EDITOR_PREVIEW_SUCCESS':
        case 'EDITOR_PREVIEW_FAILURE':
          state = updateEditor(state, action); break;
        case 'FLOW_NAME':
          state = reduceFlow(state, action);
          if (state.editor.activeKey && state.editor.drafts[state.editor.activeKey]) state = { ...state, editor: { ...state.editor, drafts: { ...state.editor.drafts, [state.editor.activeKey]: { ...state.editor.drafts[state.editor.activeKey], soundName: action.value } } } };
          break;
        case 'FLOW_STATUS':
        case 'FLOW_APPLY_ROLE':
        case 'FLOW_PREPARE_DEFAULT':
        case 'FLOW_LIBRARY_COMMIT':
        case 'LIBRARY_SYNC':
        case 'FLOW_SUMMARY':
          state = reduceFlow(state, action); break;
        default: throw new Error('未知状态操作');
      }
      state = activateEditor(state, action);
      if (['CATALOG_LOAD_SUCCESS', 'CATALOG_LOAD_FAILURE'].includes(action.type) && state.editor.activeKey?.startsWith('pool:')) state = { ...state, editor: { ...state.editor, activeKey: null } };
      for (const listener of listeners) listener(this.getState(), action.type);
    },
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); }
  };
}

export const store = createStore();
