/* Single integration boundary. UI never calls fetch directly. */
window.CyberheadAPI = (() => {
  const config = window.CYBERHEAD_CONFIG;
  async function request(path) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), config.timeoutMs);
    try {
      const response = await fetch(config.apiBaseUrl.replace(/\/$/, '') + path, { signal: controller.signal, headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error(`Server returned ${response.status}`);
      return await response.json();
    } finally { clearTimeout(timer); }
  }
  function validate(data) {
    if (!data || !Array.isArray(data.reports) || !Array.isArray(data.sources) || !Array.isArray(data.alerts) || !Array.isArray(data.briefing?.reportIds)) throw new Error('Invalid dashboard response');
    for (const r of data.reports) {
      if (typeof r.id !== 'string' || typeof r.title !== 'string' || !['Critical','High','Medium','Low'].includes(r.severity) || !Number.isFinite(r.score) || r.score < 0 || r.score > 100 || !Number.isFinite(r.confidence) || r.confidence < 0 || r.confidence > 1 || !Array.isArray(r.sourceIds) || !Array.isArray(r.indicators) || !Array.isArray(r.tags)) throw new Error('Invalid report data');
    }
    return data;
  }
  return { async getDashboard() {
    if (config.mode === 'mock') return validate(JSON.parse(JSON.stringify(window.CYBERHEAD_MOCK)));
    return validate(await request('/dashboard'));
  }};
})();
