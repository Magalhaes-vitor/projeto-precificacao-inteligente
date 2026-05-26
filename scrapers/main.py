import os
import sys
import time
import logging
from datetime import datetime

# Adiciona o diretório atual ao path para garantir que os módulos sejam encontrados
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importação de todos os Scrapers da Camada Bronze
from amazon_scraper import AmazonScraper
from atacadao_scraper import AtacadaoScraper
from mercado_livre_scraper import MercadoLivreScraper
from pao_de_acucar_scraper import PaoDeAcucarScraper
from tenda_atacado_scraper import TendaAtacadoScraper
from ze_delivery_scraper import ZeDeliveryScraper

# Configuração de Logging Centralizado (Padrão Sênior)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - ORQUESTRADOR - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('Orquestrador')

def main():
    logger.info("[INFO] Iniciando Pipeline de Extracao (Camada Bronze)...")
    start_time = time.time()

    # Dicionário com as classes de scrapers disponíveis
    scrapers_disponiveis = [
        ("Amazon", AmazonScraper),
        ("Atacadao", AtacadaoScraper),
        ("Mercado Livre", MercadoLivreScraper),
        ("Pao de Acucar", PaoDeAcucarScraper),
        ("Tenda Atacado", TendaAtacadoScraper),
        ("Ze Delivery", ZeDeliveryScraper)
    ]

    resumo_execucao = []

    for nome, scraper_class in scrapers_disponiveis:
        logger.info(f"\n{'='*40}\n[INFO] Iniciando crawler: {nome}\n{'='*40}")
        try:
            scraper_instance = scraper_class()
            scraper_instance.extrair_dados()
            
            logger.info(f"[SUCESSO] Extracao de {nome} finalizada.")
            resumo_execucao.append(f"{nome}: SUCESSO")
            
        except Exception as e:
            logger.error(f"[ERRO] Falha critica irrecuperavel no scraper {nome}: {e}")
            resumo_execucao.append(f"{nome}: FALHOU")
        finally:
            time.sleep(3)

    end_time = time.time()
    duracao_minutos = round((end_time - start_time) / 60, 2)
    
    logger.info(f"\n{'='*40}\n[INFO] Resumo da Camada Bronze\n{'='*40}")
    for res in resumo_execucao:
        logger.info(res)
    logger.info(f"[INFO] Pipeline da Camada Bronze concluido em {duracao_minutos} minutos.")
    
    # ---------------------------------------------------------
    # ACIONAMENTO AUTOMATICO DA CAMADA SILVER
    # ---------------------------------------------------------
    logger.info("\n[INFO] Acionando a Camada Silver (Transformacao de Dados)...")
    try:
        from transformacao_silver import processar_camada_silver
        processar_camada_silver()
        logger.info("[SUCESSO] Pipeline completo executado com exito.")
    except Exception as e:
        logger.error(f"[ERRO] Falha ao executar a Camada Silver: {e}")

if __name__ == "__main__":
    main()