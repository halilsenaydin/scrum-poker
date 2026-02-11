/**
 * @description Redirects the user to the detail page of the specified task.
 * @param {string|number} taskId - The unique identifier of the task
 */
const goToTaskDetail = (taskId) => {
  window.location.href += `${taskId}/`;
};
