// Global state
const state = {
  roomId: document.getElementById('room-container')?.dataset.roomId,
  userName: null,
  selectedCard: null,
  revealed: false,
  participants: [],
  socket: null,
};
const initialsCache = new Map();
let lastRevealed = null;
let lastSelectedCard = null;
let reconnectAttempts = 0;

/**
 * @description Get or ask for the user's name and store it in localStorage
 */
function initUserName() {
  const key = 'scrumPoker_userName';
  let name = localStorage.getItem(key);

  if (!name) {
    name = prompt('Lütfen adınızı girin:') || 'Anonim';
    localStorage.setItem(key, name);
  }

  state.userName = name;
}

/**
 * @description Calculates basic Scrum Poker metrics from participant votes.
 * @param participants List of participants with their votes.
 * @returns Calculated metrics.
 */
function calculateScrumMetrics(participants) {
  const votes = participants
    .map((p) => p.vote)
    .filter((v) => v != null && v !== '')
    .map((v) => Number(v))
    .filter((v) => !isNaN(v));

  if (votes.length === 0) return null;

  const average = votes.reduce((sum, v) => sum + v, 0) / votes.length;
  const sorted = [...votes].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  let median;

  if (sorted.length % 2 === 0) {
    median = (sorted[mid - 1] + sorted[mid]) / 2;
  } else {
    median = sorted[mid];
  }

  const counts = {};

  votes.forEach((v) => (counts[v] = (counts[v] || 0) + 1));

  const maxCount = Math.max(...Object.values(counts));
  const modes = Object.entries(counts)
    .filter(([vote, count]) => count === maxCount)
    .map(([vote]) => Number(vote));
  const min = Math.min(...votes);
  const max = Math.max(...votes);

  return {
    average,
    median,
    modes,
    counts,
    min,
    max,
  };
}

/**
 * @description Initialize WebSocket connection and event handlers
 */
function initSocket() {
  state.socket?.close();

  const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
  const url = `${protocol}://${location.host}/ws/room/${state.roomId}/`;
  const socket = new WebSocket(url);

  socket.onopen = () => {
    reconnectAttempts = 0;

    sendMessage('join', { name: state.userName });
  };

  socket.onmessage = (event) => {
    const data = JSON.parse(event.data);

    updateFromServer(data);

    const revealed = data.revealed;

    if (revealed !== lastRevealed) {
      const gptButton = document.getElementById('ask-gpt-btn');

      gptButton.disabled = !revealed;

      if (revealed) {
        gptButton.classList.remove('disabled');

        const metrics = calculateScrumMetrics(state.participants);

        renderMetrics(metrics);
      } else {
        gptButton.classList.add('disabled');

        renderMetrics(null);
      }

      lastRevealed = revealed;
    }
  };

  socket.onclose = () => {
    const timeout = Math.min(3000 * 2 ** reconnectAttempts, 30000);

    reconnectAttempts++;

    setTimeout(initSocket, timeout);
  };

  socket.onerror = (err) => {
    console.error('WebSocket error:', err);
  };

  state.socket = socket;
}

/**
 * @description Send a message to the server via WebSocket
 * @param action Action type
 * @param payload Additional data
 */
function sendMessage(action, payload = {}) {
  if (!state.socket || state.socket.readyState !== WebSocket.OPEN) {
    console.warn('Socket not ready, message skipped:', action);

    return;
  }

  state.socket.send(JSON.stringify({ action, ...payload }));
}

/**
 * @description Sync the selected card of the current user from server data
 */
function syncSelectedCardFromServer() {
  const me = state.participants.find((p) => p.name === state.userName);

  state.selectedCard = me?.vote ?? null;
}

/**
 * @description Update local state from server data and re-render
 * @param data Data received from server
 */
function updateFromServer(data) {
  state.participants = Array.isArray(data.participants)
    ? data.participants
    : [];
  state.revealed = Boolean(data.revealed);

  syncSelectedCardFromServer();
  renderParticipants();
  renderCardSelection();
  renderEmptyStateIfNeeded();
}

/**
 * @description Handle voting action
 * @param value Selected card value
 */
function vote(value) {
  if (state.selectedCard === value) return;

  state.selectedCard = value;

  renderCardSelection();
  sendMessage('vote', { name: state.userName, value });
}

/**
 * @description Handle reveal action
 */
function reveal() {
  sendMessage('reveal');
}

/**
 * @description Handle reset votes action
 */
function resetVotes() {
  const resetVotesConfirmText =
    document.getElementById('participant-list')?.dataset.resetVotesConfirmText;

  if (!confirm(resetVotesConfirmText)) return;

  state.selectedCard = null;

  renderCardSelection();
  sendMessage('reset');
}

/**
 * @description Remove a participant from the room
 * @param name Participant's name
 */
function removeParticipant(name) {
  initialsCache.delete(name);

  state.participants = state.participants.filter((p) => p.name !== name);

  renderParticipants();
  sendMessage('remove_participant', { name });
}

/**
 * @description Create a participant card element
 * @param p Participant object
 */
function createParticipantElement(p) {
  const card = document.createElement('div');

  card.className = `participant-card ${p.vote != null ? 'voted' : ''}`;
  card.dataset.name = p.name;

  const info = document.createElement('div');

  info.className = 'participant-info';

  const avatar = document.createElement('div');

  avatar.className = 'avatar';
  avatar.textContent = getInitials(p.name);

  const name = document.createElement('span');

  name.className = 'participant-name';
  name.textContent = p.name;

  info.append(avatar, name);

  const vote = document.createElement('div');

  vote.className = 'vote-display';
  vote.textContent = getVoteDisplay(p);

  const remove = document.createElement('div');

  remove.className = 'remove-user';
  remove.dataset.name = p.name;
  remove.innerHTML = '<i class="fa-solid fa-user-minus"></i>';

  card.append(info, vote, remove);

  return card;
}

/**
 * @description Get the vote display text for a participant
 * @param p Participant object
 */
function getVoteDisplay(p) {
  if (state.revealed || p.name === state.userName) return p.vote ?? '—';
  return p.vote != null ? '✓' : '?';
}

/**
 * @description Render the participant list
 */
function renderParticipants() {
  const participantCount = document.getElementById('participant-count');
  const container = document.getElementById('participant-list');
  const fragment = document.createDocumentFragment();
  const participants = state.participants;
  const removeParticipantConfirmText = `${participants.length} ${participantCount?.dataset.participantCount}`;

  container.textContent = '';
  participantCount.textContent = removeParticipantConfirmText;

  participants.forEach((p) => {
    const el = createParticipantElement(p);

    fragment.appendChild(el);
  });

  container.appendChild(fragment);
}

/**
 * @description Render empty state if there are no participants
 */
function renderEmptyStateIfNeeded() {
  const container = document.getElementById('participant-list');

  if (!state.participants || state.participants.length === 0) {
    container.innerHTML = emptyStateTemplate();
  }
}

/**
 * @description Render the selected card UI
 */
function renderCardSelection() {
  if (lastSelectedCard) {
    lastSelectedCard.classList.remove('selected');
  }

  const current = document.querySelector(
    `.poker-card[data-value="${state.selectedCard}"]`
  );

  current?.classList.add('selected');
  lastSelectedCard = current;
}

/**
 * @description Render the scrum metrics
 * @param metrics Metrics object
 */
function renderMetrics(metrics) {
  const metricAverageEl = document.getElementById('metric-average');
  const metricMedianEl = document.getElementById('metric-median');
  const metricMinEl = document.getElementById('metric-min');
  const metricMaxEl = document.getElementById('metric-max');
  const modesEl = document.getElementById('metric-modes');
  const countsEl = document.getElementById('metric-counts');

  if (!metrics) {
    metricAverageEl.textContent = '-';
    metricMedianEl.textContent = '-';
    metricMinEl.textContent = '-';
    metricMaxEl.textContent = '-';
    modesEl.textContent = '-';
    countsEl.textContent = '-';

    return;
  }

  metricAverageEl.textContent = metrics.average.toFixed(1);
  metricMedianEl.textContent = metrics.median;
  metricMinEl.textContent = metrics.min;
  metricMaxEl.textContent = metrics.max;
  modesEl.textContent = '';
  countsEl.textContent = '';

  const modesFragment = document.createDocumentFragment();

  metrics.modes.forEach((v) => {
    const span = document.createElement('span');
    span.className = 'metric-badge';
    span.textContent = v;
    modesFragment.appendChild(span);
  });

  modesEl.appendChild(modesFragment);

  const countsFragment = document.createDocumentFragment();

  Object.entries(metrics.counts).forEach(([vote, count]) => {
    const span = document.createElement('span');
    span.className = 'metric-badge';
    span.textContent = `${vote} × ${count}`;
    countsFragment.appendChild(span);
  });

  countsEl.appendChild(countsFragment);
}

/**
 * @description Get initials from a name
 * @param name Full name
 */
function getInitials(name) {
  if (initialsCache.has(name)) return initialsCache.get(name);

  const val = name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  initialsCache.set(name, val);

  return val;
}

/**
 * @description Template for empty participant state
 */
function emptyStateTemplate() {
  const emptyText =
    document.getElementById('participant-list')?.dataset.emptyText;

  return `
    <div class="empty-state">
      <div class="empty-icon">👤</div>
      <div class="empty-text">${emptyText}</div>
    </div>
  `;
}

/**
 * @description Handle room info copy action
 */
function handleRoomInfo() {
  navigator.clipboard
    .writeText(window.location.href)
    .then(() => {
      const toast = document.getElementById('toast');
      const toastText = document.getElementById('toast-text');
      const roomInfo = document.getElementById('room-info');
      const copiedText = roomInfo?.dataset.copiedText;

      toastText.textContent = copiedText;
      toast.classList.add('show');

      setTimeout(() => toast.classList.remove('show'), 2000);
    })
    .catch((err) => {
      console.error('Kopyalama başarısız:', err);
    });
}

/**
 * @description Generate prompt for GPT based on scrum metrics
 */
function generateMetricsPrompt() {
  const getText = (id) =>
    document.getElementById(id)?.textContent?.trim() || '-';
  const getBadgesText = (id) => {
    const container = document.getElementById(id);

    if (!container) return '-';

    const texts = Array.from(container.children)
      .map((span) => span.textContent?.trim())
      .filter(Boolean);

    return texts.length ? texts.join(', ') : '-';
  };
  const average = getText('metric-average');
  const median = getText('metric-median');
  const min = getText('metric-min');
  const max = getText('metric-max');
  const modes = getBadgesText('metric-modes');
  const counts = getBadgesText('metric-counts');

  return `
We conducted a Scrum Poker session using Fibonacci sequence voting. Based on the following metrics, provide a recommended estimate (choose a Fibonacci number).

Your response should:
- Give the recommended estimate first.
- Explain your reasoning briefly but clearly, considering all relevant metrics such as average, median, minimum, maximum, modes, and vote distribution.
- Highlight if there is significant spread or disagreement in the votes that might affect the recommendation.
- Keep the explanation detailed enough to justify your choice, but avoid unnecessary verbosity.
- Average vote: ${average}
- Median vote: ${median}
- Minimum vote: ${min}
- Maximum vote: ${max}
- Most frequently chosen votes: ${modes}
- Vote distribution: ${counts}
`.trim();
}

// Event listeners
document.getElementById('participant-list').addEventListener('click', (e) => {
  const btn = e.target.closest('.remove-user');

  if (!btn) return;

  const name = btn.dataset.name;

  if (!name) return;

  const removeParticipantConfirmText = `${
    document.getElementById('participant-list')?.dataset
      .removeParticipantConfirmText
  } - ${name}`;

  if (confirm(removeParticipantConfirmText)) {
    removeParticipant(name);
  }
});
document.getElementById('ask-gpt-btn').addEventListener('click', () => {
  const metricsPrompt = generateMetricsPrompt();
  const encodedPrompt = encodeURIComponent(metricsPrompt);
  const url = `https://chatgpt.com/?prompt=${encodedPrompt}`;

  window.open(url, '_blank');
});

// Close WebSocket on page unload
window.addEventListener('beforeunload', () => {
  state.socket?.close();
});

/**
 * @description Initialize the application
 */
function init() {
  initUserName();
  initSocket();
}

init();
