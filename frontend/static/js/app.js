/* ═══════════════════════════════════════════════════════════════════
   ResumeFlow Interview Studio — Main Application
   ═══════════════════════════════════════════════════════════════════ */

const API = `${window.location.protocol}//${window.location.host}/api`;

/* ── Application State ─────────────────────────────────────────── */
const State = {
  resumeId: null,
  sessionId: null,
  profile: null,
  questions: [],
  currentQuestionIdx: 0,
  isRecording: false,
  isPaused: false,
  interviewStartTime: null,
  timerInterval: null,
  questionStartTime: null,
  elapsedSeconds: 0,
  transcripts: [],
  consentGiven: false,
  voiceAvailable: false,
};

/* ── Main App Controller ───────────────────────────────────────── */
const App = {
  /* ── Navigation ────────────────────────────────────────────── */
  navigate(view) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    const el = document.getElementById(`view-${view}`);
    if (el) el.classList.add('active');
    window.scrollTo(0, 0);
    this.updateNav(view);
  },

  updateNav(view) {
    const nav = document.getElementById('navActions');
    if (view === 'landing') {
      nav.innerHTML = `<button class="btn btn--primary btn--sm" onclick="App.navigate('upload')">Start Interview</button>`;
    } else if (view === 'interview') {
      nav.innerHTML = `<span style="font-size:0.78rem;color:var(--text-secondary)">Interview in progress</span>`;
    } else if (view === 'results') {
      nav.innerHTML = `
        <button class="btn btn--secondary btn--sm" onclick="App.downloadPDF()">Download PDF</button>
        <button class="btn btn--primary btn--sm" onclick="App.navigate('upload')">New Interview</button>
      `;
    } else {
      nav.innerHTML = '';
    }
  },

  showLoading(text = 'Processing...') {
    document.getElementById('loadingText').textContent = text;
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById('view-loading').style.display = 'flex';
    document.getElementById('view-loading').classList.add('active');
  },

  hideLoading() {
    document.getElementById('view-loading').style.display = 'none';
    document.getElementById('view-loading').classList.remove('active');
  },

  /* ── Toast Notifications ───────────────────────────────────── */
  toast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const t = document.createElement('div');
    t.className = `toast toast--${type}`;
    t.textContent = message;
    container.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; t.style.transform = 'translateY(10px)'; setTimeout(() => t.remove(), 300); }, 4000);
  },

  /* ── Resume Upload ─────────────────────────────────────────── */
  initUpload() {
    const zone = document.getElementById('uploadZone');
    const input = document.getElementById('fileInput');

    zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('dragover'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
    zone.addEventListener('drop', (e) => {
      e.preventDefault(); zone.classList.remove('dragover');
      if (e.dataTransfer.files.length) this.uploadFile(e.dataTransfer.files[0]);
    });
    input.addEventListener('change', () => { if (input.files.length) this.uploadFile(input.files[0]); });
  },

  async uploadFile(file) {
    const allowed = ['application/pdf', 'text/plain',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
    const ext = file.name.split('.').pop().toLowerCase();
    if (!allowed.includes(file.type) && !['pdf', 'docx', 'txt'].includes(ext)) {
      this.toast('Please upload a PDF, DOCX, or TXT file.', 'error');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      this.toast('File size exceeds 10MB limit.', 'error');
      return;
    }

    const progress = document.getElementById('uploadProgress');
    const fill = document.getElementById('progressFill');
    const text = document.getElementById('uploadProgressText');
    const error = document.getElementById('uploadError');
    progress.style.display = 'block';
    error.style.display = 'none';
    fill.style.width = '30%';
    text.textContent = 'Uploading and parsing resume...';

    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${API}/resume/upload`, { method: 'POST', body: form });
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'Upload failed');
      }

      fill.style.width = '100%';
      text.textContent = 'Parsing complete!';

      State.resumeId = data.resume_id;
      State.profile = data.profile;

      setTimeout(() => {
        progress.style.display = 'none';
        this.renderReview(data);
        this.navigate('review');
      }, 500);

    } catch (err) {
      progress.style.display = 'none';
      error.style.display = 'block';
      error.textContent = err.message || 'Failed to upload resume. Please try again.';
    }
  },

  /* ── Resume Review ─────────────────────────────────────────── */
  renderReview(data) {
    const profile = data.profile;
    const container = document.getElementById('reviewContent');

    const section = (label, value, full = false) => {
      const isEmpty = !value || (Array.isArray(value) && value.length === 0);
      return `
        <div class="review-card${full ? ' review-card--full' : ''}">
          <div class="review-card__label">${label}</div>
          <div class="review-card__value${isEmpty ? ' review-card__value--empty' : ''}">
            ${isEmpty ? 'Not detected' : value}
          </div>
        </div>`;
    };

    const tagSection = (label, tags, warningTags = []) => {
      if (!tags || tags.length === 0) return section(label, '');
      const tagHtml = tags.map(t =>
        `<span class="review-tag${warningTags.includes(t) ? ' review-tag--warning' : ''}">${t}</span>`
      ).join('');
      return `
        <div class="review-card">
          <div class="review-card__label">${label}</div>
          <div class="review-card__tags">${tagHtml}</div>
        </div>`;
    };

    container.innerHTML = `
      <div class="review-card review-card--full">
        <div class="review-card__label">Candidate Name</div>
        <div class="review-card__value" style="font-size:1.1rem;font-weight:700">
          ${profile.name || '<span class="review-card__value--empty">Not detected</span>'}
        </div>
      </div>
      ${section('Professional Summary', profile.summary)}
      ${section('Email', profile.email)}
      ${section('Phone', profile.phone)}
      ${section('Location', profile.location)}
      ${tagSection('Job Titles', profile.job_titles)}
      ${tagSection('Skills', profile.skills)}
      ${tagSection('Tools & Technologies', profile.tools_and_tech)}
      ${section('Experience', profile.companies?.length
        ? profile.companies.join(', ')
        : '', true)}
      ${section('Projects', profile.projects?.length
        ? profile.projects.map(p => `<strong>${p.name || 'Project'}</strong>: ${p.description || ''}`).join('<br><br>')
        : '', true)}
      ${section('Achievements', profile.achievements?.length
        ? profile.achievements.join('<br>')
        : '', true)}
      ${section('Education', profile.education?.length
        ? profile.education.map(e => `${e.degree || ''}${e.institution ? ' — ' + e.institution : ''}`).join('<br>')
        : '')}
      ${tagSection('Certifications', profile.certifications)}
      ${section('Measurable Results', profile.measurable_results?.length
        ? profile.measurable_results.join('<br>')
        : '', true)}
      ${profile.missing_or_unclear?.length
        ? `<div class="review-card review-card--full">
            <div class="review-card__label">Areas Needing Clarification</div>
            <div class="review-card__tags">
              ${profile.missing_or_unclear.map(m => `<span class="review-tag review-tag--warning">${m}</span>`).join('')}
            </div>
          </div>`
        : ''}
    `;
  },

  /* ── Start Interview ───────────────────────────────────────── */
  async startInterview() {
    if (!State.resumeId) {
      this.toast('Please upload a resume first.', 'error');
      return;
    }

    this.showLoading('Generating personalized interview questions...');

    try {
      const res = await fetch(`${API}/interview/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resume_id: State.resumeId }),
      });
      const data = await res.json();

      if (!res.ok) throw new Error(data.detail || 'Failed to start interview');

      State.sessionId = data.session_id;
      State.questions = data.questions || [];
      State.currentQuestionIdx = 0;
      State.transcripts = [];
      State.elapsedSeconds = 0;
      State.interviewStartTime = Date.now();

      this.hideLoading();
      this.navigate('interview');
      this.renderInterviewQuestion(data.first_question, data.welcome_message);
      this.startTimer();
      Speech.init();

    } catch (err) {
      this.hideLoading();
      this.toast(err.message || 'Failed to start interview.', 'error');
    }
  },

  /* ── Interview Rendering ───────────────────────────────────── */
  /** Speak text while glowing the question card (TTS is active). */
  _speakWithGlow(text, cb) {
    const qEl = document.getElementById('studioQuestion');
    const area = qEl ? qEl.closest('.studio__question-area') : null;
    if (qEl) qEl.classList.add('speaking');
    if (area) area.classList.add('speaking');
    Speech.speakConversational(text, () => {
      if (qEl) qEl.classList.remove('speaking');
      if (area) area.classList.remove('speaking');
      if (cb) cb();
    });
  },

  renderInterviewQuestion(question, welcomeMsg) {
    if (!question) return;

    const total = State.questions.length;
    const current = State.currentQuestionIdx + 1;
    document.getElementById('studioQuestionNum').textContent = `Question ${current} of ${total}`;
    document.getElementById('studioCompletion').textContent = `${Math.round((current / total) * 100)}%`;
    document.getElementById('studioProgressFill').style.width = `${(current / total) * 100}%`;
    document.getElementById('studioCategory').textContent = this.formatCategory(question.category);
    document.getElementById('studioQuestion').textContent = question.question_text;

    // Show follow-up badge when the question is a dynamic follow-up
    const badge = document.getElementById('studioFollowupBadge');
    if (badge) badge.style.display = question.is_followup ? 'inline-block' : 'none';

    // Add welcome message to transcript if provided
    if (welcomeMsg && State.transcripts.length === 0) {
      this.addTranscript('system', welcomeMsg);
      // Speak welcome with conversational tone
      this._speakWithGlow(welcomeMsg, () => {
        // After welcome, speak the first question with a natural transition
        this._speakWithGlow(question.question_text, () => {
          document.getElementById('micStateText').textContent = 'Ready';
        });
      });
    } else {
      // Subsequent questions — add a natural transition
      const transition = this._getTransition();
      this.addTranscript('question', transition + question.question_text);
      this._speakWithGlow(transition + question.question_text, () => {
        document.getElementById('micStateText').textContent = 'Ready';
      });
    }

    State.questionStartTime = Date.now();
  },

  formatCategory(cat) {
    const map = {
      resume_introduction: 'Resume Introduction',
      experience_deep_dive: 'Experience Deep Dive',
      project_deep_dive: 'Project Deep Dive',
      technical_skills: 'Technical Skills',
      problem_solving: 'Problem Solving',
      achievements: 'Achievements',
      leadership_teamwork: 'Leadership & Teamwork',
      challenges_failures: 'Challenges & Failures',
      career_decisions: 'Career Decisions',
      clarification: 'Clarification',
      general: 'General',
    };
    return map[cat] || cat;
  },

  /**
   * Get a natural transition phrase to say between questions.
   * Real interviewers say things like "Good. So..." or "I see. Now..."
   */
  _getTransition() {
    const idx = State.currentQuestionIdx;
    if (idx === 0) return ''; // First question, no transition needed

    const transitions = [
      'Good. ',
      'I see. ',
      'Alright. ',
      'Thank you for that. ',
      'Got it. ',
      'Okay. ',
      'Great. ',
    ];
    return transitions[Math.floor(Math.random() * transitions.length)];
  },

  addTranscript(type, text) {
    State.transcripts.push({ type, text, time: new Date().toISOString() });
    const body = document.getElementById('transcriptBody');
    const entry = document.createElement('div');
    entry.className = 'transcript-entry';

    const roleClass = type === 'question' || type === 'followup' ? 'interviewer'
      : type === 'answer' ? 'candidate' : 'system';
    const roleLabel = type === 'question' ? 'Interviewer'
      : type === 'followup' ? 'Interviewer (Follow-up)'
      : type === 'answer' ? 'You' : 'System';

    entry.innerHTML = `
      <div class="transcript-entry__role transcript-entry__role--${roleClass}">${roleLabel}</div>
      <div class="transcript-entry__text">${text}</div>
    `;
    body.appendChild(entry);
    body.scrollTop = body.scrollHeight;
  },

  /* ── Timer ─────────────────────────────────────────────────── */
  startTimer() {
    State.timerInterval = setInterval(() => {
      State.elapsedSeconds = Math.floor((Date.now() - State.interviewStartTime) / 1000);
      const m = String(Math.floor(State.elapsedSeconds / 60)).padStart(2, '0');
      const s = String(State.elapsedSeconds % 60).padStart(2, '0');
      document.getElementById('studioTimer').textContent = `${m}:${s}`;
    }, 1000);
  },

  /* ── Recording Controls ────────────────────────────────────── */
  toggleRecording() {
    if (State.isRecording) {
      this.stopRecording();
    } else {
      this.startRecording();
    }
  },

  async startRecording() {
    if (!State.consentGiven) {
      // Show consent modal
      document.getElementById('consentModal').style.display = 'flex';
      return;
    }
    Speech.startListening();
    State.isRecording = true;
    this.updateRecordingUI(true);
  },

  stopRecording() {
    Speech.stopListening();
    State.isRecording = false;
    this.updateRecordingUI(false);

    // Get the transcribed text
    const text = Speech.getTranscript();
    if (text && text.trim().length > 0) {
      this.submitAnswer(text.trim());
    } else {
      this.toast('No answer was detected. Please try again or type your answer.', 'error');
    }
  },

  updateRecordingUI(recording) {
    const orb = document.getElementById('micOrb');
    const btn = document.getElementById('btnRecord');
    const btnText = document.getElementById('btnRecordText');
    const micStatus = document.getElementById('micStatus');
    const recStatus = document.getElementById('recordingStatus');
    const micState = document.getElementById('micStateText');

    if (recording) {
      orb.className = 'recording-indicator recording';
      btnText.textContent = 'Stop';
      micStatus.innerHTML = '<span class="dot dot--active"></span> Microphone Active';
      recStatus.innerHTML = '<span class="dot dot--recording"></span> Recording';
      micState.textContent = 'Listening';
    } else {
      orb.className = 'recording-indicator';
      btnText.textContent = 'Start';
      micStatus.innerHTML = '<span class="dot dot--inactive"></span> Microphone';
      recStatus.innerHTML = '<span class="dot dot--inactive"></span> Not Recording';
      micState.textContent = 'Ready';
    }
  },

  /* ── Text Input Fallback ───────────────────────────────────── */
  toggleTextInput() {
    const area = document.getElementById('textInputArea');
    area.style.display = area.style.display === 'none' ? 'flex' : 'none';
  },

  submitTextAnswer() {
    const text = document.getElementById('textInput').value.trim();
    if (!text) {
      this.toast('Please type your answer.', 'error');
      return;
    }
    document.getElementById('textInput').value = '';
    document.getElementById('textInputArea').style.display = 'none';
    this.submitAnswer(text);
  },

  /* ── Submit Answer ─────────────────────────────────────────── */
  async submitAnswer(answerText) {
    const duration = State.questionStartTime
      ? (Date.now() - State.questionStartTime) / 1000
      : 0;

    const currentQ = State.questions[State.currentQuestionIdx];
    if (!currentQ) return;

    this.addTranscript('answer', answerText);

    try {
      const res = await fetch(`${API}/interview/answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: State.sessionId,
          question_id: currentQ.question_id,
          answer_text: answerText,
          duration_seconds: Math.round(duration * 10) / 10,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to submit answer');

      // Handle follow-up question
      if (data.follow_up) {
        State.questions.splice(State.currentQuestionIdx + 1, 0, data.follow_up);
        State.currentQuestionIdx++;
        this.renderInterviewQuestion(data.follow_up, null);
      } else {
        // Move to next question
        State.currentQuestionIdx++;
        if (State.currentQuestionIdx < State.questions.length) {
          this.renderInterviewQuestion(State.questions[State.currentQuestionIdx], null);
        } else {
          // Interview complete
          this.endInterview();
        }
      }

    } catch (err) {
      this.toast(err.message || 'Failed to submit answer.', 'error');
    }
  },

  /* ── Interview Controls ────────────────────────────────────── */
  repeatQuestion() {
    const q = State.questions[State.currentQuestionIdx];
    if (q) this._speakWithGlow(q.question_text);
  },

  /** Skip the current question without submitting an answer. */
  skipQuestion() {
    const q = State.questions[State.currentQuestionIdx];
    if (!q) return;
    this.addTranscript('answer', '(Skipped this question)');
    State.isRecording = false;
    this.updateRecordingUI(false);
    Speech.stopListening();
    State.currentQuestionIdx++;
    if (State.currentQuestionIdx < State.questions.length) {
      this.renderInterviewQuestion(State.questions[State.currentQuestionIdx], null);
    } else {
      this.endInterview();
    }
  },

  pauseInterview() {
    State.isPaused = !State.isPaused;
    const btn = document.getElementById('btnPause');
    if (State.isPaused) {
      Speech.stop();
      this.toast('Interview paused.', 'info');
    }
  },

  toggleTranscript() {
    const body = document.getElementById('transcriptBody');
    body.style.display = body.style.display === 'none' ? 'block' : 'none';
  },

  async endInterview() {
    if (State.isRecording) this.stopRecording();
    clearInterval(State.timerInterval);
    Speech.stop();

    this.showLoading('Evaluating your interview performance...');

    try {
      const res = await fetch(`${API}/interview/end`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: State.sessionId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to end interview');

      this.hideLoading();
      this.renderResults(data);
      this.navigate('results');

    } catch (err) {
      this.hideLoading();
      this.toast(err.message || 'Failed to generate results.', 'error');
    }
  },

  /* ── Consent Modal ─────────────────────────────────────────── */
  async closeConsent(granted) {
    document.getElementById('consentModal').style.display = 'none';
    if (granted) {
      State.consentGiven = true;
      document.getElementById('consentNotice').style.display = 'flex';
      const ok = await Speech.requestMic();
      if (ok) {
        this.startRecording();
      } else {
        this.toast('Microphone permission denied. You can type your answers instead.', 'info');
        document.getElementById('textInputArea').style.display = 'flex';
      }
    } else {
      document.getElementById('textInputArea').style.display = 'flex';
      this.toast('You can type your answers instead.', 'info');
    }
  },

  /* ── Results Dashboard ─────────────────────────────────────── */
  renderResults(data) {
    // Overview cards
    const duration = data.duration_seconds || 0;
    const durStr = `${Math.floor(duration / 60)}m ${Math.floor(duration % 60)}s`;
    document.getElementById('resultsSubtitle').textContent =
      `${data.candidate_name ? data.candidate_name + ' — ' : ''}${data.resume_filename || 'Resume'} • ${data.interview_date || ''}`;

    // Score banner — animated ring + counting number
    const overall = Math.max(0, Math.min(100, data.overall_score || 0));
    const CIRC = 2 * Math.PI * 52;
    const ring = document.getElementById('scoreRingFill');
    if (ring) {
      ring.style.strokeDashoffset = CIRC;
      requestAnimationFrame(() => requestAnimationFrame(() => {
        ring.style.strokeDashoffset = CIRC * (1 - overall / 100);
      }));
    }
    const scoreVal = document.getElementById('scoreBannerValue');
    if (scoreVal) {
      let shown = 0;
      const step = Math.max(1, Math.round(overall / 40));
      const iv = setInterval(() => {
        shown = Math.min(overall, shown + step);
        scoreVal.textContent = shown;
        if (shown >= overall) clearInterval(iv);
      }, 24);
    }
    document.getElementById('scoreBannerHeadline').textContent =
      overall >= 80 ? 'Strong performance' :
      overall >= 60 ? 'Solid effort with room to grow' :
      overall >= 40 ? 'A good start — keep practicing' :
      'Time to build your foundations';
    document.getElementById('scoreBannerSub').textContent =
      `${data.total_questions || 0} questions • ${data.total_followups || 0} follow-ups • ${durStr}`;
    const level = document.getElementById('scoreBannerLevel');
    level.textContent = data.readiness_level || 'N/A';
    level.className = 'score-banner__level ' +
      (overall >= 75 ? 'score-banner__level--high' : overall >= 50 ? 'score-banner__level--mid' : 'score-banner__level--low');

    document.getElementById('resultsOverview').innerHTML = `
      <div class="overview-card overview-card--highlight">
        <div class="overview-card__value">${data.overall_score || 0}%</div>
        <div class="overview-card__label">Overall Score</div>
      </div>
      <div class="overview-card">
        <div class="overview-card__value" style="color:${data.overall_score >= 75 ? 'var(--emerald)' : data.overall_score >= 50 ? 'var(--amber)' : 'var(--coral)'}">${data.readiness_level || 'N/A'}</div>
        <div class="overview-card__label">Readiness Level</div>
      </div>
      <div class="overview-card">
        <div class="overview-card__value">${durStr}</div>
        <div class="overview-card__label">Duration</div>
      </div>
      <div class="overview-card">
        <div class="overview-card__value">${data.total_questions || 0}</div>
        <div class="overview-card__label">Questions</div>
      </div>
      <div class="overview-card">
        <div class="overview-card__value">${data.total_followups || 0}</div>
        <div class="overview-card__label">Follow-ups</div>
      </div>
      <div class="overview-card">
        <div class="overview-card__value">${data.completion_percentage || 0}%</div>
        <div class="overview-card__label">Completion</div>
      </div>
    `;

    // Scorecard
    const scores = data.scores || [];
    document.getElementById('resultsScorecard').innerHTML = scores.map(s => {
      const pct = (s.score / s.max_score) * 100;
      const color = pct >= 80 ? 'var(--emerald)' : pct >= 60 ? 'var(--warm-blue)' : pct >= 40 ? 'var(--amber)' : 'var(--coral)';
      return `
        <div class="score-card">
          <div class="score-card__header">
            <span class="score-card__label">${s.dimension}</span>
            <span class="score-card__value" style="color:${color}">${s.score}/${s.max_score}</span>
          </div>
          <div class="score-card__bar">
            <div class="score-card__bar-fill" style="width:${pct}%;background:${color}"></div>
          </div>
        </div>`;
    }).join('');

    // Strengths
    const strengths = data.strengths || [];
    document.getElementById('resultsStrengths').innerHTML = strengths.length
      ? strengths.map(s => `<div class="result-item result-item--green">${s.description || s.area || s}</div>`).join('')
      : '<div class="result-item result-item--green">No specific strengths identified.</div>';

    // Improvements
    const improvements = data.improvements || [];
    document.getElementById('resultsImprovements').innerHTML = improvements.length
      ? improvements.map(i => `<div class="result-item result-item--amber">${i.description || i.area || i}</div>`).join('')
      : '<div class="result-item result-item--amber">No specific improvement areas identified.</div>';

    // Communication
    const comm = data.communication || {};
    document.getElementById('resultsComm').innerHTML = `
      <div class="comm-item">
        <div class="comm-item__label">Avg Answer Duration</div>
        <div class="comm-item__value">${(comm.avg_answer_duration || 0).toFixed(0)}s</div>
      </div>
      <div class="comm-item">
        <div class="comm-item__label">Speaking Pace</div>
        <div class="comm-item__value">${comm.speaking_pace || 'N/A'}</div>
      </div>
      <div class="comm-item">
        <div class="comm-item__label">Filler Words</div>
        <div class="comm-item__value">${comm.filler_word_count || 0}</div>
      </div>
      <div class="comm-item">
        <div class="comm-item__label">Repeated Phrases</div>
        <div class="comm-item__value">${comm.repeated_phrases || 0}</div>
      </div>
      <div class="comm-item">
        <div class="comm-item__label">Conciseness</div>
        <div class="comm-item__value">${comm.conciseness_rating || 'N/A'}</div>
      </div>
    `;

    // Question-by-question review
    const qe = data.question_evaluations || [];
    document.getElementById('resultsQuestions').innerHTML = qe.map((q, i) => {
      const scores = (q.scores || []).map(s => {
        const cls = s.score >= 4 ? 'good' : s.score >= 2.5 ? 'mid' : 'low';
        return `<span class="mini-score mini-score--${cls}">${s.dimension}: ${s.score}</span>`;
      }).join('');

      const strengths = (q.strengths || []).map(s => `<li>${s}</li>`).join('');
      const improvements = (q.improvements || []).map(i => `<li>${i}</li>`).join('');

      return `
        <div class="question-review${i === 0 ? ' open' : ''}" onclick="this.classList.toggle('open')">
          <div class="question-review__header">
            <span class="question-review__num">Q${i + 1}${q.is_followup ? ' (Follow-up)' : ''}</span>
            <span class="question-review__category">${this.formatCategory(q.category)}</span>
          </div>
          <div class="question-review__body">
            <div class="question-review__q">${q.question_text}</div>
            <div class="question-review__a">${q.answer_text || '<em>No answer recorded</em>'}</div>
            <div class="question-review__meta">
              <span>Duration: ${(q.answer_duration || 0).toFixed(0)}s</span>
            </div>
            <div class="question-review__scores">${scores}</div>
            ${strengths ? `<div class="question-review__section">
              <div class="question-review__section-title">What went well</div>
              <ul class="question-review__list question-review__list--strengths">${strengths}</ul>
            </div>` : ''}
            ${improvements ? `<div class="question-review__section">
              <div class="question-review__section-title">What could be improved</div>
              <ul class="question-review__list question-review__list--improvements">${improvements}</ul>
            </div>` : ''}
            ${q.suggested_answer_structure ? `<div class="question-review__suggested">
              <strong>Suggested structure:</strong> ${q.suggested_answer_structure}
            </div>` : ''}
          </div>
        </div>`;
    }).join('');

    // Practice plan
    const plan = data.practice_plan || [];
    document.getElementById('resultsPractice').innerHTML = plan.map(p => `
      <div class="practice-item">
        <div class="practice-item__num">${p.priority}</div>
        <div>
          <div class="practice-item__text">${p.recommendation}</div>
          ${p.rationale ? `<div class="practice-item__rationale">${p.rationale}</div>` : ''}
        </div>
      </div>
    `).join('');

    // Resume consistency
    const consistency = data.resume_consistency || [];
    const section = document.getElementById('consistencySection');
    if (consistency.length > 0) {
      section.style.display = 'block';
      document.getElementById('resultsConsistency').innerHTML = consistency.map(c => `
        <div class="result-item result-item--blue">${c.statement} — <em>${c.resume_context}</em> (${c.status})</div>
      `).join('');
    }
  },

  /* ── PDF Download ──────────────────────────────────────────── */
  downloadPDF() {
    if (!State.sessionId) return;
    window.open(`${API}/interview/${State.sessionId}/pdf`, '_blank');
  },

  downloadTranscript(format) {
    if (!State.sessionId) return;
    window.open(`${API}/interview/${State.sessionId}/transcript?format=${format}`, '_blank');
  },
};

/* ── Initialize ────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  App.initUpload();
  App.navigate('landing');
});
