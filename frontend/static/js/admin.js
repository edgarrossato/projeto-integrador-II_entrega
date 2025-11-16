// static/js/admin.js
document.addEventListener("DOMContentLoaded", () => {
  // ====== GRÁFICO DE STATUS ======
  if (typeof Chart !== "undefined" && typeof pedidosStats !== "undefined") {
    const ctx = document.getElementById("chartStatus");

    if (ctx) {
      new Chart(ctx, {
        type: "bar",
        data: {
          labels: Object.keys(pedidosStats),
          datasets: [
            {
              label: "Pedidos",
              data: Object.values(pedidosStats),
              backgroundColor: [
                "#4e73df", // Recebido
                "#f6c23e", // Em produção
                "#36b9cc", // Pronto
                "#1cc88a", // Entregue
                "#d9534f"  // Cancelado
              ],
              borderRadius: 6,
              barThickness: 32,
            },
          ],
        },
        options: {
          responsive: true,
          animation: {
            duration: 900,
            easing: "easeOutQuart",
          },
          plugins: {
            legend: { display: false },
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: { precision: 0 },
            },
          },
        },
      });
    }
  }

  // ====== CONFIRMAÇÃO DE STATUS ======
  document.querySelectorAll("form[data-confirm-status]").forEach(form => {
    form.addEventListener("submit", e => {
      if (!confirm("Deseja realmente alterar o status deste pedido?")) {
        e.preventDefault();
      }
    });
  });
});
