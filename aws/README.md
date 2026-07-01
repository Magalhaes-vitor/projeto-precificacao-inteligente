# Documentacao Tecnica: Pipeline de Inteligencia de Precos (AWS Serverless)

Este documento descreve as configuracoes exatas e o passo a passo da infraestrutura provisionada na AWS para suportar a extracao, transformacao e disponibilizacao de dados de precificacao de supermercados, utilizando uma abordagem 100% Serverless e focada em FinOps.

graph TD
    subgraph Local [Ambiente Local / Desenvolvimento]
        A[Terminal: Executar main.py] --> B[Chrome Local: Scraping]
        B --> C[Salvar JSON: Camada Bronze]
        C --> D[Pandas: Limpeza e Deduplicação]
        D --> E[Armazenamento: data_samples/parquet/]
    end

    subgraph AWS [Ambiente Nuvem / Produção Serverless]
        F[Amazon EventBridge: Cron 04:00 AM] --> G[AWS ECS Fargate: Contêiner Docker]
        G --> H[Extração e Transformação Python]
        H --> I[Amazon S3: Data Lake / Parquet]
        I --> J[AWS Glue: Catalogação de Dados]
        J --> K[Amazon Athena: Camada SQL]
        K --> L[Power BI: Dashboard e KPIs]
    end

    %% Estilos de Cor para a Nuvem AWS e Power BI
    style F fill:#ff9900,stroke:#232f3e,stroke-width:2px,color:#fff
    style I fill:#3b48cc,stroke:#232f3e,stroke-width:2px,color:#fff
    style K fill:#ff9900,stroke:#232f3e,stroke-width:2px,color:#fff
    style L fill:#f2c811,stroke:#000,stroke-width:2px,color:#000

## Fase 1: Seguranca e Data Lake (IAM e S3)

O alicerce do projeto garante que os dados tenham um local seguro para armazenamento e que os servicos tenham permissao estrita para interagir entre si.

**1. Criacao do Usuario de Servico (AWS IAM)**
* **Nome do Usuario:** robo-etl-silver
* **Tipo de Acesso:** Acesso programatico (Access Key ID e Secret Access Key)
* **Politica de Permissao Anexada:** AmazonS3FullAccess (Garante que o script Python consiga ler e gravar arquivos no bucket)

**2. Provisionamento do Data Lake (Amazon S3)**
* **Nome do Bucket:** datalake-precificacao-magalhaes-vitor
* **Regiao:** us-east-2 (Ohio)
* **Estrutura de Pastas:** `/silver/parquet/` para o destino final analitico, `/silver/csv/` para backup legivel por humanos e `/athena-results/` para o armazenamento de cache de consultas SQL do Athena.

---

## Fase 2: Conteinerizacao (Docker e ECR)

Para garantir que o Undetected Chromedriver e o Selenium rodem sem erros de compatibilidade de sistema operacional, a aplicacao foi empacotada em uma imagem Docker baseada em Linux.

**1. Configuracao do Repositorio**
* **Servico:** Amazon Elastic Container Registry (ECR)
* **Nome do Repositorio:** robo-precificacao
* **Visibilidade:** Privado

**2. Comandos de Implantacao (CLI)**
* **Autenticacao:** `aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin [ID_DA_CONTA].dkr.ecr.us-east-2.amazonaws.com`
* **Build:** `docker build -t robo-precificacao .`
* **Tag:** `docker tag robo-precificacao:latest [URI_DO_ECR]:latest`
* **Push:** `docker push [URI_DO_ECR]:latest`

---

## Fase 3: Poder Computacional (ECS Fargate)

O conteiner e executado sem instancias EC2, garantindo que o custo (US$ 0,02 a US$ 0,05 por execucao) ocorra estritamente durante os minutos de processamento.

**1. Definicao de Tarefa (Task Definition)**
* **Nome da Tarefa:** robo-precificacao-task
* **Tipo de Inicializacao:** AWS Fargate
* **Sistema Operacional:** Linux/X86_64
* **Recursos Alocados:** 1 vCPU e 3 GB de RAM (Obrigatorio para evitar travamentos de memoria do Google Chrome em modo Headless)
* **URI da Imagem:** Aponta para a tag latest do ECR

**2. Variaveis de Ambiente Injetadas no Conteiner**
* **AWS_S3_BUCKET:** datalake-precificacao-magalhaes-vitor
* **AWS_ACCESS_KEY_ID:** Preenchido com a chave do usuario robo-etl-silver
* **AWS_SECRET_ACCESS_KEY:** Preenchido com o segredo do usuario robo-etl-silver

---

## Fase 4: Orquestracao e Agendamento (EventBridge)

O disparo da tarefa ocorre de forma autonoma para garantir que os analistas tenham os dados prontos no inicio do expediente.

**1. Configuracao da Regra**
* **Nome da Regra:** cron-robo-precificacao-diario
* **Padrao de Agendamento (Cron):** `0 7 * * ? *` (Equivalente as 04h00 da manha no horario de Sao Paulo UTC-3)

**2. Configuracao de Rede (Web Scraping)**
* **Target:** API do ECS (RunTask)
* **Task Definition:** robo-precificacao-task
* **Subnets:** Selecionadas sub-redes publicas da VPC Padrao para viabilizar a navegacao externa
* **Auto-assign public IP:** ENABLED (Garante que o conteiner obtenha acesso a internet para realizar a raspagem de dados)

---

## Fase 5: Catalogo e Consulta SQL (AWS Glue e Athena)

Os dados salvos no S3 em formato `.parquet` sao mapeados para tabelas relacionais virtuais.

**1. Mapeamento de Esquema (AWS Glue)**
* **Database:** db_precificacao
* **Crawler:** crawler_silver_precificacao
* **Data Source (S3 Path):** `s3://datalake-precificacao-magalhaes-vitor/silver/parquet/`
* **Comportamento:** Ao rodar, o Crawler identifica automaticamente as colunas e unifica todos os arquivos diarios em uma unica tabela historica chamada tb_parquet.

**2. Camada de Abstracao SQL (Amazon Athena)**
* **Configuracao Previa:** O local de saida das consultas foi configurado para a pasta `/athena-results/` no Data Lake.
* **Validacao de Integridade:** Confirmada executando a query `SELECT * FROM db_precificacao.tb_parquet ORDER BY data_extracao DESC;`

---

## Fase 6: Camada de Visualizacao (Power BI via ODBC)

A conexao entre o ambiente local e a AWS utiliza um canal direto com o motor do Athena para consumo dos dados.

**1. Configuracao do Driver**
* **Software:** Instalacao do Simba Athena ODBC Driver (64-bit) para Windows
* **Criacao do DSN de Sistema:** Nomeado como AWSPrecificacao
* **Parametros do DSN:** A regiao (Aws Region) e definida como us-east-2, o local de saida (S3 Output Location) e apontado para a pasta de cache do Athena, e a autenticacao (Authentication) e feita via IAM Credentials utilizando as chaves de acesso.

**2. Importacao no Power BI**
* **Fonte de Dados:** ODBC utilizando o DSN AWSPrecificacao
* **Navegacao:** AwsDataCatalog > db_precificacao > tb_parquet
* **Modo de Conectividade:** Dados importados diretamente da nuvem para a construcao de visuais e medidas DAX (Ex: Variacao de Preco, Menor Preco Atual).