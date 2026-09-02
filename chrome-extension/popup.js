/** Enseña la sesión que la extensión está contando ahora mismo, si hay alguna. */

const content = document.getElementById("content");

function fmt(totalSeconds) {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  const pad = (n) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

async function render() {
  const { config } = await chrome.storage.local.get("config");
  if (!config || !config.baseUrl) {
    content.innerHTML = '<p class="empty">Sin configurar todavía — abre Ajustes.</p>';
    return;
  }

  const { current } = await chrome.storage.session.get("current");
  if (!current) {
    content.innerHTML = '<p class="empty">Sin actividad de Udemy detectada ahora mismo.</p>';
    return;
  }

  const elapsed = Math.floor((Date.now() - current.startedAt) / 1000);
  content.innerHTML = `
    <p class="task-title">${current.task.title}</p>
    <p class="elapsed">${fmt(elapsed)}</p>
  `;
}

document.getElementById("open-options").addEventListener("click", (e) => {
  e.preventDefault();
  chrome.runtime.openOptionsPage();
});

render();
setInterval(render, 1000);
