"""Modelo do e-mail (HTML compatível com Gmail, Outlook e celular)."""

from datetime import datetime, timedelta, timezone
from html import escape

FUSO_BR = timezone(timedelta(hours=-3))
COR_SETOR = {
    "Energia e Petróleo": "#B45309", "Indústria": "#1D4ED8", "Logística": "#0F766E",
    "Tecnologia": "#7C3AED", "Comércio e Serviços": "#BE185D",
    "Imobiliário e Construção": "#4D7C0F", "Saúde e Educação": "#0369A1",
    "Infraestrutura Pública": "#475569", "Agronegócio": "#15803D",
}


def formatar_reais(valor):
    if valor >= 1e9:
        return f"R$ {valor / 1e9:.1f} bi".replace(".", ",")
    if valor >= 1e6:
        return f"R$ {valor / 1e6:.0f} mi"
    return ""


def data_br(iso):
    return datetime.fromisoformat(iso).astimezone(FUSO_BR).strftime("%d/%m/%Y")


def _chip(texto, cor, fundo):
    return (f'<span style="display:inline-block;padding:3px 9px;margin:0 6px 6px 0;border-radius:999px;'
            f'font-size:12px;font-weight:600;color:{cor};background:{fundo};">{escape(texto)}</span>')


def _mais_fontes(n):
    outras = n.get("outras_fontes") or []
    return f" e mais {len(outras)} veículo{'s' if len(outras) > 1 else ''}" if outras else ""


def _cartao(n):
    cor = COR_SETOR.get(n["setor"], "#475569")
    chips = ""
    if n.get("empresa"):
        chips += _chip(f"🏢 {n['empresa']}", "#0F172A", "#E2E8F0")
    if n.get("tipo"):
        chips += _chip(n["tipo"], "#0B3B66", "#E7F0FB")
    chips += _chip(n["setor"], cor, "#F1F5F9")
    if n["relevancia"] == "alta":
        chips = _chip("★ Alta relevância", "#92400E", "#FEF3C7") + chips
    if n.get("valor_reais"):
        chips += _chip(f"💰 {formatar_reais(n['valor_reais'])}", "#065F46", "#D1FAE5")
    elif n.get("valores"):
        chips += _chip(f"💰 {n['valores'][0]}", "#065F46", "#D1FAE5")
    if n.get("empregos"):
        chips += _chip(f"👷 {n['empregos']:,} empregos".replace(",", "."), "#1E3A8A", "#DBEAFE")
    return f"""
<tr><td style="padding:0 0 14px 0;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background:#FFFFFF;border:1px solid #E2E8F0;border-left:4px solid {cor};border-radius:10px;">
    <tr><td style="padding:18px 20px;">
      <div>{chips}</div>
      <a href="{escape(n['link'])}" style="font-size:17px;line-height:1.35;font-weight:700;color:#0F172A;text-decoration:none;">{escape(n['titulo'])}</a>
      <div style="font-size:12px;color:#64748B;margin:6px 0 10px;">{escape(n['fonte'])}{_mais_fontes(n)} · {data_br(n['publicado'])}</div>
      <div style="font-size:14px;line-height:1.55;color:#334155;">{escape(n['resumo'])}</div>
      <div style="margin-top:14px;">
        <a href="{escape(n['link'])}" style="display:inline-block;padding:8px 16px;border-radius:8px;background:#0B3B66;color:#FFFFFF;font-size:13px;font-weight:600;text-decoration:none;">Ler notícia completa →</a>
      </div>
    </td></tr>
  </table>
</td></tr>"""


def montar_email(noticias, tipo, painel_url=""):
    qtd = len(noticias)
    altas = sum(1 for n in noticias if n["relevancia"] == "alta")
    hoje = datetime.now(FUSO_BR).strftime("%d/%m/%Y")
    plural = "s" if qtd > 1 else ""

    if tipo == "semanal":
        titulo = "Resumo semanal de investimentos"
        assunto = f"📊 Resumo semanal: {qtd} notícia{plural} de investimento em Paulínia"
        intro = f"Destaques dos últimos 7 dias sobre investimentos em Paulínia — {qtd} notícia{plural}."
    elif tipo == "teste":
        titulo = "E-mail de teste"
        assunto = "✅ Radar de Investimentos de Paulínia — e-mail de teste"
        intro = "O envio de e-mails está funcionando. Abaixo, as notícias mais recentes do radar."
    else:
        titulo = "Novas notícias de investimento"
        destaque = f" ({altas} de alta relevância)" if altas else ""
        assunto = f"🔔 {qtd} nova{plural} notícia{plural} de investimento em Paulínia{destaque}"
        intro = f"O radar encontrou {qtd} nova{plural} notícia{plural} sobre investimentos em Paulínia{destaque}."

    botao_painel = ""
    if painel_url:
        botao_painel = (f'<div style="text-align:center;margin:8px 0 4px;"><a href="{escape(painel_url)}" '
                        'style="display:inline-block;padding:11px 22px;border-radius:8px;border:1px solid #0B3B66;'
                        'color:#0B3B66;font-size:14px;font-weight:600;text-decoration:none;">'
                        'Abrir painel completo</a></div>')

    html = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#F1F5F9;font-family:Segoe UI,Helvetica,Arial,sans-serif;">
<div style="display:none;max-height:0;overflow:hidden;">{escape(intro)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F1F5F9;">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;">
  <tr><td style="background:#0B3B66;border-radius:12px 12px 0 0;padding:26px 24px;">
    <div style="font-size:12px;letter-spacing:1.5px;text-transform:uppercase;color:#93C5FD;font-weight:700;">Paulínia · Desenvolvimento Econômico</div>
    <div style="font-size:24px;font-weight:700;color:#FFFFFF;margin-top:6px;">Radar de Investimentos</div>
    <div style="font-size:14px;color:#CBD5E1;margin-top:4px;">{titulo} · {hoje}</div>
  </td></tr>
  <tr><td style="background:#FFFFFF;padding:18px 24px;border-radius:0 0 12px 12px;margin-bottom:16px;">
    <div style="font-size:15px;color:#334155;line-height:1.5;">{escape(intro)}</div>
  </td></tr>
  <tr><td style="height:16px;"></td></tr>
  {''.join(_cartao(n) for n in noticias)}
  <tr><td>{botao_painel}</td></tr>
  <tr><td style="padding:18px 8px;text-align:center;font-size:12px;color:#94A3B8;line-height:1.5;">
    Mensagem automática do Radar de Investimentos de Paulínia.<br>
    Resumos gerados a partir de notícias públicas — confira sempre a fonte original.
  </td></tr>
</table></td></tr></table></body></html>"""

    linhas = [f"RADAR DE INVESTIMENTOS — PAULÍNIA ({hoje})", intro, ""]
    for n in noticias:
        linhas += [f"• {n['titulo']}", f"  {n['fonte']} · {data_br(n['publicado'])} · {n['setor']}",
                   f"  {n['resumo']}", f"  {n['link']}", ""]
    if painel_url:
        linhas.append(f"Painel completo: {painel_url}")
    return assunto, html, "\n".join(linhas)
