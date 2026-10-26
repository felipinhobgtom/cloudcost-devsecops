"use strict";

const form = document.getElementById("cost-form");
const fields = document.getElementById("scenario-fields");
const calculateButton = document.getElementById("calculate-button");
const calculateLabel = document.getElementById("calculate-label");
const resetButton = document.getElementById("reset-button");
const resultCard = document.getElementById("result-card");
const resultValues = document.getElementById("result-values");
const resultSource = document.getElementById("result-source");
const statusMessage = document.getElementById("calculation-status");
const errorMessage = document.getElementById("calculation-error");
const totalOutput = document.getElementById("total");
const fieldNames = ["instances", "hours_per_month", "hourly_rate", "storage_gb", "storage_rate", "egress_gb", "egress_rate"];
const categories = ["compute", "storage", "egress"];
const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "USD" });
const amount = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
let hasResult = false;

function showResult(data) {
  totalOutput.textContent = amount.format(data.total);
  for (const category of categories) {
    document.getElementById(category).textContent = money.format(data[category]);
    const share = data.total === 0 ? 0 : (data[category] / data.total) * 100;
    const progress = document.getElementById(`${category}-share`);
    progress.value = share;
    progress.textContent = `${amount.format(share)}%`;
  }
  hasResult = true;
}

function clearResult() {
  totalOutput.textContent = "—";
  for (const category of categories) {
    document.getElementById(category).textContent = "—";
    const progress = document.getElementById(`${category}-share`);
    progress.value = 0;
    progress.textContent = "0%";
  }
  hasResult = false;
}

async function calculate(event) {
  if (event) event.preventDefault();
  if (calculateButton.disabled || !form.reportValidity()) return;

  const payload = {};
  for (const name of fieldNames) {
    payload[name] = form.elements.namedItem(name).valueAsNumber;
  }

  fields.disabled = true;
  calculateButton.disabled = true;
  resetButton.disabled = true;
  calculateLabel.textContent = "Calculando…";
  resultCard.dataset.state = "loading";
  resultValues.setAttribute("aria-busy", "true");
  resultSource.textContent = "Consultando API";
  statusMessage.textContent = "Calculando seu cenário no servidor…";
  errorMessage.hidden = true;

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch("/api/estimate", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload),
      credentials: "omit",
      cache: "no-store",
      redirect: "error",
      signal: controller.signal
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(typeof data.error === "string" ? data.error : "Não foi possível calcular este cenário.");
    }
    if (data.currency !== "USD" || ![...categories, "total"].every((key) => typeof data[key] === "number" && Number.isFinite(data[key]) && data[key] >= 0)) {
      throw new Error("O serviço retornou uma resposta inesperada. Tente novamente.");
    }
    showResult(data);
    resultCard.dataset.state = "success";
    resultSource.textContent = "Calculado pela API";
    statusMessage.textContent = `Estimativa atualizada: ${money.format(data.total)} por mês. Altere os valores para explorar outro cenário.`;
  } catch (error) {
    clearResult();
    resultCard.dataset.state = "error";
    resultSource.textContent = "Cálculo indisponível";
    statusMessage.textContent = "Nenhuma estimativa foi gerada. Seus valores continuam no formulário.";
    errorMessage.textContent = error.name === "AbortError"
      ? "O servidor demorou para responder. Verifique a conexão e calcule novamente."
      : error instanceof TypeError || error instanceof SyntaxError
        ? "Não foi possível acessar a API. Verifique a conexão e tente novamente."
        : error.message;
    errorMessage.hidden = false;
  } finally {
    window.clearTimeout(timeout);
    fields.disabled = false;
    calculateButton.disabled = false;
    resetButton.disabled = false;
    calculateLabel.textContent = "Calcular estimativa";
    resultValues.setAttribute("aria-busy", "false");
  }
}

form.addEventListener("submit", calculate);
form.addEventListener("input", () => {
  resultCard.dataset.state = "stale";
  resultSource.textContent = hasResult ? "Resultado anterior" : "Aguardando cálculo";
  statusMessage.textContent = hasResult
    ? "Valores alterados. O resultado acima é do cálculo anterior; calcule novamente para atualizar."
    : "Valores alterados. Calcule para obter uma estimativa.";
  errorMessage.hidden = true;
});
resetButton.addEventListener("click", () => {
  form.reset();
  form.requestSubmit();
});

calculateButton.disabled = false;
resetButton.disabled = false;
form.requestSubmit();
