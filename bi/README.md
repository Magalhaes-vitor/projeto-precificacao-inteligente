# Dashboard de Inteligência de Preços (Power BI)

Este diretório contém a camada de visualização e análise (BI) do pipeline de Engenharia de Dados. O objetivo deste painel é transformar os dados brutos extraídos diariamente de supermercados e atacadistas num motor estratégico de compras, garantindo a melhor margem de lucro no reabastecimento de stock da Adega Four Seasons em São Paulo.

> ** Nota de Acesso:** Este projeto foi desenvolvido na versão Desktop. Para interagir com o dashboard, faça o download do ficheiro `precificacao_dashboard.pbix` incluído nesta pasta e abra-o no seu Power BI Desktop. Para visualizar o layout e as métricas sem abrir o Power BI, consulte o documento PDF em anexo.

---

## Documentação Visual (PDF)

O design corporativo, os gráficos interativos e a estrutura de tomada de decisão deste dashboard estão devidamente documentados no arquivo PDF anexado a este repositório. 

* **[Abrir pipeline_de_dados.pdf](./pipeline_de_dados.pdf)**

---

## Arquitetura e Conectividade

O dashboard consome dados diretamente da nossa infraestrutura Serverless na nuvem AWS, conectando-se ao Data Lake através do motor de consultas Athena.

* **Fonte de Dados:** Amazon Athena (lendo arquivos `.parquet` armazenados no Amazon S3).
* **Conector:** Simba Athena ODBC Driver (64-bit).
* **Autenticação:** IAM Credentials (via AWS) com políticas estritas de leitura (`AmazonAthenaFullAccess` e `AWSGlueConsoleFullAccess`).
* **Governança de Dados (Power Query):** * Dados de *marketplaces* abertos (como o Mercado Livre) foram bloqueados e filtrados via linguagem `M` na raiz da importação. Esta decisão arquitetural previne a contaminação da métrica de Preço Médio por anúncios fora do padrão, garantindo a integridade dos KPIs.

---

##  Modelagem de Dados (Star Schema)

O modelo foi projetado para alta performance analítica e inteligência de tempo (Time Intelligence).

1. **Tabela Fato (`tb_parquet`):** Consolida o histórico completo das extrações da Camada Silver, contendo dados como marca, preço unitário, datas e links diretos para os anúncios.
2. **Tabela Dimensão (`Dim_Calendario`):** Gerada dinamicamente via **DAX** a partir da Fato. Responsável por suportar os filtros temporais e os cálculos de variação (Day-over-Day e Month-over-Month).

---

##  Lógica de Negócio e Medidas DAX

A inteligência competitiva foi traduzida em fórmulas DAX para detetar oportunidades de compra em tempo real:

* **Oportunidade de Compra (Menor Preço):**
  Acompanha o valor mínimo absoluto encontrado no mercado no período selecionado.
  ```dax
  Menor Preço = MIN(tb_parquet[preco_unitario])
  ```

* **Termômetro do Mercado (Preço Médio):**
  Estabelece a linha de base para avaliar se um fornecedor está a cobrar acima ou abaixo do padrão.
  ```dax
  Preço Médio = AVERAGE(tb_parquet[preco_unitario])
  ```

* **Variação Diária (Day-over-Day):**
  Identifica a flutuação percentual da inflação de um dia para o outro.
  ```dax
  Variação Preço DoD = 
  VAR PrecoAtual = [Preço Médio]
  VAR PrecoOntem = CALCULATE([Preço Médio], DATEADD(Dim_Calendario[Date], -1, DAY))
  RETURN
  DIVIDE(PrecoAtual - PrecoOntem, PrecoOntem, 0)
  ```

---

## 📱 Estrutura do Relatório

O painel foi desenhado com um layout claro e pragmático, dividido em duas frentes táticas:

### 1. Visão Geral e Concorrência (Operacional)
Focada na tomada de decisão em segundos.
* **KPIs no Topo:** Leitura imediata do menor preço, preço médio e variação percentual.
* **Matriz de Decisão (Heatmap):** Cruzamento de `Marcas x Fornecedores` com formatação condicional (verde para o menor preço, vermelho para o maior).
* **Call-to-Action:** Links configurados como "URL da Web", permitindo clicar no ícone do dashboard e ser direcionado para a página de checkout do atacadista vencedor.

### 2. Evolução Temporal (Analítico)
Focada em auditoria e tendências de longo prazo.
* **Volatilidade de Preços:** Gráficos de linha que mapeiam o histórico de cada concorrente, permitindo prever padrões de promoções de fim de semana.
* **Monitoramento de Saúde da Coleta:** Gráfico de área demonstrando o volume diário de anúncios capturados, funcionando como auditoria contra falhas ou bloqueios anti-bot na nuvem.

---

##  Como Executar Localmente

1. Clone este repositório.
2. Certifique-se de que possui o **Power BI Desktop** instalado.
3. Instale o driver **Simba Athena ODBC** e configure o DSN local apontando para o seu catálogo AWS.
4. Abra o arquivo `.pbix` localizado nesta pasta.
5. Em caso de solicitação de credenciais, utilize a aba "Padrão ou Personalizado".
