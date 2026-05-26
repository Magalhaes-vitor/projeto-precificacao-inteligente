import os
import glob
import json
import hashlib
import logging
from datetime import datetime
import pandas as pd
import boto3
from botocore.exceptions import NoCredentialsError, ClientError

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
    string_base = f"{row['site']}{row['marca']}{row['termo_buscado']}{str(row['data_extracao'])[:10]}"
    return hashlib.md5(string_base.encode('utf-8')).hexdigest()

def upload_para_s3(caminho_arquivo, nome_arquivo_s3):
    """
    Faz o upload de um ficheiro local para o Amazon S3 de forma segura.
    As credenciais e o nome do bucket são obtidos através de variáveis de ambiente.
    """
    bucket_name = os.environ.get('AWS_S3_BUCKET')
    
    if not bucket_name:
        logger.warning("[AVISO] A variável AWS_S3_BUCKET não está definida. O upload para a nuvem será ignorado e os ficheiros mantidos localmente.")
        return False

    try:
        # O boto3 deteta automaticamente as chaves de acesso no ambiente (Access Key e Secret Key)
        s3_client = boto3.client('s3')
        s3_client.upload_file(caminho_arquivo, bucket_name, nome_arquivo_s3)
        logger.info(f"[SUCESSO] Ficheiro sincronizado com o Amazon S3: s3://{bucket_name}/{nome_arquivo_s3}")
        return True
    except NoCredentialsError:
        logger.error("[ERRO] Credenciais da AWS não encontradas. Verifique se as variáveis AWS_ACCESS_KEY_ID e AWS_SECRET_ACCESS_KEY estão configuradas.")
        return False
    except ClientError as e:
        logger.error(f"[ERRO] Falha de comunicação com a AWS: {e}")
        return False

def processar_camada_silver(diretorio_dados='data_samples'):
    logger.info("[INFO] Iniciando Processamento ETL (Extract, Transform, Load)...")
    
    # 1. EXTRACT
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
        logger.warning("[AVISO] Nenhum dado válido extraído dos arquivos JSON.")
        return
        
    # 2. LOAD (In-Memory)
    df = pd.DataFrame(dados_consolidados)
    qtd_inicial = len(df)
    logger.info(f"[INFO] Total de registros brutos em memória: {qtd_inicial}")
    
    # 3. TRANSFORM (Tipagem)
    logger.info("[INFO] Aplicando tipagem forte e qualidade de dados...")
    df['data_extracao'] = pd.to_datetime(df['data_extracao'])
    df['preco_unitario'] = df['preco_unitario'].astype(float)
    df['preco_total_anuncio'] = df['preco_total_anuncio'].astype(float)
    df['quantidade_embalagem'] = df['quantidade_embalagem'].astype(int)
    df['data_referencia'] = df['data_extracao'].dt.date
    
    # 4. TRANSFORM (Deduplicação)
    df = df.sort_values(by=['data_referencia', 'site', 'marca', 'data_extracao'], ascending=[False, True, True, False])
    df = df.drop_duplicates(subset=['data_referencia', 'site', 'marca', 'termo_buscado'], keep='first')
    
    qtd_final = len(df)
    linhas_removidas = qtd_inicial - qtd_final
    logger.info(f"[INFO] Deduplicação concluída. Registos removidos: {linhas_removidas}")
    logger.info(f"[INFO] Total de registros únicos validados: {qtd_final}")
    
    # 5. TRANSFORM (Surrogate Key)
    df['sk_id'] = df.apply(gerar_surrogate_key, axis=1)
    colunas_finais = [
        'sk_id', 'data_referencia', 'data_extracao', 'site', 'categoria', 
        'marca', 'termo_buscado', 'titulo_anuncio', 'quantidade_embalagem', 
        'preco_total_anuncio', 'preco_unitario', 'link'
    ]
    df = df[colunas_finais]
    
    # 6. LOAD (Local Disk e AWS S3)
    data_hoje = datetime.now().strftime('%Y%m%d')
    caminho_parquet = os.path.join(diretorio_dados, f'dataset_silver_{data_hoje}.parquet')
    caminho_csv = os.path.join(diretorio_dados, f'dataset_silver_{data_hoje}.csv')
    
    try:
        # Gravação Local
        df.to_parquet(caminho_parquet, index=False, engine='pyarrow', compression='snappy')
        df.to_csv(caminho_csv, index=False, sep=';', encoding='utf-8-sig')
        logger.info("[SUCESSO] Camada Silver gerada com sucesso localmente!")
        
        # Sincronização com AWS S3
        nome_s3_parquet = f"silver/dataset_silver_{data_hoje}.parquet"
        nome_s3_csv = f"silver/dataset_silver_{data_hoje}.csv"
        
        logger.info("[INFO] A iniciar sincronização com o Amazon S3...")
        upload_pq = upload_para_s3(caminho_parquet, nome_s3_parquet)
        upload_csv = upload_para_s3(caminho_csv, nome_s3_csv)
        
        # 7. CLEANUP: Garbage Collection Condicional
        # Apenas remove os ficheiros brutos se a geração local correu bem. 
        # (Em produção restrita, a remoção poderia estar condicionada também ao sucesso do S3)
        logger.info("[INFO] Iniciando rotina de Garbage Collection (Remoção de arquivos RAW)...")
        removidos = 0
        for arquivo in arquivos_json:
            try:
                os.remove(arquivo)
                removidos += 1
            except Exception as e:
                pass
        logger.info(f"[SUCESSO] Limpeza concluída. {removidos} ficheiros JSON removidos da pasta data_samples.")
        
    except Exception as e:
        logger.error(f"[ERRO] Falha crítica ao exportar a Camada Silver: {e}")

if __name__ == "__main__":
    processar_camada_silver()
    