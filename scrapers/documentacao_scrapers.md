# Projeto de Precificação Inteligente - Documentação Arquitetural e Técnica

## 1. Visão Geral do Projeto

Este projeto consiste em um ecossistema de Engenharia de Dados voltado para a captura, transformação e análise de preços de produtos em diversas plataformas de e-commerce e varejo. O objetivo principal é extrair inteligência competitiva de preços, permitindo a comparação precisa de valores unitários de itens específicos em múltiplos concorrentes.

O fluxo de dados foi desenhado para ser resiliente, altamente validado e preparado para execução automatizada em ambientes de Cloud Computing (como AWS Fargate, Amazon S3 e, futuramente, Amazon Athena).

## 2. Estrutura do Repositório

A arquitetura do repositório está organizada da seguinte forma:

* **scrapers/**: Diretório contendo os scripts de extração (Camada Bronze). Inclui a classe base, os scrapers específicos para cada domínio e o orquestrador principal.
* **data_samples/**: Armazenamento efêmero dos dados brutos (Raw Data) extraídos em formato JSON durante a execução da Camada Bronze.
* **transformacao_silver.py**: Script responsável pelo pipeline ETL, processando os dados brutos, convertendo para formatos analíticos e enviando para a nuvem.
* **config_produtos.json**: Arquivo de configuração que atua como base de conhecimento, contendo a matriz de produtos, marcas, categorias e termos de busca.
* **aws/**: Armazenamento de scripts para infraestrutura de nuvem, como queries do Amazon Athena e possíveis definições do AWS Glue.
* **bi/**: Arquivos relacionados à visualização de dados, como dashboards no Power BI.

## 3. Arquitetura de Extração (Camada Bronze)

A camada de extração foi construída em Python utilizando `undetected_chromedriver` (para evasão de defesas antibot e Web Application Firewalls) e `BeautifulSoup4` (para parseamento de alta performance). A arquitetura baseia-se no padrão de projeto Orientação a Objetos.

### 3.1. BaseScraper (`base_scraper.py`)
A classe fundacional que garante padronização comportamental em todos os scrapers. Responsabilidades principais:
* **Gestão de Logs**: Centraliza a emissão de logs operacionais em formato padronizado de terminal (INFO, AVISO, ERRO).
* **Leitura de Configurações**: Carrega dinamicamente a matriz de produtos a buscar (`config_produtos.json`).
* **Normalização Matemática (`normalizar_preco`)**: Motor semântico baseado em Expressões Regulares (Regex) que decodifica kits e fardos (exemplo: "Pack com 12") para extrair a quantidade da embalagem e calcular o preço unitário real.
* **Persistência**: Padroniza a gravação local dos outputs temporários em arquivos JSON com marcadores de tempo (timestamps).

### 3.2. Orquestrador Central (`main.py`)
Funciona como o controlador principal de execução do pipeline.
* **Isolamento de Falhas**: Instancia e executa cada scraper sequencialmente dentro de blocos de tratamento de exceções (`try/except`). Falhas críticas em um domínio não interrompem o fluxo geral.
* **Gestão de Recursos (Memory Cleanup)**: Aplica rotinas de limpeza forçada (`limpar_navegador`) utilizando chamadas de sistema operativo (subprocess) para encerrar processos zumbis do Chrome e ChromeDriver, prevenindo vazamentos de memória e erros de portas travadas (como WinError 6).
* **Acionamento em Cascata**: Ao finalizar a Camada Bronze, aciona automaticamente o processamento da Camada Silver.

## 4. Scrapers e Suas Estratégias de Resiliência

Cada scraper foi projetado com estratégias dedicadas para contornar bloqueios específicos e peculiaridades de renderização de sua respectiva plataforma.

### 4.1. Amazon (`amazon_scraper.py`)
* **Evasão Avançada**: Utilização do Chrome indetectável para mascarar assinaturas de automação frente aos sistemas da plataforma e rotina de backoff mediante detecção de desafio CAPTCHA.
* **Manipulação de DOM Dinâmico**: Injeção de JavaScript para forçamento de scroll e acionamento de carregamento tardio (Lazy Loading).
* **Filtro de Buy Box**: Capacidade de extrair preços tanto da listagem principal quanto de vendedores parceiros (`secondary-offer-recipe`).

### 4.2. Atacadão (`atacadao_scraper.py`)
* **Gestão de Estado e Localização**: Definição programática de localização inserindo o CEP padrão, mimetizando a interação de um usuário real no front-end React para liberação do acesso ao catálogo.
* **Interceptação de Autocomplete**: Navegação focada no menu dropdown de busca, otimizando a performance da rede e prevenindo o carregamento custoso de páginas completas.
* **Tratamento de Modais**: Remoção ativa de overlays promocionais que interceptam cliques no DOM.

### 4.3. Mercado Livre (`mercado_livre_scraper.py`)
* **Status Atual**: Inativo no pipeline principal da AWS (comentado no orquestrador `main.py`) e mantido como recurso em quarentena documentada.
* **Estratégia Anti-WAF (Akamai)**: O sistema do Mercado Livre aplica um hard block em tráfego oriundo de datacenters (AWS). O script contorna este bloqueio implementando injeção dinâmica de Proxy Residencial ou Comercial (via variável de ambiente `PROXY_MERCADO_LIVRE`) para mascarar a origem da requisição.
* **Validação Estrita de Volumetria**: O algoritmo extrai a litragem/volume alvo do termo de busca original (ex: "2L" ou "350ml") e valida rigorosamente contra o título do anúncio, descartando itens fora do escopo.
* **Ordenação por Preço Unitário**: Após os filtros de relevância e marca, o motor organiza os anúncios aprovados baseando-se estritamente no menor preço unitário real calculado, evitando a captura de itens avulsos irrelevantes ou falsos positivos de vitrine.

### 4.4. Pão de Açúcar (`pao_de_acucar_scraper.py`)
* **Resolução de WAF PoW (Altcha)**: O sistema de proteção utiliza um sistema de Proof-of-Work. O script detecta a presença do componente Shadow DOM `<altcha-widget>`, injeta a interação e aplica uma rotina de espera em polling para aguardar a solução criptográfica do desafio.
* **Navegação Silenciosa e Filtro de Relevância**: Utiliza o motor indetectável para aguardar o carregamento assíncrono dos componentes de vitrine. Processa a árvore HTML isolando a marca e a string de busca estrita para descartar sugestões imprecisas ou anúncios patrocinados.
* **Filtro de Disponibilidade**: Ignora elementos categorizados como `StockOutLabel`, prevenindo poluição dos dados com preços base irreais.

### 4.5. Tenda Atacado (`tenda_atacado_scraper.py`)
* **Controle VTEX**: Desativação forçada de classes do `<body>` (`modal-open`) que bloqueiam manipulação do DOM e fluxo de scroll de página.
* **Sincronia Rigorosa de Lazy Loading**: Pausas cronometradas intercaladas com injeções de `window.scrollTo` estratégicas para disparar APIs de paginação da arquitetura VTEX.
* **Tratamento de Dados e Textos**: Limpeza pré-parser para caracteres inquebráveis comuns nesta plataforma e consolidação do preço base localizando as classes CSS específicas de fracionamento de valores (inteiros e centavos).

### 4.6. Zé Delivery (`ze_delivery_scraper.py`)
* **Navegação Georreferenciada e Age Gate**: Resolução mandatória de bloqueios de maioridade e interação baseada em deslocamento de eixos (`ActionChains`) para contornar a validação do Google Places na definição de domicílio.
* **Extração Dinâmica em Menus**: Processamento veloz através de modais de sugestão de busca, localizando ativamente elementos estruturais para extrair o valor comercial correto.
* **Extração Dinâmica de Preços Mínimos**: Em casos de dualidade de valores (descontos aplicados e preço cortado), isola e capta apenas o valor comercial de face (`min()`) após descartar componentes como descontos percentuais.

## 5. Pipeline ETL (Camada Silver)

Após a extração bruta pela Camada Bronze, os dados passam por um processo de refinamento e consolidação no script `transformacao_silver.py`.
* **Deduplicação e Chave Surrogate**: Geração de um hash MD5 único para cada registro (combinando site, marca, termo de busca e data), impedindo a ingestão de dados duplicados no repositório final.
* **Conversão e Tipagem Forte**: Transformação dos dados em DataFrame do Pandas e exportação para formatos analíticos de alta compactação (Parquet via engine PyArrow) e leitura tabular (CSV).
* **Sincronização AWS S3**: Upload seguro e autenticado dos artefatos processados para o Amazon S3 (Data Lake) utilizando a biblioteca `boto3`.
* **Garbage Collection Condicional**: Rotina de limpeza que remove automaticamente os arquivos JSON temporários da pasta local após o sucesso na transformação e envio para a nuvem, mantendo o ambiente do contêiner leve e otimizado.

## 6. Algoritmo de Consistência de Dados (Motor Semântico)

A arquitetura estabelece purificação estrita de dados antes do salvamento, garantindo comparações homogêneas:
1. **Filtro Negativo de Variantes**: Recusa sumária de strings contendo expressões colidentes (ex: Diet, Zero, Light) caso não tenham sido explicitamente solicitadas na busca original.
2. **Validação Equivalentede Embalagens**: Discriminação binária entre embalagens metálicas (Lata) e plásticas (Pet).
3. **Validação de Identidade Nominal**: Verificação da presença obrigatória da marca e categoria limpa no título do anúncio para evitar captura de produtos paralelos, acessórios ou brindes.
4. **Comparação Matemática de Medidas**: Conversão semântica universal (ex: 2L para 2000ml, 1KG para 1000g) cruzando com a string base de pesquisa para isolar medidas unitárias, calculando o divisor exato de embalagens múltiplas.
5. **Bypass de Exceção de Padrão**: Lógica validatória para garantir a aderência de produtos mal formatados nas lojas (ex: Coca-Cola 2L Original), mantendo alta capilaridade de matches corretos.

## 7. Padronização e Manutenibilidade

Todos os componentes lógicos e saídas de terminal obedecem a práticas consolidadas de engenharia de software. A separação estrita de responsabilidades entre Camada Bronze (Scraping e Parsing), Camada Silver (ETL) e integração nativa com recursos de infraestrutura AWS (S3 e Variáveis de Ambiente) permite que o ecossistema seja modular, de fácil depuração e altamente escalável para integração de novos canais de mercado.