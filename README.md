# Radar de Investimentos — Paulínia

Robô que **procura sozinho**, várias vezes por dia, notícias públicas sobre investimentos em Paulínia
(novas fábricas, expansões, centros de distribuição, data centers, energia, empregos etc.) e
**envia por e-mail um resumo com o link** de cada notícia encontrada. Também mantém um
**painel visual na internet** com todo o histórico, filtros por setor e exportação para planilha.

**Custo: R$ 0.** Usa apenas serviços gratuitos: GitHub (automação e hospedagem do painel),
Google Notícias e Bing Notícias (busca) e uma conta Gmail (envio).

---

## Como funciona

```
 5x ao dia (7h, 10h, 13h, 16h, 19h)          toda segunda-feira, 8h
            │                                          │
            ▼                                          ▼
 Busca no Google Notícias, Bing Notícias      E-mail "Resumo semanal"
 e em 14 sites prioritários (Valor, G1,       com os destaques dos
 Estadão, InvestSP, Prefeitura, ACidadeON…)   últimos 7 dias
            │
            ▼
 Filtra: precisa citar Paulínia + sinais de investimento
 Descarta: notícias policiais, esportes, repetidas
            │
            ▼
 Lê a notícia, gera resumo, identifica setor,
 valor anunciado (R$) e número de empregos
            │
      ┌─────┴──────┐
      ▼            ▼
  E-mail com     Painel web
  as novidades   atualizado
```

Notícias com valor ≥ R$ 10 milhões, ≥ 100 empregos ou sinais fortes recebem o selo **★ Alta relevância**
e aparecem primeiro no e-mail.

---

## Instalação (cerca de 20 minutos, feita uma única vez)

### 1. Criar a conta de e-mail que vai enviar os alertas
Recomendado: uma conta Gmail dedicada, por exemplo `radar.investimentos.paulinia@gmail.com`.

1. Ative a **Verificação em duas etapas**: <https://myaccount.google.com/security>
2. Crie uma **Senha de app**: <https://myaccount.google.com/apppasswords>
   (nome: "Radar"). Copie a senha de 16 letras — ela será usada no passo 3.

> Pode ser usado também um e-mail institucional (Outlook/Office 365 etc.). Nesse caso, informe
> `SMTP_HOST` e `SMTP_PORTA` no passo 3 (ex.: `smtp.office365.com` e `587`).

### 2. Colocar o robô no GitHub
1. Crie uma conta gratuita em <https://github.com> (de preferência com e-mail da Secretaria).
2. Clique em **New repository** → nome `radar-investimentos-paulinia` → marque **Public** → **Create**.
   (Repositório público = automação e painel gratuitos e ilimitados. Só ficam públicos o código e
   as notícias, que já são públicas. Senhas ficam protegidas no passo 3.)
3. Na página do repositório, clique em **uploading an existing file** e arraste **todo o conteúdo**
   desta pasta (incluindo a pasta oculta `.github`). Clique em **Commit changes**.

### 3. Cadastrar as senhas e os destinatários (com segurança)
No repositório: **Settings → Secrets and variables → Actions → New repository secret**. Crie:

| Nome | Valor |
|---|---|
| `SMTP_USUARIO` | e-mail remetente (passo 1) |
| `SMTP_SENHA` | senha de app de 16 letras (passo 1) |
| `EMAIL_DESTINATARIOS` | e-mails separados por vírgula, ex.: `secretario@paulinia.sp.gov.br, gabinete@paulinia.sp.gov.br` |
| `SMTP_HOST` *(opcional)* | só se não for Gmail |
| `SMTP_PORTA` *(opcional)* | só se não for Gmail |
| `GEMINI_API_KEY` *(opcional)* | veja "Resumos com IA" abaixo |

### 4. Permitir que o robô salve o histórico
**Settings → Actions → General → Workflow permissions** → marque **Read and write permissions** → **Save**.

### 5. Publicar o painel
**Settings → Pages** → em *Source* escolha **Deploy from a branch** → Branch **main**, pasta **/docs** → **Save**.
Em 1–2 minutos o painel estará em:
`https://SEU-USUARIO.github.io/radar-investimentos-paulinia/`

### 6. Testar
**Actions → Radar de Investimentos → Run workflow**:
- `busca` → faz uma busca agora (a primeira traz as notícias dos últimos 15 dias);
- `email-teste` → envia um e-mail de teste com as notícias mais recentes;
- `resumo-semanal` → envia o resumo da semana.

Pronto. A partir daí o robô roda sozinho.

---

## Uso no dia a dia

- **E-mail**: chega somente quando há notícia nova (sem spam). Cada item traz resumo, setor,
  valor, empregos e o botão "Ler notícia completa".
- **Painel**: busca por empresa/palavra, filtro por período (7/30/90 dias), por setor e
  "somente alta relevância"; botões **Exportar planilha** (abre no Excel) e **Imprimir**
  (útil para levar a reuniões). Funciona no celular.

## Ajustes (sem programar)
Edite o arquivo `robo/config.py` direto no GitHub (ícone de lápis):
- `CONSULTAS` — termos pesquisados (ex.: acrescentar nomes de empresas ou distritos industriais);
- `SITES_PRIORITARIOS` — sites com busca dedicada;
- `FEEDS_EXTRAS` — endereços RSS de portais locais;
- `TERMOS_EXCLUSAO` — palavras que descartam a notícia;
- `SETORES` — setores e palavras que os identificam.

Para mudar os horários, edite as linhas `cron` em `.github/workflows/radar.yml`
(horário em UTC = Brasília + 3h).

## Resumos com IA (opcional, gratuito)
Por padrão o resumo é feito **sem IA**, selecionando as frases mais informativas da notícia
(empresa, valor, empregos, prazo). Para resumos redigidos por IA, crie uma chave gratuita do
Google Gemini em <https://aistudio.google.com/apikey> e cadastre-a como `GEMINI_API_KEY` no passo 3.
Observação: na camada gratuita o Google pode usar os textos enviados para melhorar seus produtos —
como são notícias públicas, não há dado sensível envolvido.

## Observações
- O GitHub pode atrasar execuções agendadas em alguns minutos — é normal.
- Se o repositório ficar 60 dias sem nenhuma alteração, o GitHub pausa o agendamento; como o
  robô grava o horário da última verificação a cada execução, isso não deve ocorrer. Se ocorrer,
  basta clicar em **Enable workflow** na aba Actions.
- Valores e empregos são extraídos automaticamente do texto — confira sempre a fonte original
  antes de uso oficial.

## Rodar no próprio computador (opcional, para técnicos)
```bash
pip install -r requirements.txt
python robo/radar.py --sem-email
```
