"""
Configuração do Radar de Investimentos de Paulínia.

Este é o ÚNICO arquivo que precisa ser editado para ajustar o robô:
termos de busca, sites prioritários, setores e palavras de exclusão.
Os termos são comparados sem acento e sem diferenciar maiúsculas.
"""

CIDADE = "Paulínia"

import os

# Quantos dias para trás uma notícia ainda é considerada "nova".
# (Na primeira execução, use o botão "Run workflow" com mais dias para buscar o histórico.)
DIAS_RETROATIVOS = int(os.getenv("DIAS_RETROATIVOS") or 15)

# Limite de notícias analisadas (com leitura da página) por execução.
MAX_ARTIGOS_POR_EXECUCAO = int(os.getenv("MAX_ARTIGOS") or 120)

# Limite de notícias listadas em um único e-mail.
MAX_NOTICIAS_POR_EMAIL = 40

# ---------------------------------------------------------------------------
# BUSCAS — cada linha vira uma busca no Google Notícias e no Bing Notícias.
# Foco: empresas que estão chegando, se instalando, construindo, expandindo
# ou anunciando investimentos em Paulínia.
# ---------------------------------------------------------------------------
CONSULTAS = [
    # Novas empresas e instalações
    '"Paulínia" empresa investe',
    '"Paulínia" empresa vai investir',
    '"Paulínia" empresa anuncia investimento',
    '"Paulínia" nova fábrica',
    '"Paulínia" nova planta industrial',
    '"Paulínia" nova unidade industrial',
    '"Paulínia" instalação de unidade',
    '"Paulínia" escolhe área para instalação',
    '"Paulínia" aquisição de terreno empresa',

    # Construção e expansão
    '"Paulínia" construção de fábrica',
    '"Paulínia" obras nova unidade empresa',
    '"Paulínia" expansão industrial',
    '"Paulínia" ampliação da capacidade produtiva',
    '"Paulínia" nova linha de produção',
    '"Paulínia" expansão da unidade industrial',
    '"Paulínia" investimento em planta industrial',

    # Logística e infraestrutura empresarial
    '"Paulínia" centro de distribuição',
    '"Paulínia" novo centro logístico',
    '"Paulínia" galpão logístico empresa',
    '"Paulínia" novo data center',
    '"Paulínia" terminal logístico investimento',

    # Setores estratégicos
    '"Paulínia" biocombustíveis investimento',
    '"Paulínia" SAF combustível sustentável',
    '"Paulínia" indústria química investimento',
    '"Paulínia" indústria farmacêutica expansão',
    '"Paulínia" laboratório investimento empresa',
    '"Paulínia" fertilizantes nova unidade',
    '"Paulínia" petroquímica expansão',
    '"Paulínia" energia nova planta',

    # Valores e projetos anunciados
    '"Paulínia" investimento milhões empresa',
    '"Paulínia" investimento bilhões indústria',
    '"Paulínia" projeto industrial anunciado',
    '"Paulínia" inicia construção unidade',
    '"Paulínia" obras unidade industrial',
    '"Paulínia" inaugura nova fábrica',
]

# Sites que recebem uma busca dedicada (Google Notícias com "site:").
SITES_PRIORITARIOS = [
    # Imprensa econômica e de negócios
    "valor.globo.com",
    "exame.com",
    "infomoney.com.br",
    "estadao.com.br",
    "forbes.com.br",
    "bloomberglinea.com.br",

    # Energia, petróleo e biocombustíveis
    "novacana.com",
    "eixos.com.br",
    "epbr.com.br",
    "petrobras.com.br",

    # Indústria, química e agronegócio
    "revistacultivar.com.br",
    "quimica.com.br",
    "chemicalindustry.com.br",

    # Engenharia, construção e logística
    "afonsofranca.com.br",
    "logweb.com.br",
    "mundologistica.com.br",

    # Tecnologia e data centers
    "datacenterdynamics.com",
    "datacenterdynamics.com.br",

    # Investimento e desenvolvimento econômico
    "investe.sp.gov.br",
    "saopaulo.sp.gov.br",
    "paulinia.sp.gov.br",
]

# Feeds RSS adicionais (portais locais, órgãos públicos). Opcional.
FEEDS_EXTRAS = [
    # "https://exemplo.com.br/feed/",
]

# ---------------------------------------------------------------------------
# FILTRO DE RELEVÂNCIA
# ---------------------------------------------------------------------------
# A notícia só é aceita se o TÍTULO ou o SUBTÍTULO tiver ao menos um destes
# sinais de empreendimento (comparação pelo início da palavra).
SINAIS_EMPREENDIMENTO = [
    "invest", "aporte", "planta", "fabrica", "unidade", "laboratorio", "centro de distribuicao",
    "centro logistico", "condominio logistico", "galpao", "data center", "datacenter",
    "construcao", "construir", "constroi", "obras", "instala", "implanta", "expansao", "expande",
    "amplia", "nova sede", "nova operacao", "passa a operar", "inaugura", "terreno", "area",
    "duto", "usina", "refinaria", "biorrefinaria", "complexo", "milhoes", "milhao", "bilhoes",
    "bilhao", "investment", "plant", "facility", "expansion",
]

# Pontuação: peso 2 = sinal forte; peso 1 = sinal fraco.
TERMOS_INVESTIMENTO = {
    "investimento": 2, "investimentos": 2, "investe": 2, "investir": 2, "investira": 2,
    "aporte": 2, "expansao": 2, "ampliacao": 2, "amplia": 1, "expande": 2,
    "nova fabrica": 3, "nova planta": 3, "nova unidade": 3, "nova sede": 2, "planta": 1,
    "fabrica": 1, "laboratorio": 1, "centro de distribuicao": 3, "condominio logistico": 2,
    "galpao": 1, "data center": 3, "implantacao": 2, "instalacao": 1, "instalar": 2,
    "construcao": 2, "construir": 2, "obras": 1, "terreno": 1, "inaugura": 2,
    "inauguracao": 2, "passa a operar": 3, "multinacional": 2, "empresa": 1, "companhia": 1,
    "milhoes": 2, "milhao": 2, "bilhoes": 3, "bilhao": 3,
    "empregos diretos": 2, "postos de trabalho": 1,
    "financiamento": 1, "bndes": 2, "investsp": 2, "incentivo fiscal": 2,
    "refinaria": 1, "biorrefinaria": 2, "usina": 1, "duto": 1, "saf": 1,
    "biocombustivel": 1, "etanol": 1, "biometano": 1, "hidrogenio": 1,
    "investment": 2, "plant": 1, "facility": 1,
}

TERMOS_INVESTIMENTO.update({
    # Instalação de novas operações
    "implantará": 3,
    "implantacao de unidade": 3,
    "instalacao de planta": 3,
    "nova planta industrial": 3,
    "construira uma unidade": 3,
    "construcao de nova fabrica": 3,
    "escolheu paulinia": 3,
    "area para implantacao": 3,
    "aquisição de terreno": 2,
    "adquiriu terreno": 3,
    "reservou area": 3,

    # Expansão e capacidade produtiva
    "expansao da fabrica": 3,
    "ampliacao da unidade": 3,
    "aumento da capacidade produtiva": 3,
    "nova linha de producao": 3,
    "segunda unidade": 3,
    "nova unidade produtiva": 3,

    # Fases de investimento
    "anunciou investimento": 3,
    "investimento previsto": 3,
    "investimento de r$": 3,
    "iniciou as obras": 3,
    "inicio da construcao": 3,
    "obras da nova unidade": 3,
    "licenca de instalacao": 2,
    "licenciamento ambiental": 1,
})

# Pontuação mínima para a notícia ser aceita.
PONTUACAO_MINIMA = 6
# Pontuação a partir da qual a notícia é marcada como "alta relevância".
PONTUACAO_ALTA = 16

# Notícias cujo TÍTULO contenha um destes termos são descartadas
# (comparação pelo início da palavra, sem acento).
TERMOS_EXCLUSAO = [
    # vagas, cursos e programas de emprego (não são investimentos)
    "vagas de emprego", "vaga de emprego", "vagas abertas", "vagas disponiveis", "emprega paulinia",
    "processo seletivo", "concurso", "inscricoes", "curso", "capacitacao", "estagio",
    "jovem aprendiz", "oportunidades de emprego", "feirao", "pat ", "seleciona", "contrata ",
    "cadastro reserva", "trabalhe conosco",
    # obras e serviços públicos (o foco são empresas)
    "escola", "creche", "fatec", "faculdade de tecnologia", "ubs", "ponte", "pavimentacao",
    "recape", "ar-condicionado", "mobilidade urbana", "estacao de tratamento de esgoto",
    "habitantes", "socioambient", "recorde", "melhor julho", "melhor mes", "producao de derivados",
    # investigações e fraudes
    "operacao", "investiga", "fraude", "lavagem", "falsos", "receita mira",
    # segurança, esportes e entretenimento
    "homicidio", "assassin", "preso", "presa ", "prisao", "acidente", "incendio", "explosao",
    "morre", "morte", "roubo", "furto", "trafico", "tiroteio", "policia", "golpe",
    "futebol", "campeonato", "novela", "horoscopo", "previsao do tempo", "show", "festival",
]

# ---------------------------------------------------------------------------
# SETORES — usados para classificar e filtrar no painel.
# ---------------------------------------------------------------------------
SETORES = {
    "Energia e Petróleo": ["replan", "petrobras", "refinaria", "petroquim", "combustive",
                           "biocombustive", "etanol", "biometano", "hidrogenio", "energia",
                           "usina", "solar", "gas natural", "diesel"],
    "Indústria": ["fabrica", "industria", "industrial", "planta", "manufatura", "quimica",
                  "farmaceutic", "automotiv", "metalurg"],
    "Logística": ["logistic", "centro de distribuicao", "galpao", "armazem", "condominio logistico",
                  "transportadora", "e-commerce", "rodovia", "ferrovia"],
    "Tecnologia": ["data center", "tecnologia", "software", "startup", "inovacao",
                   "inteligencia artificial", "telecom", "fibra optica", "semicondutor"],
    "Comércio e Serviços": ["shopping", "varejo", "supermercado", "atacad", "loja", "hotel",
                            "restaurante", "comercio", "servicos"],
    "Imobiliário e Construção": ["imobiliari", "loteamento", "condominio residencial",
                                 "empreendimento", "construtora", "habitacional", "apartamentos"],
    "Saúde e Educação": ["hospital", "saude", "clinica", "escola", "faculdade", "universidade",
                         "educacao", "ensino"],
    "Infraestrutura Pública": ["prefeitura", "governo do estado", "ppp", "concessao", "saneamento",
                               "pavimentacao", "obra publica", "viaduto", "licitacao", "mobilidade"],
    "Agronegócio": ["agro", "agricola", "agropecuari", "cana", "fertilizante", "defensivo"],
}
SETOR_PADRAO = "Outros"
