const handleRemoveUserClick = (e, roomCode) => {
  const btn = e.target.closest(".remove-user");

  if (!btn) return;

  const name = btn.dataset.name;
  const removeParticipantConfirmText = `${
    document.getElementById("participant-list")?.dataset
      .removeParticipantConfirmText
  } - ${name}`;

  if (confirm(removeParticipantConfirmText)) {
    fetch(`/room/${roomCode}/remove-participant/`, {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken"),
      },
      body: JSON.stringify({
        name: name,
      }),
    })
      .then((res) => res.json())
      .then((data) => {
        showToast(data);

        if (data.status) {
          const participant = document.querySelector(
            `.participant-card[data-name="${name}"]`,
          );

          participant.remove();

          const participantCount =
            document.querySelectorAll(".participant-card").length;
          const participantCountText = `${participantCount} ${document.getElementById("participant-count")?.dataset.participantCountText}`;
          const participantCountElement =
            document.getElementById("participant-count");

          participantCountElement.textContent = participantCountText;

          renderEmptyStateIfNeeded();
        }
      });
  }
};
