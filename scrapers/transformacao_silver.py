import os
import glob
import json
import hashlib
import logging
from datetime import datetime
import pandas as pd

# Configuração de Logging Centralizado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - CAMADA SILVER - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('SilverLayer')

def gerar_surrogate_key(row):
    """
    Gera um Hash MD5 (Chave Única) para cada registro.
    Isso impede que os mesmos dados sejam duplicados no Banco de Dados Analítico.
    """
    # A chave combina: Site + Marca + Termo Buscado + Data (YYYY-MM-DD)
    string_base = f"{row['site']}{row['marca']}{row['termo_buscado']}{str(row['data_extracao'])[:10]}"
    return hashlib.md5(string_base.encode('utf-8')).hexdigest()

def processar_camada_silver(diretorio_dados='data_samples'):
    logger.info("[INFO] Iniciando Processamento ETL (Extract, Transform, Load)...")
    
    # 1. EXTRACT: Varredura de todos os JSONs gerados pela Camada Bronze
    caminho_busca = os.path.join(diretorio_dados, '*_bronze_*.json')
    arquivos_json = glob.glob(caminho_busca)
    
    if not arquivos_json:
        logger.warning("[AVISO] Nenhum arquivo JSON da Camada Bronze encontrado.")
        return
        
    dados_consolidados = []
    for arquivo in arquivos_json:
        try:
            with open(arquivo, 'r', encoding='utf-8') as f:
                dados = json.load(f)
                dados_consolidados.extend(dados)
        except Exception as e:
            logger.error(f"[ERRO] Falha ao ler o arquivo {arquivo}: {e}")
    
    if not dados_consolidados:
        logger.warning("[AVISO] Nenhum dado valido extraido dos arquivos JSON.")
        return
        
    # 2. LOAD (In-Memory): Criacao do DataFrame Pandas
    df = pd.DataFrame(dados_consolidados)
    qtd_inicial = len(df)
    logger.info(f"[INFO] Total de registros brutos em memoria: {qtd_inicial}")
    
    # 3. TRANSFORM: Limpeza e Tipagem de Dados (Data Quality)
    logger.info("[INFO] Aplicando tipagem forte e qualidade de dados...")
    df['data_extracao'] = pd.to_datetime(df['data_extracao'])
    df['preco_unitario'] = df['preco_unitario'].astype(float)
    df['preco_total_anuncio'] = df['preco_total_anuncio'].astype(float)
    df['quantidade_embalagem'] = df['quantidade_embalagem'].astype(int)
    
    # Criacao de coluna de particao logica (Data Referencia)
    df['data_referencia'] = df['data_extracao'].dt.date
    
    # 4. TRANSFORM: Deduplicacao Logica (Upsert Simulation)
    # Ordenamos pela data exata descrescente para garantir que o mais recente do dia prevaleca
    df = df.sort_values(by=['data_referencia', 'site', 'marca', 'data_extracao'], ascending=[False, True, True, False])
    
    # Apaga duplicadas matendo a primeira ocorrencia (a mais recente por causa do sort acima)
    df = df.drop_duplicates(subset=['data_referencia', 'site', 'marca', 'termo_buscado'], keep='first')
    
    qtd_final = len(df)
    linhas_removidas = qtd_inicial - qtd_final
    logger.info(f"[INFO] Deduplicacao concluida. Registos removidos: {linhas_removidas}")
    logger.info(f"[INFO] Total de registros unicos validados: {qtd_final}")
    
    # 5. TRANSFORM: Surrogate Key
    df['sk_id'] = df.apply(gerar_surrogate_key, axis=1)
    
    # Reordenar as colunas para o padrao analitico do Data Warehouse
    colunas_finais = [
        'sk_id', 'data_referencia', 'data_extracao', 'site', 'categoria', 
        'marca', 'termo_buscado', 'titulo_anuncio', 'quantidade_embalagem', 
        'preco_total_anuncio', 'preco_unitario', 'link'
    ]
    df = df[colunas_finais]
    
    # 6. LOAD (Disk/S3 Ready): Exportacao Parquet e CSV particionado por dia
    data_hoje = datetime.now().strftime('%Y%m%d')
    caminho_parquet = os.path.join(diretorio_dados, f'dataset_silver_{data_hoje}.parquet')
    caminho_csv = os.path.join(diretorio_dados, f'dataset_silver_{data_hoje}.csv')
    
    try:
        # Exportacao Otimizada para AWS Athena
        df.to_parquet(caminho_parquet, index=False, engine='pyarrow', compression='snappy')
        # Exportacao Legivel para Testes Locais/Excel
        df.to_csv(caminho_csv, index=False, sep=';', encoding='utf-8-sig')
        
        logger.info(f"[SUCESSO] Camada Silver gerada com sucesso!")
        logger.info(f"   -> Parquet: {caminho_parquet}")
        logger.info(f"   -> CSV: {caminho_csv}")
        
        # 7. CLEANUP: Excluir os arquivos JSON da Camada Bronze apos processamento bem-sucedido
        logger.info("[INFO] Iniciando rotina de Garbage Collection (Remocao de arquivos RAW)...")
        removidos_com_sucesso = 0
        for arquivo in arquivos_json:
            try:
                os.remove(arquivo)
                removidos_com_sucesso += 1
            except Exception as e:
                logger.error(f"[ERRO] Falha ao tentar remover o arquivo {arquivo}: {e}")
        
        logger.info(f"[SUCESSO] Limpeza concluida. {removidos_com_sucesso} ficheiros JSON removidos da pasta data_samples.")
        
    except Exception as e:
        logger.error(f"[ERRO] Falha critica ao exportar a Camada Silver (os JSONs NAO foram apagados): {e}")

if __name__ == "__main__":
    processar_camada_silver()
