const LIMIT = 100;

export function createEventLog() {
  let entries = [];
  const listeners = new Set();
  const notify = () => { for (const listener of listeners) listener(); };
  return {
    record({ name, objectId = '—', result = '', error = null }) {
      const entry = { time: new Date().toISOString(), name, objectId, result, error: error ? String(error.message ?? error) : '' };
      entries = [...entries.slice(-(LIMIT - 1)), entry];
      notify();
      return structuredClone(entry);
    },
    getEntries: () => structuredClone(entries),
    clear() { entries = []; notify(); },
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); }
  };
}

export const eventLog = createEventLog();
