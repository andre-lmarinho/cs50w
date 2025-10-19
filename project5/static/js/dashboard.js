(() => {
  const root = document.getElementById('dashboard-app');
  if (!root) {
    return;
  }

  const summaryUrl = root.dataset.summaryUrl;
  const accountsUrl = root.dataset.accountsUrl;
  const spendingUrl = root.dataset.spendingUrl;
  const cashflowUrl = root.dataset.cashflowUrl;

  const summaryBalanceEl = document.getElementById('summary-total-balance');
  const summaryAccountsEl = document.getElementById('summary-total-accounts');
  const summaryTransactionsEl = document.getElementById('summary-total-transactions');
  const summaryNetEl = document.getElementById('summary-monthly-net');
  const summaryBreakdownEl = document.getElementById('summary-monthly-breakdown');

  const currencyCode = summaryBalanceEl?.dataset.currency || 'USD';
  const currencyFormatter = new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: currencyCode,
    minimumFractionDigits: 2,
  });

  const numberFormatter = new Intl.NumberFormat();

  const charts = {};

  function fetchJSON(url) {
    return fetch(url, { headers: { Accept: 'application/json' } }).then((response) => {
      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }
      return response.json();
    });
  }

  function updateSummary() {
    if (!summaryUrl) {
      return;
    }
    fetchJSON(summaryUrl)
      .then((data) => {
        if (data.primary_currency && data.primary_currency !== currencyCode) {
          currencyCode = data.primary_currency;
          currencyFormatter = new Intl.NumberFormat(undefined, {
            style: "currency",
            currency: currencyCode,
            minimumFractionDigits: 2,
          });
        }
        if (summaryAccountsEl) {
          summaryAccountsEl.textContent = numberFormatter.format(data.total_accounts || 0);
        }
        if (summaryTransactionsEl) {
          summaryTransactionsEl.textContent = numberFormatter.format(data.total_transactions || 0);
        }
        if (summaryBalanceEl) {
          summaryBalanceEl.dataset.currency = currencyCode;
          summaryBalanceEl.textContent = currencyFormatter.format(data.total_balance || 0);
        }
        if (summaryNetEl) {
          summaryNetEl.textContent = currencyFormatter.format(data.monthly_net || 0);
          summaryNetEl.classList.remove('text-success', 'text-danger');
          if (data.monthly_net > 0) {
            summaryNetEl.classList.add('text-success');
          } else if (data.monthly_net < 0) {
            summaryNetEl.classList.add('text-danger');
          }
        }
        if (summaryBreakdownEl) {
          summaryBreakdownEl.innerHTML = `
            <span class="text-success">+${currencyFormatter.format(data.monthly_income || 0)}</span>
            /
            <span class="text-danger">-${currencyFormatter.format(data.monthly_expense || 0)}</span>
          `;
        }
      })
      .catch((error) => {
        console.error('Unable to load dashboard summary', error);
      });
  }

  function toggleChartEmptyState(canvasId, hasData) {
    const emptyMessage = document.getElementById(`${canvasId}-empty`);
    const canvas = document.getElementById(canvasId);
    if (!canvas || !emptyMessage) {
      return;
    }
    if (hasData) {
      canvas.classList.remove('d-none');
      emptyMessage.classList.add('d-none');
    } else {
      canvas.classList.add('d-none');
      emptyMessage.classList.remove('d-none');
    }
  }

  function renderAccountsChart() {
    if (!accountsUrl || !window.Chart) {
      return;
    }
    fetchJSON(accountsUrl)
      .then((data) => {
        const accounts = data.accounts || [];
        const hasData = accounts.length > 0;
        toggleChartEmptyState('accounts-chart', hasData);
        if (!hasData) {
          if (charts.accounts) {
            charts.accounts.destroy();
            charts.accounts = null;
          }
          return;
        }
        const ctx = document.getElementById('accounts-chart');
        if (!ctx) {
          return;
        }
        const labels = accounts.map((item) => item.name);
        const values = accounts.map((item) => item.current_balance);
        if (charts.accounts) {
          charts.accounts.destroy();
        }
        charts.accounts = new Chart(ctx, {
          type: 'doughnut',
          data: {
            labels,
            datasets: [
              {
                data: values,
                backgroundColor: [
                  '#4c6ef5',
                  '#845ef7',
                  '#f59f00',
                  '#37b24d',
                  '#ff6b6b',
                  '#15aabf',
                ],
              },
            ],
          },
          options: {
            responsive: true,
            plugins: {
              legend: {
                position: 'bottom',
              },
              tooltip: {
                callbacks: {
                  label(context) {
                    const amount = context.parsed;
                    return `${context.label}: ${currencyFormatter.format(amount)}`;
                  },
                },
              },
            },
          },
        });
      })
      .catch((error) => console.error('Unable to load accounts chart', error));
  }

  function renderSpendingChart() {
    if (!spendingUrl || !window.Chart) {
      return;
    }
    fetchJSON(spendingUrl)
      .then((data) => {
        const labels = data.labels || [];
        const values = data.values || [];
        const hasData = labels.length > 0;
        toggleChartEmptyState('spending-chart', hasData);
        if (!hasData) {
          if (charts.spending) {
            charts.spending.destroy();
            charts.spending = null;
          }
          return;
        }
        const ctx = document.getElementById('spending-chart');
        if (!ctx) {
          return;
        }
        if (charts.spending) {
          charts.spending.destroy();
        }
        charts.spending = new Chart(ctx, {
          type: 'doughnut',
          data: {
            labels,
            datasets: [
              {
                data: values,
                backgroundColor: [
                  '#ff6b6b',
                  '#ffa94d',
                  '#ffd43b',
                  '#69db7c',
                  '#4dabf7',
                  '#b197fc',
                ],
              },
            ],
          },
          options: {
            responsive: true,
            plugins: {
              legend: { position: 'bottom' },
              tooltip: {
                callbacks: {
                  label(context) {
                    return `${context.label}: ${currencyFormatter.format(context.parsed)}`;
                  },
                },
              },
            },
          },
        });
      })
      .catch((error) => console.error('Unable to load spending chart', error));
  }

  function renderCashflowChart() {
    if (!cashflowUrl || !window.Chart) {
      return;
    }
    fetchJSON(cashflowUrl)
      .then((data) => {
        const labels = data.labels || [];
        const incomes = data.income || [];
        const expenses = data.expense || [];
        const hasData = labels.length > 0 && (incomes.some((v) => v !== 0) || expenses.some((v) => v !== 0));
        toggleChartEmptyState('cashflow-chart', hasData);
        if (!hasData) {
          if (charts.cashflow) {
            charts.cashflow.destroy();
            charts.cashflow = null;
          }
          return;
        }
        const ctx = document.getElementById('cashflow-chart');
        if (!ctx) {
          return;
        }
        if (charts.cashflow) {
          charts.cashflow.destroy();
        }
        charts.cashflow = new Chart(ctx, {
          type: 'bar',
          data: {
            labels,
            datasets: [
              {
                label: 'Income',
                data: incomes,
                backgroundColor: '#51cf66',
                borderRadius: 6,
              },
              {
                label: 'Expenses',
                data: expenses,
                backgroundColor: '#ff8787',
                borderRadius: 6,
              },
            ],
          },
          options: {
            responsive: true,
            scales: {
              y: {
                ticks: {
                  callback(value) {
                    return currencyFormatter.format(value);
                  },
                },
              },
            },
            plugins: {
              tooltip: {
                callbacks: {
                  label(context) {
                    return `${context.dataset.label}: ${currencyFormatter.format(context.parsed.y)}`;
                  },
                },
              },
            },
          },
        });
      })
      .catch((error) => console.error('Unable to load cashflow chart', error));
  }

  function initialiseDashboard() {
    updateSummary();
    renderAccountsChart();
    renderSpendingChart();
    renderCashflowChart();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialiseDashboard);
  } else {
    initialiseDashboard();
  }
})();
