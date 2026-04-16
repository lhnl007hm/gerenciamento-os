// static/js/main.js
document.addEventListener("DOMContentLoaded", function () {
  // Carregar nome do contrato
  fetch("/api/estatisticas")
    .then((response) => response.json())
    .then((data) => {
      // Pode adicionar mais informações aqui se necessário
    })
    .catch((error) => console.error("Erro ao carregar dados:", error));

  // Ativar tooltips
  var tooltipTriggerList = [].slice.call(
    document.querySelectorAll('[data-bs-toggle="tooltip"]'),
  );
  tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
  });

  // Formatar datas
  document.querySelectorAll(".format-date").forEach((element) => {
    const date = new Date(element.textContent);
    if (!isNaN(date)) {
      element.textContent = date.toLocaleDateString("pt-BR");
    }
  });

  // Confirmação de exclusão genérica
  window.confirmarExclusao = function (mensagem, callback) {
    if (confirm(mensagem || "Tem certeza que deseja excluir este item?")) {
      callback();
    }
  };

  // Máscara para campos de data
  document.querySelectorAll('input[type="date"]').forEach((input) => {
    if (!input.value) {
      const today = new Date();
      const year = today.getFullYear();
      const month = String(today.getMonth() + 1).padStart(2, "0");
      const day = String(today.getDate()).padStart(2, "0");
      input.value = `${year}-${month}-${day}`;
    }
  });
});

// Função para formatar status com cores
function getStatusBadge(status) {
  const badges = {
    Concluído: "success",
    "Em Andamento": "warning",
    "À Fazer": "info",
    Cancelado: "danger",
  };

  return `<span class="badge bg-${badges[status] || "secondary"}">${status}</span>`;
}

// Função para exportar dados (se necessário)
function exportarDados(formato = "csv") {
  window.location.href = `/api/exportar?formato=${formato}`;
}

// Validação de formulários
(function () {
  "use strict";

  var forms = document.querySelectorAll(".needs-validation");

  Array.prototype.slice.call(forms).forEach(function (form) {
    form.addEventListener(
      "submit",
      function (event) {
        if (!form.checkValidity()) {
          event.preventDefault();
          event.stopPropagation();
        }

        form.classList.add("was-validated");
      },
      false,
    );
  });
})();
