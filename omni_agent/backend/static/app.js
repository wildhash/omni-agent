(function () {
  const API_BASE = '';
  const STORAGE_KEY = 'omni_agent_api_key';

  function getApiKey() {
    return document.getElementById('apiKey').value.trim() || localStorage.getItem(STORAGE_KEY) || '';
  }

  function setApiKeyStatus(msg, ok) {
    const el = document.getElementById('keyStatus');
    el.textContent = msg;
    el.style.color = ok ? 'var(--success)' : 'var(--text-muted)';
  }

  document.getElementById('saveKey').addEventListener('click', function () {
    const key = document.getElementById('apiKey').value.trim();
    if (key) {
      localStorage.setItem(STORAGE_KEY, key);
      setApiKeyStatus('Saved', true);
    } else {
      localStorage.removeItem(STORAGE_KEY);
      setApiKeyStatus('Cleared', false);
    }
  });

  const apiKeyInput = document.getElementById('apiKey');
  if (localStorage.getItem(STORAGE_KEY)) {
    apiKeyInput.placeholder = '••••••••';
  }

  async function postTask(task, context) {
    const key = getApiKey();
    const headers = { 'Content-Type': 'application/json' };
    if (key) headers['X-API-Key'] = key;
    const res = await fetch(API_BASE + '/task', {
      method: 'POST',
      headers,
      body: JSON.stringify({ task, context: context || {} }),
    });
    const data = await res.json().catch(() => ({ detail: res.statusText }));
    if (res.status === 401) {
      const err = new Error(data.detail || 'Unauthorized');
      err.needKey = true;
      throw err;
    }
    if (!res.ok) {
      const msg = data.detail || data.error || data.hint || res.statusText;
      throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
    return data;
  }

  function showResult(elId, data, isError) {
    const el = document.getElementById(elId);
    el.className = 'result-box' + (isError ? ' error' : '');
    el.innerHTML = '';
    if (data === null || data === undefined) return;
    if (typeof data === 'object') {
      const pre = document.createElement('pre');
      pre.textContent = JSON.stringify(data, null, 2);
      el.appendChild(pre);
    } else {
      el.textContent = String(data);
    }
  }

  function showLoading(elId, on) {
    const el = document.getElementById(elId);
    if (on) {
      el.className = 'result-box';
      el.innerHTML = '<span class="loading-text">Loading…</span>';
    }
  }

  function setLoading(btn, on) {
    if (on) btn.classList.add('loading'); else btn.classList.remove('loading');
    btn.disabled = on;
  }

  // --- Tabs
  document.querySelectorAll('.tab').forEach(function (tab) {
    tab.addEventListener('click', function () {
      const name = this.getAttribute('data-tab');
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
      this.classList.add('active');
      document.getElementById('panel-' + name).classList.add('active');
    });
  });

  // --- Task
  document.getElementById('runTask').addEventListener('click', async function () {
    const btn = this;
    const task = document.getElementById('taskInput').value.trim();
    const contextRaw = document.getElementById('contextInput').value.trim();
    const resultEl = document.getElementById('taskResult');
    if (!task) {
      showResult('taskResult', { error: 'Enter a task' }, true);
      return;
    }
    let context = {};
    if (contextRaw) {
      try {
        context = JSON.parse(contextRaw);
      } catch (e) {
        showResult('taskResult', { error: 'Invalid JSON in context' }, true);
        return;
      }
    }
    setLoading(btn, true);
    showLoading('taskResult', true);
    try {
      const data = await postTask(task, context);
      showResult('taskResult', data, !!data.error);
    } catch (e) {
      if (e.needKey) {
        setApiKeyStatus('Set API key and click Save', false);
        showResult('taskResult', { error: 'API key required. Set in header and save.' }, true);
      } else {
        showResult('taskResult', { error: e.message }, true);
      }
    } finally {
      setLoading(btn, false);
    }
  });

  // --- Voice TTS
  document.getElementById('ttsBtn').addEventListener('click', async function () {
    const btn = this;
    const text = document.getElementById('ttsText').value.trim();
    const audioEl = document.getElementById('ttsAudio');
    const resultEl = document.getElementById('ttsResult');
    audioEl.innerHTML = '';
    if (!text) {
      showResult('ttsResult', { error: 'Enter text' }, true);
      return;
    }
    setLoading(btn, true);
    showLoading('ttsResult', true);
    audioEl.innerHTML = '';
    try {
      const data = await postTask('speak', { agent: 'voice', action: 'speak', text });
      if (data.error) {
        showResult('ttsResult', data, true);
        return;
      }
      showResult('ttsResult', { status: data.status, content_type: data.content_type }, false);
      if (data.audio_base64) {
        const audio = document.createElement('audio');
        audio.controls = true;
        audio.src = 'data:' + (data.content_type || 'audio/mpeg') + ';base64,' + data.audio_base64;
        audioEl.appendChild(audio);
      }
    } catch (e) {
      if (e.needKey) setApiKeyStatus('Set API key and click Save', false);
      showResult('ttsResult', { error: e.message }, true);
    } finally {
      setLoading(btn, false);
    }
  });

  // --- Voice STT
  document.getElementById('sttBtn').addEventListener('click', async function () {
    const btn = this;
    const fileInput = document.getElementById('sttFile');
    const resultEl = document.getElementById('sttText');
    const file = fileInput && fileInput.files[0];
    if (!file) {
      showResult('sttText', { error: 'Choose an audio file' }, true);
      return;
    }
    setLoading(btn, true);
    showLoading('sttText', true);
    try {
      const buf = await file.arrayBuffer();
      const b64 = btoa(String.fromCharCode.apply(null, new Uint8Array(buf)));
      const data = await postTask('transcribe', { agent: 'voice', action: 'transcribe', audio_base64: b64 });
      if (data.error) {
        showResult('sttText', data, true);
        return;
      }
      showResult('sttText', { text: data.text, status: data.status }, false);
    } catch (e) {
      if (e.needKey) setApiKeyStatus('Set API key and click Save', false);
      showResult('sttText', { error: e.message }, true);
    } finally {
      setLoading(btn, false);
    }
  });

  // --- Vision
  function runVision(task, context) {
    const btn = event && event.target;
    const url = document.getElementById('visionUrl').value.trim() || 'https://example.com';
    const imgEl = document.getElementById('visionImage');
    const resultEl = document.getElementById('visionResult');
    imgEl.innerHTML = '';
    const ctx = Object.assign({ agent: 'vision', url }, context || {});
    if (btn) setLoading(btn, true);
    showLoading('visionResult', true);
    return postTask(task, ctx)
      .then(function (data) {
        if (data.error) {
          showResult('visionResult', data, true);
          return;
        }
        if (data.image_base64) {
          const img = document.createElement('img');
          img.src = 'data:image/png;base64,' + data.image_base64;
          img.alt = 'Screenshot';
          imgEl.appendChild(img);
        }
        const out = Object.assign({}, data);
        delete out.image_base64;
        delete out.before_base64;
        delete out.after_base64;
        showResult('visionResult', out, false);
      })
      .catch(function (e) {
        if (e.needKey) setApiKeyStatus('Set API key and click Save', false);
        showResult('visionResult', { error: e.message }, true);
      })
      .finally(function () {
        if (btn) setLoading(btn, false);
      });
  }

  document.getElementById('visionScreenshot').addEventListener('click', function () {
    runVision('screenshot', {});
  });
  document.getElementById('visionAnalyze').addEventListener('click', function () {
    runVision('analyze frontend', {});
  });
  document.getElementById('visionElements').addEventListener('click', function () {
    runVision('list elements', {}).then(function () {
      const img = document.getElementById('visionImage');
      img.innerHTML = '';
    });
  });
})();
