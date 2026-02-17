/**
 * @description Redirects the user to the sprint tasks page of the specified sprint.
 * @param {string|number} sprintId - The unique identifier of the sprint
 */
const goToTask = (sprintId) => {
  window.location.href += `${sprintId}/tasks/`;
};
