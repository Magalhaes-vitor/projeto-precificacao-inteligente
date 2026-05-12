import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
import os

class BaseScraper(ABC):
    """
    Classe base abstrata para todos os scrapers de e-commerce.
    Define o contrato e métodos utilitários comuns.
    """

    def __init__(self, nome_site: str):
        self.nome_site = nome_site
        self.dados_extraidos = []
        self._configurar_logger()

    def _configurar_logger(self):
        """Configura o sistema de logs para o terminal."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(self.nome_site)

    def carregar_produtos_alvo(self, caminho_arquivo: str = 'scrapers/config_produtos.json') -> list:
        """Carrega a lista de produtos a serem buscados."""
        try:
            with open(caminho_arquivo, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.error(f"Arquivo de configuração não encontrado: {caminho_arquivo}")
            return []

    @abstractmethod
    def extrair_dados(self):
        """
        Método obrigatório. Toda classe filha (ex: MercadoLivreScraper) 
        deve implementar a sua própria lógica de raspagem aqui.
        """
        pass

    def salvar_dados(self):
        """Salva a lista de dados extraídos em um arquivo JSON local na camada Bronze."""
        if not self.dados_extraidos:
            self.logger.warning("Nenhum dado para salvar.")
            return

        # Cria a pasta caso não exista
        os.makedirs('data_samples', exist_ok=True)
        
        data_atual = datetime.now().strftime('%Y%m%d_%H%M%S')
        nome_arquivo = f"data_samples/{self.nome_site}_bronze_{data_atual}.json"

        with open(nome_arquivo, 'w', encoding='utf-8') as f:
            json.dump(self.dados_extraidos, f, ensure_ascii=False, indent=4)
        
        self.logger.info(f"Dados salvos com sucesso em: {nome_arquivo}")