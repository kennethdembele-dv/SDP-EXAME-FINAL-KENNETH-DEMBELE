/* Global-Scale: interface Web. Usa so a API REST publica (a mesma documentada em /docs). */
"use strict";

const E = (id) => document.getElementById(id);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const eur = (c) => new Intl.NumberFormat("pt-PT", { style: "currency", currency: "EUR" }).format((c || 0) / 100);
const data = (iso) => (iso ? new Date(iso).toLocaleString("pt-PT", { dateStyle: "short", timeStyle: "medium" }) : "—");
const curto = (id) => String(id || "").slice(0, 8);
const chip = (s) => `<span class="estado e-${esc(s)}">${esc(s || "—")}</span>`;
const regiaoDe = (conta) => (String(conta).startsWith("EU") ? "europa" : "america");
const NOMES_NO = { europa: "Europa (db-europa)", america: "América (db-america)" };
const TERMINAIS = ["CONCLUIDA", "ABORTADA"];
const EXPLICACAO = {
  INICIADA: "Registada no coordenador; a preparar os participantes.",
  PREPARADA: "Todos os participantes prepararam; a gravar a decisão.",
  COMMIT_DECIDIDO: "Decisão COMMIT gravada; falta aplicá-la num nó que não respondeu. O crédito/débito aparece quando o nó voltar — a recuperação repete automaticamente.",
  CONCLUIDA: "Confirmada em todos os participantes: exactamente um débito e um crédito.",
  ABORT_DECIDIDO: "Decisão ABORT gravada; a desfazer nos participantes pendentes. Nenhum saldo muda.",
  ABORTADA: "Abortada em todos os participantes: nenhum saldo foi alterado.",
};

// Duas instancias da API: a que serviu a pagina e a outra (failover no navegador).
const OUTRA = location.port === "8001" ? location.origin.replace(":8001", ":8002") : location.origin.replace(":8002", ":8001");
const BASES = [location.origin, OUTRA];
let base = BASES[0];
const estado = { token: null, contas: [], ultimaOrdem: null, transferencias: [] };
const temporizadores = {};

// ------------------------------------------------------------------ utilitarios
function guardar(chave, valor) { try { valor == null ? sessionStorage.removeItem(chave) : sessionStorage.setItem(chave, valor); } catch (_) { /* sem armazenamento */ } }
function ler(chave) { try { return sessionStorage.getItem(chave); } catch (_) { return null; } }

function aviso(texto, ms = 4200) {
  const a = E("aviso");
  a.textContent = texto;
  a.hidden = false;
  clearTimeout(temporizadores.aviso);
  temporizadores.aviso = setTimeout(() => (a.hidden = true), ms);
}

function decodificarJwt(token) {
  const [h, c] = token.split(".").slice(0, 2).map((p) => JSON.parse(decodeURIComponent(escape(atob(p.replace(/-/g, "+").replace(/_/g, "/"))))));
  return { cabecalho: h, carga: c };
}

function mostrarInstancia(inst, b) {
  const p = E("pill-instancia");
  p.textContent = `● ${inst}`;
  p.title = `Respondeu: ${inst} (${b})`;
}

/** Pedido a API com failover: se a instancia actual nao aceitar a ligacao, tenta a outra. */
async function api(metodo, caminho, corpo, cabecalhos = {}) {
  const ordem = [base, ...BASES.filter((b) => b !== base)];
  let ultimoErro;
  for (const b of ordem) {
    try {
      const h = { ...cabecalhos };
      if (estado.token) h.Authorization = `Bearer ${estado.token}`;
      if (corpo !== undefined) h["Content-Type"] = "application/json";
      const r = await fetch(b + caminho, { method: metodo, headers: h, body: corpo === undefined ? undefined : JSON.stringify(corpo) });
      const inst = r.headers.get("X-Instancia") || "?";
      if (b !== base) {
        aviso(`A instância anterior não respondeu: o pedido foi atendido pela ${inst}.`);
        base = b;
      }
      mostrarInstancia(inst, b);
      const tipo = r.headers.get("content-type") || "";
      const dados = tipo.includes("json") ? await r.json() : await r.text();
      if (r.status === 401 && estado.token && !caminho.includes("/autenticacao/")) {
        sair(typeof dados === "object" && dados.detail ? `Sessão terminada: ${dados.detail}` : "Sessão terminada");
      }
      return { status: r.status, ok: r.ok, dados, instancia: inst };
    } catch (e) {
      ultimoErro = e; // ligacao recusada ou sem resposta: tenta a outra instancia
    }
  }
  throw new Error(`Nenhuma instância da API responde (${ultimoErro?.message || "erro de rede"}).`);
}

function mensagemErro(r) {
  const d = r.dados;
  if (d && typeof d === "object") {
    if (Array.isArray(d.detail)) return d.detail.map((x) => x.msg).join("; ");
    if (d.detail) return d.detail;
    if (d.motivo) return d.motivo;
  }
  return `HTTP ${r.status}`;
}

// ------------------------------------------------------------------ entrada e sessao
async function entrar(utilizador, senha) {
  E("e-erro").textContent = "";
  try {
    const r = await api("POST", "/api/v1/autenticacao/token", { utilizador, palavra_passe: senha });
    if (!r.ok) { E("e-erro").textContent = mensagemErro(r); return; }
    iniciarSessao(r.dados.access_token);
  } catch (e) {
    E("e-erro").textContent = e.message;
  }
}

function iniciarSessao(token) {
  estado.token = token;
  estado.jwt = decodificarJwt(token);
  guardar("gs-token", token);
  const c = estado.jwt.carga;
  E("u-nome").textContent = c.nome || c.sub;
  E("u-regiao").textContent = c.regiao === "EU" ? "Região Europa" : "Região América";
  E("u-avatar").textContent = (c.nome || c.sub || "?").slice(0, 1).toUpperCase();
  E("entrada").hidden = true;
  E("app").hidden = false;
  clearInterval(temporizadores.token);
  temporizadores.token = setInterval(actualizarValidade, 1000);
  actualizarValidade();
  irPara(location.hash.slice(1) || "painel");
}

function actualizarValidade() {
  if (!estado.jwt) return;
  const resta = estado.jwt.carga.exp - Math.floor(Date.now() / 1000);
  if (resta <= 0) { sair("O token expirou (15 minutos). Entre de novo."); return; }
  E("pill-token").textContent = `JWT ${String(Math.floor(resta / 60)).padStart(2, "0")}:${String(resta % 60).padStart(2, "0")}`;
}

function sair(motivo) {
  estado.token = null;
  estado.jwt = null;
  guardar("gs-token", null);
  Object.keys(temporizadores).forEach((k) => { clearInterval(temporizadores[k]); clearTimeout(temporizadores[k]); });
  E("app").hidden = true;
  E("entrada").hidden = false;
  E("gaveta").hidden = true;
  if (motivo) E("e-erro").textContent = motivo;
}

// ------------------------------------------------------------------ navegacao
const VISTAS = {
  painel: ["Painel", carregarPainel], contas: ["Contas e saldos", carregarContas], transferir: ["Transferir", prepararTransferir],
  transferencias: ["Monitor do Two-Phase Commit", carregarMonitor], relatorios: ["Relatórios e auditoria no DFS", carregarRelatorios],
  sistema: ["Estado do sistema distribuído", carregarSistema], seguranca: ["Segurança", carregarSeguranca],
};

function irPara(nome) {
  if (!VISTAS[nome]) nome = "painel";
  if (location.hash !== `#${nome}`) history.replaceState(null, "", `#${nome}`);
  document.querySelectorAll(".vista").forEach((v) => (v.hidden = v.id !== `v-${nome}`));
  document.querySelectorAll("#menu a").forEach((a) => a.classList.toggle("activo", a.dataset.vista === nome));
  E("titulo-vista").textContent = VISTAS[nome][0];
  document.querySelector(".lateral").classList.remove("aberta");
  clearInterval(temporizadores.monitor);
  clearInterval(temporizadores.sistema);
  VISTAS[nome][1]();
}

// ------------------------------------------------------------------ painel
async function obterContas() {
  const r = await api("GET", "/api/v1/contas");
  if (r.ok) estado.contas = r.dados.contas;
  return estado.contas;
}

async function carregarPainel() {
  try {
    const [contas, rt] = await Promise.all([obterContas(), api("GET", "/api/v1/transferencias")]);
    const lista = rt.ok ? rt.dados.transferencias : [];
    estado.transferencias = lista;
    E("k-saldo").textContent = eur(contas.reduce((s, c) => s + c.saldo_centimos, 0));
    E("k-contas").textContent = `${contas.length} conta(s) no nó ${contas[0] ? NOMES_NO[contas[0].no] : "—"}`;
    E("k-concluidas").textContent = lista.filter((t) => t.estado === "CONCLUIDA").length;
    E("k-pendentes").textContent = lista.filter((t) => !TERMINAIS.includes(t.estado)).length;
    E("k-abortadas").textContent = lista.filter((t) => t.estado === "ABORTADA").length;
    E("p-contas").innerHTML = contas.map((c) => `
      <div class="linha-conta"><div><b>${esc(c.id)}</b><br><small>${esc(NOMES_NO[c.no])}</small></div>
      <span class="valor">${eur(c.saldo_centimos)}</span></div>`).join("") || '<div class="vazio">Sem contas.</div>';
    E("p-transf").innerHTML = tabelaTransferencias(lista.slice(0, 6));
    ligarLinhas(E("p-transf"));
  } catch (e) { aviso(e.message); }
  try {
    const rs = await api("GET", "/api/v1/sistema/estado");
    if (rs.ok) E("p-sistema").innerHTML = rs.dados.componentes.map((c) =>
      `<div><span class="ponto ${c.estado}"></span><b>${esc(c.nome)}</b></div>`).join("");
  } catch (_) { /* o painel continua utilizavel */ }
}

// ------------------------------------------------------------------ contas
async function carregarContas() {
  try {
    const contas = await obterContas();
    E("c-contas").innerHTML = contas.map((c) => `
      <button class="cartao-conta ${c.no === "america" ? "us" : ""}" data-conta="${esc(c.id)}">
        <div class="cc-topo"><span>${esc(NOMES_NO[c.no])}</span><span>${esc(c.moeda)}</span></div>
        <div class="cc-num">${esc(c.id)}</div>
        <div><small>Saldo disponível</small><div class="cc-saldo">${eur(c.saldo_centimos)}</div></div>
        <div class="cc-topo"><span>Titular: ${esc(c.titular)}</span><span>desde ${new Date(c.criada_em).toLocaleDateString("pt-PT")}</span></div>
      </button>`).join("");
    E("c-contas").querySelectorAll("[data-conta]").forEach((b) => b.addEventListener("click", () => mostrarHistorico(b.dataset.conta)));
    if (contas[0]) mostrarHistorico(estado.contaHistorico || contas[0].id);
  } catch (e) { aviso(e.message); }
}

async function mostrarHistorico(conta) {
  estado.contaHistorico = conta;
  document.querySelectorAll(".cartao-conta").forEach((b) => b.classList.toggle("seleccionada", b.dataset.conta === conta));
  E("c-historico-cartao").hidden = false;
  E("c-historico-titulo").textContent = `Histórico de ${conta}`;
  const r = await api("GET", `/api/v1/contas/${conta}/movimentos`);
  if (!r.ok) { E("c-historico").innerHTML = `<div class="vazio">${esc(mensagemErro(r))}</div>`; return; }
  const m = r.dados.movimentos;
  E("c-historico").innerHTML = m.length ? `<div class="rolar"><table class="tabela"><thead><tr><th>Data</th><th>Tipo</th><th>Contraparte</th>
    <th class="num">Montante</th><th class="num">Saldo após</th><th>Transferência</th></tr></thead><tbody>${m.map((x) => `
    <tr class="clicavel" data-transf="${esc(x.transferencia_id)}"><td>${data(x.data)}</td>
      <td>${x.tipo === "DEBITO" ? '<span class="debito">▼ Débito</span>' : '<span class="credito">▲ Crédito</span>'}</td>
      <td class="mono">${esc(x.contraparte)}</td>
      <td class="num ${x.tipo === "DEBITO" ? "debito" : "credito"}">${x.tipo === "DEBITO" ? "−" : "+"}${eur(x.montante_centimos)}</td>
      <td class="num">${esc(x.saldo_apos)} €</td><td class="mono">${curto(x.transferencia_id)}…</td></tr>`).join("")}</tbody></table></div>`
    : '<div class="vazio">Ainda não há movimentos nesta conta.</div>';
  ligarLinhas(E("c-historico"));
}

// ------------------------------------------------------------------ transferir
function novaChave() { E("t-chave").value = `web-${crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36)}`; }

async function prepararTransferir() {
  if (!E("t-chave").value) novaChave();
  const contas = estado.contas.length ? estado.contas : await obterContas();
  const actual = E("t-origem").value;
  E("t-origem").innerHTML = contas.map((c) => `<option value="${esc(c.id)}">${esc(c.id)} · ${eur(c.saldo_centimos)}</option>`).join("");
  if (actual) E("t-origem").value = actual;
  mostrarRota();
}

function mostrarRota() {
  const o = E("t-origem").value, d = E("t-destino").value.trim().toUpperCase();
  if (!/^(EU|US)-\d{4}$/.test(d)) { E("t-rota").textContent = ""; return; }
  const a = regiaoDe(o), b = regiaoDe(d);
  E("t-rota").innerHTML = a === b
    ? `Mesma região: um só participante (${esc(NOMES_NO[a])}).`
    : `<b>Entre regiões:</b> débito em ${esc(NOMES_NO[a])}, crédito em ${esc(NOMES_NO[b])} — dois participantes no 2PC.`;
}

async function enviarTransferencia(repetir = false) {
  E("t-erro").textContent = "";
  const corpo = { conta_origem: E("t-origem").value, conta_destino: E("t-destino").value.trim().toUpperCase(),
    montante: E("t-montante").value.trim().replace(",", "."), moeda: "EUR" };
  const chave = E("t-chave").value.trim();
  const botao = E("b-transferir");
  botao.disabled = true;
  botao.textContent = "A executar o 2PC…";
  if (!repetir) E("t-linha").innerHTML = '<div class="vazio">A enviar a ordem assinada ao coordenador…</div>';
  try {
    const r = await api("POST", "/api/v1/transferencias", corpo, { "Idempotency-Key": chave });
    const t = r.dados;
    if (t && typeof t === "object" && t.id) {
      if (t.ordem_assinada) estado.ultimaOrdem = { ...t.ordem_assinada, id: t.id, corpo, chave };
      estado.ultimoHttp = { id: t.id, status: r.status };
      desenharLinha(E("t-linha"), t, r);
      E("b-repetir").disabled = false;
      if (repetir) aviso(t.repetido ? "Mesma chave: a API devolveu a transferência existente (não duplicou)." : "Pedido repetido.");
      acompanhar(t.id);
      obterContas().then(prepararTransferir);
    } else {
      E("t-erro").textContent = mensagemErro(r);
      E("t-linha").innerHTML = `<div class="vazio">Pedido recusado antes do 2PC: ${esc(mensagemErro(r))}</div>`;
    }
  } catch (e) {
    E("t-erro").textContent = e.message;
  } finally {
    botao.disabled = false;
    botao.textContent = "Transferir";
  }
}

/** Enquanto a transferencia nao terminar (ou o parceiro nao confirmar), consulta o estado a cada 2 s. */
function acompanhar(id) {
  clearInterval(temporizadores.acompanhar);
  let vezes = 0;
  temporizadores.acompanhar = setInterval(async () => {
    vezes += 1;
    try {
      const r = await api("GET", `/api/v1/transferencias/${id}`);
      if (!r.ok) return;
      const t = r.dados;
      if (!E("v-transferir").hidden && estado.ultimaOrdem?.id === id) desenharLinha(E("t-linha"), t, { status: estado.ultimoHttp?.status || r.status, instancia: r.instancia });
      if ((TERMINAIS.includes(t.estado) && t.parceiro.estado !== "POR_ENVIAR") || vezes > 90) clearInterval(temporizadores.acompanhar);
    } catch (_) { /* tenta outra vez */ }
  }, 2000);
}

/** Linha temporal do protocolo, coerente com o estado do coordenador e de cada participante. */
function desenharLinha(alvo, t, r) {
  alvo.className = "";
  const ordem = { europa: 0, america: 1 };
  const parts = (t.participantes || []).slice().sort((a, b) => ordem[a.no] - ordem[b.no]);
  const pendentes = t.pendente_em || [];
  const commit = t.decisao === "COMMIT", abort = t.decisao === "ABORT";
  const passo = (classe, num, titulo, texto, extra = "") =>
    `<div class="passo ${classe}"><div class="marcador">${num}</div><div><h3>${titulo}</h3><p>${texto}</p>${extra}</div></div>`;
  const cartoesParts = `<div class="participantes">${parts.map((p) => `
      <div class="participante"><div><b>${esc(NOMES_NO[p.no] || p.no)}</b> ${chip(p.estado)}</div><small>${esc(p.gid)}</small></div>`).join("")}</div>`;
  const fase1 = commit ? "feito" : abort ? "erro" : "espera";
  const fase2 = TERMINAIS.includes(t.estado) ? "feito" : t.decisao ? "espera" : "";
  const parceiro = t.parceiro || {};
  alvo.innerHTML = `
    <div class="resumo-transf">
      <span class="mono">${esc(t.conta_origem)}</span><span class="seta">→</span><span class="mono">${esc(t.conta_destino)}</span>
      ${chip(t.estado)} <span class="pill neutro">HTTP ${esc(r.status)}</span>
      <span class="pill" title="Instância que assinou a ordem">${esc(t.instancia_api)}</span>
      ${t.repetido ? '<span class="pill neutro">repetido (idempotência)</span>' : ""}
      <span class="montante">${eur(t.montante_centimos)}</span>
    </div>
    <p class="explicacao">${esc(EXPLICACAO[t.estado] || t.explicacao)}${t.motivo ? ` — <b>${esc(t.motivo)}</b>` : ""}</p>
    <div class="linha-2pc">
      ${passo("feito", "1", "Ordem assinada e registada",
        `A ${esc(t.instancia_api)} assinou a ordem (RSA-PSS/SHA-256); o coordenador verificou a assinatura e o JWT e registou-a
         com a chave <code>${esc(t.chave_idempotencia)}</code>. Criada às ${data(t.criada_em)}.`)}
      ${passo(fase1, "2", "Fase 1 — preparação nos participantes",
        abort ? `Um participante votou NÃO ou não respondeu (<b>${esc(t.codigo_erro)}</b>).`
          : "Cada nó faz o débito ou o crédito e <code>PREPARE TRANSACTION</code>, pela ordem fixa Europa → América.", cartoesParts)}
      ${passo(t.decisao ? (commit ? "feito" : "erro") : "espera", "3", `Decisão global: ${t.decisao || "por decidir"}`,
        t.decisao ? `Gravada no registo durável do coordenador às ${data(t.decidida_em)}, antes de ser comunicada. Já não muda.`
          : "O coordenador aguarda os votos.")}
      ${passo(fase2, "4", "Fase 2 — confirmação",
        t.estado === "CONCLUIDA" ? `<code>COMMIT PREPARED</code> em todos os nós às ${data(t.concluida_em)}: um débito e um crédito.`
          : t.estado === "ABORTADA" ? "<code>ROLLBACK PREPARED</code> nos nós que tinham preparado: nenhum saldo mudou."
            : pendentes.length ? `Pendente em <b>${esc(pendentes.join(", "))}</b>: a recuperação repete a decisão a cada 5 s até o nó responder.`
              : "À espera da decisão.")}
      ${passo(parceiro.estado === "CONFIRMADA" ? "feito" : parceiro.estado === "POR_ENVIAR" ? "espera" : "", "5",
        "Banco parceiro (Java, XML)",
        parceiro.estado === "CONFIRMADA" ? `Confirmação aceite com a referência <b>${esc(parceiro.referencia)}</b>.`
          : parceiro.estado === "POR_ENVIAR" ? "Confirmação por enviar (o Java pode estar em baixo); o coordenador repete." : "Não se aplica (transferência não concluída).")}
    </div>
    <div class="acoes"><button class="botao fantasma" data-detalhe="${esc(t.id)}">Detalhe, auditoria e XML</button></div>`;
  alvo.querySelector("[data-detalhe]").addEventListener("click", () => abrirDetalhe(t.id));
}

// ------------------------------------------------------------------ monitor 2PC
function tabelaTransferencias(lista) {
  if (!lista.length) return '<div class="vazio">Ainda não há transferências.</div>';
  return `<div class="rolar"><table class="tabela"><thead><tr><th>Criada</th><th>Id</th><th>Origem → destino</th><th class="num">Montante</th>
    <th>Estado</th><th>Participantes</th><th>Parceiro</th><th>API</th></tr></thead><tbody>${lista.map((t) => `
    <tr class="clicavel" data-transf="${esc(t.id)}"><td>${data(t.criada_em)}</td><td class="mono">${curto(t.id)}…</td>
      <td class="mono">${esc(t.conta_origem)} → ${esc(t.conta_destino)}</td><td class="num">${eur(t.montante_centimos)}</td>
      <td>${chip(t.estado)}</td>
      <td>${(t.participantes || []).map((p) => `<span title="${esc(p.gid)}">${p.no === "europa" ? "EU" : "US"} ${chip(p.estado)}</span>`).join(" ")}</td>
      <td>${chip(t.parceiro.estado)}</td><td>${esc(t.instancia_api)}</td></tr>`).join("")}</tbody></table></div>`;
}

function ligarLinhas(raiz) {
  raiz.querySelectorAll("[data-transf]").forEach((tr) => tr.addEventListener("click", () => abrirDetalhe(tr.dataset.transf)));
}

async function carregarMonitor() {
  const desenhar = async () => {
    try {
      const r = await api("GET", "/api/v1/transferencias");
      if (r.ok) { E("m-tabela").innerHTML = tabelaTransferencias(r.dados.transferencias); ligarLinhas(E("m-tabela")); }
    } catch (e) { E("m-tabela").innerHTML = `<div class="vazio">${esc(e.message)}</div>`; }
  };
  await desenhar();
  if (E("m-auto").checked) temporizadores.monitor = setInterval(desenhar, 3000);
}

// ------------------------------------------------------------------ detalhe (gaveta)
async function abrirDetalhe(id) {
  E("gaveta").hidden = false;
  E("g-titulo").textContent = `Transferência ${curto(id)}…`;
  E("g-corpo").innerHTML = '<div class="vazio">A carregar…</div>';
  const r = await api("GET", `/api/v1/transferencias/${id}`);
  if (!r.ok) { E("g-corpo").innerHTML = `<div class="vazio">${esc(mensagemErro(r))}</div>`; return; }
  E("g-corpo").innerHTML = `<div class="cartao" id="g-linha"></div>
    <div class="cartao"><div class="cartao-topo"><h2>Banco parceiro (Java)</h2><button class="botao fantasma" id="g-b-parceiro">Consultar por XML</button></div>
      <div id="g-parceiro" class="nota">Consulta <code>GET /legado/transferencias/{id}</code> no serviço Java, em XML sobre HTTPS.</div></div>
    <div class="cartao"><div class="cartao-topo"><h2>Auditoria no DFS (NFS)</h2><button class="botao fantasma" id="g-b-auditoria">Ler eventos</button></div>
      <div id="g-auditoria" class="nota">Um ficheiro JSON por evento, escrito por cada serviço em <code>/mnt/dfs/auditoria</code>.</div></div>
    <details class="cartao"><summary><b>Resposta JSON completa</b></summary><pre class="bloco">${esc(JSON.stringify(r.dados, null, 2))}</pre></details>`;
  desenharLinha(E("g-linha"), r.dados, r);
  E("g-linha").querySelector("[data-detalhe]")?.remove();
  E("g-b-parceiro").addEventListener("click", async () => {
    const p = await api("GET", `/api/v1/parceiro/transferencias/${id}`);
    E("g-parceiro").innerHTML = p.ok
      ? `<dl class="claims">${Object.entries(p.dados.registo).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>
         <p class="nota">XML recebido do Java:</p><pre class="bloco">${esc(p.dados.xml_recebido)}</pre>`
      : `<div class="vazio">HTTP ${p.status}: ${esc(mensagemErro(p))}</div>`;
  });
  E("g-b-auditoria").addEventListener("click", async () => {
    const a = await api("GET", `/api/v1/transferencias/${id}/auditoria`);
    E("g-auditoria").innerHTML = a.ok
      ? `<p class="nota">Lido por <b>${esc(a.dados.lido_por)}</b> no DFS partilhado.</p><div class="rolar"><table class="tabela"><thead><tr><th>Data UTC</th><th>Serviço</th><th>Evento</th><th>Resultado</th></tr></thead>
         <tbody>${a.dados.eventos.map((e) => `<tr title="${esc(e.ficheiro)}"><td class="mono">${esc(e.data_utc.slice(11, 23))}</td><td>${esc(e.servico)}</td>
         <td class="mono">${esc(e.evento)}</td><td>${esc(String(e.resultado).slice(0, 70))}</td></tr>`).join("")}</tbody></table></div>`
      : `<div class="vazio">HTTP ${a.status}: ${esc(mensagemErro(a))}</div>`;
  });
}

// ------------------------------------------------------------------ relatorios (DFS)
async function carregarRelatorios() {
  const contas = estado.contas.length ? estado.contas : await obterContas();
  E("r-conta").innerHTML = contas.map((c) => `<option>${esc(c.id)}</option>`).join("");
  listarRelatorios();
}

async function listarRelatorios() {
  const r = await api("GET", "/api/v1/relatorios");
  if (!r.ok) { E("r-lista").innerHTML = `<div class="vazio">${esc(mensagemErro(r))}</div>`; return; }
  const nomes = r.dados.relatorios.slice().reverse();
  E("r-lista").innerHTML = nomes.length ? `<table class="tabela"><thead><tr><th>Ficheiro</th><th>Escrito por</th></tr></thead><tbody>${nomes.map((n) => `
    <tr class="clicavel" data-rel="${esc(n)}"><td class="mono">${esc(n)}</td><td>${esc(n.split("_").pop().replace(".csv", ""))}</td></tr>`).join("")}</tbody></table>`
    : '<div class="vazio">Ainda não há relatórios.</div>';
  E("r-lista").querySelectorAll("[data-rel]").forEach((tr) => tr.addEventListener("click", () => abrirRelatorio(tr.dataset.rel)));
}

async function abrirRelatorio(nome) {
  const r = await api("GET", `/api/v1/relatorios/${encodeURIComponent(nome)}`);
  E("r-titulo").textContent = nome;
  E("r-lido").textContent = `lido por ${r.instancia}`;
  if (!r.ok) { E("r-conteudo").innerHTML = `<div class="vazio">${esc(mensagemErro(r))}</div>`; return; }
  const linhas = String(r.dados).trim().split(/\r?\n/).map((l) => l.split(","));
  E("r-conteudo").className = "";
  E("r-conteudo").innerHTML = `<div class="rolar"><table class="tabela">${linhas.map((l, i) =>
    `<tr>${l.map((c) => (i === 0 || i === 3 ? `<th>${esc(c)}</th>` : `<td>${esc(c)}</td>`)).join("")}</tr>`).join("")}</table></div>`;
}

async function gerarExtracto(conta) {
  const r = await api("POST", "/api/v1/relatorios/extracto", { conta });
  if (r.ok) {
    aviso(`Extracto escrito no DFS pela ${r.dados.escrito_por}.`);
    if (!E("v-relatorios").hidden) {
      E("r-msg").innerHTML = `Escrito por <b>${esc(r.dados.escrito_por)}</b> em <code>${esc(r.dados.caminho_dfs)}</code> (${r.dados.movimentos} movimentos).`;
      await listarRelatorios();
      abrirRelatorio(r.dados.nome);
    }
  } else aviso(mensagemErro(r));
}

// ------------------------------------------------------------------ estado do sistema
async function carregarSistema() {
  const desenhar = async () => {
    try {
      const r = await api("GET", "/api/v1/sistema/estado");
      if (!r.ok) return;
      const comps = r.dados.componentes;
      E("s-topologia").innerHTML = comps.map((c) => `
        <div class="no ${c.estado}"><header><span class="ponto ${c.estado}"></span><b>${esc(c.nome)}</b></header>
        <span>${esc(c.tipo)}</span><small>${esc(c.detalhe)}</small></div>`).join("");
      E("s-tabela").innerHTML = `<div class="rolar"><table class="tabela"><thead><tr><th>Componente</th><th>Endereço</th><th>Estado</th>
        <th class="num">Tempo</th><th>Detalhe</th></tr></thead><tbody>${comps.map((c) => `<tr><td><b>${esc(c.nome)}</b><br><small>${esc(c.tipo)}</small></td>
        <td class="mono">${esc(c.endereco)}</td><td>${chip(c.estado)}</td><td class="num">${c.ms} ms</td><td>${esc(c.detalhe)}</td></tr>`).join("")}</tbody></table></div>`;
      E("s-hora").textContent = `Verificado pela ${r.dados.instancia} em ${data(r.dados.verificado_em)}.`;
    } catch (e) { E("s-hora").textContent = e.message; }
  };
  await desenhar();
  if (E("s-auto").checked) temporizadores.sistema = setInterval(desenhar, 3000);
}

// ------------------------------------------------------------------ seguranca
function carregarSeguranca() {
  const partes = estado.token.split(".");
  E("j-partes").innerHTML = `<span class="h">${esc(partes[0])}</span>.<span class="c">${esc(partes[1])}</span>.<span class="s">${esc(partes[2])}</span>`;
  const { cabecalho, carga } = estado.jwt;
  const linhas = { ...Object.fromEntries(Object.entries(cabecalho).map(([k, v]) => [`header.${k}`, v])), ...carga };
  const explicar = { iss: "emissor (verificado)", aud: "destinatário (verificado)", exp: "expira", iat: "emitido", nbf: "válido a partir de", sub: "utilizador", jti: "identificador único" };
  E("j-claims").innerHTML = `<dl class="claims">${Object.entries(linhas).map(([k, v]) => {
    const tempo = ["exp", "iat", "nbf"].includes(k) ? ` (${new Date(v * 1000).toLocaleString("pt-PT")})` : "";
    return `<dt>${esc(k)}</dt><dd>${esc(v)}${tempo}${explicar[k] ? ` <small class="nota">— ${explicar[k]}</small>` : ""}</dd>`;
  }).join("")}</dl>`;
  const o = estado.ultimaOrdem;
  E("j-ordem").className = o ? "" : "vazio";
  if (o) E("j-ordem").innerHTML = `<dl class="claims"><dt>transferência</dt><dd class="mono">${esc(o.id)}</dd>
    <dt>assinada por</dt><dd>${esc(o.instancia)} (${esc(o.algoritmo)})</dd><dt>emitida em</dt><dd>${esc(o.emitido_em)}</dd>
    <dt>SHA-256</dt><dd class="mono">${esc(o.sha256_canonico)}</dd>
    <dt>campos</dt><dd class="mono">${esc(o.corpo.conta_origem)} → ${esc(o.corpo.conta_destino)}, ${esc(o.corpo.montante)} EUR, chave ${esc(o.chave)}</dd></dl>`;
}

// ------------------------------------------------------------------ eventos
document.addEventListener("DOMContentLoaded", () => {
  E("form-entrada").addEventListener("submit", (ev) => { ev.preventDefault(); entrar(E("e-utilizador").value.trim(), E("e-senha").value); });
  document.querySelectorAll(".demo-lista button").forEach((b) => b.addEventListener("click", () => {
    E("e-utilizador").value = b.dataset.u; E("e-senha").value = b.dataset.p; entrar(b.dataset.u, b.dataset.p);
  }));
  E("b-sair").addEventListener("click", () => sair());
  E("b-menu").addEventListener("click", () => document.querySelector(".lateral").classList.toggle("aberta"));
  window.addEventListener("hashchange", () => estado.token && irPara(location.hash.slice(1)));
  E("form-transf").addEventListener("submit", (ev) => { ev.preventDefault(); enviarTransferencia(false); });
  E("b-repetir").addEventListener("click", () => enviarTransferencia(true));
  E("b-nova-chave").addEventListener("click", () => { novaChave(); E("b-repetir").disabled = true; });
  E("t-origem").addEventListener("change", mostrarRota);
  E("t-destino").addEventListener("input", mostrarRota);
  E("m-auto").addEventListener("change", () => irPara("transferencias"));
  E("s-auto").addEventListener("change", () => irPara("sistema"));
  E("b-trocar").addEventListener("click", () => { base = base === BASES[0] ? BASES[1] : BASES[0]; aviso(`A usar ${base}`); carregarSistema(); });
  E("b-gerar").addEventListener("click", () => gerarExtracto(E("r-conta").value));
  E("b-r-actualizar").addEventListener("click", listarRelatorios);
  E("b-extracto-conta").addEventListener("click", () => estado.contaHistorico && gerarExtracto(estado.contaHistorico));
  document.querySelectorAll("[data-fechar]").forEach((x) => x.addEventListener("click", () => (E("gaveta").hidden = true)));
  document.addEventListener("keydown", (ev) => { if (ev.key === "Escape") E("gaveta").hidden = true; });

  const guardado = ler("gs-token");
  if (guardado) {
    try {
      if (decodificarJwt(guardado).carga.exp * 1000 > Date.now()) { iniciarSessao(guardado); return; }
    } catch (_) { /* token invalido: pede login */ }
  }
  E("entrada").hidden = false;
});
