// static/js/base.js
document.addEventListener("DOMContentLoaded", () => {

  // ===== FLASH MESSAGES =====
  const flashes = document.querySelectorAll(".flash");
  flashes.forEach(flash => {
    setTimeout(() => {
      flash.style.transition = "opacity 0.5s ease";
      flash.style.opacity = "0";
      setTimeout(() => flash.remove(), 500);
    }, 4000);
  });

  // ===== DROPDOWN ADMIN =====
  const dropdowns = document.querySelectorAll(".dropdown");
  dropdowns.forEach(dropdown => {
    const btn = dropdown.querySelector(".dropdown-btn");
    const content = dropdown.querySelector(".dropdown-content");
    if (!btn || !content) return;

    btn.addEventListener("click", e => {
      e.stopPropagation();
      content.classList.toggle("show");
    });

    document.addEventListener("click", () => content.classList.remove("show"));
  });

  // ===== CONFIRMAÇÃO GENÉRICA (delete, etc.) =====
  document.querySelectorAll("[data-confirm]").forEach(form => {
    form.addEventListener("submit", e => {
      const msg = form.dataset.confirm || "Confirma esta ação?";
      if (!confirm(msg)) e.preventDefault();
    });
  });

  // ===== PREVIEW DE IMAGEM (cadastro e edição de cupcake) =====
  const imageInputs = document.querySelectorAll("input[type='file'][data-preview-target]");
  imageInputs.forEach(input => {
    const targetId = input.getAttribute("data-preview-target");
    const preview = document.getElementById(targetId);
    if (!preview) return;

    input.addEventListener("change", event => {
      const file = event.target.files[0];
      if (file) {
        const reader = new FileReader();
        reader.onload = e => preview.src = e.target.result;
        reader.readAsDataURL(file);
      }
    });
  });

  // ===== FEEDBACK DE BOTÃO =====
  const botoes = document.querySelectorAll(".botao");
  botoes.forEach(btn => {
    btn.addEventListener("click", () => {
      btn.classList.add("clicked");
      setTimeout(() => btn.classList.remove("clicked"), 200);
    });
  });
});
