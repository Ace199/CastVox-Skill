export function createCatalogLoader(store, api) {
  let latest = 0;
  return async options => {
    const request = ++latest;
    store.dispatch({ type: 'CATALOG_LOAD_START' });
    try {
      const voices = await api.listCatalog(options);
      if (request === latest) store.dispatch({ type: 'CATALOG_LOAD_SUCCESS', voices });
    } catch (error) {
      if (request === latest) store.dispatch({ type: 'CATALOG_LOAD_FAILURE', error: error.message });
    }
  };
}
