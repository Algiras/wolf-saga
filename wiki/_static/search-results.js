// Search summaries flatten markup. Keep each result's default language honest,
// including asynchronously fetched excerpts, and disclose mixed preview text.
const sagaSearchPageLanguages = JSON.parse(document.getElementById('saga-search-page-languages').textContent);
const sagaNativePerformSearch = Search.performSearch;
Search.performSearch = (...args) => {
  const notice = document.getElementById('saga-search-incomplete');
  notice.hidden = true;
  const result = sagaNativePerformSearch(...args);
  const output = Search.output;
  const annotate = item => {
    const link = item.querySelector('a[href]');
    if (!link) return;
    const route = link.getAttribute('href').split(/[?#]/)[0];
    item.lang = sagaSearchPageLanguages[route] || 'en';
    if (notice.dataset.locale !== 'en' && item.lang === 'en') notice.hidden = false;
  };
  // The first result can be synchronous if the native index is already loaded.
  Array.from(output.children).forEach(annotate);
  const append = output.appendChild.bind(output);
  output.appendChild = item => { annotate(item); return append(item); };
  return result;
};
