document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('transcript-form');
  const urlInput = document.getElementById('video-url');
  const languageSelect = document.getElementById('language-select');
  const includeTimestamps = document.getElementById('include-timestamps');
  const transcriptSection = document.getElementById('transcript-section');
  const transcriptDisplay = document.getElementById('transcript-display');
  const errorMessage = document.getElementById('error-message');
  const copyBtn = document.getElementById('copy-btn');
  const downloadBtn = document.getElementById('download-btn');
  const fetchBtn = document.getElementById('fetch-btn');
  const fetchBtnLabel = fetchBtn.querySelector('.btn__label');
  const titleEl = document.getElementById('video-title');
  const langBadge = document.getElementById('lang-badge');
  const bulkInput = document.getElementById('bulk-input');
  const bulkLanguage = document.getElementById('bulk-language');
  const bulkLimit = document.getElementById('bulk-limit');
  const bulkBtn = document.getElementById('bulk-download-btn');

  let currentTranscript = '';
  let currentTitle = '';

  function sanitizeFilename(name) {
    const cleaned = (name || '').replace(/[\\\/:*?"<>|]/g, '').trim();
    return (cleaned || 'transcript').slice(0, 120);
  }

  function setLoading(button, on) {
    if (!button) return;
    const label = button.querySelector('.btn__label');
    if (on) {
      button.classList.add('loading');
      button.setAttribute('aria-busy', 'true');
      button.disabled = true;
      if (label) label.textContent = 'Working…';
    } else {
      button.classList.remove('loading');
      button.removeAttribute('aria-busy');
      button.disabled = false;
      if (label === fetchBtnLabel) label.textContent = 'Fetch transcript';
      else if (label) label.textContent = 'Download ZIP';
    }
  }

  function populateLanguages(languages, usedLanguage) {
    languageSelect.innerHTML = '';
    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = 'Auto';
    languageSelect.appendChild(defaultOption);

    (languages || []).forEach((lang) => {
      const option = document.createElement('option');
      option.value = lang.language_code;
      option.textContent = `${lang.language}${lang.is_generated ? ' (auto)' : ''}`;
      if (lang.language_code === usedLanguage) option.selected = true;
      languageSelect.appendChild(option);
    });
    languageSelect.disabled = false;
  }

  async function fetchTranscript() {
    errorMessage.textContent = '';
    transcriptSection.classList.add('hidden');
    setLoading(fetchBtn, true);

    try {
      const payload = {
        url: urlInput.value.trim(),
        language: languageSelect.value || null,
        include_timestamps: includeTimestamps.checked,
      };
      const response = await fetch('/api/transcript', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Failed to fetch transcript');

      currentTranscript = data.transcript || '';
      currentTitle = data.video_title || '';
      document.title = currentTitle ? `${currentTitle} — Transcript` : 'YouTube Transcript Viewer';
      titleEl.textContent = currentTitle || 'Transcript';
      langBadge.textContent = (data.language_used || '').toUpperCase() || '—';

      transcriptDisplay.textContent = currentTranscript || '(No transcript text)';
      transcriptSection.classList.remove('hidden');
      populateLanguages(data.available_languages || [], data.language_used || '');
    } catch (err) {
      errorMessage.textContent = err.message;
    } finally {
      setLoading(fetchBtn, false);
    }
  }

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    if (!urlInput.value.trim()) {
      errorMessage.textContent = 'Please enter a valid YouTube URL.';
      return;
    }
    fetchTranscript();
  });

  languageSelect.addEventListener('change', () => {
    if (urlInput.value.trim()) fetchTranscript();
  });

  copyBtn.addEventListener('click', () => {
    if (!currentTranscript) return;
    navigator.clipboard.writeText(currentTranscript).then(() => {
      const original = copyBtn.textContent;
      copyBtn.textContent = 'Copied!';
      setTimeout(() => (copyBtn.textContent = original), 1800);
    });
  });

  downloadBtn.addEventListener('click', () => {
    if (!currentTranscript) return;
    const blob = new Blob([currentTranscript], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const base = sanitizeFilename(currentTitle || 'transcript');
    a.href = url;
    a.download = `${base}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  });

bulkBtn.addEventListener('click', async (e) => {
  e.preventDefault();
  errorMessage.textContent = '';
  const inputs = bulkInput.value.trim();
  if (!inputs) {
    errorMessage.textContent = 'Paste links (or a playlist/channel URL) first.';
    return;
  }
  const language = (bulkLanguage.value || '').trim() || null;
  const limit = Math.max(1, Math.min(1000, parseInt(bulkLimit.value || '200', 10)));
  const includeTimestamps = document.getElementById('include-timestamps').checked;
  const body = { limit, language, include_timestamps: includeTimestamps };

  const isPlaylist = /[?&]list=/.test(inputs);
  const isChannel = /\/channel\/UC[0-9A-Za-z_-]{22}/.test(inputs) || /\/@[\w.\-]+/.test(inputs);

  if (isPlaylist) {
    body.playlist_url = inputs;
  } else if (isChannel) {
    body.channel_url = inputs;
  } else {
    const urls = inputs.split(/[,\s]+/).filter(Boolean);
    if (!urls.length) {
      errorMessage.textContent = 'No valid video URLs found.';
      return;
    }
    body.urls = urls;
  }
  setLoading(bulkBtn, true);
  try {
    const response = await fetch('/api/bulk-transcripts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      let msg = 'Bulk request failed';
      try {
        const data = await response.json();
        if (data.expansion_errors?.length) {
          msg += `: ${data.expansion_errors.join(' | ')}`;
        } else if (data.detail) {
          msg += `: ${data.detail}`;
        }
      } catch {}
      throw new Error(msg);
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const stamp = new Date().toISOString().replace(/[:.]/g, '').slice(0, 15);
    a.href = url;
    a.download = `transcripts-${stamp}.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (err) {
    errorMessage.textContent = err.message;
  } finally {
    setLoading(bulkBtn, false);
  }
});

});
