import os
import sys
import time
import logging
import platform
import subprocess
from datetime import datetime
import undetected_chromedriver as uc

# Adiciona o diretório atual ao path para garantir que os módulos sejam encontrados
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importação de todos os Scrapers da Camada Bronze
from amazon_scraper import AmazonScraper
from atacadao_scraper import AtacadaoScraper
from mercado_livre_scraper import MercadoLivreScraper
from pao_de_acucar_scraper import PaoDeAcucarScraper
from tenda_atacado_scraper import TendaAtacadoScraper
from ze_delivery_scraper import ZeDeliveryScraper

if __name__ == "__main__":
    # Configuração de Logging Centralizado
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - ORQUESTRADOR - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger('Orquestrador')

# SILENCIADOR DO UNDETECTED CHROMEDRIVER (Evita o WinError 6 no final do log)
_original_del = uc.Chrome.__del__

def _silenced_del(self):
    try:
        _original_del(self)
    except Exception:
        pass # Ignora silenciosamente qualquer erro de processo fantasma

uc.Chrome.__del__ = _silenced_del

def main():
    logger.info("[INFO] Iniciando Pipeline de Extracao (Camada Bronze)...")
    start_time = time.time()

    # Dicionário com as classes de scrapers disponíveis
    # ==============================================================================
    # AVISO: MERCADO LIVRE EM QUARENTENA NA AWS
    # O Mercado Livre possui proteção severa (Akamai) contra IPs de Data Centers (AWS).
    # Para ativar este scraper na nuvem, é OBRIGATÓRIO o uso de um Proxy Residencial.
    # Consulte o documentacao_scrapers.md e o cabeçalho de mercado_livre_scraper.py para instruções.
    # ==============================================================================

    scrapers_disponiveis = [
        ("Amazon", AmazonScraper),
        ("Atacadao", AtacadaoScraper),
        ("Pao de Acucar", PaoDeAcucarScraper),
        ("Tenda Atacado", TendaAtacadoScraper),
        ("Ze Delivery", ZeDeliveryScraper),
        #("Mercado Livre", MercadoLivreScraper)
    ]

    resumo_execucao = []

    def limpar_navegador():
        '''Mata qualquer processo fantasma do Chrome que possa estar a travar as portas.'''
        try:
            if platform.system() == "Windows":
                # Comando para Windows (silencioso para não poluir o terminal)
                subprocess.call("taskkill /F /IM chrome.exe /T >nul 2>&1", shell=True)
                subprocess.call("taskkill /F /IM chromedriver.exe /T >nul 2>&1", shell=True)
            else:
                # Comando para Linux/AWS
                subprocess.call("pkill -9 -f chrome", shell=True)
                subprocess.call("pkill -9 -f chromedriver", shell=True)
            time.sleep(2) # Dá tempo ao SO para limpar a memória
        except Exception:
            pass

        
    for nome, scraper_class in scrapers_disponiveis:
        logger.info(f"\n{'='*40}\n[INFO] Iniciando crawler: {nome}\n{'='*40}")
        try:
            limpar_navegador()
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