/* ===================================================
   PULSE CHAT — Global Media Player
   Audio persists across chats, custom video player
   =================================================== */

const MediaPlayer = {
  _audio: null,
  _current: null,  // {url, title, artist, duration}
  _queue: [],
  _queueIdx: -1,
  _interval: null,
  _visible: false,

  // ══════════════════════════════════════════
  // PLAY AUDIO (from message or queue)
  // ══════════════════════════════════════════
  play(url, title, artist) {
    // Stop voice messages if playing
    if (typeof Voice !== 'undefined' && Voice._currentAudio) {
      Voice._currentAudio.pause();
      Voice._currentAudio = null;
    }

    if (this._audio && this._current?.url === url) {
      // Toggle play/pause same track
      if (this._audio.paused) {
        this._audio.play();
        this._updateUI(true);
      } else {
        this._audio.pause();
        this._updateUI(false);
      }
      return;
    }

    // New track
    if (this._audio) { this._audio.pause(); clearInterval(this._interval); }
    
    this._audio = new Audio(url);
    this._current = { url, title: title || 'Аудио', artist: artist || '' };
    
    this._audio.play().catch(e => console.warn('Play failed:', e));
    this._show();
    this._updateUI(true);
    this._startProgress();

    this._audio.onended = () => {
      if (this._queueIdx < this._queue.length - 1) {
        this.next();
      } else {
        this._updateUI(false);
        clearInterval(this._interval);
      }
    };

    this._audio.onerror = () => {
      this._updateUI(false);
    };
  },

  // ══════════════════════════════════════════
  // QUEUE MANAGEMENT
  // ══════════════════════════════════════════
  setQueue(tracks, startIdx) {
    // tracks = [{url, title, artist}]
    this._queue = tracks;
    this._queueIdx = startIdx || 0;
    if (this._queue.length > 0) {
      const t = this._queue[this._queueIdx];
      this.play(t.url, t.title, t.artist);
    }
  },

  next() {
    if (this._queueIdx < this._queue.length - 1) {
      this._queueIdx++;
      const t = this._queue[this._queueIdx];
      this.play(t.url, t.title, t.artist);
    }
  },

  prev() {
    if (this._audio && this._audio.currentTime > 3) {
      this._audio.currentTime = 0;
      return;
    }
    if (this._queueIdx > 0) {
      this._queueIdx--;
      const t = this._queue[this._queueIdx];
      this.play(t.url, t.title, t.artist);
    }
  },

  // ══════════════════════════════════════════
  // CONTROLS
  // ══════════════════════════════════════════
  toggle() {
    if (!this._audio) return;
    if (this._audio.paused) {
      this._audio.play();
      this._updateUI(true);
      this._startProgress();
    } else {
      this._audio.pause();
      this._updateUI(false);
      clearInterval(this._interval);
    }
  },

  seek(pct) {
    if (!this._audio || !this._audio.duration) return;
    this._audio.currentTime = (pct / 100) * this._audio.duration;
  },

  close() {
    if (this._audio) {
      this._audio.pause();
      this._audio = null;
    }
    this._current = null;
    this._queue = [];
    this._queueIdx = -1;
    clearInterval(this._interval);
    this._hide();
  },

  // ══════════════════════════════════════════
  // UI: Global player bar
  // ══════════════════════════════════════════
  _show() {
    let bar = document.getElementById('globalPlayerBar');
    if (!bar) {
      bar = document.createElement('div');
      bar.id = 'globalPlayerBar';
      bar.className = 'global-player';
      bar.innerHTML = `
        <div class="gp-progress-track" onclick="MediaPlayer._seekClick(event)">
          <div class="gp-progress-fill" id="gpProgress"></div>
        </div>
        <button class="gp-btn" onclick="MediaPlayer.prev()"><i class="fa-solid fa-backward-step"></i></button>
        <button class="gp-btn gp-play" onclick="MediaPlayer.toggle()" id="gpPlayBtn"><i class="fa-solid fa-play"></i></button>
        <button class="gp-btn" onclick="MediaPlayer.next()"><i class="fa-solid fa-forward-step"></i></button>
        <div class="gp-info">
          <div class="gp-title" id="gpTitle">Аудио</div>
          <div class="gp-artist" id="gpArtist"></div>
        </div>
        <span class="gp-time" id="gpTime">0:00</span>
        <button class="gp-btn" onclick="MediaPlayer.close()"><i class="fa-solid fa-xmark"></i></button>
      `;
      // Insert at top of page-chat
      const chatPage = document.getElementById('page-chat');
      if (chatPage) chatPage.insertBefore(bar, chatPage.firstChild);
      else document.body.prepend(bar);
    }
    bar.style.display = 'flex';
    this._visible = true;
  },

  _hide() {
    const bar = document.getElementById('globalPlayerBar');
    if (bar) bar.style.display = 'none';
    this._visible = false;
  },

  _updateUI(isPlaying) {
    const btn = document.getElementById('gpPlayBtn');
    if (btn) btn.innerHTML = isPlaying
      ? '<i class="fa-solid fa-pause"></i>'
      : '<i class="fa-solid fa-play"></i>';
    
    const title = document.getElementById('gpTitle');
    if (title && this._current) title.textContent = this._current.title;
    
    const artist = document.getElementById('gpArtist');
    if (artist && this._current) artist.textContent = this._current.artist;
  },

  _startProgress() {
    clearInterval(this._interval);
    this._interval = setInterval(() => {
      if (!this._audio || this._audio.paused) return;
      const pct = (this._audio.currentTime / (this._audio.duration || 1)) * 100;
      const fill = document.getElementById('gpProgress');
      if (fill) fill.style.width = pct + '%';
      
      const timeEl = document.getElementById('gpTime');
      if (timeEl) {
        const cur = Math.floor(this._audio.currentTime);
        const m = Math.floor(cur / 60);
        const s = cur % 60;
        timeEl.textContent = `${m}:${s.toString().padStart(2, '0')}`;
      }
    }, 250);
  },

  _seekClick(e) {
    const track = e.currentTarget;
    const rect = track.getBoundingClientRect();
    const pct = ((e.clientX - rect.left) / rect.width) * 100;
    this.seek(Math.max(0, Math.min(100, pct)));
  },

  // ══════════════════════════════════════════
  // CUSTOM VIDEO PLAYER (replaces default)
  // ══════════════════════════════════════════
  renderVideo(url, msgId) {
    return `
      <div class="custom-video" id="vid_${msgId}">
        <video src="${url}" preload="metadata" onclick="MediaPlayer.videoToggle('${msgId}')" playsinline></video>
        <div class="cv-overlay" id="vidOverlay_${msgId}" onclick="MediaPlayer.videoToggle('${msgId}')">
          <button class="cv-play"><i class="fa-solid fa-play"></i></button>
        </div>
        <div class="cv-controls" id="vidControls_${msgId}">
          <button class="cv-btn" onclick="MediaPlayer.videoToggle('${msgId}')">
            <i class="fa-solid fa-play" id="vidIcon_${msgId}"></i>
          </button>
          <div class="cv-progress" onclick="MediaPlayer.videoSeek(event, '${msgId}')">
            <div class="cv-progress-fill" id="vidProgress_${msgId}"></div>
          </div>
          <span class="cv-time" id="vidTime_${msgId}">0:00</span>
          <button class="cv-btn" onclick="MediaPlayer.videoPiP('${msgId}')">
            <i class="fa-solid fa-up-right-and-down-left-from-center"></i>
          </button>
        </div>
      </div>
    `;
  },

  videoToggle(msgId) {
    const container = document.getElementById(`vid_${msgId}`);
    const video = container?.querySelector('video');
    const icon = document.getElementById(`vidIcon_${msgId}`);
    const overlay = document.getElementById(`vidOverlay_${msgId}`);
    if (!video) return;

    if (video.paused) {
      video.play();
      icon.className = 'fa-solid fa-pause';
      overlay.style.display = 'none';
      this._startVideoProgress(msgId, video);
    } else {
      video.pause();
      icon.className = 'fa-solid fa-play';
      overlay.style.display = 'flex';
    }
  },

  _startVideoProgress(msgId, video) {
    const update = () => {
      if (video.paused) return;
      const pct = (video.currentTime / (video.duration || 1)) * 100;
      const fill = document.getElementById(`vidProgress_${msgId}`);
      if (fill) fill.style.width = pct + '%';
      const time = document.getElementById(`vidTime_${msgId}`);
      if (time) {
        const s = Math.floor(video.currentTime);
        time.textContent = `${Math.floor(s/60)}:${(s%60).toString().padStart(2,'0')}`;
      }
      requestAnimationFrame(update);
    };
    requestAnimationFrame(update);
    
    video.onended = () => {
      const icon = document.getElementById(`vidIcon_${msgId}`);
      const overlay = document.getElementById(`vidOverlay_${msgId}`);
      if (icon) icon.className = 'fa-solid fa-play';
      if (overlay) overlay.style.display = 'flex';
    };
  },

  videoSeek(e, msgId) {
    const container = document.getElementById(`vid_${msgId}`);
    const video = container?.querySelector('video');
    if (!video || !video.duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    video.currentTime = pct * video.duration;
  },

  videoPiP(msgId) {
    const container = document.getElementById(`vid_${msgId}`);
    const video = container?.querySelector('video');
    if (video && document.pictureInPictureEnabled) {
      video.requestPictureInPicture().catch(() => {});
    }
  },
};
