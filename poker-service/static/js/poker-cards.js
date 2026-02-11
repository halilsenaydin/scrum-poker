(() => {
  const cards = document.getElementsByClassName("poker-card");
  const container = document.getElementById("poker-cards");
  let lastClickedPokerCard = null;

  if (!container) return;

  const selectedVote = container.dataset.selectedVote;
  const selectedCard = document.querySelector(
    `.poker-card[data-value="${selectedVote}"]`,
  );

  const handlePokerCardListener = (card) => {
    lastClickedPokerCard?.classList.remove("selected");
    selectedCard?.classList.remove("selected");

    lastClickedPokerCard = card;
    card.classList.add("selected");
    container.dataset.selectedVote = card.dataset.value;

    fetch(window.location.pathname, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken"),
      },
      body: JSON.stringify({
        vote: card.dataset.value,
      }),
    })
      .then((res) => res.json())
      .then((data) => {
        showToast(data);

        if (data.status) {
          const currentParticipant = document.getElementById(
            "current-participant",
          );

          if (!currentParticipant) return;

          const voteDisplay = currentParticipant.querySelector(".vote-display");

          voteDisplay.textContent = data.data.vote;
          currentParticipant.classList.add("voted");
        }
      });
  };

  for (const card of cards) {
    card.addEventListener("click", () => handlePokerCardListener(card));
  }
})();
