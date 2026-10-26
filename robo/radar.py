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
from difflib import SequenceMatcher
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
ESTATISTICAS = {"google_sem_link": 0}
ULTIMO_ERRO = {}
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
    # O filtro "when:" do Google só é útil para períodos curtos; acima disso, o corte é feito depois.
    if config.DIAS_RETROATIVOS <= 30:
        periodo = f" when:{config.DIAS_RETROATIVOS}d"
    else:
        periodo = f" after:{(agora() - timedelta(days=config.DIAS_RETROATIVOS)):%Y-%m-%d}"
    q = quote_plus(f"{consulta}{periodo}")
    return f"https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419"


def url_bing(consulta):
    return f"https://www.bing.com/news/search?q={quote_plus(consulta)}&format=rss&setlang=pt-BR&cc=BR"


def montar_fontes():
    fontes = []
    for c in config.CONSULTAS:
        fontes.append(("Google Notícias", url_google(c)))
        fontes.append(("Bing Notícias", url_bing(c)))
    for site in config.SITES_PRIORITARIOS + config.SITES_EMPRESAS:
        fontes.append(("Google Notícias", url_google(f'"{config.CIDADE}" site:{site}')))
    for feed in config.FEEDS_EXTRAS:
        fontes.append(("RSS", feed))
    return fontes


def baixar_feed(url):
    resposta = requests.get(url, headers=CABECALHOS, timeout=20)
    resposta.raise_for_status()
    return feedparser.parse(resposta.content)


def parecido(a, b):
    return SequenceMatcher(None, normalizar(a), normalizar(b)).ratio()


def buscar_original_no_bing(titulo):
    """Quando o link do Google não pode ser decodificado, procura a mesma notícia no Bing."""
    try:
        feed = baixar_feed(url_bing(f'"{titulo[:150]}"'))
    except Exception:
        return None, ""
    for e in feed.entries[:5]:
        titulo_bing = limpar_html(e.get("title", ""))
        semelhanca = parecido(titulo_bing, titulo)
        if semelhanca >= 0.85 or (normalizar(config.CIDADE) in normalizar(titulo_bing) and semelhanca >= 0.75):
            return link_real(e.get("link", "")), limpar_html(e.get("summary", ""))
    return None, ""


def link_real(link):
    """Remove redirecionadores conhecidos (Bing, Google) para chegar ao site original."""
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
            print(f"  ! link do Google não decodificado: {r.get('message', '')[:120]}")
        except Exception as erro:
            print(f"  ! link do Google não decodificado: {erro}")
        ESTATISTICAS["google_sem_link"] += 1
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
            if origem == "Google Notícias":
                if fonte and titulo.endswith(f" - {fonte}"):
                    titulo = titulo[: -len(fonte) - 3]
                elif " - " in titulo:
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


MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7,
         "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}


def _converter_data(valor):
    try:
        d = datetime.fromisoformat(str(valor).strip().replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=FUSO_BR)
    except ValueError:
        return None


def datas_da_pagina(sopa, url, html, texto_corpo):
    """Datas candidatas à data de publicação, da mais confiável para a menos confiável."""
    candidatas = []
    atributos = [("property", "article:published_time"), ("property", "og:published_time"),
                 ("itemprop", "datePublished"), ("name", "date"), ("name", "pubdate"),
                 ("name", "publishdate"), ("name", "DC.date.issued"), ("name", "article:published_time")]
    for attr, nome in atributos:
        tag = sopa.find("meta", attrs={attr: nome})
        if tag:
            candidatas.append(_converter_data(tag.get("content", "")[:25]))
    candidatas += [_converter_data(v[:25]) for v in re.findall(r'"datePublished"\s*:\s*"([^"]+)"', html)]
    tempo = sopa.find("time", attrs={"datetime": True})
    if tempo:
        candidatas.append(_converter_data(tempo["datetime"][:25]))
    m = re.search(r"/(20\d{2})/(\d{2})/(\d{2})/", url)
    if m:
        candidatas.append(datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=FUSO_BR))
    # datas escritas no início do corpo da matéria (sem cabeçalho/rodapé do site)
    inicio = normalizar(texto_corpo)
    for d, mes, ano in re.findall(r"\b(\d{1,2}) de (" + "|".join(MESES) + r") de (20\d{2})", inicio):
        candidatas.append(datetime(int(ano), MESES[mes], int(d), tzinfo=FUSO_BR))
    for d, mes, ano in re.findall(r"\b(\d{2})/(\d{2})/(20\d{2})\b", inicio):
        if 1 <= int(mes) <= 12 and 1 <= int(d) <= 31:
            candidatas.append(datetime(int(ano), int(mes), int(d), tzinfo=FUSO_BR))
    candidatas.append(ano_no_endereco(url))
    return [c for c in candidatas if c]


def ano_no_endereco(url):
    """Ano no endereço da notícia (ex.: /2022/), quando é anterior ao ano atual."""
    m = re.search(r"/(20\d{2})/", url)
    if m and int(m.group(1)) < agora().year:
        return datetime(int(m.group(1)), 12, 31, tzinfo=FUSO_BR)
    return None


def escolher_data(candidatas, data_rss):
    """Primeira data candidata que não seja posterior à data informada pelo Bing/Google.
    (Muitos sites exibem a data de HOJE no topo; uma notícia não pode ser publicada
    depois de indexada.)"""
    for c in candidatas:
        if c <= data_rss + timedelta(days=1):
            return c
    return None


def ler_artigo(url):
    """Baixa a página da notícia e devolve (texto, descrição meta, url final, data de publicação)."""
    ULTIMO_ERRO["ler_artigo"] = None
    try:
        r = requests.get(url, headers=CABECALHOS, timeout=15)
        r.raise_for_status()
    except Exception as erro:
        ULTIMO_ERRO["ler_artigo"] = str(erro)[:150]
        return "", "", url, None
    if "news.google.com" in r.url or "consent.google" in r.url:
        return "", "", url, None  # página do próprio Google, não da notícia
    sopa = BeautifulSoup(r.text, "html.parser")
    metas_html = str(sopa.head or "") + "".join(str(t) for t in sopa.find_all("script", type="application/ld+json"))
    meta = sopa.find("meta", attrs={"property": "og:description"}) or \
        sopa.find("meta", attrs={"name": "description"})
    descricao = meta.get("content", "").strip() if meta else ""
    for tag in sopa(["script", "style", "nav", "header", "footer", "aside", "form", "figure"]):
        tag.decompose()
    corpo = sopa.find("article") or sopa.body or sopa
    paragrafos = [p.get_text(" ", strip=True) for p in corpo.find_all("p")]
    texto = " ".join(p for p in paragrafos if len(p) > 60)
    datas = datas_da_pagina(BeautifulSoup(metas_html, "html.parser"), r.url, metas_html,
                            corpo.get_text(" ", strip=True)[:6000])
    return texto[:20000], descricao, r.url, datas


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
# A ordem importa: "mil" precisa ser testado antes de "mi".
MULTIPLICADORES = [("bilh", 1e9), ("bi", 1e9), ("milh", 1e6), ("mil", 1e3), ("mi", 1e6)]


def extrair_valores(texto):
    valores, maior_reais = [], 0.0
    for moeda, numero, escala in RE_VALOR.findall(texto):
        escala_n = normalizar(escala)
        mult = next((v for k, v in MULTIPLICADORES if escala_n.startswith(k)), 1)
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


def contem(texto_normalizado, termo, inteiro=True):
    """Procura o termo (sem acento) como palavra inteira ou, se inteiro=False, como início de palavra."""
    fim = r"(?!\w)" if inteiro else ""
    return re.search(rf"(?<!\w){re.escape(normalizar(termo))}{fim}", texto_normalizado) is not None


def pontuar(titulo, descricao, artigo):
    partes = [(normalizar(titulo), 3), (normalizar(descricao), 2), (normalizar(artigo), 1)]
    pontos = 0
    for termo, peso in config.TERMOS_INVESTIMENTO.items():
        padrao = re.compile(rf"(?<!\w){re.escape(normalizar(termo))}(?!\w)")
        multiplicador = max((m for texto, m in partes if padrao.search(texto)), default=0)
        pontos += peso * multiplicador
    return pontos


VERBOS_EMPRESA = (
    r"investe|investir[áa]|vai investir|planeja|projeta|anuncia|anunciou|inicia|iniciou|inaugura|"
    r"inaugurou|garante|passa a|constr[óo]i|construir[áa]|vai construir|instala|instalar[áa]|"
    r"vai instalar|implanta|implantar[áa]|amplia|ampliar[áa]|expande|compra|adquire|adquiriu|"
    r"escolhe|escolheu|confirma|ter[áa]|abre|come[çc]a|recebe aval|leva|traz|aposta|adapta|reformula|"
    r"negocia|reserva|vence|vai sair|ser[áa] a maior|transfere|transferiu|muda|leva"
)
RE_EMPRESA_TITULO = re.compile(rf"^([A-Z0-9][\w&.'’-]*(?:\s+(?:[A-Z0-9][\w&.'’-]*|de|do|da|&)){{0,5}})\s+(?:{VERBOS_EMPRESA})\b")
RE_EMPRESA_TEXTO = re.compile(
    r"\b(?:multinacional|empresa|companhia|grupo|fabricante|startup|farmac[êe]utica|"
    r"distribuidora|operadora|produtora)\s+(?:[a-zà-ú]+\s+){0,2}"
    r"([A-Z][\w&.'’-]*(?:\s+[A-Z][\w&.'’-]*){0,3})")
NAO_EMPRESA = {"paulinia", "prefeitura", "governo", "estado", "cidade", "regiao", "municipio", "brasil",
               "sp", "sao paulo", "campinas", "empresa", "multinacional", "nova", "novo", "projeto",
               "investimento", "o", "a", "os", "as", "em", "com", "setor", "industria", "polo",
               "lula", "presidente", "governador", "prefeito", "ministro", "secretaria", "refinaria",
               "maior", "projeto", "obras", "diesel", "alcoolduto", "etanolduto", "bom", "camara",
               "vereadores", "vereador", "justica", "tj", "governo", "tarcisio", "ons",
               "data", "anp", "cetesb", "mpt", "senai", "fatec", "hospital", "ubs"}


def identificar_empresa(titulo, descricao, texto):
    candidatos = []
    m = RE_EMPRESA_TITULO.match(titulo)
    if m:
        candidatos.append(m.group(1))
    for trecho in (descricao, texto[:1500]):
        m = RE_EMPRESA_TEXTO.search(trecho or "")
        if m:
            candidatos.append(m.group(1))
    titulo_n = normalizar(titulo)
    # empresas conhecidas, na ordem em que aparecem no título
    achadas = [(titulo_n.find(normalizar(nome)), nome) for nome in config.EMPRESAS_CONHECIDAS
               if contem(titulo_n, nome)]
    candidatos += [nome for _, nome in sorted(achadas)]
    for c in candidatos:
        c = c.strip(" .,-")
        if normalizar(c) not in NAO_EMPRESA and normalizar(c.split()[0]) not in NAO_EMPRESA and len(c) >= 2:
            return c
    return ""


TIPOS = [
    ("Início de operação", ["inaugura", "passa a operar", "inicia operacao", "inicia operacoes",
                            "comeca a operar", "entra em operacao"]),
    ("Obras iniciadas", ["inicia construcao", "iniciou a construcao", "inicio da construcao",
                         "iniciou as obras", "inicia obras", "inicio das obras", "pedra fundamental",
                         "iniciou oficialmente", "inicia oficialmente", "comecou a construir", "obras comecam"]),
    ("Nova instalação", ["nova fabrica", "nova planta", "nova unidade", "instalar", "instalacao",
                         "implantacao", "implanta", "se instala", "garante area", "terreno",
                         "construir", "construira", "escolhe", "escolheu", "chega", "instalad",
                         "construid", "novo centro", "novo data center", "novo laboratorio"]),
    ("Expansão", ["expansao", "amplia", "ampliacao", "expande", "segunda unidade",
                  "nova linha de producao", "capacidade produtiva"]),
    ("Investimento anunciado", ["invest", "aporte", "milhoes", "bilhoes", "bilhao", "milhao"]),
]


def classificar_tipo(titulo, descricao):
    t = normalizar(f"{titulo} {descricao}")
    for tipo, termos in TIPOS:
        if any(contem(t, termo, inteiro=False) for termo in termos):
            return tipo
    return "Outros sinais"


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


def cidade_relevante(titulo, descricao, texto):
    """Paulínia no título/subtítulo, ou citada logo no início da matéria e mais de uma vez."""
    cidade = normalizar(config.CIDADE)
    if cidade in normalizar(f"{titulo} {descricao}"):
        return True
    texto_n = normalizar(texto)
    mencoes = texto_n.count(cidade)
    if cidade not in texto_n[:1500] or mencoes < 2:
        return False
    return all(texto_n.count(lugar) <= mencoes for lugar in config.OUTRAS_LOCALIDADES)


def passa_triagem(titulo, descricao):
    """Título/subtítulo precisam indicar um empreendimento de EMPRESA em Paulínia."""
    titulo_n = normalizar(titulo)
    if any(contem(titulo_n, t.strip(), inteiro=False) for t in config.TERMOS_EXCLUSAO):
        return False
    texto = normalizar(f"{titulo} {descricao}")
    if not any(contem(texto, s, inteiro=False) for s in config.SINAIS_EMPREENDIMENTO):
        return False
    if identificar_empresa(titulo, descricao, ""):
        return True
    return any(contem(texto, t, inteiro=False) for t in config.TERMOS_EMPRESARIAIS)


def analisar(item):
    titulo_n = normalizar(item["titulo"])
    descricao = item["descricao"]
    if normalizar(descricao).startswith(titulo_n[:40]):
        descricao = ""  # o RSS do Google repete o título na descrição

    # Triagem pelo título/subtítulo: se não passar, nem vale a pena abrir a página.
    if not passa_triagem(item["titulo"], descricao):
        return None

    url = link_real(item["link"])
    if "news.google.com" in url:
        original, desc_bing = buscar_original_no_bing(item["titulo"])
        if original:
            url, descricao = original, descricao or desc_bing
    texto, meta_desc, url_final, datas = ler_artigo(url) if "news.google.com" not in url else ("", "", url, [])
    datas = datas or [d for d in [ano_no_endereco(url_final)] if d]
    data_pagina = escolher_data(datas, item["publicado"])
    # A data do Bing/Google às vezes é a da indexação; prevalece a data da página.
    if data_pagina and data_pagina < item["publicado"] - timedelta(days=1):
        item["publicado"] = data_pagina
    if item["publicado"] < agora() - timedelta(days=config.DIAS_RETROATIVOS):
        return None
    if not descricao or normalizar(descricao).startswith(titulo_n[:40]):
        descricao = meta_desc

    fonte = item["fonte"]
    if not fonte or "bing.com" in fonte or "google.com" in fonte:
        fonte = urlparse(url_final).netloc.replace("www.", "")

    tudo = f"{item['titulo']} {descricao} {texto}"
    # Paulínia precisa aparecer no título, no subtítulo ou no início da matéria
    # (evita páginas que só citam a cidade em links laterais).
    # Se o título/subtítulo não citam a cidade, ela precisa aparecer pelo menos
    # duas vezes no texto da matéria (uma menção solta costuma ser link lateral).
    if not cidade_relevante(item["titulo"], descricao, texto):
        return None

    pontos = pontuar(item["titulo"], descricao, texto)
    if pontos < config.PONTUACAO_MINIMA:
        return None

    valores, maior_valor = extrair_valores(tudo)
    empregos = extrair_empregos(tudo)
    resumo = resumo_ia(item["titulo"], texto) or resumo_extrativo(item["titulo"], texto, descricao)
    empresa = identificar_empresa(item["titulo"], descricao, texto)
    alta = pontos >= config.PONTUACAO_ALTA or maior_valor >= 1e7 or empregos >= 100

    return {
        "id": item["id"],
        "titulo": item["titulo"],
        "link": url_final if url_final.startswith("http") and "news.google.com" not in url_final else url,
        "fonte": fonte,
        "publicado": item["publicado"].isoformat(),
        "coletado": agora().isoformat(),
        "resumo": resumo,
        "empresa": empresa,
        "tipo": classificar_tipo(item["titulo"], descricao),
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
    remetente = os.getenv("EMAIL_REMETENTE") or usuario
    msg["From"] = formataddr((os.getenv("EMAIL_REMETENTE_NOME", "Radar de Investimentos"), remetente))
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
        servidor.sendmail(remetente, destinatarios, msg.as_string())
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


PALAVRAS_VAZIAS = {"paulinia", "para", "com", "sobre", "mais", "entre", "anuncia", "sera", "apos",
                   "como", "pela", "pelo", "pelos", "pelas", "cidade", "estado", "partir", "nesta",
                   "desde", "ate", "seu", "sua", "seus", "suas", "novo", "nova", "tem", "vai"}


def palavras_chave(titulo):
    return {p for p in re.findall(r"[a-z0-9]+", normalizar(titulo))
            if (len(p) >= 4 or (p.isdigit() and len(p) >= 2)) and p not in PALAVRAS_VAZIAS}


def mesma_historia(a, b):
    pa, pb = palavras_chave(a), palavras_chave(b)
    if not pa or not pb:
        return False
    return parecido(a, b) >= 0.7 or len(pa & pb) / len(pa | pb) >= 0.34


def registrar_repetida(item, conhecidas):
    """Mesma notícia publicada por outro veículo: guarda só como fonte adicional."""
    for n in conhecidas:
        dias = abs((datetime.fromisoformat(n["publicado"]) - item["publicado"]).days)
        if dias <= 10 and mesma_historia(n["titulo"], item["titulo"]):
            fontes = n.setdefault("outras_fontes", [])
            if item["fonte"] != n["fonte"] and item["fonte"] not in fontes:
                fontes.append(item["fonte"])
            return True
    return False


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------
def revisar_historico(historico):
    """Reaplica filtros e confere a data real de publicação das notícias já gravadas."""
    corte = agora() - timedelta(days=365)
    mantidas, relatorio = [], []
    for n in historico:
        if not passa_triagem(n["titulo"], ""):
            print(f"  - filtro: {n['titulo'][:90]}")
            continue
        if "news.google.com" not in n["link"]:
            texto, _, _, datas = ler_artigo(n["link"])
            datas = datas or [d for d in [ano_no_endereco(n["link"])] if d]
            data = escolher_data(datas, datetime.fromisoformat(n["publicado"]))
            relatorio.append({"titulo": n["titulo"][:80], "pagina_lida": bool(texto),
                              "data_rss": n["publicado"][:10], "data_pagina": f"{data:%Y-%m-%d}" if data else None,
                              "erro": ULTIMO_ERRO.get("ler_artigo")})
            if data and data < datetime.fromisoformat(n["publicado"]) - timedelta(days=1):
                print(f"  ~ data corrigida {n['publicado'][:10]} -> {data:%Y-%m-%d}: {n['titulo'][:70]}")
                n["publicado"] = data.isoformat()
            if texto and not cidade_relevante(n["titulo"], "", texto):
                print(f"  - não é sobre {config.CIDADE}: {n['titulo'][:90]}")
                continue
        if datetime.fromisoformat(n["publicado"]) < corte:
            print(f"  - antiga: {n['titulo'][:90]}")
            continue
        mantidas.append(n)
    mantidas.sort(key=lambda n: n["publicado"], reverse=True)
    gravar_json(ARQ_NOTICIAS, mantidas)
    gravar_json(RAIZ / "data" / "revisao.json", relatorio)
    print(f"Histórico revisado: {len(historico)} -> {len(mantidas)} notícias.")


def executar(args):
    inicio = agora()
    historico = ler_json(ARQ_NOTICIAS, [])
    vistos = set(ler_json(ARQ_VISTOS, []))
    vistos.update(n["id"] for n in historico)

    if args.revisar_historico:
        revisar_historico(historico)
        return
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
        if registrar_repetida(item, novas + historico):
            continue
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
        "links_google_nao_decodificados": ESTATISTICAS["google_sem_link"],
    })
    print(f"Concluído: {len(novas)} notícia(s) nova(s).")

    if novas and not args.sem_email:
        enviar_noticias(novas, "alerta")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Radar de Investimentos de Paulínia")
    p.add_argument("--sem-email", action="store_true", help="coleta sem enviar e-mail")
    p.add_argument("--resumo-semanal", action="store_true", help="envia o resumo dos últimos 7 dias")
    p.add_argument("--email-teste", action="store_true", help="envia e-mail de teste")
    p.add_argument("--revisar-historico", action="store_true",
                   help="reaplica os filtros e corrige datas das notícias já gravadas")
    executar(p.parse_args())
