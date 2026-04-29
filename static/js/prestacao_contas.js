document.addEventListener("DOMContentLoaded", () => {
  const textareas = document.querySelectorAll(".rt-form-layout textarea");
  textareas.forEach((textarea) => {
    textarea.classList.add("form-control");
  });
});
