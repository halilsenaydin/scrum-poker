(() => {
  /**
   * @description Generate prompt for GPT based on scrum metrics
   */
  const generateMetricsPrompt = () => {
    const getText = (id) =>
      document.getElementById(id)?.textContent?.trim() || "-";
    const getBadgesText = (id) => {
      const container = document.getElementById(id);

      if (!container) return "-";

      const texts = Array.from(container.children)
        .map((span) => span.textContent?.trim())
        .filter(Boolean);

      return texts.length ? texts.join(", ") : "-";
    };
    const average = getText("metric-average");
    const median = getText("metric-median");
    const min = getText("metric-min");
    const max = getText("metric-max");
    const stdDev = getText("metric-std-dev");
    const consensusScore = getText("metric-consensus-score");
    const modes = getBadgesText("metric-modes");
    const counts = getBadgesText("metric-counts");

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
  - Standard Deviation: ${stdDev}
  - Consensus Score: ${consensusScore}
  - Most frequently chosen votes: ${modes}
  - Vote distribution: ${counts}
  `.trim();
  };

  /**
   * @description Handle save button click
   */
  const handleSaveButtonClick = () => {
    const sp = document.getElementById('story-points');

    fetch(window.location.pathname, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken"),
      },
      body: JSON.stringify({
        sp: sp.value
      }),
    })
    .then((res) => res.json())
    .then((data) => {
      showToast(data);

      if (data.status) {
        const spValue = document.querySelector('.sp-value');

        if (spValue) {
          spValue.textContent = data.data.sp;
        }
      }
    })
  };

  /**
   * @description Handle ask gpt button click
   */
  const handleAskGptButtonClick = () => {
    const metricsPrompt = generateMetricsPrompt();
    const encodedPrompt = encodeURIComponent(metricsPrompt);
    const url = `https://chatgpt.com/?prompt=${encodedPrompt}`;

    window.open(url, "_blank");
  };

  /**
   * @description Set save button click listener
   */
  const setSaveButtonClickListener = () => {
    const saveButton = document.getElementById("vote-save-button");
    if (!saveButton) return;

    saveButton.addEventListener("click", handleSaveButtonClick);
  };
  
  /**
   * @description Set ask gpt button click listener
   */
  const setAsgGptButtonClickListener = () => {
    const askGptButton = document.getElementById('ask-gpt-btn');
    if (!askGptButton) return;

    askGptButton.addEventListener("click", handleAskGptButtonClick);
  };

  setSaveButtonClickListener();
  setAsgGptButtonClickListener();
})();
