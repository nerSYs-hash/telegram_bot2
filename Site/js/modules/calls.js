/* ===================================================
   PULSE CHAT — WebRTC Calls (Audio + Video)
   Day 12: 1-on-1 calls via signaling server
   =================================================== */

const Calls = {
  _pc: null,           // RTCPeerConnection
  _localStream: null,
  _remoteStream: null,
  _callState: 'idle',  // idle | calling | ringing | active
  _peerId: null,
  _peerName: '',
  _isVideo: false,
  _isMuted: false,
  _isCamOff: false,
  _timer: null,
  _startTime: 0,

  STUN: { urls: 'stun:stun.l.google.com:19302' },

  // ══════════════════════════════════════════
  // INITIATE CALL
  // ══════════════════════════════════════════
  async startCall(userId, userName, video = false) {
    if (this._callState !== 'idle') return;
    this._peerId = userId;
    this._peerName = userName;
    this._isVideo = video;
    this._callState = 'calling';

    this._showCallScreen('calling');

    try {
      const r = await API.request('/api/call/start', {
        method: 'POST',
        body: JSON.stringify({ caller_id: State.currentUser.id, callee_id: userId, video })
      });
      if (r.status === 'error') {
        this._showToast(r.detail || 'Не удалось позвонить');
        this.endCall();
        return;
      }

      // Get local media
      this._localStream = await navigator.mediaDevices.getUserMedia({
        audio: true,
        video: video ? { width: 640, height: 480 } : false,
      });
      if (video) this._showLocalVideo();

      // Create peer connection and offer
      this._createPC();
      this._localStream.getTracks().forEach(t => this._pc.addTrack(t, this._localStream));

      const offer = await this._pc.createOffer();
      await this._pc.setLocalDescription(offer);

      await API.request('/api/call/signal', {
        method: 'POST',
        body: JSON.stringify({
          from_id: State.currentUser.id, to_id: userId,
          signal_type: 'offer', data: { sdp: offer.sdp, type: offer.type },
        })
      });
    } catch (e) {
      console.error('Call start error:', e);
      this._showToast('Ошибка: нет доступа к микрофону');
      this.endCall();
    }
  },

  // ══════════════════════════════════════════
  // RECEIVE CALL
  // ══════════════════════════════════════════
  async handleIncoming(callerId, callerName, video) {
    if (this._callState !== 'idle') {
      // Already in a call — auto reject
      await API.request('/api/call/signal', {
        method: 'POST',
        body: JSON.stringify({ from_id: State.currentUser.id, to_id: callerId, signal_type: 'reject' })
      });
      return;
    }

    this._peerId = callerId;
    this._peerName = callerName;
    this._isVideo = video;
    this._callState = 'ringing';
    this._showCallScreen('ringing');

    // Play ringtone
    if (typeof Notify !== 'undefined') Notify.playSound();
  },

  async acceptCall() {
    if (this._callState !== 'ringing') return;
    this._callState = 'active';

    try {
      this._localStream = await navigator.mediaDevices.getUserMedia({
        audio: true,
        video: this._isVideo ? { width: 640, height: 480 } : false,
      });
      if (this._isVideo) this._showLocalVideo();

      this._createPC();
      this._localStream.getTracks().forEach(t => this._pc.addTrack(t, this._localStream));
      this._showCallScreen('active');
    } catch (e) {
      this._showToast('Ошибка доступа к микрофону');
      this.endCall();
    }
  },

  rejectCall() {
    API.request('/api/call/signal', {
      method: 'POST',
      body: JSON.stringify({ from_id: State.currentUser.id, to_id: this._peerId, signal_type: 'reject' })
    }).catch(() => {});
    this.endCall();
  },

  // ══════════════════════════════════════════
  // SIGNALING HANDLER (called from WS)
  // ══════════════════════════════════════════
  async handleSignal(signalType, fromId, data) {
    if (signalType === 'offer') {
      if (!this._pc) return;
      await this._pc.setRemoteDescription(new RTCSessionDescription(data));
      const answer = await this._pc.createAnswer();
      await this._pc.setLocalDescription(answer);

      await API.request('/api/call/signal', {
        method: 'POST',
        body: JSON.stringify({
          from_id: State.currentUser.id, to_id: fromId,
          signal_type: 'answer', data: { sdp: answer.sdp, type: answer.type },
        })
      });
    }
    else if (signalType === 'answer') {
      if (!this._pc) return;
      await this._pc.setRemoteDescription(new RTCSessionDescription(data));
      this._callState = 'active';
      this._showCallScreen('active');
    }
    else if (signalType === 'ice') {
      if (this._pc && data) {
        await this._pc.addIceCandidate(new RTCIceCandidate(data)).catch(() => {});
      }
    }
    else if (signalType === 'reject') {
      this._showToast('Звонок отклонён');
      this.endCall();
    }
    else if (signalType === 'end') {
      this._showToast('Звонок завершён');
      this.endCall();
    }
  },

  // ══════════════════════════════════════════
  // PEER CONNECTION
  // ══════════════════════════════════════════
  _createPC() {
    this._pc = new RTCPeerConnection({ iceServers: [this.STUN] });

    this._pc.onicecandidate = (e) => {
      if (e.candidate) {
        API.request('/api/call/signal', {
          method: 'POST',
          body: JSON.stringify({
            from_id: State.currentUser.id, to_id: this._peerId,
            signal_type: 'ice', data: e.candidate.toJSON(),
          })
        }).catch(() => {});
      }
    };

    this._pc.ontrack = (e) => {
      this._remoteStream = e.streams[0];
      const audio = document.getElementById('callRemoteAudio');
      const video = document.getElementById('callRemoteVideo');
      if (this._isVideo && video) { video.srcObject = this._remoteStream; video.style.display = 'block'; }
      else if (audio) { audio.srcObject = this._remoteStream; }
    };

    this._pc.onconnectionstatechange = () => {
      if (this._pc?.connectionState === 'disconnected' || this._pc?.connectionState === 'failed') {
        this.endCall();
      }
    };
  },

  // ══════════════════════════════════════════
  // CONTROLS
  // ══════════════════════════════════════════
  toggleMute() {
    this._isMuted = !this._isMuted;
    this._localStream?.getAudioTracks().forEach(t => { t.enabled = !this._isMuted; });
    const btn = document.getElementById('callMuteBtn');
    if (btn) btn.innerHTML = this._isMuted
      ? '<i class="fa-solid fa-microphone-slash"></i>'
      : '<i class="fa-solid fa-microphone"></i>';
    btn?.classList.toggle('call-btn-active', this._isMuted);
  },

  toggleCamera() {
    this._isCamOff = !this._isCamOff;
    this._localStream?.getVideoTracks().forEach(t => { t.enabled = !this._isCamOff; });
    const btn = document.getElementById('callCamBtn');
    if (btn) btn.innerHTML = this._isCamOff
      ? '<i class="fa-solid fa-video-slash"></i>'
      : '<i class="fa-solid fa-video"></i>';
    btn?.classList.toggle('call-btn-active', this._isCamOff);
  },

  endCall() {
    // Signal end to peer
    if (this._peerId && this._callState !== 'idle') {
      API.request('/api/call/signal', {
        method: 'POST',
        body: JSON.stringify({ from_id: State.currentUser.id, to_id: this._peerId, signal_type: 'end' })
      }).catch(() => {});
    }

    // Cleanup
    this._localStream?.getTracks().forEach(t => t.stop());
    this._pc?.close();
    this._pc = null;
    this._localStream = null;
    this._remoteStream = null;
    this._callState = 'idle';
    this._peerId = null;
    this._isMuted = false;
    this._isCamOff = false;
    clearInterval(this._timer);

    this._hideCallScreen();
  },

  // ══════════════════════════════════════════
  // UI
  // ══════════════════════════════════════════
  _showCallScreen(state) {
    let screen = document.getElementById('callScreen');
    if (!screen) {
      screen = document.createElement('div');
      screen.id = 'callScreen';
      screen.className = 'call-screen';
      document.body.appendChild(screen);
    }

    const initials = this._peerName.substring(0, 2).toUpperCase();
    let statusText = '';
    let buttons = '';

    if (state === 'calling') {
      statusText = 'Вызываем...';
      buttons = `<button class="call-btn call-btn-end" onclick="Calls.endCall()"><i class="fa-solid fa-phone-slash"></i></button>`;
    }
    else if (state === 'ringing') {
      statusText = 'Входящий звонок';
      buttons = `
        <button class="call-btn call-btn-reject" onclick="Calls.rejectCall()"><i class="fa-solid fa-phone-slash"></i></button>
        <button class="call-btn call-btn-accept" onclick="Calls.acceptCall()"><i class="fa-solid fa-phone"></i></button>
      `;
    }
    else if (state === 'active') {
      statusText = '<span id="callTimer">0:00</span>';
      this._startTime = Date.now();
      this._startTimer();
      buttons = `
        <button class="call-btn" id="callMuteBtn" onclick="Calls.toggleMute()"><i class="fa-solid fa-microphone"></i></button>
        ${this._isVideo ? `<button class="call-btn" id="callCamBtn" onclick="Calls.toggleCamera()"><i class="fa-solid fa-video"></i></button>` : ''}
        <button class="call-btn call-btn-end" onclick="Calls.endCall()"><i class="fa-solid fa-phone-slash"></i></button>
      `;
    }

    screen.innerHTML = `
      <audio id="callRemoteAudio" autoplay></audio>
      <video id="callRemoteVideo" autoplay playsinline style="display:none;width:100%;max-height:70vh;border-radius:12px;background:#000"></video>
      <div class="call-info">
        <div class="call-avatar">${initials}</div>
        <div class="call-name">${escapeHTML(this._peerName)}</div>
        <div class="call-status">${statusText}</div>
        ${this._isVideo ? '<div class="call-type">Видеозвонок</div>' : ''}
      </div>
      <div class="call-controls">${buttons}</div>
      <video id="callLocalVideo" autoplay muted playsinline style="display:none"></video>
    `;
    screen.style.display = 'flex';
  },

  _hideCallScreen() {
    const screen = document.getElementById('callScreen');
    if (screen) screen.style.display = 'none';
  },

  _showLocalVideo() {
    setTimeout(() => {
      const vid = document.getElementById('callLocalVideo');
      if (vid && this._localStream) {
        vid.srcObject = this._localStream;
        vid.style.display = 'block';
      }
    }, 100);
  },

  _startTimer() {
    clearInterval(this._timer);
    this._timer = setInterval(() => {
      const secs = Math.floor((Date.now() - this._startTime) / 1000);
      const m = Math.floor(secs / 60);
      const s = secs % 60;
      const el = document.getElementById('callTimer');
      if (el) el.textContent = `${m}:${s.toString().padStart(2, '0')}`;
    }, 1000);
  },

  _showToast(msg) {
    const t = document.createElement('div');
    t.className = 'invite-toast';
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 3000);
  },
};
