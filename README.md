# Inteligência Competitiva e Precificação para Varejo 📊🚀

Este projeto faz parte da iniciativa **#BuildInPublic**, onde documento a construção de um pipeline de dados ponta a ponta (End-to-End) focado no setor de bebidas/conveniência.

O objetivo é automatizar a coleta de preços de mercado, processar esses dados em nuvem e gerar insights estratégicos para tomada de decisão em precificação.

## 🏗️ Arquitetura do Projeto
O pipeline foi desenhado seguindo as melhores práticas de Engenharia de Dados:

1.  **Extração (RPA/Python):** Scripts automatizados para coleta de preços em marketplaces e e-commerces.
2.  **Ingestão (Data Lake):** Armazenamento de dados brutos (Raw Data) em **Amazon S3 (Camada Bronze)**.
3.  **Processamento (ETL):** Utilização de **AWS Glue** para limpeza, normalização e tipagem dos dados.
4.  **Data Warehouse (Query Engine):** Camada de dados prontos para análise consumidos via **AWS Athena (SQL)**.
5.  **BI & Analytics:** Dashboard interativo no **Power BI** para monitoramento de competitividade.

## 🛠️ Tecnologias Utilizadas
* **Linguagem:** Python 3.x (Bibliotecas: Selenium, Pandas, Boto3)
* **Cloud (AWS):** S3, Glue, Athena, EventBridge
* **Banco de Dados:** SQL (Athena/Presto)
* **Visualização:** Microsoft Power BI

## 🚀 Como o projeto está organizado
* `/scrapers`: Contém a lógica de automação e captura de dados.
* `/aws`: Scripts de criação de tabelas e transformações ETL.
* `/bi`: Relatórios e métricas de desempenho.

## 📈 Status do Projeto
- [x] Definição da Arquitetura
- [x] Desenvolvimento do Scraper 
- [ ] Configuração do ambiente AWS (Em andamento)
- [ ] Construção do Dashboard

---
**Desenvolvido por [Vitor de Toledo Magalhães](https://www.linkedin.com/in/magalhaes-vitor/)**
