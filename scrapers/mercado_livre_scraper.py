import time
from datetime import datetime

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.edge.options import Options

from base_scraper import BaseScraper


class MercadoLivreScraper(BaseScraper):
    """
    Scraper especializado no Mercado Livre.
    Utiliza Edge visível para contornar proteções Akamai Anti-bot.
    """

    def __init__(self):
        super().__init__('MercadoLivre')
        self.driver = self._configurar_driver()

    def _configurar_driver(self):
        """Configura e inicializa o motor do Edge."""
        edge_options = Options()
        edge_options.add_argument("--disable-gpu")
        edge_options.add_argument("--window-size=1920,1080")
        
        # Oculta rastros de automação
        edge_options.add_argument("--disable-blink-features=AutomationControlled")
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        edge_options.add_experimental_option('useAutomationExtension', False)
        
        self.logger.info("Inicializando o motor do Edge (ML)...")
        driver = webdriver.Edge(options=edge_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver

    def extrair_dados(self):
        produtos = self.carregar_produtos_alvo()
        
        if not produtos:
            self.logger.warning("A lista de produtos está vazia.")
            if self.driver: self.driver.quit()
            return

        for produto in produtos:
            termo_formatado = produto['termo_busca'].replace(' ', '-')
            url = f"https://lista.mercadolivre.com.br/{termo_formatado}"
            
            self.logger.info(f"Processando extração para: {produto['termo_busca']}")
            
            try:
                self.driver.get(url)
                time.sleep(5) # Aguarda renderização do JavaScript e bypass
                
                html_renderizado = self.driver.page_source
                soup = BeautifulSoup(html_renderizado, 'html.parser')

                # Suporte aos layouts antigo (list) e novo (poly-card)
                anuncios = soup.find_all('li', class_='ui-search-layout__item')
                if not anuncios: 
                    anuncios = soup.find_all('div', class_=lambda c: c and 'poly-card' in c)
                    
                if not anuncios:
                    self.logger.warning(f"Sem anúncios localizados para {produto['termo_busca']}.")
                    continue

                encontrados = 0
                for anuncio in anuncios:
                    if encontrados >= 2:
                        break
                        
                    link_elem = anuncio.find('a', href=True)
                    titulo_elem = anuncio.find('h2') or anuncio.find('h3') or (link_elem if link_elem else None)
                    preco_elem = anuncio.find('span', class_='andes-money-amount__fraction')
                    
                    if titulo_elem and preco_elem and link_elem:
                        titulo = titulo_elem.text.strip()
                        if not titulo: 
                            titulo = link_elem.text.strip()
                            
                        preco_texto = preco_elem.text.replace('.', '')
                        preco_float = float(preco_texto) if preco_texto else 0.0
                        
                        # UTILIZAÇÃO DA REGEX DA CLASSE MÃE
                        dados_preco = self.normalizar_preco(titulo, preco_float)
                        link = link_elem['href']
                        
                        self.dados_extraidos.append({
                            "data_extracao": datetime.now().isoformat(),
                            "site": self.nome_site,
                            "categoria": produto['categoria'],
                            "marca": produto['marca'],
                            "termo_buscado": produto['termo_busca'],
                            "titulo_anuncio": titulo,
                            "quantidade_embalagem": dados_preco["quantidade_embalagem"],
                            "preco_total_anuncio": dados_preco["preco_total_anuncio"],
                            "preco_unitario": dados_preco["preco_unitario"],
                            "link": link
                        })
                        encontrados += 1
                        self.logger.info(f"✅ Extraído: {titulo[:30]}... | Unitário: R${dados_preco['preco_unitario']}")
            
            except Exception as e:
                self.logger.error(f"Falha inesperada durante a automação de {produto['termo_busca']}: {e}")
        
        self.salvar_dados()
        if self.driver: 
            self.driver.quit()

if __name__ == "__main__":
    scraper = MercadoLivreScraper()
    scraper.extrair_dados()