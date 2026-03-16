// login.js — Luzinete Turismo
window.addEventListener('DOMContentLoaded', function () {

  function fazerLogin() {
    var btn    = document.getElementById('btn-login');
    var alerta = document.getElementById('alerta');
    alerta.style.display = 'none';

    var email   = document.getElementById('email').value.trim();
    var senha   = document.getElementById('senha').value;
    var lembrar = document.getElementById('lembrar').checked;

    if (!email || !senha) {
      alerta.textContent = 'Preencha e-mail e senha.';
      alerta.style.display = 'flex';
      return;
    }

    btn.disabled = true;
    btn.textContent = 'Entrando...';

    fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email, senha: senha, lembrar: lembrar }),
      credentials: 'same-origin'
    })
    .then(function(res) { return res.json().then(function(data) { return { ok: res.ok, data: data }; }); })
    .then(function(r) {
      if (r.ok) {
        window.location.href = '/dashboard';
      } else {
        alerta.textContent = (r.data && r.data.erro) ? r.data.erro : 'E-mail ou senha incorretos.';
        alerta.style.display = 'flex';
        btn.disabled = false;
        btn.textContent = 'Entrar no sistema';
      }
    })
    .catch(function() {
      alerta.textContent = 'Erro de conexao. Tente novamente.';
      alerta.style.display = 'flex';
      btn.disabled = false;
      btn.textContent = 'Entrar no sistema';
    });
  }

  // Botao
  var btn = document.getElementById('btn-login');
  if (btn) btn.addEventListener('click', fazerLogin);

  // Enter
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') fazerLogin();
  });

});
