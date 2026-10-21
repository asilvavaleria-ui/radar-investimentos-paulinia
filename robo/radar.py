"""
Radar de Investimentos de Paulínia
==================================

Busca notícias públicas sobre investimentos em Paulínia (Google Notícias,
Bing Notícias, sites prioritários e feeds RSS), filtra as relevantes,
gera um resumo, grava o histórico usado pelo painel e envia um e-mail
com as novidades.

Uso:
    python robo/radar.py                    # execução normal
    python robo/radar.py --sem-email        # coleta sem enviar e-mail
    python robo/radar.py --resumo-semanal   # e-mail com os destaques dos últimos 7 dias
    python robo/radar.py --email-teste      # envia e-mail com as 5 notícias mais recentes
"""

import argparse
import hashlib
import json
import os
import re
import smtplib
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
import config  # noqa: E402
from email_template import montar_email  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
ARQ_NOTICIAS = RAIZ / "docs" / "data" / "noticias.json"
ARQ_STATUS = RAIZ / "docs" / "data" / "status.json"
ARQ_VISTOS = RAIZ / "data" / "vistos.json"

FUSO_BR = timezone(timedelta(hours=-3))
CABECALHOS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "pt-BR,pt;q=0.9",
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", texto.lower()).strip()


def limpar_html(texto):
    return re.sub(r"\s+", " ", BeautifulSoup(texto or "", "html.parser").get_text(" ")).strip()


def gerar_id(titulo):
    base = re.sub(r"[^a-z0-9]", "", normalizar(titulo))[:120]
    return hashlib.sha1(base.encode()).hexdigest()[:16]


def ler_json(caminho, padrao):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return padrao


def gravar_json(caminho, dados):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")


def agora():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Coleta
# ---------------------------------------------------------------------------
def url_google(consulta):
    q = quote_plus(f"{consulta} when:{config.DIAS_RETROATIVOS}d")
    return f"https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419"


def url_bing(consulta):
    return f"https://www.bing.com/news/search?q={quote_plus(consulta)}&format=rss&setlang=pt-BR&cc=BR"


def montar_fontes():
    fontes = []
    for c in config.CONSULTAS:
        fontes.append(("Google Notícias", url_google(c)))
        fontes.append(("Bing Notícias", url_bing(c)))
    for site in config.SITES_PRIORITARIOS:
        fontes.append(("Google Notícias", url_google(f"{config.CIDADE} site:{site}")))
    for feed in config.FEEDS_EXTRAS:
        fontes.append(("RSS", feed))
    return fontes


def baixar_feed(url):
    resposta = requests.get(url, headers=CABECALHOS, timeout=20)
    resposta.raise_for_status()
    return feedparser.parse(resposta.content)


def link_real(link):
    """Remove redirecionadores conhecidos (Bing) para chegar ao site original."""
    if "bing.com" in link:
        destino = parse_qs(urlparse(link).query).get("url")
        if destino:
            return destino[0]
    if "news.google.com" in link:
        try:
            from googlenewsdecoder import gnewsdecoder
            r = gnewsdecoder(link, interval=0.5)
            if r.get("status"):
                return r["decoded_url"]
        except Exception:
            pass
    return link


def data_publicacao(entrada):
    for campo in ("published_parsed", "updated_parsed"):
        valor = entrada.get(campo)
        if valor:
            return datetime(*valor[:6], tzinfo=timezone.utc)
    return agora()


def coletar_itens():
    itens, status_fontes = {}, {"ok": 0, "erro": 0}
    for origem, url in montar_fontes():
        try:
            feed = baixar_feed(url)
            status_fontes["ok"] += 1
        except Exception as erro:
            print(f"  ! falha na fonte {url[:90]}: {erro}")
            status_fontes["erro"] += 1
            continue
        for e in feed.entries:
            titulo = limpar_html(e.get("title", ""))
            fonte = ""
            if e.get("source") and e.source.get("title"):
                fonte = e.source.get("title")
            # O Google acrescenta " - Nome do Veículo" ao fim do título.
            if origem == "Google Notícias" and " - " in titulo:
                titulo, _, sufixo = titulo.rpartition(" - ")
                fonte = fonte or sufixo
            if not titulo:
                continue
            item_id = gerar_id(titulo)
            if item_id in itens:
                continue
            itens[item_id] = {
                "id": item_id,
                "titulo": titulo.strip(),
                "link": e.get("link", ""),
                "fonte": fonte or urlparse(e.get("link", "")).netloc.replace("www.", ""),
                "descricao": limpar_html(e.get("summary", "")),
                "publicado": data_publicacao(e),
                "origem": origem,
            }
        time.sleep(0.6)
    return list(itens.values()), status_fontes


def ler_artigo(url):
    """Baixa a página da notícia e devolve (texto, descrição meta, url final)."""
    try:
        r = requests.get(url, headers=CABECALHOS, timeout=15)
        r.raise_for_status()
    except Exception:
        return "", "", url
    sopa = BeautifulSoup(r.text, "html.parser")
    meta = sopa.find("meta", attrs={"property": "og:description"}) or \
        sopa.find("meta", attrs={"name": "description"})
    descricao = meta.get("content", "").strip() if meta else ""
    for tag in sopa(["script", "style", "nav", "header", "footer", "aside", "form", "figure"]):
        tag.decompose()
    corpo = sopa.find("article") or sopa.body or sopa
    paragrafos = [p.get_text(" ", strip=True) for p in corpo.find_all("p")]
    texto = " ".join(p for p in paragrafos if len(p) > 60)
    return texto[:20000], descricao, r.url


# ---------------------------------------------------------------------------
# Análise
# ---------------------------------------------------------------------------
RE_VALOR = re.compile(
    r"(R\$|US\$|€)\s?(\d{1,3}(?:[.\s]\d{3})*(?:,\d+)?|\d+(?:,\d+)?)\s*"
    r"(bilh(?:ão|ões|ao|oes)|bi\b|milh(?:ão|ões|ao|oes)|mi\b|mil\b)?",
    re.IGNORECASE,
)
RE_EMPREGOS = re.compile(
    r"(\d{1,3}(?:\.\d{3})*|\d+)\s+(?:novos\s+|novas\s+)?(empregos|postos de trabalho|vagas)",
    re.IGNORECASE,
)
MULTIPLICADORES = {"bi": 1e9, "bilh": 1e9, "mi": 1e6, "milh": 1e6, "mil": 1e3}


def extrair_valores(texto):
    valores, maior_reais = [], 0.0
    for moeda, numero, escala in RE_VALOR.findall(texto):
        escala_n = normalizar(escala)
        mult = next((v for k, v in MULTIPLICADORES.items() if escala_n.startswith(k)), 1)
        try:
            n = float(numero.replace(".", "").replace(" ", "").replace(",", ".")) * mult
        except ValueError:
            continue
        if n < 1e5:  # ignora valores pequenos (preços, tarifas)
            continue
        rotulo = f"{moeda} {numero} {escala}".strip()
        if rotulo not in valores:
            valores.append(rotulo)
        if moeda.upper() == "R$":
            maior_reais = max(maior_reais, n)
    return valores[:4], maior_reais


def extrair_empregos(texto):
    maior = 0
    for numero, _ in RE_EMPREGOS.findall(texto):
        try:
            maior = max(maior, int(numero.replace(".", "")))
        except ValueError:
            pass
    return maior if maior < 100000 else 0


def pontuar(titulo, descricao, artigo):
    partes = [(normalizar(titulo), 3), (normalizar(descricao), 2), (normalizar(artigo), 1)]
    pontos = 0
    for termo, peso in config.TERMOS_INVESTIMENTO.items():
        padrao = re.compile(rf"\b{re.escape(termo)}\b")
        multiplicador = max((m for texto, m in partes if padrao.search(texto)), default=0)
        pontos += peso * multiplicador
    return pontos


def classificar_setor(texto):
    texto = normalizar(texto)
    contagem = {s: sum(texto.count(t) for t in termos) for s, termos in config.SETORES.items()}
    setor, n = max(contagem.items(), key=lambda kv: kv[1])
    return setor if n else config.SETOR_PADRAO


def resumo_extrativo(titulo, texto, descricao):
    """Seleciona as frases mais informativas do texto, sem custo e sem IA."""
    frases = re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ú\"“])", texto)
    frases = [f.strip() for f in frases if 50 <= len(f.strip()) <= 400]
    if not frases:
        return (descricao or titulo)[:420]
    termos = list(config.TERMOS_INVESTIMENTO)
    cidade = normalizar(config.CIDADE)
    pontuadas = []
    for i, frase in enumerate(frases[:60]):
        f = normalizar(frase)
        p = sum(1 for t in termos if t in f)
        p += 3 if cidade in f else 0
        p += 3 if RE_VALOR.search(frase) else 0
        p += 2 if RE_EMPREGOS.search(frase) else 0
        p += 1.5 if i < 3 else 0  # o início da matéria costuma conter o essencial
        pontuadas.append((p, i, frase))
    escolhidas = sorted(sorted(pontuadas, reverse=True)[:3], key=lambda x: x[1])
    resumo = ""
    for _, _, frase in escolhidas:
        if len(resumo) + len(frase) > 520:
            break
        resumo = f"{resumo} {frase}".strip()
    return resumo or (descricao or titulo)[:420]


def resumo_ia(titulo, texto):
    """Resumo opcional pelo Google Gemini (camada gratuita). Ativado só se houver chave."""
    chave = os.getenv("GEMINI_API_KEY")
    if not chave or len(texto) < 300:
        return None
    modelo = os.getenv("GEMINI_MODELO", "gemini-2.5-flash")
    prompt = (
        "Você assessora a Secretaria de Desenvolvimento Econômico de Paulínia (SP). "
        "Resuma a notícia abaixo em até 3 frases objetivas, em português, destacando: "
        "empresa envolvida, valor do investimento, empregos, prazo e local. "
        "Não invente informações.\n\n"
        f"Título: {titulo}\n\nTexto: {texto[:8000]}"
    )
    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent",
            params={"key": chave},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=40,
        )
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as erro:
        print(f"  ! resumo por IA indisponível: {erro}")
        return None


def analisar(item):
    titulo_n = normalizar(item["titulo"])
    if any(re.search(rf"\b{re.escape(t)}", titulo_n) for t in config.TERMOS_EXCLUSAO):
        return None

    url = link_real(item["link"])
    texto, meta_desc, url_final = ler_artigo(url)
    descricao = item["descricao"]
    if not descricao or normalizar(descricao).startswith(titulo_n[:40]):
        descricao = meta_desc  # o RSS do Google repete o título na descrição

    fonte = item["fonte"]
    if not fonte or "bing.com" in fonte or "google.com" in fonte:
        fonte = urlparse(url_final).netloc.replace("www.", "")

    tudo = f"{item['titulo']} {descricao} {texto}"
    if normalizar(config.CIDADE) not in normalizar(tudo):
        return None

    pontos = pontuar(item["titulo"], descricao, texto)
    if pontos < config.PONTUACAO_MINIMA:
        return None

    valores, maior_valor = extrair_valores(tudo)
    empregos = extrair_empregos(tudo)
    resumo = resumo_ia(item["titulo"], texto) or resumo_extrativo(item["titulo"], texto, descricao)
    alta = pontos >= config.PONTUACAO_ALTA or maior_valor >= 1e7 or empregos >= 100

    return {
        "id": item["id"],
        "titulo": item["titulo"],
        "link": url_final if url_final.startswith("http") and "news.google.com" not in url_final else url,
        "fonte": fonte,
        "publicado": item["publicado"].isoformat(),
        "coletado": agora().isoformat(),
        "resumo": resumo,
        "setor": classificar_setor(tudo),
        "valores": valores,
        "valor_reais": maior_valor,
        "empregos": empregos,
        "pontuacao": pontos,
        "relevancia": "alta" if alta else "media",
    }


# ---------------------------------------------------------------------------
# E-mail
# ---------------------------------------------------------------------------
def enviar_email(assunto, html, texto):
    usuario = os.getenv("SMTP_USUARIO")
    senha = os.getenv("SMTP_SENHA")
    destinatarios = [d.strip() for d in os.getenv("EMAIL_DESTINATARIOS", "").split(",") if d.strip()]
    if not (usuario and senha and destinatarios):
        print("  (e-mail não configurado — defina SMTP_USUARIO, SMTP_SENHA e EMAIL_DESTINATARIOS)")
        return False
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    porta = int(os.getenv("SMTP_PORTA", "465"))

    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = formataddr((os.getenv("EMAIL_REMETENTE_NOME", "Radar de Investimentos"), usuario))
    msg["To"] = ", ".join(destinatarios)
    msg.attach(MIMEText(texto, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    if porta == 465:
        servidor = smtplib.SMTP_SSL(host, porta, timeout=30)
    else:
        servidor = smtplib.SMTP(host, porta, timeout=30)
        servidor.starttls()
    with servidor:
        servidor.login(usuario, senha)
        servidor.sendmail(usuario, destinatarios, msg.as_string())
    print(f"  e-mail enviado para {len(destinatarios)} destinatário(s)")
    return True


def enviar_noticias(noticias, tipo):
    if not noticias:
        return
    # alta relevância primeiro, depois as mais recentes
    noticias = sorted(noticias, key=lambda n: (n["relevancia"] == "alta", n["publicado"]),
                      reverse=True)[: config.MAX_NOTICIAS_POR_EMAIL]
    assunto, html, texto = montar_email(noticias, tipo, os.getenv("PAINEL_URL", ""))
    enviar_email(assunto, html, texto)


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------
def executar(args):
    inicio = agora()
    historico = ler_json(ARQ_NOTICIAS, [])
    vistos = set(ler_json(ARQ_VISTOS, []))
    vistos.update(n["id"] for n in historico)

    if args.email_teste:
        enviar_noticias(historico[:5], "teste")
        return
    if args.resumo_semanal:
        limite = (inicio - timedelta(days=7)).isoformat()
        semana = [n for n in historico if n["coletado"] >= limite]
        if semana:
            enviar_noticias(semana, "semanal")
        else:
            print("Nenhuma notícia na última semana; resumo semanal não enviado.")
        return

    print(f"Coletando notícias sobre investimentos em {config.CIDADE}...")
    itens, status_fontes = coletar_itens()
    corte = inicio - timedelta(days=config.DIAS_RETROATIVOS)
    candidatos = [i for i in itens if i["id"] not in vistos and i["publicado"] >= corte]
    candidatos.sort(key=lambda i: i["publicado"], reverse=True)
    print(f"  {len(itens)} itens encontrados, {len(candidatos)} ainda não analisados")

    novas = []
    for item in candidatos[: config.MAX_ARTIGOS_POR_EXECUCAO]:
        vistos.add(item["id"])
        resultado = analisar(item)
        if resultado:
            novas.append(resultado)
            print(f"  + [{resultado['relevancia']}] {resultado['titulo'][:90]}")

    historico = sorted(novas + historico, key=lambda n: n["publicado"], reverse=True)[:2000]
    gravar_json(ARQ_NOTICIAS, historico)
    gravar_json(ARQ_VISTOS, sorted(vistos)[-20000:])
    gravar_json(ARQ_STATUS, {
        "ultima_execucao": agora().isoformat(),
        "novas_na_ultima_execucao": len(novas),
        "total_noticias": len(historico),
        "fontes_consultadas": status_fontes["ok"],
        "fontes_com_falha": status_fontes["erro"],
    })
    print(f"Concluído: {len(novas)} notícia(s) nova(s).")

    if novas and not args.sem_email:
        enviar_noticias(novas, "alerta")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Radar de Investimentos de Paulínia")
    p.add_argument("--sem-email", action="store_true", help="coleta sem enviar e-mail")
    p.add_argument("--resumo-semanal", action="store_true", help="envia o resumo dos últimos 7 dias")
    p.add_argument("--email-teste", action="store_true", help="envia e-mail de teste")
    executar(p.parse_args())
