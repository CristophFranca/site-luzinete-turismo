/**
 * app.js — Utilitários globais — Luzinete Turismo
 */

// ── Máscaras de input ─────────────────────────────────────
document.addEventListener('input', e => {
  const id = e.target.id;

  if (id === 'p-cpf') {
    let v = e.target.value.replace(/\D/g, '').slice(0, 11);
    if (v.length > 9)      v = v.replace(/(\d{3})(\d{3})(\d{3})(\d{0,2})/, '$1.$2.$3-$4');
    else if (v.length > 6) v = v.replace(/(\d{3})(\d{3})(\d{0,3})/, '$1.$2.$3');
    else if (v.length > 3) v = v.replace(/(\d{3})(\d{0,3})/, '$1.$2');
    e.target.value = v;
  }

  if (['p-tel', 'p-wpp'].includes(id)) {
    let v = e.target.value.replace(/\D/g, '').slice(0, 11);
    if (v.length > 10)     v = v.replace(/(\d{2})(\d{5})(\d{4})/, '($1) $2-$3');
    else if (v.length > 6) v = v.replace(/(\d{2})(\d{4,5})(\d{0,4})/, '($1) $2-$3');
    else if (v.length > 2) v = v.replace(/(\d{2})(\d{0,5})/, '($1) $2');
    e.target.value = v;
  }
});

// ── Fechar modal com Escape ───────────────────────────────
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.open').forEach(m => m.classList.remove('open'));
  }
});

// ── BUSCA GLOBAL ─────────────────────────────────────────────
let buscaTimeout;
function buscaGlobal(q) {
  clearTimeout(buscaTimeout);
  const dd = document.getElementById('busca-dropdown');
  if (!q || q.length < 2) { dd.style.display = 'none'; return; }
  buscaTimeout = setTimeout(async () => {
    const r = await api.get('/api/busca/?q=' + encodeURIComponent(q));
    if (!r.ok) return;
    const { passagens, encomendas } = r.data;
    if (!passagens.length && !encomendas.length) {
      dd.innerHTML = '<div class="busca-empty">Nenhum resultado encontrado.</div>';
      dd.style.display = 'block'; return;
    }
    let html = '';
    if (passagens.length) {
      html += '<div class="busca-section-title">Passagens</div>';
      passagens.forEach(p => {
        const tag = p.cancelada ? ' <span style="color:var(--vermelho);font-weight:400">(cancelada)</span>' : '';
        html += `<div class="busca-item" onclick="window.location='/historico'">
          <div class="busca-item-icon p">🎫</div>
          <div>
            <div class="busca-item-main">${p.nome}${tag}</div>
            <div class="busca-item-sub">${p.codigo} · Poltrona ${p.poltrona} · ${p.origem} → ${p.destino} · ${p.data}</div>
          </div>
        </div>`;
      });
    }
    if (encomendas.length) {
      html += '<div class="busca-section-title">Encomendas</div>';
      encomendas.forEach(e => {
        html += `<div class="busca-item" onclick="window.location='/encomendas/historico'">
          <div class="busca-item-icon e">📦</div>
          <div>
            <div class="busca-item-main">${e.remetente} → ${e.destinatario}</div>
            <div class="busca-item-sub">${e.codigo} · ${e.origem} → ${e.destino} · ${e.status}</div>
          </div>
        </div>`;
      });
    }
    dd.innerHTML = html;
    dd.style.display = 'block';
  }, 300);
}

function showDropdown() {
  const q = document.getElementById('busca-global-input');
  if (q && q.value.length >= 2) buscaGlobal(q.value);
}

function hideDropdown() {
  setTimeout(() => {
    const dd = document.getElementById('busca-dropdown');
    if (dd) dd.style.display = 'none';
  }, 180);
}

// Atalho / para focar busca
document.addEventListener('keydown', e => {
  if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
    e.preventDefault();
    document.getElementById('busca-global-input')?.focus();
  }
});
