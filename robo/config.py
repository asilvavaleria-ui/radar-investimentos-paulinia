"""
Configuração do Radar de Investimentos de Paulínia.

Este é o ÚNICO arquivo que precisa ser editado para ajustar o robô:
termos de busca, sites prioritários, setores e palavras de exclusão.
Os termos são comparados sem acento e sem diferenciar maiúsculas.
"""

CIDADE = "Paulínia"

# Quantos dias para trás uma notícia ainda é considerada "nova".
DIAS_RETROATIVOS = 15

# Limite de notícias analisadas (com leitura da página) por execução.
MAX_ARTIGOS_POR_EXECUCAO = 80

# Limite de notícias listadas em um único e-mail.
MAX_NOTICIAS_POR_EMAIL = 30

# ---------------------------------------------------------------------------
# BUSCAS — cada linha vira uma busca no Google Notícias e no Bing Notícias.
# ---------------------------------------------------------------------------
CONSULTAS = [
    "Paulínia investimento",
    "Paulínia investimentos milhões",
    "Paulínia nova fábrica",
    "Paulínia expansão empresa",
    "Paulínia nova unidade",
    "Paulínia centro de distribuição",
    "Paulínia empregos empresa",
    "Paulínia data center",
    "Paulínia Replan investimento",
    "Paulínia logística galpão",
    "Paulínia inauguração empresa",
    "Paulínia indústria",
    "Paulínia energia usina",
    "Paulínia polo petroquímico",
]

# Sites que recebem uma busca dedicada (Google Notícias com "site:").
SITES_PRIORITARIOS = [
    "valor.globo.com",
    "g1.globo.com",
    "estadao.com.br",
    "folha.uol.com.br",
    "exame.com",
    "infomoney.com.br",
    "investe.sp.gov.br",
    "saopaulo.sp.gov.br",
    "paulinia.sp.gov.br",
    "acidadeon.com",
    "correio.rac.com.br",
    "agenciabrasil.ebc.com.br",
    "petrobras.com.br",
    "metropoledigital.com.br",
]

# Feeds RSS adicionais (portais locais, órgãos públicos). Opcional.
FEEDS_EXTRAS = [
    # "https://exemplo.com.br/feed/",
]

# ---------------------------------------------------------------------------
# FILTRO DE RELEVÂNCIA
# Peso 2 = sinal forte de investimento; peso 1 = sinal fraco.
# ---------------------------------------------------------------------------
TERMOS_INVESTIMENTO = {
    "investimento": 2, "investimentos": 2, "investir": 2, "investira": 2,
    "aporte": 2, "expansao": 2, "ampliacao": 2, "amplia": 1,
    "nova fabrica": 2, "nova planta": 2, "nova unidade": 2, "nova sede": 2,
    "centro de distribuicao": 2, "condominio logistico": 2, "galpao": 1,
    "data center": 2, "implantacao": 2, "instalara": 2, "instala": 1,
    "inaugura": 2, "inauguracao": 2, "anuncia": 1,
    "milhoes": 2, "milhao": 2, "bilhoes": 2, "bilhao": 2,
    "empregos": 2, "postos de trabalho": 2, "vagas": 1, "contratacoes": 1,
    "financiamento": 2, "bndes": 2, "desenvolve sp": 2, "investsp": 2,
    "incentivo fiscal": 2, "parceria": 1, "ppp": 1, "concessao": 1,
    "fabrica": 1, "industria": 1, "obra": 1, "construcao": 1, "projeto": 1,
    "refinaria": 1, "replan": 1, "usina": 1, "biocombustivel": 1,
    "hidrogenio": 1, "etanol": 1, "biometano": 1, "energia solar": 1,
}

# Pontuação mínima para a notícia ser considerada sobre investimento.
PONTUACAO_MINIMA = 5
# Pontuação a partir da qual a notícia é marcada como "alta relevância".
PONTUACAO_ALTA = 12

# Notícias cujo TÍTULO contenha um destes termos são descartadas.
TERMOS_EXCLUSAO = [
    "homicidio", "assassin", "preso", "presa", "prisao", "acidente", "incendio",
    "morre", "morte", "roubo", "furto", "trafico", "tiroteio", "policia",
    "futebol", "campeonato", "novela", "horoscopo", "previsao do tempo",
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
