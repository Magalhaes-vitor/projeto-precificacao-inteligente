# Projeto de Precificacao Inteligente - Documentacao Arquitetural e Tecnica

## 1. Visao Geral do Projeto

Este projeto consiste em um ecossistema de Engenharia de Dados voltado para a captura, transformacao e analise de precos de produtos em diversas plataformas de e-commerce e varejo. O objetivo principal e extrair inteligencia competitiva de precos, permitindo a comparacao de valores unitarios de itens especificos em multiplos concorrentes.

O fluxo de dados foi desenhado para ser resiliente, altamente validado e preparado para execucao em ambientes de Cloud Computing (como AWS Fargate, S3 e Athena).

## 2. Estrutura do Repositorio

A arquitetura do repositorio esta organizada da seguinte forma:

- **scrapers/**: Contem todos os scripts de extracao (Camada Bronze). Inclui a classe base e os scrapers especificos para cada dominio.
- **data_samples/**: Armazena os dados brutos (Raw Data) extraidos em formato JSON. (Camada Bronze)
- **aws/**: Armazenamento de scripts para infraestrutura de nuvem, como queries do Amazon Athena e possiveis definicoes do AWS Glue.
- **bi/**: Arquivos relacionados a visualizacao de dados, como dashboards no Power BI.

## 3. Arquitetura de Extracao (Camada Bronze)

A camada de extracao foi construida utilizando Python, Selenium e BeautifulSoup4. Ela e orquestrada por um script central (`main.py`) e baseia-se no padrao de projeto Orientacao a Objetos, onde cada scraper herda comportamentos de `BaseScraper`.

### 3.1. BaseScraper (`base_scraper.py`)
A classe fundacional que garante padronizacao em todos os scrapers. Funcoes principais:
- **Gestao de Logs**: Centraliza a emissao de logs operacionais em formato padronizado (INFO, AVISO, ERRO, SUCESSO).
- **Leitura de Configuracoes**: Carrega dinamicamente a matriz de produtos (`config_produtos.json`).
- **Normalizacao Matematica (`normalizar_preco`)**: Algoritmo central baseado em Expressoes Regulares (Regex) que decodifica kits e pacotes (ex: "Pack com 6") para calcular o preco unitario base.
- **Persistencia**: Padroniza a gravacao dos outputs JSON com timestamps.

### 3.2. Orquestrador Central (`main.py`)
O `main.py` funciona como o controlador de execucao. 
- **Isolamento de Falhas**: Instancia e executa cada scraper sequencialmente dentro de blocos `try/except`. Uma falha critica em um dominio nao afeta os demais.
- **Gestao de Recursos**: Aplica pausas estruturais (`time.sleep`) para desalocacao de processos de memoria do navegador entre execucoes.

## 4. Scrapers e Suas Resiliencias

Cada scraper possui estrategias dedicadas para lidar com os bloqueios e fluxos de navegacao de sua respectiva plataforma.

### 4.1. Amazon (`amazon_scraper.py`)
- **Evasao de WAF**: Modificacao de assinaturas de navegacao (`AutomationControlled`) e rotina de backoff mediante deteccao de desafio CAPTCHA.
- **DOM Dinamico**: Injeccao de JavaScript para forcamento de scroll e acionamento de carregamento tardio (Lazy Loading).
- **Filtro de Buy Box**: Capacidade de extrair precos tanto da listagem principal quanto de vendedores parceiros (`secondary-offer-recipe`).

### 4.2. Atacadao (`atacadao_scraper.py`)
- **Gestao de Estado**: Definicao programatica de localizacao via CEP, mimetizando a interacao de um usuario no front-end React.
- **Interceptacao de Autocomplete**: Leitura estruturada dos resultados retornados pelo dropdown de busca, garantindo performance e prevencao contra carregamentos completos de pagina.
- **Tratamento de Modais**: Remocao ativa de overlays promocionais que interceptam cliques no DOM.

### 4.3. Mercado Livre (`mercado_livre_scraper.py`)
- **Estrategia Hibrida**: Utilizacao de esperas explicitas (`WebDriverWait`) combinadas com parseamento passivo via BeautifulSoup para lidar com vitrines geradas por renderizacao mista (Server-Side / Client-Side).
- **Filtro Estrito de Marketplace**: Logica agressiva de exclusao de itens concorrentes ou falsos positivos inseridos nativamente pela engine de anuncios patrocinados da plataforma.

### 4.4. Pao de Acucar (`pao_de_acucar_scraper.py`)
- **Resolucao de WAF PoW (Altcha)**: O sistema de protecao utiliza um sistema de Proof-of-Work. O script detecta a presenca do componente Shadow DOM `<altcha-widget>`, injeta a interacao e aplica uma rotina de espera em polling para aguardar a solucao criptografica do desafio.
- **Filtro de Disponibilidade**: Ignora elementos categorizados como `StockOutLabel`, prevenindo poluicao dos dados com precos base irreais.

### 4.5. Tenda Atacado (`tenda_atacado_scraper.py`)
- **Controle VTEX**: Desativacao forcada de classes do `<body>` (`modal-open`) que bloqueiam manipulacao do DOM e fluxo de scroll de pagina.
- **Sincronia Rigorosa de Lazy Loading**: Pausas cronometradas intercaladas com injecoes de `window.scrollTo` estrategicas para disparar APIs de paginacao da VTEX.
- **Normalizacao de Textos Sujos**: Limpeza pre-parser para caracteres inquebraveis (` `) comuns nesta plataforma.

### 4.6. Ze Delivery (`ze_delivery_scraper.py`)
- **Interacao com Age Gate**: Resolucao mandatoria de bloqueios de idades.
- **Navegacao Georreferenciada**: Interacao baseada em deslocamento de eixos (`ActionChains`) para superar a validacao do Google Places na definicao de domicilio.
- **Extracao Dinamica de Precos Minimos**: Em casos de dualidade de valores (descontos aplicados e preco cortado), isola e capta apenas o valor comercial de face (`min()`) apos descartar badges como `-12%`.

## 5. Algoritmo de Consistencia de Dados (Motor Semantico)

Presente em multiplos scrapers, a arquitetura garante validacao e purificacao da extracao antes da criacao do JSON, utilizando as seguintes operacoes de checagem cruzada:
1.  **Filtro Negativo de Sabores/Variantes**: Recusa sumaria de strings contendo expressoes colidentes pre-cadastradas (ex: Limao, Cafe, Diet, Zero).
2.  **Validacao Equivalente de Embalagens**: Discriminacao binaria entre embalagens metalicas (Lata) e plasticas (Pet).
3.  **Comparacao Matematica de Medidas**: Conversao semantica universal (ex: 2L para 2000ml, 1KG para 1000g) cruzando com a String base de pesquisa para evitar captacao de versoes minimas do produto ou amostras gratis.
4.  **Bypass de Excecao de Padrao**: Hardcode validatorio para garantir a aderencia de produtos mal formatados nas lojas (ex: Coca-Cola 2L Original) garantindo alta capilaridade de matches corretos.

## 6. Padronizacao e Manutenibilidade

Todos os codigos e outputs de loggin seguem boas praticas para facil depuracao. Arquivos JSON resultantes representam o fim do estagio de Extractions, devendo ser posteriormente consolidados e tratados via ferramentas da Camada Silver.