import json
import logging
import os
import re
from abc import ABC, abstractmethod
from datetime import datetime

class BaseScraper(ABC):
    """
    Classe base abstrata para todos os scrapers de e-commerce.
    Define o contrato de extração, métodos utilitários de log, 
    persistência de dados e normalização analítica (Regex).
    """

    def __init__(self, nome_site: str):
        self.nome_site = nome_site
        self.dados_extraidos = []
        self._configurar_logger()

    def _configurar_logger(self):
        """Configura o sistema de logs padronizado para o terminal."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(self.nome_site)

    def carregar_produtos_alvo(self, caminho_arquivo: str = 'scrapers/config_produtos.json') -> list:
        """Lê o arquivo de configuração e retorna a lista de produtos alvo."""
        try:
            with open(caminho_arquivo, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.error(f"Arquivo de configuração não encontrado: {caminho_arquivo}")
            return []

    def normalizar_preco(self, titulo_anuncio: str, preco_total: float) -> dict:
        """
        Analisa o título do anúncio usando Expressões Regulares (Regex) para identificar 
        packs, fardos e caixas. Retorna a quantidade de itens e o preço unitário real.
        """
        titulo_lower = titulo_anuncio.lower()
        quantidade = 1

        # Padrões comuns em e-commerces (ex: "Pack com 12", "Fardo 24", "12 latas")
        padroes = [
            r'pack.*?(?:de|com)?\s*(\d+)',       
            r'caixa.*?(?:de|com)?\s*(\d+)',      
            r'fardo.*?(?:de|com)?\s*(\d+)',      
            r'kit.*?(?:de|com)?\s*(\d+)',        
            r'(\d+)\s*(?:unidades|latas|garrafas|und|un)' 
        ]

        for padrao in padroes:
            match = re.search(padrao, titulo_lower)
            if match:
                qtd_encontrada = int(match.group(1))
                # Filtro de sanidade: ignora números muito altos (ex: "Lata 350ml")
                if 1 < qtd_encontrada <= 100: 
                    quantidade = qtd_encontrada
                    break

        # Evita divisão por zero e formata com 2 casas decimais
        preco_unitario = round(preco_total / quantidade, 2) if quantidade > 0 else preco_total

        return {
            "quantidade_embalagem": quantidade,
            "preco_total_anuncio": preco_total,
            "preco_unitario": preco_unitario
        }

    @abstractmethod
    def extrair_dados(self):
        """Método obrigatório. Toda classe filha deve implementar a sua lógica de raspagem aqui."""
        pass

    def salvar_dados(self):
        """Persiste os dados extraídos em formato JSON local (Camada Bronze)."""
        if not self.dados_extraidos:
            self.logger.warning("Nenhum dado extraído para salvar.")
            return

        os.makedirs('data_samples', exist_ok=True)
        
        data_atual = datetime.now().strftime('%Y%m%d_%H%M%S')
        nome_arquivo = f"data_samples/{self.nome_site}_bronze_{data_atual}.json"

        with open(nome_arquivo, 'w', encoding='utf-8') as f:
            json.dump(self.dados_extraidos, f, ensure_ascii=False, indent=4)
        
        self.logger.info(f"Dados salvos com sucesso na camada bronze: {nome_arquivo}")