/**
 * SANFFOURA — Premium Dashboard Application
 * Complete rewrite with modern JS patterns, error handling, and optimizations
 */

const APP = (() => {
  const config = {
    apiBase: '/api',
    chatContainer: '#chat-messages',
    inputField: '#chat-input',
    sendButton: '#btn-send',
    activeTab: 'chat',
    toastDuration: 4000,
  };

  const state = {
    isLoading: false,
    currentPersona: null,
    personas: [],
    messages: [],
    user: null,
  };

  /* ──────────────────────────────────────────────────────────── */
  /* Utility Functions */
  /* ──────────────────────────────────────────────────────────── */

  const utils = {
    escapeHTML: (text) => {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    },

    showToast: (message, type = 'info') => {
      const toast = document.createElement('div');
      toast.className = `toast ${type}`;
      toast.textContent = message;
      document.body.appendChild(toast);
      
      setTimeout(() => toast.classList.add('show'), 10);
      setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
      }, config.toastDuration);
    },

    showLoader: () => {
      const loader = document.querySelector('.loader');
      if (loader) loader.classList.remove('hidden');
      state.isLoading = true;
    },

    hideLoader: () => {
      const loader = document.querySelector('.loader');
      if (loader) loader.classList.add('hidden');
      state.isLoading = false;
    },

    formatDate: (date) => {
      return new Date(date).toLocaleString('ar-SA', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    },
  };

  /* ──────────────────────────────────────────────────────────── */
  /* API Methods */
  /* ──────────────────────────────────────────────────────────── */

  const api = {
    fetch: async (endpoint, options = {}) => {
      try {
        const response = await fetch(`${config.apiBase}${endpoint}`, {
          ...options,
          headers: {
            'Content-Type': 'application/json',
            ...options.headers,
          },
        });

        if (!response.ok) {
          const error = await response.json().catch(() => ({}));
          throw new Error(error.خطأ || `API Error: ${response.status}`);
        }

        return await response.json();
      } catch (error) {
        console.error('API Error:', error);
        utils.showToast(`خطأ: ${error.message}`, 'error');
        throw error;
      }
    },

    getStats: () => api.fetch('/stats'),
    getPersonas: () => api.fetch('/personas'),
    setPersona: (personaId) => api.fetch('/persona', { method: 'POST', body: JSON.stringify({ id: personaId }) }),
    sendMessage: (message) => api.fetch('/chat', { method: 'POST', body: JSON.stringify({ message }) }),
    generateImage: (prompt) => api.fetch('/image', { method: 'POST', body: JSON.stringify({ prompt }) }),
    generateTTS: (text, voice = 'ar') => api.fetch('/tts', { method: 'POST', body: JSON.stringify({ text, voice }) }),
  };

  /* ──────────────────────────────────────────────────────────── */
  /* Chat Management */
  /* ──────────────────────────────────────────────────────────── */

  const chat = {
    init: () => {
      const sendBtn = document.querySelector(config.sendButton);
      const inputField = document.querySelector(config.inputField);

      if (sendBtn) sendBtn.addEventListener('click', chat.send);
      if (inputField) {
        inputField.addEventListener('keypress', (e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chat.send();
          }
        });
      }
    },

    send: async () => {
      const inputField = document.querySelector(config.inputField);
      const message = inputField?.value.trim();

      if (!message || state.isLoading) return;

      try {
        utils.showLoader();
        inputField.value = '';

        // Add user message to UI
        chat.addMessage(message, 'user');

        // Send to API
        const response = await api.sendMessage(message);
        chat.addMessage(response.reply || '❌ لا توجد استجابة', 'assistant');
      } catch (error) {
        console.error('Chat error:', error);
      } finally {
        utils.hideLoader();
      }
    },

    addMessage: (content, role) => {
      const container = document.querySelector(config.chatContainer);
      if (!container) return;

      const messageEl = document.createElement('div');
      messageEl.className = `message message-${role}`;
      messageEl.innerHTML = `<div class="message-content">${utils.escapeHTML(content)}</div>`;
      container.appendChild(messageEl);
      container.scrollTop = container.scrollHeight;
    },

    clear: async () => {
      if (!confirm('هل تريد مسح المحادثة؟')) return;
      try {
        await api.fetch('/chat/clear', { method: 'POST' });
        const container = document.querySelector(config.chatContainer);
        if (container) container.innerHTML = '';
        utils.showToast('تم مسح المحادثة', 'success');
      } catch (error) {
        console.error('Clear chat error:', error);
      }
    },
  };

  /* ──────────────────────────────────────────────────────────── */
  /* Personas Management */
  /* ──────────────────────────────────────────────────────────── */

  const personas = {
    init: async () => {
      try {
        state.personas = await api.getPersonas();
        personas.render();
      } catch (error) {
        console.error('Failed to load personas:', error);
      }
    },

    render: () => {
      const container = document.querySelector('#personas-list');
      if (!container) return;

      container.innerHTML = state.personas
        .map((p) => `
          <div class="persona-card" data-id="${p.id}">
            <div class="persona-emoji">${p.avatar}</div>
            <h3>${p.name}</h3>
            <p>${p.description || ''}</p>
            <button class="btn btn-sm btn-primary" onclick="APP.personas.select(${p.id})">تحديد</button>
          </div>
        `)
        .join('');
    },

    select: async (personaId) => {
      try {
        await api.setPersona(personaId);
        state.currentPersona = personaId;
        personas.render();
        utils.showToast('تم تغيير الشخصية ✅', 'success');
      } catch (error) {
        console.error('Failed to select persona:', error);
      }
    },
  };

  /* ──────────────────────────────────────────────────────────── */
  /* Image Generation */
  /* ──────────────────────────────────────────────────────────── */

  const imageGen = {
    init: () => {
      const btn = document.querySelector('#btn-generate-image');
      if (btn) btn.addEventListener('click', imageGen.generate);
    },

    generate: async () => {
      const input = document.querySelector('#image-prompt');
      const prompt = input?.value.trim();

      if (!prompt) {
        utils.showToast('أدخل وصف الصورة', 'error');
        return;
      }

      try {
        utils.showLoader();
        const response = await api.generateImage(prompt);
        imageGen.displayImage(response.url || response.image);
      } catch (error) {
        console.error('Image generation error:', error);
      } finally {
        utils.hideLoader();
      }
    },

    displayImage: (imageUrl) => {
      const container = document.querySelector('#generated-image');
      if (!container) return;

      const img = document.createElement('img');
      img.src = imageUrl;
      img.alt = 'صورة مولدة';
      img.onerror = () => {
        container.innerHTML = '<p>❌ خطأ في تحميل الصورة</p>';
      };
      container.innerHTML = '';
      container.appendChild(img);
    },
  };

  /* ──────────────────────────────────────────────────────────── */
  /* Text-to-Speech */
  /* ──────────────────────────────────────────────────────────── */

  const tts = {
    init: () => {
      const btn = document.querySelector('#btn-generate-tts');
      if (btn) btn.addEventListener('click', tts.generate);
    },

    generate: async () => {
      const input = document.querySelector('#tts-text');
      const text = input?.value.trim();
      const voiceSelect = document.querySelector('#tts-voice');
      const voice = voiceSelect?.value || 'ar';

      if (!text) {
        utils.showToast('أدخل النص', 'error');
        return;
      }

      try {
        utils.showLoader();
        const response = await api.generateTTS(text, voice);
        tts.playAudio(response.audio);
      } catch (error) {
        console.error('TTS error:', error);
      } finally {
        utils.hideLoader();
      }
    },

    playAudio: (audioUrl) => {
      const audio = new Audio(audioUrl);
      audio.play().catch((e) => console.error('Playback error:', e));
    },
  };

  /* ──────────────────────────────────────────────────────────── */
  /* Navigation & Tabs */
  /* ──────────────────────────────────────────────────────────── */

  const nav = {
    init: () => {
      document.querySelectorAll('[data-tab]').forEach((btn) => {
        btn.addEventListener('click', (e) => {
          e.preventDefault();
          nav.switchTab(btn.dataset.tab);
        });
      });
    },

    switchTab: (tabName) => {
      document.querySelectorAll('[data-tab-panel]').forEach((panel) => {
        panel.classList.toggle('hidden', panel.dataset.tabPanel !== tabName);
      });

      document.querySelectorAll('[data-tab]').forEach((btn) => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
      });

      config.activeTab = tabName;
    },
  };

  /* ──────────────────────────────────────────────────────────── */
  /* Statistics */
  /* ──────────────────────────────────────────────────────────── */

  const stats = {
    init: async () => {
      try {
        const data = await api.getStats();
        stats.render(data);
      } catch (error) {
        console.error('Stats error:', error);
      }
    },

    render: (data) => {
      const container = document.querySelector('#stats-container');
      if (!container) return;

      container.innerHTML = `
        <div class="stat-item">
          <span class="stat-label">إجمالي الرسائل</span>
          <span class="stat-value">${data.total_messages || 0}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">عدد المستخدمين</span>
          <span class="stat-value">${data.total_users || 0}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">الشخصية الحالية</span>
          <span class="stat-value">${state.currentPersona || 'افتراضية'}</span>
        </div>
      `;
    },
  };

  /* ──────────────────────────────────────────────────────────── */
  /* Initialization */
  /* ──────────────────────────────────────────────────────────── */

  const init = () => {
    document.addEventListener('DOMContentLoaded', async () => {
      console.log('🚀 Initializing SANFFOURA Dashboard...');
      
      nav.init();
      chat.init();
      imageGen.init();
      tts.init();
      
      await personas.init();
      await stats.init();
      
      console.log('✅ Dashboard ready!');
    });
  };

  return {
    init,
    chat,
    personas,
    imageGen,
    tts,
    stats,
    utils,
    api,
  };
})();

/* Start the application */
APP.init();
