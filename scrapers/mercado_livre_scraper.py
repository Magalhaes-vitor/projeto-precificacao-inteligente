import time
from datetime import datetime

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.edge.options import Options

from base_scraper import BaseScraper


class MercadoLivreScraper(BaseScraper):
    """
    Scraper especializado na extração de dados do Mercado Livre.
    Utiliza Selenium com Edge nativo para contornar proteções anti-bot (Akamai/Captcha)
    e BeautifulSoup para parsing eficiente do HTML renderizado.
    """

    def __init__(self):
        super().__init__('MercadoLivre')
        self.driver = self._configurar_driver()

    def _configurar_driver(self):
        """
        Configura e inicializa o navegador Microsoft Edge controlado via automação.
        
        Nota: O Mercado Livre bloqueia ativamente requisições em modo 
        Headless (invisível). Portanto, o navegador deve rodar em modo gráfico (visível)
        junto com flags anti-detecção para garantir a extração com sucesso.
        """
        edge_options = Options()
        
        # Desativado propositalmente devido ao bloqueio severo de anti-bot do ML
        # edge_options.add_argument("--headless=new") 
        
        edge_options.add_argument("--disable-gpu")
        edge_options.add_argument("--window-size=1920,1080")
        
        # Flags para mitigar a detecção do Selenium pelos sistemas de segurança do site
        edge_options.add_argument("--disable-blink-features=AutomationControlled")
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        edge_options.add_experimental_option('useAutomationExtension', False)
        
        self.logger.info("Inicializando o motor do Edge (Modo Visível para bypass de segurança)...")
        
        driver = webdriver.Edge(options=edge_options)
        
        # Oculta a variável nativa 'webdriver' do JavaScript do navegador
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver

    def extrair_dados(self):
        """
        Método principal que itera sobre a lista de produtos, acessa as URLs alvo,
        aguarda a renderização do JavaScript e extrai os títulos, links e preços.
        """
        produtos = self.carregar_produtos_alvo()
        
        if not produtos:
            self.logger.warning("A lista de produtos em config_produtos.json está vazia ou ausente.")
            if self.driver: 
                self.driver.quit()
            return

        for produto in produtos:
            # O Mercado Livre utiliza URLs com hífens no lugar de espaços
            termo_formatado = produto['termo_busca'].replace(' ', '-')
            url = f"https://lista.mercadolivre.com.br/{termo_formatado}"
            
            self.logger.info(f"Processando extração para: {produto['termo_busca']}")
            
            try:
                self.driver.get(url)
                
                # Pausa estratégica (5s) para garantir o processamento do JavaScript 
                # e o carregamento total do DOM após o bypass do anti-bot
                time.sleep(5) 
                
                # Repassa o HTML final renderizado para o BeautifulSoup processar mais rápido
                html_renderizado = self.driver.page_source
                soup = BeautifulSoup(html_renderizado, 'html.parser')

                # Tenta localizar o container padrão de anúncios, com fallback para o novo layout 'poly-card'
                anuncios = soup.find_all('li', class_='ui-search-layout__item')
                if not anuncios: 
                    anuncios = soup.find_all('div', class_=lambda c: c and 'poly-card' in c)
                    
                if not anuncios:
                    self.logger.warning(f"Sem anúncios localizados para {produto['termo_busca']}. O layout pode ter mudado.")
                    # Em caso de falha, salva um print visual para facilitar o debug
                    self.driver.save_screenshot(f"debug_tela_{produto['marca']}.png")
                    continue

                encontrados = 0
                for anuncio in anuncios:
                    # Limita a extração aos 2 primeiros anúncios relevantes (orgânicos/patrocinados)
                    if encontrados >= 2:
                        break
                        
                    # Mapeamento dinâmico dos elementos HTML
                    link_elem = anuncio.find('a', href=True)
                    titulo_elem = anuncio.find('h2') or anuncio.find('h3') or (link_elem if link_elem else None)
                    preco_elem = anuncio.find('span', class_='andes-money-amount__fraction')
                    
                    if titulo_elem and preco_elem and link_elem:
                        # Limpeza e tratamento dos dados brutos
                        titulo = titulo_elem.text.strip()
                        if not titulo: 
                            titulo = link_elem.text.strip()
                            
                        # Converte string monetária (ex: 1.200) para padrão aceito em banco de dados
                        preco_texto = preco_elem.text.replace('.', '')
                        link = link_elem['href']
                        
                        # Constrói o dicionário de saída (Camada Bronze)
                        self.dados_extraidos.append({
                            "data_extracao": datetime.now().isoformat(),
                            "site": self.nome_site,
                            "categoria": produto['categoria'],
                            "marca": produto['marca'],
                            "termo_buscado": produto['termo_busca'],
                            "titulo_anuncio": titulo,
                            "preco_extraido": float(preco_texto),
                            "link": link
                        })
                        encontrados += 1
                        self.logger.info(f"✅ Sucesso: {titulo[:30]}... - R${preco_texto}")
                    else:
                        # Rotina de Debug: Salva o bloco HTML específico caso as tags CSS tenham sido alteradas
                        if encontrados == 0: 
                            with open(f"debug_card_{produto['marca']}.html", "w", encoding="utf-8") as f:
                                f.write(anuncio.prettify())
                            self.logger.warning(f"Alerta de Estrutura! HTML do card salvo em debug_card_{produto['marca']}.html")
            
            except Exception as e:
                self.logger.error(f"Falha inesperada durante a automação de {produto['termo_busca']}: {e}")
        
        # Persiste os dados extraídos localmente
        self.salvar_dados()
        
        # Encerra o processo do navegador para liberar memória RAM
        if self.driver: 
            self.driver.quit()


# Bloco de execução isolada
if __name__ == "__main__":
    scraper = MercadoLivreScraper()
    scraper.extrair_dados()