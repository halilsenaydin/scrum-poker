/**
 * @description Retrieves the value of a cookie by its name.
 * @param {string} name - The name of the cookie to retrieve
 * @returns {string|null} The cookie value if found, otherwise null
 */
const getCookie = (name) => {
  let cookieValue = null;

  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");

    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();

      if (cookie.startsWith(name + "=")) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }

  return cookieValue;
};

/**
 * @description Display a toast notification based on a result object.
 * @param {Object} result - The result object containing status, message, and optional data.
 * @param {boolean} result.status - Indicates whether the operation was successful.
 * @param {string} result.message - The message to display in the toast.
 * @param {*} [result.data] - Optional additional data associated with the result.
 */
let toastTimeoutId = null;

const showToast = (result) => {
  if (!result.message) {
    return;
  }

  const toast = document.getElementById("toast");
  const toastText = document.getElementById("toast-text");

  if (toastTimeoutId) {
    clearTimeout(toastTimeoutId);
  }

  toast.classList.remove("success", "error");

  if (result.status) {
    toast.classList.add("success");
  } else {
    toast.classList.add("error");
  }

  toastText.textContent = result.message;
  toast.classList.add("show");

  toastTimeoutId = setTimeout(() => {
    toast.classList.remove("show");
    toastTimeoutId = null;
  }, 2000);
};

/**
 * @description Handles the room info copy action by copying the room code to the clipboard.
 * @param {string} roomCode - The unique code of the room to be copied
 */
const handleRoomInfoClick = (roomCode) => {
  const baseUrl = `${window.location.origin}/room/${roomCode}`;

  navigator.clipboard
    .writeText(baseUrl)
    .then(() => {
      const roomInfo = document.getElementById("room-info");
      const copiedText = roomInfo?.dataset.copiedText;

      showToast({
        status: true,
        message: copiedText,
      });
    })
    .catch(() => {
      showToast({
        status: false,
        message: 'Copied failed'
      })
    });
};

/**
 * @description Get initials from a name
 * @param name Full name
 */
const getInitials = (name) => {
  const val = name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return val;
};

/**
 * @description Create a participant card element
 * @param p Participant object
 */
const createParticipantElement = (p) => {
  const card = document.createElement("div");

  card.id = "current-participant";
  card.className = "participant-card";
  card.dataset.name = p.username;

  const info = document.createElement("div");

  info.className = "participant-info";

  const avatar = document.createElement("div");

  avatar.className = "avatar";
  avatar.textContent = getInitials(p.username);

  const name = document.createElement("span");

  name.className = "participant-name";
  name.textContent = p.username;

  info.append(avatar, name);

  const currentParticipantBadge = document.createElement("span");
  const participantList = document.getElementById("participant-list");

  currentParticipantBadge.className = "participant-badge";
  currentParticipantBadge.textContent = participantList.dataset.currentParticipantBadgeText;

  card.append(info, currentParticipantBadge);

  return card;
};

/**
 * @description Add participant to participants list
 */
const addParticipant = (participant) => {
  const container = document.getElementById("participant-list");

  container.appendChild(createParticipantElement(participant));
}

/**
 * @description Template for empty participant state
 */
const emptyStateTemplate = () => {
  const emptyText =
    document.getElementById("participant-list")?.dataset.emptyText;

  return `
    <div class="empty-state">
      <div class="empty-icon">👤</div>
      <div class="empty-text">${emptyText}</div>
    </div>
  `;
}

/**
 * @description Render empty state if there are no participants
 */
const renderEmptyStateIfNeeded = () => {
  const container = document.getElementById("participant-list");
  const participantCount = document.querySelectorAll(".participant-card").length;

  if (participantCount == 0) {
    container.innerHTML = emptyStateTemplate();
  }
}

/**
 * @description Opens the join room modal.
 */
const openModal = () => {
    document.getElementById('modal').classList.add('active');
}

/**
 * @description Closes the join room modal.
 */
const closeModal = () => {
    document.getElementById('modal').classList.remove('active');
}

/**
 * @description Handles the join room form submission.
 * @param {SubmitEvent} e Form submit event
 */
const handleJoinRoomButtonClick = (e) => {
  e.preventDefault();

  const form = e.target;  
  const formData = new FormData(form);
  const name = formData.get("username");

  saveParticipant(name);
}

/**
 * @description Saves the participant information and initiates the room join process.
 */
const saveParticipant = () => {
  const roomContainer = document.getElementById("room-container");
  const roomCode = roomContainer.dataset.roomId;

  fetch(`/room/${roomCode}/add-participant/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    }
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status && !data.data?.no_need_add_participant) {
        showToast(data);
        addParticipant(data.data);

        const participantCount =
          document.querySelectorAll(".participant-card").length;
        const participantCountText = `${participantCount} ${document.getElementById("participant-count")?.dataset.participantCountText}`;
        const participantCountElement =
          document.getElementById("participant-count");

        participantCountElement.textContent = participantCountText;

        if (participantCount > 0) {
          const emptyState = document.querySelector('.empty-state');

          if (emptyState) {
            emptyState.remove();
          }
        }
      } else if (!data.status) {
        showToast(data);

        window.location.replace("/admin/");
      }
    });
}

/**
 * @description Initializes the application
 */
const init = () => {
  saveParticipant();
};

init();
