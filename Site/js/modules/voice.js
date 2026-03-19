/* ===================================================
   PULSE CHAT — Voice Messages Module
   Record → Upload → Custom Player
   =================================================== */

const Voice = {
  _recorder: null,
  _stream: null,
  _chunks: [],
  _startTime: 0,
  _timerInterval: null,
  _analyser: null,
  _isRecording: false,

  // ══════════════════════════════════════════
  // RECORDING
  // ══════════════════════════════════════════
  async toggleRecording() {
    if (this._isRecording) {
      this.stopAndSend();
    } else {
      this.startRecording();
    }
  },

  async startRecording() {
    try {
      this._stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      alert('Нет доступа к микрофону. Разрешите в настройках браузера.');
      return;
    }

    this._chunks = [];
    this._isRecording = true;

    // Setup MediaRecorder
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')
        ? 'audio/ogg;codecs=opus'
        : 'audio/webm';

    this._recorder = new MediaRecorder(this._stream, { mimeType });

    this._recorder.ondataavailable = (e) => {
      if (e.data.size > 0) this._chunks.push(e.data);
    };

    this._recorder.onstop = () => {
      this._stream?.getTracks().forEach(t => t.stop());
    };

    this._recorder.start(100); // Collect data every 100ms

    // Setup analyser for visual feedback
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const source = ctx.createMediaStreamSource(this._stream);
      this._analyser = ctx.createAnalyser();
      this._analyser.fftSize = 256;
      source.connect(this._analyser);
      this._audioCtx = ctx;
    } catch (e) {}

    // Show recording UI
    this._startTime = Date.now();
    document.getElementById('inputArea').style.display = 'none';
    document.getElementById('voiceRecordBar').style.display = 'flex';
    this._startTimer();
    this._animateDot();
  },

  stopAndSend() {
    if (!this._isRecording || !this._recorder) return;
    this._isRecording = false;

    this._recorder.onstop = async () => {
      this._stream?.getTracks().forEach(t => t.stop());
      this._hideRecordUI();

      const blob = new Blob(this._chunks, { type: this._recorder.mimeType });
      if (blob.size < 500) return; // Too short, ignore

      const duration = Math.round((Date.now() - this._startTime) / 1000);
      await this._uploadAndSend(blob, duration);
    };

    this._recorder.stop();
  },

  cancel() {
    this._isRecording = false;
    if (this._recorder?.state === 'recording') {
      this._recorder.stop();
    }
    this._stream?.getTracks().forEach(t => t.stop());
    this._chunks = [];
    this._hideRecordUI();
  },

  _hideRecordUI() {
    clearInterval(this._timerInterval);
    document.getElementById('voiceRecordBar').style.display = 'none';
    document.getElementById('inputArea').style.display = 'flex';
    if (this._audioCtx) {
      try { this._audioCtx.close(); } catch (e) {}
      this._audioCtx = null;
    }
  },

  _startTimer() {
    const el = document.getElementById('voiceTimer');
    this._timerInterval = setInterval(() => {
      const secs = Math.floor((Date.now() - this._startTime) / 1000);
      const m = Math.floor(secs / 60);
      const s = secs % 60;
      el.textContent = `${m}:${s.toString().padStart(2, '0')}`;
    }, 200);
  },

  _animateDot() {
    // CSS handles the pulsing animation
  },

  // ══════════════════════════════════════════
  // UPLOAD + SEND
  // ══════════════════════════════════════════
  async _uploadAndSend(blob, duration) {
    const ext = blob.type.includes('ogg') ? '.ogg' : '.webm';
    const filename = `voice_${Date.now()}${ext}`;
    const file = new File([blob], filename, { type: blob.type });

    try {
      // Upload
      const formData = new FormData();
      formData.append('file', file);
      formData.append('user_id', State.currentUser.id);

      const url = (API.baseUrl || '') + '/api/upload';
      const response = await fetch(url, { method: 'POST', body: formData });
      const uploadResult = await response.json();

      if (uploadResult.status !== 'success') {
        console.error('Voice upload failed:', uploadResult);
        return;
      }

      // Send message with voice data
      const targetId = Chat.currentTopicId || State.currentChatId;
      if (!targetId) return;

      const r = await API.request(`/api/messages/${targetId}/send`, {
        method: 'POST',
        body: JSON.stringify({
          user_id: State.currentUser.id,
          text: `🎤 Голосовое (${Voice._formatDuration(duration)})`,
          media_url: uploadResult.url,
          media_type: 'voice',
          media_name: filename,
        })
      });

      if (r.message) {
        r.message._voiceDuration = duration;
        Chat.messages.push(r.message);
        Chat._renderMessages();
      }
      if (r.bot_reply) {
        Chat.messages.push(r.bot_reply);
        Chat._renderMessages();
      }
      Sidebar.render();

    } catch (e) {
      console.error('Voice send error:', e);
    }
  },

  // ══════════════════════════════════════════
  // CUSTOM PLAYER (renders in bubble)
  // ══════════════════════════════════════════
  renderPlayer(url, msgId, duration) {
    const dur = duration || 0;
    const bars = Voice._generateBars();

    return `
      <div class="voice-player" id="vp_${msgId}" data-url="${url}" data-dur="${dur}">
        <button class="voice-play-btn" onclick="Voice.playToggle('${msgId}')">
          <i class="fa-solid fa-play" id="vpIcon_${msgId}"></i>
        </button>
        <div class="voice-wave" id="vpWave_${msgId}">
          ${bars}
        </div>
        <span class="voice-duration" id="vpDur_${msgId}">${Voice._formatDuration(dur)}</span>
      </div>
    `;
  },

  _generateBars() {
    // Generate random waveform bars (28 bars)
    let html = '';
    for (let i = 0; i < 28; i++) {
      const h = 4 + Math.random() * 18;
      html += `<div class="voice-bar" style="height:${h}px"></div>`;
    }
    return html;
  },

  // ══════════════════════════════════════════
  // PLAYBACK
  // ══════════════════════════════════════════
  _currentAudio: null,
  _currentMsgId: null,
  _playInterval: null,

  playToggle(msgId) {
    const container = document.getElementById(`vp_${msgId}`);
    if (!container) return;
    const url = container.dataset.url;
    const icon = document.getElementById(`vpIcon_${msgId}`);
    const durEl = document.getElementById(`vpDur_${msgId}`);
    const wave = document.getElementById(`vpWave_${msgId}`);

    // If already playing this one — pause
    if (this._currentMsgId === msgId && this._currentAudio && !this._currentAudio.paused) {
      this._currentAudio.pause();
      icon.className = 'fa-solid fa-play';
      clearInterval(this._playInterval);
      return;
    }

    // Stop any other playing voice
    if (this._currentAudio) {
      this._currentAudio.pause();
      this._currentAudio.currentTime = 0;
      const oldIcon = document.getElementById(`vpIcon_${this._currentMsgId}`);
      if (oldIcon) oldIcon.className = 'fa-solid fa-play';
      this._resetBars(this._currentMsgId);
      clearInterval(this._playInterval);
    }

    // Play
    this._currentAudio = new Audio(url);
    this._currentMsgId = msgId;
    icon.className = 'fa-solid fa-pause';

    this._currentAudio.play().catch(() => {
      icon.className = 'fa-solid fa-play';
    });

    // Animate bars during playback
    const bars = wave?.querySelectorAll('.voice-bar') || [];
    const totalBars = bars.length;

    this._playInterval = setInterval(() => {
      if (!this._currentAudio || this._currentAudio.paused) return;
      const progress = this._currentAudio.currentTime / (this._currentAudio.duration || 1);
      const activeCount = Math.floor(progress * totalBars);

      bars.forEach((bar, i) => {
        bar.classList.toggle('active', i <= activeCount);
      });

      // Update time
      const remaining = Math.max(0, (this._currentAudio.duration || 0) - this._currentAudio.currentTime);
      durEl.textContent = Voice._formatDuration(Math.ceil(remaining));
    }, 100);

    this._currentAudio.onended = () => {
      icon.className = 'fa-solid fa-play';
      clearInterval(this._playInterval);
      this._resetBars(msgId);
      const origDur = parseInt(container.dataset.dur) || 0;
      durEl.textContent = Voice._formatDuration(origDur);
    };
  },

  _resetBars(msgId) {
    const wave = document.getElementById(`vpWave_${msgId}`);
    wave?.querySelectorAll('.voice-bar').forEach(b => b.classList.remove('active'));
  },

  // ══════════════════════════════════════════
  // UTILS
  // ══════════════════════════════════════════
  _formatDuration(secs) {
    if (!secs || secs < 0) return '0:00';
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  },

  // Parse duration from text like "🎤 Голосовое (0:15)"
  parseDuration(text) {
    const match = text?.match(/\((\d+):(\d+)\)/);
    if (match) return parseInt(match[1]) * 60 + parseInt(match[2]);
    return 0;
  },
};
