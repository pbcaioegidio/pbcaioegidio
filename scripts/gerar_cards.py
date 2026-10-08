#!/usr/bin/env python3
"""Gera assets/celular.svg: um celular que passa pelas telas de atividade do GitHub.

Todos os dados vêm da API do GitHub no momento em que o script roda (precisa do `gh` com token,
via login local ou variável GH_TOKEN). O GitHub Actions roda isto a cada hora.
"""
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ASSETS = Path(__file__).resolve().parent.parent / "assets"

USUARIO = os.environ.get("GITHUB_USUARIO", "pbcaioegidio")
FUSO = ZoneInfo("America/Sao_Paulo")
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

CORES_ORG = {
    "BsTechSolution": "#39D353",
    "desenvolvimento-biglar": "#58A6FF",
    "Work-In-Ideas-WiiD": "#A371F7",
    "consimples": "#F0883E",
    USUARIO: "#F778BA",
}
PALETA_EXTRA = ["#2DD4BF", "#F2CC60", "#FF7B72", "#79C0FF", "#D2A8FF"]
NOMES_ORG = {"desenvolvimento-biglar": "biglar", "Work-In-Ideas-WiiD": "WiiD", USUARIO: "Pessoal"}

QUERY = """
query($login: String!, $inicioMes: DateTime!, $agora: DateTime!, $buscaMerged: String!) {
  user(login: $login) {
    ano: contributionsCollection {
      totalCommitContributions
      totalIssueContributions
      contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }
    }
    mes: contributionsCollection(from: $inicioMes, to: $agora) {
      totalCommitContributions
      totalPullRequestContributions
      commitContributionsByRepository(maxRepositories: 25) {
        repository { name owner { login } }
        contributions { totalCount }
      }
    }
    repositoriesContributedTo(first: 1, contributionTypes: [COMMIT, PULL_REQUEST]) { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name color } } }
      }
    }
  }
  merged: search(query: $buscaMerged, type: ISSUE) { issueCount }
}
"""


def carregar():
    """Busca tudo na API e preenche as variáveis usadas pelas telas."""
    global CONTRIBUICOES_ANO, MES, ANO, PULL_REQUESTS, PRS_MERGEADOS, ESTRELAS, ISSUES
    global REPOS_CONTRIBUIDOS, COMMITS, LINGUAGENS, HORA, ATUALIZADO

    agora = datetime.now(FUSO)
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    variaveis = {
        "login": USUARIO,
        "inicioMes": inicio_mes.isoformat(),
        "agora": agora.isoformat(),
        "buscaMerged": f"is:pr author:{USUARIO} is:merged merged:>={inicio_mes.date().isoformat()}",
    }
    args = ["gh", "api", "graphql", "-f", f"query={QUERY}"]
    for k, v in variaveis.items():
        args += ["-f", f"{k}={v}"]
    saida = subprocess.run(args, capture_output=True, text=True, check=True)
    dados = json.loads(saida.stdout)["data"]
    user = dados["user"]
    ano, mes = user["ano"], user["mes"]

    CONTRIBUICOES_ANO = f"{ano['contributionCalendar']['totalContributions']:,}".replace(",", ".")
    MES, ANO = MESES[agora.month - 1], agora.year
    PULL_REQUESTS = mes["totalPullRequestContributions"]
    PRS_MERGEADOS = dados["merged"]["issueCount"]
    ISSUES = ano["totalIssueContributions"]
    REPOS_CONTRIBUIDOS = user["repositoriesContributedTo"]["totalCount"]
    ESTRELAS = sum(r["stargazerCount"] for r in user["repositories"]["nodes"])
    HORA = agora.strftime("%H:%M")
    ATUALIZADO = agora.strftime("%d/%m %H:%M")

    COMMITS = sorted(
        ((r["repository"]["owner"]["login"], r["repository"]["name"], r["contributions"]["totalCount"])
         for r in mes["commitContributionsByRepository"]),
        key=lambda x: -x[2],
    )
    for org, _, _ in COMMITS:
        if org not in CORES_ORG:
            CORES_ORG[org] = PALETA_EXTRA[len(CORES_ORG) % len(PALETA_EXTRA)]

    tamanhos, cores = {}, {}
    for repo in user["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            nome = e["node"]["name"]
            tamanhos[nome] = tamanhos.get(nome, 0) + e["size"]
            cores[nome] = e["node"]["color"] or "#8B949E"
    soma = sum(tamanhos.values()) or 1
    LINGUAGENS = [(n, 100 * t / soma, cores[n]) for n, t in sorted(tamanhos.items(), key=lambda x: -x[1])[:8]]

    col = {"totalCommitContributions": ano["totalCommitContributions"], "contributionCalendar": ano["contributionCalendar"]}
    dias = [d for w in ano["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    return col, dias


FONTE = '-apple-system, "Segoe UI", Helvetica, Arial, sans-serif'
MONO = '"JetBrains Mono", "Fira Code", Consolas, monospace'

W, H = 420, 680
PX, PY, PW, PH = 40, 20, 340, 640
SX, SY, SW, SH = 50, 30, 320, 620
X0, X1 = 74, 346
CX = W / 2
SLOT = 5.0


def resumo_sequencias(dias):
    melhor = atual = 0
    inicio_atual = inicio_melhor = fim_melhor = None
    for d in dias:
        if d["contributionCount"]:
            if atual == 0:
                inicio_atual = d["date"]
            atual += 1
            if atual > melhor:
                melhor, inicio_melhor, fim_melhor = atual, inicio_atual, d["date"]
        elif d["date"] != datetime.now(FUSO).date().isoformat():
            atual = 0
    return melhor, atual, inicio_melhor, fim_melhor


def fmt_data(iso):
    return f"{iso[8:10]}/{iso[5:7]}" if iso else "--"


class Tela:
    """Cada tela entra no seu intervalo do ciclo; atrasos negativos deixam todas sincronizadas desde o início."""

    def __init__(self, indice, total):
        self.periodo = SLOT * total
        self.base = -((self.periodo - indice * SLOT) % self.periodo)

    def d(self, extra=0.0):
        return f"animation-delay: {self.base + extra:.2f}s"


def cabecalho(rotulo, titulo):
    return f"""
      <text class="mono" x="{X0}" y="104" font-size="10" fill="#39D353" letter-spacing="1.2">{rotulo}</text>
      <text x="{X0}" y="134" font-size="26" font-weight="800" fill="#F0F6FC">{titulo}</text>"""


def tela_visao_geral(t):
    pulso = f"M{X0} 300 H130 l7 -7 l5 12 l8 -38 l8 48 l6 -20 l5 3 H236 l7 -5 l5 10 l8 -30 l8 40 l6 -16 l5 1 H{X1}"
    tiles = [
        (str(sum(c for *_, c in COMMITS)), f"commits em {MES}", "#39D353"),
        (str(PULL_REQUESTS), "PRs no mês", "#58A6FF"),
        (str(PRS_MERGEADOS), "mergeados no mês", "#A371F7"),
        (str(len(COMMITS)), "repos no mês", "#F0883E"),
    ]
    blocos = []
    for i, (num, label, cor) in enumerate(tiles):
        x = X0 + (i % 2) * 140
        y = 340 + (i // 2) * 92
        blocos.append(f"""
      <g class="up" style="{t.d(0.3 + i * 0.1)}">
        <rect x="{x}" y="{y}" width="132" height="82" rx="14" fill="#FFFFFF" fill-opacity="0.04" stroke="#FFFFFF" stroke-opacity="0.08" />
        <rect x="{x}" y="{y + 18}" width="3" height="46" rx="1.5" fill="{cor}" filter="url(#glow)" />
        <text x="{x + 18}" y="{y + 44}" font-size="28" font-weight="800" fill="#F0F6FC">{num}</text>
        <text x="{x + 18}" y="{y + 66}" font-size="11" fill="#8B949E">{label}</text>
      </g>""")
    return f"""{cabecalho("VISÃO GERAL", "Último ano")}
      <text class="mono up" x="{X0}" y="170" font-size="11" fill="#39D353" style="{t.d(0.1)}">~/{USUARIO} <tspan fill="#8B949E">$ git log</tspan><tspan class="cursor"> ▋</tspan></text>
      <g class="up" style="{t.d(0.2)}">
        <text x="{X0 - 2}" y="236" font-size="60" font-weight="800" fill="url(#texto)" filter="url(#glow)">{CONTRIBUICOES_ANO}</text>
        <text x="{X0}" y="260" font-size="13" fill="#C9D1D9">contribuições no último ano</text>
      </g>
      <path d="{pulso}" fill="none" stroke="#30363D" stroke-width="2" stroke-linejoin="round" />
      <path class="pulse" d="{pulso}" pathLength="1" fill="none" stroke="url(#texto)" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" filter="url(#glow)" />
      {''.join(blocos)}
      <g class="up" style="{t.d(0.7)}">
        <circle class="beat" cx="{X0 + 4}" cy="540" r="3.5" fill="#39D353" />
        <text class="mono" x="{X0 + 14}" y="544" font-size="10" fill="#8B949E">ao vivo · atualizado {ATUALIZADO}</text>
      </g>"""


def tela_sequencia(t, col, dias):
    melhor, atual, ini, fim = resumo_sequencias(dias)
    total = col["contributionCalendar"]["totalContributions"]
    cy, r = 226, 60
    progresso = min(melhor / 7, 1)

    semanas = 17
    ultimos = dias[-semanas * 7:]
    maximo = max((d["contributionCount"] for d in ultimos), default=1) or 1
    cores = ["#161B22", "#0E4429", "#006D32", "#26A641", "#39D353"]
    celulas = []
    for i, d in enumerate(ultimos):
        n = d["contributionCount"]
        nivel = 0 if n == 0 else min(4, 1 + int(3 * n / maximo))
        x = X0 + (i // 7) * 16
        y = 438 + (i % 7) * 16
        celulas.append(f'<rect class="pop" x="{x}" y="{y}" width="13" height="13" rx="3" fill="{cores[nivel]}" style="{t.d(0.6 + (i // 7) * 0.06)}" />')

    linhas = [("Contribuições públicas", str(total)), ("Sequência atual", f"{atual} dias"), ("Recorde", f"{fmt_data(ini)} – {fmt_data(fim)}")]
    texto_linhas = "".join(
        f"""
      <g class="up" style="{t.d(0.4 + i * 0.1)}">
        <text x="{X0}" y="{326 + i * 26}" font-size="12" fill="#8B949E">{a}</text>
        <text x="{X1}" y="{326 + i * 26}" font-size="12" font-weight="700" fill="#F0F6FC" text-anchor="end">{b}</text>
      </g>"""
        for i, (a, b) in enumerate(linhas)
    )
    return f"""{cabecalho("STREAK", "Sequência")}
      <circle cx="{CX}" cy="{cy}" r="{r}" fill="none" stroke="#FFFFFF" stroke-opacity="0.06" stroke-width="12" />
      <circle class="ring" cx="{CX}" cy="{cy}" r="{r}" pathLength="1" fill="none" stroke="url(#fogo)" stroke-width="12" stroke-linecap="round"
        transform="rotate(-90 {CX} {cy})" filter="url(#glow)" style="--alvo: {1 - progresso:.3f}; {t.d(0.2)}" />
      <path class="flame" d="M{CX} {cy - 44} c7 9 13 14 13 22 a13 13 0 0 1 -26 0 c0 -6 4 -9 6 -13 c1 5 3 7 5 7 c0 -6 -1 -10 2 -16z" fill="url(#fogo)" />
      <text x="{CX}" y="{cy + 22}" font-size="34" font-weight="800" fill="#F0F6FC" text-anchor="middle">{melhor}</text>
      <text x="{CX}" y="{cy + 38}" font-size="10" fill="#8B949E" text-anchor="middle">dias de recorde</text>
      {texto_linhas}
      <text class="mono" x="{X0}" y="426" font-size="9" fill="#6E7681" letter-spacing="1">ÚLTIMAS {semanas} SEMANAS</text>
      {''.join(celulas)}"""


def tela_estatisticas(t, col, dias):
    commits = col["totalCommitContributions"]
    meses = {}
    for d in dias:
        meses[d["date"][:7]] = meses.get(d["date"][:7], 0) + d["contributionCount"]
    valores = list(meses.values())[-12:]
    topo = max(valores) or 1
    base, altura = 300, 62
    largura = X1 - X0
    pontos = [(X0 + i * largura / (len(valores) - 1), base - v / topo * altura) for i, v in enumerate(valores)]
    linha = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pontos)
    area = f"{linha} L{X1} {base} L{X0} {base} Z"

    itens = [
        ("Pull requests", str(PULL_REQUESTS), "#58A6FF", "M4 2a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm0 4v6m8-8a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm0 4c0 3-2 4-5 4"),
        ("Estrelas", str(ESTRELAS), "#F2CC60", "M8 1l2 4.5 5 .5-3.8 3.3 1.1 4.9L8 11.8 3.7 14.2l1.1-4.9L1 6l5-.5z"),
        ("Issues", str(ISSUES), "#F778BA", "M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm0 4v4m0 2v1"),
        ("Contribuiu em", f"{REPOS_CONTRIBUIDOS} repos", "#A371F7", "M3 2h8l2 2v10H3zM5 6h6M5 9h6M5 12h4"),
    ]
    linhas = []
    for i, (nome, valor, cor, icone) in enumerate(itens):
        y = 340 + i * 50
        linhas.append(f"""
      <g class="up" style="{t.d(0.5 + i * 0.1)}">
        <rect x="{X0}" y="{y}" width="{largura}" height="42" rx="12" fill="#FFFFFF" fill-opacity="0.04" />
        <rect x="{X0 + 10}" y="{y + 10}" width="22" height="22" rx="7" fill="{cor}" fill-opacity="0.15" />
        <path d="{icone}" transform="translate({X0 + 13} {y + 13})" fill="none" stroke="{cor}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
        <text x="{X0 + 44}" y="{y + 26}" font-size="13" fill="#C9D1D9">{nome}</text>
        <text x="{X1 - 12}" y="{y + 26}" font-size="14" font-weight="700" fill="#F0F6FC" text-anchor="end">{valor}</text>
      </g>""")

    return f"""{cabecalho("GITHUB", "Estatísticas")}
      <g class="up" style="{t.d(0.1)}">
        <text x="{X0 - 2}" y="206" font-size="58" font-weight="800" fill="url(#texto)" filter="url(#glow)">{commits}</text>
        <text x="{X0}" y="226" font-size="11" fill="#8B949E">commits públicos no último ano</text>
      </g>
      <path class="fade" d="{area}" fill="url(#area)" style="{t.d(0.6)}" />
      <path class="draw" d="{linha}" pathLength="1" fill="none" stroke="#39D353" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round" style="{t.d(0.2)}" />
      <circle class="beat" cx="{pontos[-1][0]:.1f}" cy="{pontos[-1][1]:.1f}" r="4" fill="#39D353" />
      <text x="{X0}" y="316" font-size="9" fill="#6E7681">12 meses atrás</text>
      <text x="{X1}" y="316" font-size="9" fill="#6E7681" text-anchor="end">hoje</text>
      {''.join(linhas)}"""


def tela_linguagens(t):
    cy, r = 222, 62
    total = sum(p for _, p, _ in LINGUAGENS)
    inicio = 0.0
    fatias = []
    for nome, p, cor in LINGUAGENS:
        tam = 100 * p / total
        fatias.append(
            f'<circle cx="{CX}" cy="{cy}" r="{r}" pathLength="100" fill="none" stroke="{cor}" stroke-width="18" '
            f'stroke-dasharray="{max(tam - 0.6, 0.3):.2f} 100" stroke-dashoffset="{-inicio:.2f}" transform="rotate(-90 {CX} {cy})" />'
        )
        inicio += tam

    principal = LINGUAGENS[0]
    lista = []
    for i, (nome, p, cor) in enumerate(LINGUAGENS):
        y = 330 + i * 30
        bw = max((X1 - X0 - 16) * p / principal[1], 4)
        lista.append(f"""
      <g class="up" style="{t.d(0.4 + i * 0.07)}">
        <circle cx="{X0 + 4}" cy="{y - 4}" r="4" fill="{cor}" />
        <text x="{X0 + 16}" y="{y}" font-size="12" fill="#C9D1D9">{nome}</text>
        <text class="mono" x="{X1}" y="{y}" font-size="10.5" fill="#8B949E" text-anchor="end">{p:.1f}%</text>
        <rect x="{X0 + 16}" y="{y + 7}" width="{X1 - X0 - 16}" height="3" rx="1.5" fill="#FFFFFF" fill-opacity="0.06" />
        <rect class="grow" x="{X0 + 16}" y="{y + 7}" width="{bw:.1f}" height="3" rx="1.5" fill="{cor}" style="{t.d(0.6 + i * 0.07)}" />
      </g>""")

    return f"""{cabecalho(f"TOP {len(LINGUAGENS)}", "Linguagens")}
      <mask id="revela"><circle class="ring" cx="{CX}" cy="{cy}" r="{r}" pathLength="1" fill="none" stroke="#FFFFFF" stroke-width="22"
        transform="rotate(-90 {CX} {cy})" style="--alvo: 0; {t.d(0.1)}" /></mask>
      <circle cx="{CX}" cy="{cy}" r="{r}" fill="none" stroke="#FFFFFF" stroke-opacity="0.05" stroke-width="18" />
      <g mask="url(#revela)">{''.join(fatias)}</g>
      <text x="{CX}" y="{cy + 4}" font-size="24" font-weight="800" fill="#F0F6FC" text-anchor="middle">{principal[0]}</text>
      <text class="mono" x="{CX}" y="{cy + 22}" font-size="11" fill="#8B949E" text-anchor="middle">{principal[1]:.1f}%</text>
      {''.join(lista)}"""


def tela_commits(t):
    total = sum(c for *_, c in COMMITS)
    largura = X1 - X0
    if not total:
        return f"""{cabecalho(f"{MES.upper()} {ANO}", "Commits")}
      <text class="up" x="{X0}" y="200" font-size="14" fill="#8B949E" style="{t.d(0.1)}">Nenhum commit em {MES} ainda.</text>"""
    maximo = max(c for *_, c in COMMITS)
    visiveis = COMMITS[:8]

    por_org = {}
    for org, _, c in COMMITS:
        por_org[org] = por_org.get(org, 0) + c

    segmentos, x = [], X0
    for i, (org, c) in enumerate(por_org.items()):
        bw = largura * c / total
        segmentos.append(f'<rect class="grow" x="{x:.1f}" y="196" width="{max(bw - 2, 2):.1f}" height="10" rx="3" fill="{CORES_ORG[org]}" style="{t.d(0.2 + i * 0.1)}" />')
        x += bw

    legenda = []
    for i, (org, c) in enumerate(por_org.items()):
        if i >= 6:
            break
        lx = X0 + (i % 2) * 140
        ly = 230 + (i // 2) * 18
        legenda.append(f"""<g class="up" style="{t.d(0.3 + i * 0.05)}"><rect x="{lx}" y="{ly - 8}" width="8" height="8" rx="2" fill="{CORES_ORG[org]}" />
        <text x="{lx + 13}" y="{ly}" font-size="10" fill="#C9D1D9">{NOMES_ORG.get(org, org)} <tspan fill="#6E7681">{c}</tspan></text></g>""")

    linhas = []
    topo_lista = 230 + ((min(len(por_org), 6) + 1) // 2) * 18 + 20
    for i, (org, repo, c) in enumerate(visiveis):
        y = topo_lista + i * 32
        if len(repo) > 22:
            repo = repo[:21] + "…"
        cor = CORES_ORG[org]
        bw = max((largura - 14) * c / maximo, 6)
        linhas.append(f"""
      <g class="up" style="{t.d(0.4 + i * 0.07)}">
        <text class="mono" x="{X0}" y="{y}" font-size="10" fill="{cor}">{i + 1:02d}</text>
        <text x="{X0 + 22}" y="{y}" font-size="12" font-weight="600" fill="#F0F6FC">{repo}</text>
        <text class="mono" x="{X1}" y="{y}" font-size="11" text-anchor="end"><tspan fill="#F0F6FC" font-weight="700">{c}</tspan><tspan fill="#6E7681"> · {round(c * 100 / total)}%</tspan></text>
        <rect x="{X0 + 22}" y="{y + 7}" width="{largura - 22}" height="4" rx="2" fill="#FFFFFF" fill-opacity="0.06" />
        <rect class="grow" x="{X0 + 22}" y="{y + 7}" width="{bw * (largura - 22) / (largura - 14):.1f}" height="4" rx="2" fill="{cor}" style="{t.d(0.6 + i * 0.07)}" />
      </g>""")

    return f"""{cabecalho(f"{MES.upper()} {ANO}", "Commits")}
      <g class="up" style="{t.d(0.1)}">
        <text x="{X0}" y="178" font-size="13" fill="#8B949E"><tspan font-size="22" font-weight="800" fill="#F0F6FC">{total}</tspan>  commits em {len(COMMITS)} repositórios</text>
      </g>
      {''.join(segmentos)}
      {''.join(legenda)}
      {''.join(linhas)}"""


def gerar():
    col, dias = carregar()
    construtores = [
        lambda t: tela_visao_geral(t),
        lambda t: tela_commits(t),
        lambda t: tela_sequencia(t, col, dias),
        lambda t: tela_estatisticas(t, col, dias),
        lambda t: tela_linguagens(t),
    ]
    n = len(construtores)
    periodo = SLOT * n
    janela = 100 / n
    entra, sai = janela * 0.06, janela * 0.94

    telas, pontos = [], []
    for i, construir in enumerate(construtores):
        t = Tela(i, n)
        telas.append(f'\n    <g class="tela" style="{t.d()}">{construir(t)}\n    </g>')
        px = CX - (n - 1) * 9 + i * 18
        pontos.append(f'<rect class="ponto" x="{px - 3}" y="606" width="6" height="6" rx="3" fill="#F0F6FC" style="{t.d()}" />')

    def pct(v):
        return f"{v:.2f}%"

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Celular mostrando a atividade de {USUARIO} no GitHub">
  <defs>
    <clipPath id="tela"><rect x="{SX}" y="{SY}" width="{SW}" height="{SH}" rx="42" /></clipPath>
    <filter id="blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="45" /></filter>
    <filter id="glow" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="3" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
    <filter id="sombra" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="18" stdDeviation="10" flood-color="#000000" flood-opacity="0.45" /></filter>
    <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" stroke="#FFFFFF" stroke-opacity="0.03" /></pattern>
    <linearGradient id="moldura" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="{W}" y2="{H}">
      <stop offset="0" stop-color="#39D353" />
      <stop offset="0.5" stop-color="#58A6FF" />
      <stop offset="1" stop-color="#A371F7" />
      <animateTransform attributeName="gradientTransform" type="rotate" from="0 {CX} {H / 2}" to="360 {CX} {H / 2}" dur="8s" repeatCount="indefinite" />
    </linearGradient>
    <linearGradient id="texto" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#39D353" /><stop offset="1" stop-color="#58A6FF" /></linearGradient>
    <linearGradient id="fogo" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#F0883E" /><stop offset="1" stop-color="#F2CC60" /></linearGradient>
    <linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#39D353" stop-opacity="0.35" /><stop offset="1" stop-color="#39D353" stop-opacity="0" /></linearGradient>
  </defs>
  <style>
    text {{ font-family: {FONTE}; }}
    .mono {{ font-family: {MONO}; }}
    .blob {{ opacity: 0.22; animation: drift 9s ease-in-out infinite alternate; }}
    .b2 {{ animation-duration: 11s; animation-direction: alternate-reverse; }}
    .float {{ animation: float 6s ease-in-out infinite; }}
    .tela, .up, .pop, .grow, .ring, .draw, .fade, .ponto {{ animation-duration: {periodo}s; animation-iteration-count: infinite; animation-fill-mode: both; }}
    .tela {{ animation-name: tela; animation-timing-function: cubic-bezier(.2,.8,.2,1); }}
    .up {{ animation-name: up; }}
    .pop, .fade {{ animation-name: pop; }}
    .grow {{ animation-name: grow; transform-box: fill-box; transform-origin: left center; }}
    .ring {{ animation-name: ring; stroke-dasharray: 1 1; }}
    .draw {{ animation-name: draw; stroke-dasharray: 1 1; }}
    .ponto {{ animation-name: ponto; transform-box: fill-box; transform-origin: center; }}
    .pulse {{ stroke-dasharray: 0.35 0.65; animation: trace 3s linear infinite; }}
    .flame {{ transform-box: fill-box; transform-origin: center bottom; animation: flicker 1.4s ease-in-out infinite; }}
    .beat {{ transform-box: fill-box; transform-origin: center; animation: beat 1.6s ease-in-out infinite; }}
    .cursor {{ animation: blink 1s steps(1) infinite; }}
    @keyframes tela {{
      0% {{ opacity: 0; transform: translateX(60px); }}
      {pct(entra)} {{ opacity: 1; transform: translateX(0); }}
      {pct(sai)} {{ opacity: 1; transform: translateX(0); }}
      {pct(janela)}, 100% {{ opacity: 0; transform: translateX(-60px); }}
    }}
    @keyframes up {{ 0%, {pct(entra)} {{ opacity: 0; transform: translateY(12px); }} {pct(janela * 0.22)}, 100% {{ opacity: 1; transform: translateY(0); }} }}
    @keyframes pop {{ 0%, {pct(entra)} {{ opacity: 0; }} {pct(janela * 0.2)}, 100% {{ opacity: 1; }} }}
    @keyframes grow {{ 0%, {pct(entra)} {{ transform: scaleX(0); }} {pct(janela * 0.3)}, 100% {{ transform: scaleX(1); }} }}
    @keyframes ring {{ 0%, {pct(entra)} {{ stroke-dashoffset: 1; }} {pct(janela * 0.35)}, 100% {{ stroke-dashoffset: var(--alvo); }} }}
    @keyframes draw {{ 0%, {pct(entra)} {{ stroke-dashoffset: 1; }} {pct(janela * 0.4)}, 100% {{ stroke-dashoffset: 0; }} }}
    @keyframes ponto {{ 0%, {pct(janela)} {{ opacity: 1; transform: scaleX(2.2); }} {pct(janela + 0.01)}, 100% {{ opacity: 0.25; transform: scaleX(1); }} }}
    @keyframes trace {{ from {{ stroke-dashoffset: 1; }} to {{ stroke-dashoffset: -1; }} }}
    @keyframes float {{ 0%, 100% {{ transform: translateY(0); }} 50% {{ transform: translateY(-8px); }} }}
    @keyframes drift {{ from {{ transform: translate(0, 0); }} to {{ transform: translate(40px, 30px); }} }}
    @keyframes flicker {{ 0%, 100% {{ transform: scale(1, 1); }} 50% {{ transform: scale(0.92, 1.08); }} }}
    @keyframes beat {{ 0%, 100% {{ transform: scale(1); opacity: 1; }} 50% {{ transform: scale(1.8); opacity: 0.5; }} }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}
  </style>

  <g class="float">
    <rect x="{PX - 2}" y="{PY - 2}" width="{PW + 4}" height="{PH + 4}" rx="54" fill="url(#moldura)" filter="url(#sombra)" />
    <rect x="{PX}" y="{PY}" width="{PW}" height="{PH}" rx="52" fill="#161B22" />
    <rect x="{PX - 3}" y="150" width="3" height="40" rx="1.5" fill="#30363D" />
    <rect x="{PX - 3}" y="200" width="3" height="60" rx="1.5" fill="#30363D" />
    <rect x="{PX + PW}" y="180" width="3" height="80" rx="1.5" fill="#30363D" />
    <rect x="{SX}" y="{SY}" width="{SW}" height="{SH}" rx="42" fill="#0B0F17" />
    <g clip-path="url(#tela)">
      <rect x="{SX}" y="{SY}" width="{SW}" height="{SH}" fill="url(#grid)" />
      <circle class="blob" cx="{SX + 40}" cy="{SY + 60}" r="90" fill="#39D353" filter="url(#blur)" />
      {''.join(telas)}
    </g>
    <text class="mono" x="{X0 + 6}" y="62" font-size="12" font-weight="700" fill="#F0F6FC">{HORA}</text>
    <rect x="{CX - 48}" y="44" width="96" height="28" rx="14" fill="#000000" />
    <circle cx="{CX + 30}" cy="58" r="4" fill="#1F2A3A" />
    <path d="M{X1 - 58} 62 h3 v-3 h-3z M{X1 - 53} 62 h3 v-6 h-3z M{X1 - 48} 62 h3 v-9 h-3z" fill="#F0F6FC" />
    <rect x="{X1 - 30}" y="52" width="24" height="12" rx="3.5" fill="none" stroke="#F0F6FC" stroke-opacity="0.7" />
    <rect x="{X1 - 28}" y="54" width="16" height="8" rx="2" fill="#39D353" />
    {''.join(pontos)}
    <rect x="{CX - 50}" y="{SY + SH - 14}" width="100" height="5" rx="2.5" fill="#F0F6FC" fill-opacity="0.4" />
  </g>
</svg>
"""


if __name__ == "__main__":
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "celular.svg").write_text(gerar(), encoding="utf-8")
    print("Gerado", ASSETS / "celular.svg")
