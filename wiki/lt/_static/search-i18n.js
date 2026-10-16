// Project PO messages feed Sphinx's existing search UI; no second catalog.
const sagaSearchMessages = document.getElementById('saga-search-messages');
if (sagaSearchMessages) Documentation.addTranslations(JSON.parse(sagaSearchMessages.textContent));
