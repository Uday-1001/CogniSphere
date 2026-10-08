const API_BASE = (window.location.protocol && window.location.protocol.startsWith('http'))
  ? window.location.origin
  : 'http://localhost:8000';

// ─── Workspace (Tenant) Manager ───────────────────────────────────────────────
// Each browser/device gets its own UUID slug that is persisted in localStorage.
// On first load it is provisioned as a Tenant on the backend (idempotent).
// Every API call goes through `tenantFetch()` which injects the X-Tenant-Slug
// header automatically — zero manual setup required per user.
class WorkspaceManager {
  constructor() {
    this.STORAGE_KEY = 'cognisphere_workspace_slug';
    this.NAME_KEY = 'cognisphere_workspace_name';
    this.slug = null;
    this.name = null;
    this.ready = false;
  }

  /** Generate a URL-safe slug from a UUID4 */
  _generateSlug() {
    const uuid = ([1e7] + -1e3 + -4e3 + -8e3 + -1e11).replace(/[018]/g, c =>
      (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
    );
    // Use the first 16 chars of the UUID so the slug is compact but still unique
    return 'ws-' + uuid.replace(/-/g, '').slice(0, 16);
  }

  /** Detect a friendly device label for display */
  _detectDeviceName() {
    const ua = navigator.userAgent;
    if (/mobile/i.test(ua)) return 'Mobile Device';
    if (/tablet|ipad/i.test(ua)) return 'Tablet';
    return 'Desktop';
  }

  /** Return the current slug (must call init() first) */
  getSlug() { return this.slug; }
  getName() { return this.name; }

  /**
   * Initialize workspace: load or generate slug, then provision on backend.
   * Safe to call multiple times — subsequent calls resolve immediately.
   */
  async init() {
    if (this.ready) return;

    // Restore or generate slug
    let slug = localStorage.getItem(this.STORAGE_KEY);
    let name = localStorage.getItem(this.NAME_KEY);
    if (!slug) {
      slug = this._generateSlug();
      name = this._detectDeviceName();
      localStorage.setItem(this.STORAGE_KEY, slug);
      localStorage.setItem(this.NAME_KEY, name);
    }
    this.slug = slug;
    this.name = name || this._detectDeviceName();

    // Provision tenant on backend (idempotent — safe to call every page load)
    try {
      await fetch(`${API_BASE}/api/v1/tenants/provision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slug: this.slug, name: this.name })
      });
    } catch (_) {
      // Backend might be starting up; requests will still carry the header
      // and the tenant will be created lazily on first authenticated call.
    }

    this.ready = true;
    this._renderSidebarWidget();
  }

  /**
   * Drop-in replacement for fetch() that always attaches X-Tenant-Slug.
   * Usage: await workspace.fetch(url, options)
   */
  async fetch(url, options = {}) {
    const headers = new Headers(options.headers || {});
    if (this.slug) headers.set('X-Tenant-Slug', this.slug);
    return fetch(url, { ...options, headers });
  }

  /** Render the workspace info widget in the sidebar if the slot exists */
  _renderSidebarWidget() {
    const slots = document.querySelectorAll('.workspace-widget-slot');
    slots.forEach(slot => {
      slot.innerHTML = `
        <div class="workspace-widget" id="workspace-widget">
          <div class="workspace-widget-header">
            <span class="workspace-icon">🔒</span>
            <span class="workspace-label">My Workspace</span>
          </div>
          <div class="workspace-slug" id="workspace-slug-display" title="Your private workspace ID">${this.slug}</div>
          <div class="workspace-name" id="workspace-name-display">${this.name}</div>
          <div class="workspace-actions">
            <button class="btn btn-ghost btn-xs" id="copy-workspace-btn" title="Copy workspace ID">Copy ID</button>
            <button class="btn btn-ghost btn-xs" id="rename-workspace-btn" title="Rename this workspace">Rename</button>
          </div>
        </div>
      `;
      this._bindWidgetButtons(slot);
    });
  }

  _bindWidgetButtons(slot) {
    const copyBtn = slot.querySelector('#copy-workspace-btn');
    const renameBtn = slot.querySelector('#rename-workspace-btn');

    if (copyBtn) {
      copyBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(this.slug).then(() => {
          copyBtn.textContent = 'Copied!';
          setTimeout(() => { copyBtn.textContent = 'Copy ID'; }, 1500);
        });
      });
    }

    if (renameBtn) {
      renameBtn.addEventListener('click', () => {
        const newName = prompt('Enter a name for this workspace (e.g. "My Laptop", "iPhone"):',
          this.name);
        if (newName && newName.trim()) {
          this.name = newName.trim();
          localStorage.setItem(this.NAME_KEY, this.name);
          const nameEl = slot.querySelector('#workspace-name-display');
          if (nameEl) nameEl.textContent = this.name;
        }
      });
    }
  }
}

const workspace = new WorkspaceManager();

/** Convenience wrapper: same signature as fetch(), always tenant-scoped */
function tenantFetch(url, options) {
  return workspace.fetch(url, options);
}

class SoundSynth {
  constructor() {
    this.ctx = null;
    this.enabled = localStorage.getItem('cognisphere_sound') === 'true';
  }

  init() {
    if (!this.ctx && (window.AudioContext || window.webkitAudioContext)) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      this.ctx = new AudioCtx();
    }
  }

  playTone(freq, duration = 0.1, type = 'sine', gainVal = 0.1) {
    if (!this.enabled) return;
    try {
      this.init();
      if (this.ctx && this.ctx.state === 'suspended') {
        this.ctx.resume();
      }
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, this.ctx.currentTime);
      gain.gain.setValueAtTime(gainVal, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, this.ctx.currentTime + duration);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start();
      osc.stop(this.ctx.currentTime + duration);
    } catch (e) {

    }
  }

  send() {
    this.playTone(523.25, 0.08, 'sine', 0.12);
    setTimeout(() => this.playTone(659.25, 0.1, 'sine', 0.12), 60);
  }

  receive() {
    this.playTone(659.25, 0.08, 'sine', 0.12);
    setTimeout(() => this.playTone(880.00, 0.14, 'sine', 0.12), 70);
  }

  click() {
    this.playTone(400, 0.03, 'sine', 0.05);
  }

  error() {
    this.playTone(220, 0.15, 'sawtooth', 0.1);
  }

  success() {
    this.playTone(523.25, 0.08, 'sine', 0.1);
    setTimeout(() => this.playTone(659.25, 0.08, 'sine', 0.1), 80);
    setTimeout(() => this.playTone(1046.50, 0.15, 'sine', 0.12), 160);
  }
}

const sound = new SoundSynth();

document.addEventListener('DOMContentLoaded', async () => {

  // Initialize water wave theme switcher & canvas
  waterWaveTheme.init();

  // Initialize workspace (auto-generates per-device UUID, provisions tenant)
  await workspace.init();

  const spotlight = document.getElementById('spotlight');
  if (spotlight) {
    window.addEventListener('mousemove', (e) => {
      spotlight.style.left = `${e.clientX}px`;
      spotlight.style.top = `${e.clientY}px`;
      spotlight.style.opacity = '1';
    });
    window.addEventListener('mouseleave', () => {
      spotlight.style.opacity = '0';
    });
  }

  initSidebarSystem();

  initPageTransitionEngine();

  const soundToggleBtn = document.getElementById('sound-toggle-btn');
  if (soundToggleBtn) {
    const updateSoundUI = () => {
      const isEnabled = sound.enabled;
      soundToggleBtn.innerHTML = isEnabled
        ? `Sound on`
        : `Sound off`;
      soundToggleBtn.style.color = isEnabled ? 'var(--text-main)' : 'var(--text-muted)';
    };
    updateSoundUI();
    soundToggleBtn.addEventListener('click', () => {
      sound.enabled = !sound.enabled;
      localStorage.setItem('cognisphere_sound', sound.enabled);
      updateSoundUI();
      if (sound.enabled) sound.send();
    });
  }

  checkBackendHealth();

  const bodyId = document.body.id;
  if (bodyId === 'home-page') initHomePage();
  if (bodyId === 'chat-page') initChatPage();
  if (bodyId === 'upload-page') initUploadPage();
  if (bodyId === 'history-page') initHistoryPage();
});

function initSidebarSystem() {
  const sidebar = document.getElementById('sidebar');
  const collapseBtn = document.getElementById('sidebar-collapse-btn');
  const toggleBtn = document.getElementById('sidebar-toggle-btn');
  const overlay = document.getElementById('sidebar-overlay');

  const isMobile = () => window.innerWidth < 768;
  const storedState = localStorage.getItem('cognisphere_sidebar');

  if (storedState === 'collapsed' && !isMobile()) {
    collapseSidebar();
  }

  function collapseSidebar() {
    if (sidebar) sidebar.classList.add('collapsed');
    document.body.classList.add('sidebar-collapsed');
    document.body.classList.remove('mobile-menu-open');
    localStorage.setItem('cognisphere_sidebar', 'collapsed');
    if (overlay) overlay.classList.remove('active');
    if (sidebar) sidebar.classList.remove('open');
  }

  function expandSidebar() {
    if (sidebar) sidebar.classList.remove('collapsed');
    document.body.classList.remove('sidebar-collapsed');
    localStorage.setItem('cognisphere_sidebar', 'expanded');
    if (isMobile()) {
      if (sidebar) sidebar.classList.add('open');
      if (overlay) overlay.classList.add('active');
      document.body.classList.add('mobile-menu-open');
    }
  }

  function toggleSidebar() {
    sound.click();
    if (isMobile()) {
      if (sidebar && sidebar.classList.contains('open')) {
        collapseSidebar();
      } else {
        expandSidebar();
      }
    } else {
      if (document.body.classList.contains('sidebar-collapsed')) {
        expandSidebar();
      } else {
        collapseSidebar();
      }
    }
  }

  if (collapseBtn) collapseBtn.addEventListener('click', collapseSidebar);
  if (toggleBtn) toggleBtn.addEventListener('click', toggleSidebar);
  if (overlay) overlay.addEventListener('click', collapseSidebar);

  window.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key.toLowerCase() === 'b') {
      e.preventDefault();
      toggleSidebar();
    }
  });
}

function initPageTransitionEngine() {
  document.querySelectorAll('a[href]').forEach(link => {
    const href = link.getAttribute('href');
    if (!href || href.startsWith('#') || href.startsWith('http') || href.startsWith('javascript:')) return;
    if (link.target === '_blank') return;

    link.addEventListener('click', (e) => {
      const currentPath = window.location.pathname.split('/').pop() || 'index.html';
      const targetPath = href.split('?')[0].split('#')[0];

      if (currentPath !== targetPath) {
        e.preventDefault();
        document.body.classList.add('page-exit');
        if (typeof sound !== 'undefined') sound.click();

        setTimeout(() => {
          window.location.href = href;
        }, 220);
      }
    });
  });
}

async function checkBackendHealth() {
  const badge = document.getElementById('api-status-badge');
  const heroDot = document.getElementById('hero-api-status-dot');
  const heroText = document.getElementById('hero-api-status-text');

  try {
    const res = await fetch(`${API_BASE}/health`, { method: 'GET' });
    if (res.ok) {
      if (badge) {
        badge.className = 'badge badge-green';
        badge.textContent = 'Online';
      }
      if (heroDot) heroDot.style.background = '#22C55E';
      if (heroText) heroText.textContent = 'AVAILABLE FOR AI QUERY (ONLINE)';
    } else {
      throw new Error('Backend offline');
    }
  } catch (err) {
    if (badge) {
      badge.className = 'badge badge-red';
      badge.textContent = 'Offline';
    }
    if (heroDot) heroDot.style.background = '#EF4444';
    if (heroText) heroText.textContent = 'SYSTEM OFFLINE (RECONNECTING...)';
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatRichContent(rawText) {
  if (!rawText) return '';
  let formatted = typeof marked !== 'undefined' && marked.parse ? marked.parse(rawText) : `<p>${escapeHtml(rawText).replace(/\n/g, '<br>')}</p>`;

  // Auto-wrap markdown tables in responsive wrapper div if not already wrapped
  if (formatted.includes('<table>') && !formatted.includes('<div class="table-wrapper">')) {
    formatted = formatted.replace(/<table>/g, '<div class="table-wrapper"><table>').replace(/<\/table>/g, '</table></div>');
  }

  // Auto-format numbered section headers or Stage titles into section-heading elements with underline
  formatted = formatted.replace(/<p>(\d+\.\s+[^<]+)<\/p>/g, '<h3 class="section-heading">$1</h3>');
  formatted = formatted.replace(/<p>(Stage\s+\d+[^<]+)<\/p>/g, '<h3 class="section-heading">$1</h3>');

  // Format document citations like 【Document: SensiLoRA-RAG.pdf】 into glassmorphic badges
  formatted = formatted.replace(/【Document:\s*([^】]+)】/g, '<span class="badge badge-purple" style="font-size:0.75rem; margin: 0 0.2rem; display: inline-flex; align-items: center; gap: 0.2rem;"> $1</span>');

  // Format LaTeX inline math expressions \( ... \) cleanly
  formatted = formatted.replace(/\\\((.*?)\\\)/g, '<code style="color: var(--accent); background: var(--accent-soft); padding: 0.1rem 0.4rem; border-radius: 4px; font-family: \'JetBrains Mono\', monospace;">$1</code>');

  return formatted;
}

function formatBytes(bytes, decimals = 1) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

function showAlert(elementId, message, type = 'info') {
  const el = document.getElementById(elementId);
  if (!el) return;
  const icons = { success: '', error: '', warning: '', info: '' };
  el.className = `alert alert-${type}`;
  el.innerHTML = `<span style="font-size: 1.1rem;">${icons[type] || ''}</span><div>${message}</div>`;
  el.classList.remove('hidden');
}

function parsePythonList(raw) {
  if (!raw) return [];
  if (Array.isArray(raw)) return raw;
  try {
    const cleaned = raw.replace(/'/g, '"');
    return JSON.parse(cleaned);
  } catch (e) {
    return [raw];
  }
}

// PAGE 1: HOME PAGE (WEB3TASK ENHANCED UX ENGINE)
async function initHomePage() {
  // 1. Mouse Radial Spotlight for Web3Task Cards
  initW3CardsSpotlight();

  // 2. Scroll Reveal Observer
  initScrollRevealObserver();

  // 3. Interactive Showcase Explorer Tabs
  initEngineExplorerTabs();

  // 4. Fetch Stats with Animated Rolling Counters
  try {
    const docsRes = await tenantFetch(`${API_BASE}/history/documents`);
    if (docsRes.ok) {
      const docs = await docsRes.json();
      const el = document.getElementById('stat-docs-count');
      if (el) animateCounter(el, docs.length);
    }
  } catch (e) { }

  try {
    const sessionsRes = await tenantFetch(`${API_BASE}/history/sessions`);
    if (sessionsRes.ok) {
      const rawSessions = await sessionsRes.json();
      const validSessions = rawSessions.filter(s => s.messages && s.messages.length > 0);
      const el = document.getElementById('stat-sessions-count');
      if (el) animateCounter(el, validSessions.length);
    }
  } catch (e) { }
}

function initW3CardsSpotlight() {
  const cards = document.querySelectorAll('.w3-card');
  cards.forEach(card => {
    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      card.style.setProperty('--mouse-x', `${x}px`);
      card.style.setProperty('--mouse-y', `${y}px`);
    });
  });
}

function animateCounter(el, target, duration = 1000) {
  if (!el) return;
  const start = 0;
  const startTime = performance.now();

  function update(now) {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const easeProgress = 1 - Math.pow(1 - progress, 3);
    const val = Math.floor(start + (target - start) * easeProgress);
    el.textContent = val;
    if (progress < 1) {
      requestAnimationFrame(update);
    } else {
      el.textContent = target;
    }
  }
  requestAnimationFrame(update);
}

function initScrollRevealObserver() {
  const elements = document.querySelectorAll('.scroll-reveal');
  if (!('IntersectionObserver' in window)) {
    elements.forEach(el => el.classList.add('active'));
    return;
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('active');
      }
    });
  }, { threshold: 0.1 });

  elements.forEach(el => observer.observe(el));
}

function initEngineExplorerTabs() {
  const tabBtns = document.querySelectorAll('#explorer-tabs .explorer-tab-btn');
  if (!tabBtns.length) return;

  const dataMap = {
    docs: {
      badge: 'DOCUMENTS',
      title: 'Document Reading & Layout Preservation',
      desc: 'Automatically reads PDFs, Word docs, spreadsheets, and scanned pages while preserving layout and tables intact.',
      stats: [
        { label: 'Format Support', val: 'PDF, DOCX, TXT, CSV' },
        { label: 'Speed', val: 'Instant' }
      ],
      windowTitle: 'cognisphere_ingest.py',
      code: `> Initializing CogniSphere Document Reader...\n> Ingesting PDF file: SensiLoRA-RAG.pdf [4.2 MB]\n> Extracted 18 structural sections & 4 data tables\n> Status: READY FOR QUESTIONS (100% indexed)`
    },
    audio: {
      badge: 'AUDIO & VIDEO',
      title: 'Voice & Video Transcription with Time Links',
      desc: 'Transcribes MP3, WAV, and MP4 files with high accuracy, auto-linking answers directly back to exact timestamps.',
      stats: [
        { label: 'Audio Formats', val: 'MP3, WAV, M4A, MP4' },
        { label: 'Accuracy', val: 'High Precision' }
      ],
      windowTitle: 'voice_transcribe_stream.js',
      code: `> Connecting to CogniSphere Audio Engine...\n> Processing Audio: lecture_recording.mp3 [128 kbps]\n> Timestamp [00:04:12]: "LoRA dynamic rank allocation..."\n> Timestamp [00:08:45]: "Parameter sensitivity scores computed..."\n> Status: INDEXED WITH TIME MARKERS`
    },
    search: {
      badge: 'SEARCH',
      title: 'Instant Intelligent Search',
      desc: 'Locates exact concepts, phrases, and answers across thousands of saved document pages in milliseconds.',
      stats: [
        { label: 'Search Speed', val: 'Instant' },
        { label: 'Accuracy', val: 'Exact Matching' }
      ],
      windowTitle: 'neural_retrieval_query.py',
      code: `> Searching files: "What is sensitivity score equation?"\n> Scanning across 1,420 document sections...\n> Top match found: [Doc #42 - SensiLoRA-RAG.pdf, Line 45]\n> Relevance: 97% Match\n> Search Complete`
    },
    rag: {
      badge: 'CITATIONS',
      title: 'Source Citation & Smart Answers',
      desc: 'Generates detailed, precise AI answers enriched with markdown tables, formulas, and clickable document page numbers.',
      stats: [
        { label: 'Source Verification', val: '100% Verified' },
        { label: 'Engine', val: 'CogniSphere AI Assistant' }
      ],
      windowTitle: 'cognisphere_assistant_response.md',
      code: `> Generating Answer...\n> Source Grounding: [Document: SensiLoRA-RAG.pdf]\n> Formatted Markdown Table & formulas generated.\n> Citations appended: 3 source references verified.\n> Response Ready`
    }
  };

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      sound.click();
      const tabKey = btn.getAttribute('data-tab');
      const data = dataMap[tabKey];
      if (!data) return;

      tabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const displayBox = document.getElementById('explorer-display');
      if (displayBox) {
        displayBox.style.opacity = '0.3';
        setTimeout(() => {
          const badgeEl = document.getElementById('exp-badge');
          if (badgeEl) {
            badgeEl.textContent = data.badge;
          }
          document.getElementById('exp-title').textContent = data.title;
          document.getElementById('exp-desc').textContent = data.desc;
          document.getElementById('exp-window-title').textContent = data.windowTitle;
          document.getElementById('exp-code-body').textContent = data.code;

          const statsEl = document.getElementById('exp-stats');
          if (statsEl) {
            statsEl.innerHTML = data.stats.map(s => `
              <div class="explorer-stat-pill">${s.label}: <span>${s.val}</span></div>
            `).join('');
          }
          displayBox.style.opacity = '1';
        }, 150);
      }
    });
  });
}

// PAGE 2: CHAT ASSISTANT
let currentSessionId = localStorage.getItem('cognisphere_session_id') || null;
let selectedFileId = null;

async function initChatPage() {
  const urlParams = new URLSearchParams(window.location.search);
  const paramSessionId = urlParams.get('session_id');
  const paramFileId = urlParams.get('file_id');

  // Dynamically verify valid non-empty sessions from backend history
  let validSessionIds = new Set();
  try {
    const res = await tenantFetch(`${API_BASE}/history/sessions`);
    if (res.ok) {
      const sessions = await res.json();
      sessions.filter(s => s.messages && s.messages.length > 0).forEach(s => validSessionIds.add(s.session_id));
    }
  } catch (e) { }

  let activeSessionToLoad = null;
  if (paramSessionId && validSessionIds.has(parseInt(paramSessionId))) {
    activeSessionToLoad = parseInt(paramSessionId);
  } else {
    const storedId = localStorage.getItem('cognisphere_session_id');
    if (storedId && validSessionIds.has(parseInt(storedId))) {
      activeSessionToLoad = parseInt(storedId);
    }
  }

  if (activeSessionToLoad) {
    currentSessionId = activeSessionToLoad;
    localStorage.setItem('cognisphere_session_id', currentSessionId);
    await loadChatHistory(currentSessionId);
  } else {
    currentSessionId = null;
    localStorage.removeItem('cognisphere_session_id');
    updateSessionInfo(null, 0);
  }

  // Populate Document Selector & Setup Custom Dropdown
  await initCustomFileDropdown(paramFileId);

  // New Session Button
  const newSessionBtn = document.getElementById('new-session-btn');
  if (newSessionBtn) {
    newSessionBtn.addEventListener('click', () => {
      currentSessionId = null;
      localStorage.removeItem('cognisphere_session_id');
      clearChatMessagesArea();
      updateSessionInfo(null, 0);
      sound.click();
    });
  }

  // Clear Chat View Button
  const clearChatBtn = document.getElementById('clear-chat-btn');
  if (clearChatBtn) {
    clearChatBtn.addEventListener('click', () => {
      clearChatMessagesArea();
      sound.click();
    });
  }

  // Textarea Auto-Resize & Submit Listeners
  const textarea = document.getElementById('chat-textarea');
  const sendBtn = document.getElementById('chat-send-btn');

  if (textarea) {
    textarea.addEventListener('input', () => {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 130)}px`;
    });

    textarea.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        submitChatMessage();
      }
    });
  }

  if (sendBtn) {
    sendBtn.addEventListener('click', () => submitChatMessage());
  }

  // Initialize Scroll-Aware Auto-Hide Toolbar
  initScrollAwareToolbar();

  bindPromptPillEvents();
}

function initScrollAwareToolbar() {
  const wrapper = document.getElementById('chat-toolbar-wrapper') || document.querySelector('.chat-toolbar-wrapper');
  const chatMessages = document.getElementById('chat-messages');
  if (!wrapper || !chatMessages) return;

  let lastScrollTop = 0;

  chatMessages.addEventListener('scroll', () => {
    const st = chatMessages.scrollTop;
    const scrollHeight = chatMessages.scrollHeight;
    const clientHeight = chatMessages.clientHeight;
    const maxScroll = scrollHeight - clientHeight;

    // Prevent stutter when scrolling past top or bottom boundaries (overscroll / layout resize loop)
    if (st < 0) return;
    if (maxScroll > 0 && st >= maxScroll - 30) {
      lastScrollTop = st;
      return;
    }

    if (Math.abs(st - lastScrollTop) < 6) return;

    if (st > lastScrollTop && st > 20) {
      // Scroll Down -> Hide WHOLE toolbar wrapper upwards
      if (!wrapper.classList.contains('collapsed')) {
        wrapper.classList.add('collapsed');
      }
    } else if (st < lastScrollTop || st <= 10) {
      // Scroll Up or Near Top -> Re-appear
      if (wrapper.classList.contains('collapsed')) {
        wrapper.classList.remove('collapsed');
      }
    }
    lastScrollTop = st;
  });
}

// Custom Glassmorphic Select Component Logic
async function initCustomFileDropdown(paramFileId) {
  const wrap = document.getElementById('custom-file-dropdown');
  const trigger = document.getElementById('file-dropdown-trigger');
  const menu = document.getElementById('file-dropdown-menu');
  const selectedLabel = document.getElementById('dropdown-selected-label');
  const nativeSelect = document.getElementById('file-select');

  if (!wrap || !trigger || !menu) return;

  let documentsList = [];
  try {
    const res = await tenantFetch(`${API_BASE}/history/documents`);
    if (res.ok) {
      const docs = await res.json();
      documentsList = docs.filter(d => d.status === 'processed');
    }
  } catch (e) { }

  // Render Custom Options with CogniSphere sparkle
  menu.innerHTML = `
    <div class="custom-select-option selected" data-value="" data-label=" All Documents">
      <span></span> <span>All Documents</span>
    </div>
    ${documentsList.map(d => `
      <div class="custom-select-option" data-value="${d.id}" data-label="${getFileEmoji(d.file_type)} ${escapeHtml(d.filename)}">
        <span>${getFileEmoji(d.file_type)}</span>
        <span>${escapeHtml(d.filename)}</span>
      </div>
    `).join('')}
  `;

  // Toggle Menu
  trigger.addEventListener('click', (e) => {
    e.stopPropagation();
    wrap.classList.toggle('open');
    sound.click();
  });

  // Close on outside click
  document.addEventListener('click', () => {
    wrap.classList.remove('open');
  });

  // Option Click Handlers
  menu.querySelectorAll('.custom-select-option').forEach(opt => {
    opt.addEventListener('click', (e) => {
      e.stopPropagation();
      menu.querySelectorAll('.custom-select-option').forEach(o => o.classList.remove('selected'));
      opt.classList.add('selected');

      const val = opt.getAttribute('data-value');
      const label = opt.getAttribute('data-label');

      selectedFileId = val ? parseInt(val) : null;
      if (nativeSelect) nativeSelect.value = val;
      if (selectedLabel) selectedLabel.innerHTML = label;

      updateScopeDisplay(val, label);
      wrap.classList.remove('open');
      sound.click();
    });
  });

  // Auto-Select paramFileId if present
  if (paramFileId) {
    const targetOpt = menu.querySelector(`.custom-select-option[data-value="${paramFileId}"]`);
    if (targetOpt) {
      targetOpt.click();
    }
  }
}

function updateScopeDisplay(fileVal, fileLabel) {
  const scopeEl = document.getElementById('session-scope-display');
  if (!scopeEl) return;
  if (!fileVal) {
    scopeEl.textContent = 'All Files';
    scopeEl.style.color = 'var(--color-info)';
  } else {
    const cleanLabel = fileLabel ? fileLabel.replace(/^[^\s]+\s*/, '') : 'File';
    scopeEl.textContent = cleanLabel.length > 15 ? cleanLabel.substring(0, 13) + '...' : cleanLabel;
    scopeEl.style.color = 'var(--accent)';
  }
}

function updateSessionInfo(sessionId, msgCount) {
  const idEl = document.getElementById('session-id-display');
  const countEl = document.getElementById('msg-count-display');
  if (idEl) idEl.textContent = sessionId ? `#${sessionId}` : 'New';
  if (countEl) countEl.textContent = msgCount;
}

function bindPromptPillEvents() {
  document.querySelectorAll('.prompt-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      const promptText = pill.getAttribute('data-prompt');
      const textarea = document.getElementById('chat-textarea');
      if (textarea && promptText) {
        textarea.value = promptText;
        submitChatMessage();
      }
    });
  });
}

function clearChatMessagesArea() {
  const messagesContainer = document.getElementById('chat-messages');
  if (!messagesContainer) return;

  messagesContainer.style.opacity = '0';
  messagesContainer.style.transform = 'translateY(6px)';
  messagesContainer.style.transition = 'opacity 0.2s ease, transform 0.2s ease';

  setTimeout(() => {
    messagesContainer.innerHTML = `
      <div class="chat-empty" id="chat-empty">
        <div class="chat-empty-badge">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z"></path></svg>
        </div>
        <h2 class="chat-empty-title">Ask CogniSphere</h2>
        <p class="chat-empty-sub">
          Ask anything about your files. Answers cite exact pages and timestamps.
        </p>
        <div class="prompt-pills">
          <span class="prompt-pill pp-summary" data-prompt="Summarize all uploaded documents into key bullet points.">✨ Summarize</span>
          <span class="prompt-pill pp-flash" data-prompt="Extract key insights and core concepts from the files.">💡 Key Insights</span>
          <span class="prompt-pill pp-notes" data-prompt="Create structured study notes based on the uploaded material.">📝 Study Notes</span>
          <span class="prompt-pill pp-quiz" data-prompt="Generate 5 quiz questions with answers based on the content.">❓ Quiz Questions</span>
        </div>
      </div>
    `;
    bindPromptPillEvents();
    messagesContainer.style.opacity = '1';
    messagesContainer.style.transform = 'translateY(0)';
  }, 180);
}

async function loadChatHistory(sessionId) {
  try {
    const res = await tenantFetch(`${API_BASE}/chat/${sessionId}/history`);
    if (!res.ok) return;
    const data = await res.json();
    const messages = data.messages || [];

    if (messages.length > 0) {
      const emptyState = document.getElementById('chat-empty');
      if (emptyState) emptyState.remove();

      messages.forEach(msg => {
        appendMessageBubble(msg.role, msg.content, msg.sources, msg.timestamps, false);
      });

      updateSessionInfo(sessionId, messages.length);
      scrollToBottomMessages();
    } else {
      updateSessionInfo(sessionId, 0);
    }
  } catch (e) { }
}

async function submitChatMessage() {
  const textarea = document.getElementById('chat-textarea');
  const sendBtn = document.getElementById('chat-send-btn');
  if (!textarea) return;

  const question = textarea.value.trim();
  if (!question) return;

  textarea.value = '';
  textarea.style.height = 'auto';
  sound.send();

  const emptyState = document.getElementById('chat-empty');
  if (emptyState) emptyState.remove();

  appendMessageBubble('user', question);
  scrollToBottomMessages();

  if (sendBtn) sendBtn.disabled = true;
  showTypingIndicator();

  try {
    const bodyPayload = { question: question };
    if (currentSessionId) bodyPayload.session_id = parseInt(currentSessionId);
    if (selectedFileId) bodyPayload.file_id = parseInt(selectedFileId);

    const res = await tenantFetch(`${API_BASE}/chat/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bodyPayload)
    });

    removeTypingIndicator();

    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: 'Service unavailable' }));
      sound.error();
      appendMessageBubble('assistant', ` **Error:** ${errData.detail || 'An error occurred during inference.'}`);
      return;
    }

    const data = await res.json();
    currentSessionId = data.session_id;
    localStorage.setItem('cognisphere_session_id', currentSessionId);

    sound.receive();

    appendMessageBubble('assistant', data.answer, data.sources, data.timestamps, true);

    const messagesCount = document.querySelectorAll('#chat-messages .msg').length;
    updateSessionInfo(currentSessionId, messagesCount);

  } catch (err) {
    removeTypingIndicator();
    sound.error();
    appendMessageBubble('assistant', ` **Connection Notice:** Could not connect to the server. Please check that the application server is active.`);
  } finally {
    if (sendBtn) sendBtn.disabled = false;
    scrollToBottomMessages();
  }
}

function appendMessageBubble(role, content, sources = [], timestamps = [], isStreaming = false) {
  const container = document.getElementById('chat-messages');
  if (!container) return;

  const msgDiv = document.createElement('div');
  const isAi = (role === 'ai' || role === 'assistant');
  msgDiv.className = `msg msg-${isAi ? 'ai' : 'user'}`;
  const label = isAi ? 'CogniSphere' : 'You';

  const parsedSources = parsePythonList(sources);
  let sourcesHtml = '';
  if (parsedSources && parsedSources.length > 0) {
    sourcesHtml = `
      <details style="margin-top: 0.6rem; cursor: pointer; font-size: 0.8rem; color: var(--accent);">
        <summary style="font-weight: 600;"> Source References (${parsedSources.length})</summary>
        <ul style="margin-top: 0.4rem; padding-left: 1.2rem; color: var(--muted);">
          ${parsedSources.map(s => `<li>${escapeHtml(s)}</li>`).join('')}
        </ul>
      </details>
    `;
  }

  const parsedTimestamps = parsePythonList(timestamps);
  let timestampsHtml = '';
  if (parsedTimestamps && parsedTimestamps.length > 0) {
    timestampsHtml = `
      <div style="margin-top: 0.4rem; display: flex; gap: 0.4rem; flex-wrap: wrap;">
        ${parsedTimestamps.map(ts => `<span class="badge badge-yellow"> ${escapeHtml(typeof ts === 'object' ? ts.time || JSON.stringify(ts) : ts)}</span>`).join('')}
      </div>
    `;
  }

  if (isAi && isStreaming && content) {
    msgDiv.innerHTML = `
      <div class="msg-label">${label}</div>
      <div class="msg-bubble">
        <div class="stream-text"></div>
        ${sourcesHtml}
        ${timestampsHtml}
      </div>
    `;
    container.appendChild(msgDiv);
    scrollToBottomMessages();

    const streamEl = msgDiv.querySelector('.stream-text');
    const words = content.split(' ');
    let wordIndex = 0;
    let textAcc = '';

    const timer = setInterval(() => {
      if (wordIndex < words.length) {
        textAcc += (wordIndex === 0 ? '' : ' ') + words[wordIndex];
        streamEl.innerHTML = formatRichContent(textAcc) + '<span class="typing-cursor">▌</span>';
        wordIndex++;
        scrollToBottomMessages();
      } else {
        clearInterval(timer);
        streamEl.innerHTML = formatRichContent(textAcc);
        scrollToBottomMessages();
      }
    }, 65);
  } else {
    msgDiv.innerHTML = `
      <div class="msg-label">${label}</div>
      <div class="msg-bubble">
        ${formatRichContent(content)}
        ${sourcesHtml}
        ${timestampsHtml}
      </div>
    `;
    container.appendChild(msgDiv);
  }
}

function showTypingIndicator() {
  const container = document.getElementById('chat-messages');
  if (!container) return;
  const indicator = document.createElement('div');
  indicator.id = 'typing-indicator';
  indicator.className = 'typing-indicator';
  indicator.innerHTML = `
    <span class="typing-dot"></span>
    <span class="typing-dot"></span>
    <span class="typing-dot"></span>
    <span style="font-size: 0.8rem; color: var(--accent); margin-left: 0.4rem; font-weight: 600;">Reading your files</span>
  `;
  container.appendChild(indicator);
  scrollToBottomMessages();
}

function removeTypingIndicator() {
  const indicator = document.getElementById('typing-indicator');
  if (indicator) indicator.remove();
}

function scrollToBottomMessages() {
  const container = document.getElementById('chat-messages');
  if (container) {
    container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
  }
}

function getFileEmoji(fileType) {
  if (fileType === 'video') return 'Video';
  if (fileType === 'audio') return 'Audio';
  return 'Doc';
}

// PAGE 3: UPLOAD PAGE
let selectedUploadFile = null;
let statusPollingInterval = null;

function initUploadPage() {
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const previewCard = document.getElementById('file-preview-card');
  const processBtn = document.getElementById('process-file-btn');
  const cancelBtn = document.getElementById('cancel-file-btn');

  loadProcessedDocsLibrary();

  if (dropZone && fileInput) {
    ['dragenter', 'dragover'].forEach(eventName => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
      });
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
      });
    });

    dropZone.addEventListener('drop', (e) => {
      const files = e.dataTransfer.files;
      if (files.length > 0) {
        handleFileSelected(files[0]);
      }
    });

    fileInput.addEventListener('change', (e) => {
      if (e.target.files.length > 0) {
        handleFileSelected(e.target.files[0]);
      }
    });
  }

  if (cancelBtn) {
    cancelBtn.addEventListener('click', () => {
      selectedUploadFile = null;
      if (fileInput) fileInput.value = '';
      if (previewCard) previewCard.classList.add('hidden');
    });
  }

  if (processBtn) {
    processBtn.addEventListener('click', () => startFileIngestion());
  }
}

function handleFileSelected(file) {
  selectedUploadFile = file;
  const previewCard = document.getElementById('file-preview-card');
  const nameEl = document.getElementById('preview-name');
  const sizeEl = document.getElementById('preview-size');
  const iconEl = document.getElementById('preview-icon');
  const typeEl = document.getElementById('preview-type');

  if (nameEl) nameEl.textContent = file.name;
  if (sizeEl) sizeEl.textContent = formatBytes(file.size);

  const ext = file.name.split('.').pop().toLowerCase();
  let typeLabel = 'Document';
  let emoji = 'Doc';

  if (['mp4', 'avi', 'mkv', 'mov', 'wmv', 'webm', 'm4v'].includes(ext)) {
    typeLabel = 'Video File';
    emoji = 'Video';
  } else if (['mp3', 'wav', 'm4a', 'aac', 'flac', 'ogg', 'wma'].includes(ext)) {
    typeLabel = 'Audio File';
    emoji = 'Audio';
  }

  if (iconEl) iconEl.textContent = emoji;
  if (typeEl) typeEl.textContent = typeLabel;

  if (previewCard) previewCard.classList.remove('hidden');
  sound.click();
}

async function startFileIngestion() {
  if (!selectedUploadFile) return;

  const previewCard = document.getElementById('file-preview-card');
  const progressCard = document.getElementById('progress-card');
  const processBtn = document.getElementById('process-file-btn');
  const alertEl = document.getElementById('upload-alert');

  if (alertEl) alertEl.classList.add('hidden');
  if (processBtn) processBtn.disabled = true;

  sound.send();

  try {
    const formData = new FormData();
    formData.append('file', selectedUploadFile);

    updateProgressUI('Uploading File...', 5, 'Sending file to server storage...');
    if (previewCard) previewCard.classList.add('hidden');
    if (progressCard) progressCard.classList.remove('hidden');

    const uploadRes = await tenantFetch(`${API_BASE}/upload/`, {
      method: 'POST',
      body: formData
    });

    if (!uploadRes.ok) {
      const err = await uploadRes.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(err.detail || 'Upload failed');
    }

    const uploadData = await uploadRes.json();
    const fileId = uploadData.file_id;

    const processRes = await tenantFetch(`${API_BASE}/upload/${fileId}/process`, {
      method: 'POST'
    });

    if (!processRes.ok) {
      const err = await processRes.json().catch(() => ({ detail: 'Processing start failed' }));
      throw new Error(err.detail || 'Failed to start file processing');
    }

    pollProcessingStatus(fileId);

  } catch (err) {
    if (progressCard) progressCard.classList.add('hidden');
    if (processBtn) processBtn.disabled = false;
    sound.error();
    showAlert('upload-alert', `Ingestion failed: ${err.message}`, 'error');
  }
}

function pollProcessingStatus(fileId) {
  if (statusPollingInterval) clearInterval(statusPollingInterval);

  statusPollingInterval = setInterval(async () => {
    try {
      const res = await tenantFetch(`${API_BASE}/upload/${fileId}/status`);
      if (!res.ok) return;

      const data = await res.json();
      const current = data.current || 0;
      const status = data.status;
      const message = data.message || 'Processing...';

      updateProgressUI(
        status === 'processed' ? 'Processing Complete!' : 'Reading & Processing File...',
        current,
        message
      );

      if (status === 'processed' || current >= 100) {
        clearInterval(statusPollingInterval);
        sound.success();
        showAlert('upload-alert', ` <b>${escapeHtml(selectedUploadFile ? selectedUploadFile.name : 'File')}</b> successfully processed and ready!`, 'success');

        const progressCard = document.getElementById('progress-card');
        setTimeout(() => {
          if (progressCard) progressCard.classList.add('hidden');
        }, 1500);

        selectedUploadFile = null;
        loadProcessedDocsLibrary();
      } else if (status === 'error') {
        clearInterval(statusPollingInterval);
        sound.error();
        showAlert('upload-alert', ` Processing error: ${escapeHtml(message)}`, 'error');
        const progressCard = document.getElementById('progress-card');
        if (progressCard) progressCard.classList.add('hidden');
      }
    } catch (e) { }
  }, 500);
}

function updateProgressUI(title, percent, msg) {
  const titleEl = document.getElementById('progress-status-title');
  const percentEl = document.getElementById('progress-percent');
  const fillEl = document.getElementById('progress-fill');
  const msgEl = document.getElementById('progress-msg');

  if (titleEl) titleEl.textContent = title;
  if (percentEl) percentEl.textContent = `${percent}%`;
  if (fillEl) fillEl.style.width = `${percent}%`;
  if (msgEl) msgEl.textContent = msg;
}

async function loadProcessedDocsLibrary() {
  const container = document.getElementById('processed-docs-container');
  if (!container) return;

  try {
    const res = await tenantFetch(`${API_BASE}/history/documents`);
    if (!res.ok) return;

    const docs = await res.json();
    if (docs.length === 0) {
      container.innerHTML = `
        <div class="text-muted" style="text-align: center; padding: 2rem; background: var(--surface-2); border-radius: var(--radius-md);">
          No documents uploaded yet. Drop a file above to begin!
        </div>
      `;
      return;
    }

    container.innerHTML = docs.slice(0, 5).map(doc => `
      <div class="doc-card">
        <div class="doc-icon">${getFileEmoji(doc.file_type)}</div>
        <div class="doc-info">
          <div class="doc-name">${escapeHtml(doc.filename)}</div>
          <div class="doc-meta">${formatBytes(doc.file_size)} • ${new Date(doc.created_at).toLocaleDateString()}</div>
        </div>
        <div class="doc-actions">
          <span class="status-pill ${doc.status === 'processed' ? 'status-ready' : 'status-processing'}">
            <span class="status-dot"></span> ${doc.status === 'processed' ? 'Processed' : 'Processing'}
          </span>
          ${doc.status === 'processed' ? `
            <a href="chat.html?file_id=${doc.id}" class="doc-action-btn action-chat">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
              Chat
            </a>
          ` : ''}
        </div>
      </div>
    `).join('');
  } catch (e) { }
}

// PAGE 4: HISTORY & DOCS PAGE
let allDocumentsList = [];
let selectedDocIds = new Set();
let pendingDeleteTarget = null;

function initHistoryPage() {
  const tabDocsBtn = document.getElementById('tab-docs-btn');
  const tabSessionsBtn = document.getElementById('tab-sessions-btn');
  const tabDocsContent = document.getElementById('tab-docs-content');
  const tabSessionsContent = document.getElementById('tab-sessions-content');

  if (tabDocsBtn && tabSessionsBtn && tabDocsContent && tabSessionsContent) {
    const switchTab = (activeBtn, inactiveBtn, showContent, hideContent, callback) => {
      activeBtn.classList.add('active');
      activeBtn.style.borderBottom = '2px solid var(--accent-blue)';
      activeBtn.style.color = 'var(--text-main)';

      inactiveBtn.classList.remove('active');
      inactiveBtn.style.borderBottom = 'none';
      inactiveBtn.style.color = 'var(--text-muted)';

      hideContent.classList.add('fade-out');
      setTimeout(() => {
        hideContent.classList.add('hidden');
        hideContent.classList.remove('fade-out');

        showContent.classList.remove('hidden');
        showContent.classList.add('fade-out');
        void showContent.offsetWidth;
        showContent.classList.remove('fade-out');
        if (callback) callback();
      }, 150);
    };

    tabDocsBtn.addEventListener('click', () => {
      if (tabDocsContent.classList.contains('hidden')) {
        sound.click();
        switchTab(tabDocsBtn, tabSessionsBtn, tabDocsContent, tabSessionsContent);
      }
    });

    tabSessionsBtn.addEventListener('click', () => {
      if (tabSessionsContent.classList.contains('hidden')) {
        sound.click();
        switchTab(tabSessionsBtn, tabDocsBtn, tabSessionsContent, tabDocsContent, loadSessionsHistory);
      }
    });
  }

  loadDocumentsHistory();
  loadSessionsHistory();

  const searchInput = document.getElementById('doc-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      const query = searchInput.value.toLowerCase().trim();
      renderDocumentsList(allDocumentsList.filter(d =>
        d.filename.toLowerCase().includes(query) || d.file_type.toLowerCase().includes(query)
      ));
    });
  }

  const selectAllBtn = document.getElementById('select-all-docs-btn');
  if (selectAllBtn) {
    selectAllBtn.addEventListener('click', () => {
      if (selectedDocIds.size === allDocumentsList.length) {
        selectedDocIds.clear();
      } else {
        allDocumentsList.forEach(d => selectedDocIds.add(d.id));
      }
      renderDocumentsList(allDocumentsList);
      updateBulkDeleteBtnState();
    });
  }

  const bulkDeleteBtn = document.getElementById('bulk-delete-btn');
  if (bulkDeleteBtn) {
    bulkDeleteBtn.addEventListener('click', () => {
      if (selectedDocIds.size === 0) return;
      openDeleteModal(
        `Are you sure you want to delete ${selectedDocIds.size} selected documents? This action cannot be undone.`,
        async () => {
          try {
            const res = await tenantFetch(`${API_BASE}/history/documents/bulk`, {
              method: 'DELETE',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ file_ids: Array.from(selectedDocIds) })
            });
            if (res.ok) {
              sound.success();
              selectedDocIds.clear();
              loadDocumentsHistory();
            }
          } catch (e) { }
        }
      );
    });
  }

  const cancelModalBtn = document.getElementById('cancel-delete-btn');
  const confirmModalBtn = document.getElementById('confirm-delete-btn');
  const modal = document.getElementById('delete-modal');

  if (cancelModalBtn && modal) {
    cancelModalBtn.addEventListener('click', () => modal.classList.add('hidden'));
  }
  if (confirmModalBtn && modal) {
    confirmModalBtn.addEventListener('click', () => {
      modal.classList.add('hidden');
      if (pendingDeleteTarget) pendingDeleteTarget();
    });
  }
}

async function loadDocumentsHistory() {
  const container = document.getElementById('documents-list-container');
  const tabCount = document.getElementById('docs-tab-count');
  if (!container) return;

  try {
    const res = await tenantFetch(`${API_BASE}/history/documents`);
    if (!res.ok) return;

    allDocumentsList = await res.json();
    if (tabCount) tabCount.textContent = allDocumentsList.length;

    renderDocumentsList(allDocumentsList);
  } catch (e) {
    container.innerHTML = `<div class="alert alert-error">Failed to load document library.</div>`;
  }
}

function renderDocumentsList(docs) {
  const container = document.getElementById('documents-list-container');
  if (!container) return;

  if (docs.length === 0) {
    container.innerHTML = `
      <div class="text-muted" style="text-align: center; padding: 3rem; background: var(--surface-2); border-radius: var(--radius-md);">
        No documents found in knowledge base.
      </div>
    `;
    return;
  }

  container.innerHTML = docs.map(doc => {
    const isChecked = selectedDocIds.has(doc.id);
    return `
      <div class="doc-card" data-doc-id="${doc.id}">
        <input type="checkbox" class="doc-checkbox" data-id="${doc.id}" ${isChecked ? 'checked' : ''} style="cursor: pointer; width: 18px; height: 18px;">
        <div class="doc-icon">${getFileEmoji(doc.file_type)}</div>
        <div class="doc-info">
          <div class="doc-name">${escapeHtml(doc.filename)}</div>
          <div class="doc-meta">${formatBytes(doc.file_size)} • Uploaded ${new Date(doc.created_at).toLocaleString()}</div>
        </div>
        <div class="doc-actions">
          <span class="status-pill ${doc.status === 'processed' ? 'status-ready' : 'status-processing'}">
            <span class="status-dot"></span> ${doc.status === 'processed' ? 'Processed' : 'Processing'}
          </span>
          ${doc.status === 'processed' ? `
            <a href="chat.html?file_id=${doc.id}" class="doc-action-btn action-chat">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
              Chat
            </a>
          ` : ''}
          <button class="doc-action-btn action-delete delete-single-doc-btn" data-id="${doc.id}" data-name="${escapeHtml(doc.filename)}">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            Delete
          </button>
        </div>
      </div>
    `;
  }).join('');

  container.querySelectorAll('.doc-checkbox').forEach(cb => {
    cb.addEventListener('change', (e) => {
      const id = parseInt(e.target.getAttribute('data-id'));
      if (e.target.checked) selectedDocIds.add(id);
      else selectedDocIds.delete(id);
      updateBulkDeleteBtnState();
    });
  });

  container.querySelectorAll('.delete-single-doc-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = parseInt(btn.getAttribute('data-id'));
      const name = btn.getAttribute('data-name');
      openDeleteModal(`Are you sure you want to delete "${name}"? This action cannot be undone.`, async () => {
        try {
          const res = await tenantFetch(`${API_BASE}/history/document/${id}`, { method: 'DELETE' });
          if (res.ok) {
            sound.success();
            selectedDocIds.delete(id);
            loadDocumentsHistory();
          }
        } catch (e) { }
      });
    });
  });
}

function updateBulkDeleteBtnState() {
  const bulkBtn = document.getElementById('bulk-delete-btn');
  const countEl = document.getElementById('selected-count');
  if (countEl) countEl.textContent = selectedDocIds.size;
  if (bulkBtn) bulkBtn.disabled = selectedDocIds.size === 0;
}

function openDeleteModal(message, onConfirm) {
  const modal = document.getElementById('delete-modal');
  const msgEl = document.getElementById('delete-modal-msg');
  if (msgEl) msgEl.textContent = message;
  pendingDeleteTarget = onConfirm;
  if (modal) modal.classList.remove('hidden');
}

async function loadSessionsHistory() {
  const container = document.getElementById('sessions-list-container');
  const tabCount = document.getElementById('sessions-tab-count');
  if (!container) return;

  try {
    const res = await tenantFetch(`${API_BASE}/history/sessions`);
    if (!res.ok) return;

    const rawSessions = await res.json();
    const sessions = rawSessions.filter(s => s.messages && s.messages.length > 0);
    if (tabCount) tabCount.textContent = sessions.length;

    if (sessions.length === 0) {
      container.innerHTML = `
        <div class="text-muted" style="text-align: center; padding: 3rem; background: var(--surface-2); border-radius: var(--radius-md);">
          No past chat sessions found.
        </div>
      `;
      return;
    }

    container.innerHTML = sessions.map(s => {
      const msgCount = s.messages ? s.messages.length : 0;
      const firstMsg = s.messages && s.messages.length > 0 ? s.messages[0].content : 'Empty Session';
      const previewTitle = firstMsg.length > 65 ? firstMsg.substring(0, 65) + '...' : firstMsg;

      const msgsHtml = (s.messages || []).map(m => {
        let formattedHtml = formatRichContent(m.content);

        let sourcesHtml = '';
        const parsedSources = parsePythonList(m.sources);
        if (parsedSources && parsedSources.length > 0) {
          sourcesHtml = `
            <details style="margin-top: 0.6rem; cursor: pointer; font-size: 0.8rem; color: var(--accent);">
              <summary style="font-weight: 600;"> Source References (${parsedSources.length})</summary>
              <ul style="margin-top: 0.4rem; padding-left: 1.2rem; color: var(--text-muted);">
                ${parsedSources.map(src => `<li>${escapeHtml(src)}</li>`).join('')}
              </ul>
            </details>
          `;
        }

        let timestampsHtml = '';
        const parsedTimestamps = parsePythonList(m.timestamp_references);
        if (parsedTimestamps && parsedTimestamps.length > 0) {
          timestampsHtml = `
            <div style="margin-top: 0.4rem; display: flex; gap: 0.4rem; flex-wrap: wrap;">
              ${parsedTimestamps.map(ts => `<span class="badge badge-yellow"> ${escapeHtml(typeof ts === 'object' ? ts.time || JSON.stringify(ts) : ts)}</span>`).join('')}
            </div>
          `;
        }

        return `
          <div class="hmsg hmsg-${m.role === 'user' ? 'user' : 'ai'}">
            <div class="hmsg-label">${m.role === 'user' ? 'You' : 'CogniSphere'}</div>
            <div>${formattedHtml} ${sourcesHtml} ${timestampsHtml}</div>
          </div>
        `;
      }).join('');

      return `
        <div class="session-card">
          <div class="session-header">
            <div>
              <div class="session-title">Session #${s.session_id} — ${escapeHtml(previewTitle)}</div>
              <div class="session-meta">${msgCount} messages exchanged</div>
            </div>
            <div class="flex items-center gap-sm">
              <a href="chat.html?session_id=${s.session_id}" class="btn btn-primary btn-xs"> Resume Chat</a>
              <span class="session-chevron"></span>
            </div>
          </div>
          <div class="session-body">
            <div class="session-msgs">
              ${msgsHtml}
            </div>
          </div>
        </div>
      `;
    }).join('');

    container.querySelectorAll('.session-header').forEach(header => {
      header.addEventListener('click', (e) => {
        if (e.target.closest('a')) return;
        const card = header.closest('.session-card');
        card.classList.toggle('open');
        sound.click();
      });
    });

  } catch (e) {
    container.innerHTML = `<div class="alert alert-error">Failed to load session history.</div>`;
  }
}

// ─── Ultra-Smooth Water Wave Theme Engine ────────────────────────────────────
class WaterWaveThemeEngine {
  constructor() {
    this.canvas = null;
    this.ctx = null;
    this.animating = false;
    this.animationId = null;
    // Default to dark mode unless stored preference is light
    this.theme = localStorage.getItem('cognisphere_theme') || 'dark';
    this.initImmediateTheme();
  }

  initImmediateTheme() {
    document.documentElement.setAttribute('data-theme', this.theme);
  }

  init() {
    this.injectButton();
    this.setupCanvas();
  }

  injectButton() {
    // Mode switcher button is accessible on every page inside the menu sidebar
    if (document.getElementById('theme-toggle-btn')) return;

    let slot = document.querySelector('.sidebar-theme-slot');
    if (!slot) {
      const sidebarNav = document.querySelector('.sidebar-nav');
      if (!sidebarNav) return;
      slot = document.createElement('div');
      slot.className = 'sidebar-theme-slot';
      sidebarNav.parentNode.insertBefore(slot, sidebarNav.nextSibling);
    }

    const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    const isDark = currentTheme === 'dark';

    slot.innerHTML = `
      <div class="sidebar-theme-wrapper" id="sidebar-theme-wrapper">
        <div class="sidebar-theme-info">
          <span class="sidebar-theme-title">Appearance</span>
          <span class="sidebar-theme-mode" id="theme-orb-label">${isDark ? 'Dark Mode' : 'Light Mode'}</span>
        </div>
        <button id="theme-toggle-btn" class="theme-switch-orb" aria-label="Toggle light and dark mode" title="Switch Theme (Liquid Wave)">
          <div class="orb-glass-shell">
            <div class="orb-liquid-wrapper">
              <svg class="orb-mini-wave wave-1" viewBox="0 0 100 20" preserveAspectRatio="none">
                <path d="M0,10 Q25,18 50,10 T100,10 V20 H0 Z" fill="currentColor"></path>
              </svg>
              <svg class="orb-mini-wave wave-2" viewBox="0 0 100 20" preserveAspectRatio="none">
                <path d="M0,12 Q25,4 50,12 T100,12 V20 H0 Z" fill="currentColor"></path>
              </svg>
            </div>
            <div class="orb-icon-container">
              <svg class="orb-icon icon-moon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
              </svg>
              <svg class="orb-icon icon-sun" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="5"></circle>
                <line x1="12" y1="1" x2="12" y2="3"></line>
                <line x1="12" y1="21" x2="12" y2="23"></line>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
                <line x1="1" y1="12" x2="3" y2="12"></line>
                <line x1="21" y1="12" x2="23" y2="12"></line>
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
              </svg>
            </div>
          </div>
        </button>
      </div>
    `;

    const btn = document.getElementById('theme-toggle-btn');
    if (btn) {
      btn.addEventListener('click', () => this.toggleTheme());
    }
  }

  setupCanvas() {
    if (this.canvas) return;
    this.canvas = document.createElement('canvas');
    this.canvas.id = 'liquid-wave-canvas';
    this.canvas.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      max-width: 100vw;
      max-height: 100vh;
      overflow: hidden;
      pointer-events: none;
      z-index: 999999;
      opacity: 0;
      transition: opacity 0.25s ease;
    `;
    // Append to documentElement (<html>) so body.style.transform does not break position: fixed
    document.documentElement.appendChild(this.canvas);
    this.ctx = this.canvas.getContext('2d');
  }

  toggleTheme() {
    if (this.animating) return;
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    const targetTheme = currentTheme === 'dark' ? 'light' : 'dark';
    this.startWaterWaveAnimation(targetTheme);
  }

  startWaterWaveAnimation(targetTheme) {
    this.animating = true;
    this.setupCanvas();

    const dpr = Math.max(1, window.devicePixelRatio || 1);

    // Always measure exact viewport window dimensions
    const width = window.innerWidth || document.documentElement.clientWidth;
    const height = window.innerHeight || document.documentElement.clientHeight;

    this.canvas.width = width * dpr;
    this.canvas.height = height * dpr;
    this.canvas.style.opacity = '1';
    this.ctx.scale(dpr, dpr);

    const isTargetLight = targetTheme === 'light';

    if (window.sound && typeof window.sound.playTone === 'function') {
      window.sound.playTone(isTargetLight ? 340 : 460, 0.12, 'sine', 0.1);
      setTimeout(() => window.sound.playTone(isTargetLight ? 520 : 380, 0.18, 'sine', 0.12), 140);
      setTimeout(() => window.sound.playTone(isTargetLight ? 680 : 260, 0.22, 'sine', 0.08), 320);
    }

    // Dynamic rising bubbles inside liquid
    const bubbleCount = 45;
    const bubbles = [];
    for (let i = 0; i < bubbleCount; i++) {
      bubbles.push({
        x: Math.random() * width,
        yOffset: Math.random() * height * 0.85,
        radius: 2 + Math.random() * 6.5,
        speed: 1.8 + Math.random() * 3.8,
        wobbleSpeed: 0.02 + Math.random() * 0.04,
        opacity: 0.35 + Math.random() * 0.55
      });
    }

    const duration = 1650;
    const startTime = performance.now();
    let themeSwapped = false;

    const animate = (now) => {
      const elapsed = now - startTime;
      const linearProgress = Math.min(1, elapsed / duration);

      // Waves ALWAYS start at window bottom (height + 80) and rise to top (-80)
      const progress = Math.pow(linearProgress, 1.4);
      const startY = height + 80;
      const endY = -80;
      const waterY = startY + (endY - startY) * progress;

      if (linearProgress >= 0.52 && !themeSwapped) {
        themeSwapped = true;
        document.documentElement.setAttribute('data-theme', targetTheme);
        localStorage.setItem('cognisphere_theme', targetTheme);

        const labelEl = document.getElementById('theme-orb-label');
        if (labelEl) labelEl.textContent = targetTheme === 'dark' ? 'Dark Mode' : 'Light Mode';
      }

      // Dynamic Shaking / Wave displacement on main content container only (keeps sidebar static and sticky)
      const mainEl = document.querySelector('.main-content') || document.querySelector('.chat-main');
      if (linearProgress > 0.12 && linearProgress < 0.78) {
        const shakeIntensity = Math.sin((linearProgress - 0.12) / 0.66 * Math.PI) * 3;
        const shakeY = (Math.cos(now * 0.03) * shakeIntensity * 0.5);
        if (mainEl) {
          mainEl.style.transform = `translate3d(0, ${shakeY.toFixed(2)}px, 0)`;
        }
      } else {
        if (mainEl) mainEl.style.transform = 'none';
      }

      this.ctx.clearRect(0, 0, width, height);

      // Water Color Gradients:
      // Dark -> Light: Shimmering aqua tide turning into crisp light mode surface
      // Light -> Dark: Deep sapphire wave turning into sleek dark mode surface
      const grad = this.ctx.createLinearGradient(0, Math.max(0, waterY - 50), 0, height);
      if (isTargetLight) {
        grad.addColorStop(0, 'rgba(15, 82, 87, 0.98)');
        grad.addColorStop(0.3, 'rgba(47, 107, 63, 0.96)');
        grad.addColorStop(0.7, 'rgba(111, 189, 182, 0.97)');
        grad.addColorStop(1, 'rgba(242, 243, 240, 0.99)');
      } else {
        grad.addColorStop(0, 'rgba(111, 189, 182, 0.98)');
        grad.addColorStop(0.25, 'rgba(15, 82, 87, 0.97)');
        grad.addColorStop(0.65, 'rgba(22, 27, 30, 0.98)');
        grad.addColorStop(1, 'rgba(15, 19, 21, 0.99)');
      }

      const t = now * 0.0035;

      // Layer 1: Deep back wave
      this.drawWaveLayer(width, height, waterY + 8, 28, 0.006, t * 1.3, 'rgba(15, 82, 87, 0.45)');

      // Layer 2: Mid wave
      this.drawWaveLayer(width, height, waterY + 4, 18, 0.013, -t * 1.6, 'rgba(111, 189, 182, 0.55)');

      // Layer 3: Front wave crest with gradient fill & glowing highlights
      this.drawMainWave(width, height, waterY, grad, t, isTargetLight);

      // Draw Foam & Rising Bubbles
      this.drawBubbles(width, height, waterY, bubbles, now, isTargetLight);

      if (linearProgress < 1) {
        this.animationId = requestAnimationFrame(animate);
      } else {
        if (mainEl) mainEl.style.transform = 'none';
        this.canvas.style.opacity = '0';
        setTimeout(() => {
          this.ctx.clearRect(0, 0, width, height);
          this.animating = false;
        }, 250);
      }
    };

    this.animationId = requestAnimationFrame(animate);
  }

  drawWaveLayer(w, h, baseY, amplitude, freq, timeShift, color) {
    this.ctx.save();
    this.ctx.fillStyle = color;
    this.ctx.beginPath();
    this.ctx.moveTo(0, h);
    for (let x = 0; x <= w + 10; x += 10) {
      const y = baseY + Math.sin(x * freq + timeShift) * amplitude;
      this.ctx.lineTo(x, y);
    }
    this.ctx.lineTo(w, h);
    this.ctx.closePath();
    this.ctx.fill();
    this.ctx.restore();
  }

  drawMainWave(w, h, baseY, gradientFill, t, isTargetLight) {
    this.ctx.save();
    this.ctx.fillStyle = gradientFill;
    this.ctx.beginPath();
    this.ctx.moveTo(0, h);

    const step = 6;
    const crestPoints = [];

    for (let x = 0; x <= w + step; x += step) {
      const wave1 = Math.sin(x * 0.008 + t * 2.3) * 24;
      const wave2 = Math.cos(x * 0.016 - t * 1.9) * 14;
      const turbulence = Math.sin(x * 0.035 + t * 4.5) * 5;
      const y = baseY + wave1 + wave2 + turbulence;

      crestPoints.push({ x, y });
      this.ctx.lineTo(x, y);
    }

    this.ctx.lineTo(w, h);
    this.ctx.closePath();
    this.ctx.fill();

    // Crest highlight edge
    this.ctx.beginPath();
    this.ctx.strokeStyle = isTargetLight ? 'rgba(255, 255, 255, 0.9)' : 'rgba(111, 189, 182, 0.95)';
    this.ctx.lineWidth = 3.5;
    this.ctx.shadowBlur = 14;
    this.ctx.shadowColor = isTargetLight ? '#6FBDB6' : '#FFFFFF';

    for (let i = 0; i < crestPoints.length; i++) {
      const pt = crestPoints[i];
      if (i === 0) this.ctx.moveTo(pt.x, pt.y);
      else this.ctx.lineTo(pt.x, pt.y);
    }
    this.ctx.stroke();
    this.ctx.restore();
  }

  drawBubbles(w, h, waterY, bubbles, now, isTargetLight) {
    this.ctx.save();
    for (let b of bubbles) {
      const bubbleY = waterY + b.yOffset - ((now * 0.08 * b.speed) % (h * 0.75));
      if (bubbleY > waterY - 12 && bubbleY < h) {
        const bubbleX = b.x + Math.sin(now * b.wobbleSpeed) * 16;

        this.ctx.beginPath();
        this.ctx.arc(bubbleX, bubbleY, b.radius, 0, Math.PI * 2);
        this.ctx.fillStyle = isTargetLight
          ? `rgba(255, 255, 255, ${b.opacity})`
          : `rgba(111, 189, 182, ${b.opacity})`;
        this.ctx.fill();

        this.ctx.beginPath();
        this.ctx.arc(bubbleX - b.radius * 0.35, bubbleY - b.radius * 0.35, b.radius * 0.3, 0, Math.PI * 2);
        this.ctx.fillStyle = 'rgba(255, 255, 255, 0.75)';
        this.ctx.fill();
      }
    }
    this.ctx.restore();
  }
}

const waterWaveTheme = new WaterWaveThemeEngine();
window.waterWaveTheme = waterWaveTheme;