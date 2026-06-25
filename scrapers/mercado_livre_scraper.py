"""
=========================================================================================
MERCADO LIVRE SCRAPER - DOCUMENTAÇÃO DE INFRAESTRUTURA
=========================================================================================
Este scraper utiliza o Undetected Chromedriver com spoofing de User-Agent.

STATUS: 
Inativo no pipeline principal da AWS (Comentado no main.py).

MOTIVO:
O Mercado Livre utiliza o WAF Akamai, que bloqueia instantaneamente tráfego oriundo de
IPs de Data Centers conhecidos (como a AWS Fargate), redirecionando para uma página 
de login obrigatória (Hard Block).

COMO EXECUTAR LOCALMENTE:
Pode ser executado localmente sem restrições. Como o IP residencial do desenvolvedor
tem boa reputação, o WAF não bloqueia a requisição.
Basta rodar: `python scrapers/mercado_livre_scraper.py`

COMO EXECUTAR NA AWS (PRODUÇÃO):
Para que este scraper funcione na AWS, é obrigatório macronar o IP do contêiner usando
um Proxy Residencial ou Comercial (ex: Webshare, Proxy6, BrightData).
1. Obtenha as credenciais do proxy.
2. Defina a variável de ambiente `PROXY_MERCADO_LIVRE` no seu ambiente AWS.
   Formato: http://usuario:senha@ip:porta
=========================================================================================
"""

import os
import time
import re
from datetime import datetime
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from base_scraper import BaseScraper

_original_del = uc.Chrome.__del__

def _silenced_del(self):
    try:
        _original_del(self)
    except Exception:
        pass

uc.Chrome.__del__ = _silenced_del

class MercadoLivreScraper(BaseScraper):
    """
    Scraper especializado no Mercado Livre via Automação Web.
    Varre a página de buscas pública de forma invisível e extrai a oferta mais barata.
    Utiliza suporte a Proxy para evitar barreiras de IP em servidores cloud como AWS.
    """

    def __init__(self):
        super().__init__('MercadoLivre')
        self.driver = self._configurar_driver()

    def _configurar_driver(self):
        """Configura o Chrome Headless com Spoofing e suporte a Proxy."""
        options = uc.ChromeOptions()
        
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--start-maximized")
        
        options.add_argument("--lang=pt-BR,pt;q=0.9")
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        options.add_argument(f"--user-agent={user_agent}")
        
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-site-isolation-trials")
        options.add_argument("--disable-features=IsolateOrigins,site-per-process")
        options.add_argument("--log-level=3")
        options.add_argument("--disable-blink-features=AutomationControlled")

        proxy_servidor = os.getenv("PROXY_MERCADO_LIVRE", "")
        if proxy_servidor:
            options.add_argument(f'--proxy-server={proxy_servidor}')
            self.logger.info("Camada de Proxy ativada para navegacao anonima.")

        self.logger.info("Inicializando o motor do Chrome (Undetected) para varredura de mercado...")
        
        try:
            import platform
            if platform.system() == "Windows":
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon")
                versao, _ = winreg.QueryValueEx(key, "version")
                winreg.CloseKey(key)
                versao_main = int(versao.split('.')[0])
            else:
                import subprocess
                process = subprocess.Popen(['google-chrome', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                output, _ = process.communicate()
                versao_main = int(output.decode('utf-8').strip().split()[-1].split('.')[0])
            
            driver = uc.Chrome(options=options, version_main=versao_main)
        except Exception:
            driver = uc.Chrome(options=options)
            
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver

    def extrair_dados(self):
        produtos = self.carregar_produtos_alvo()
        
        if not produtos:
            self.logger.warning("A lista de produtos esta vazia.")
            if self.driver: self.driver.quit()
            return

        for produto in produtos:
            termo_original = produto['termo_busca']
            termo_url = termo_original.replace(' ', '-')
            url_busca = f"https://lista.mercadolivre.com.br/supermercado/{termo_url}"
            
            self.logger.info(f"Escaneando listagens web para: {termo_original}")
            
            try:
                self.driver.get(url_busca)
                
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '.ui-search-layout__item, [class*="poly-card"]'))
                )
                time.sleep(2)
                
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                cards = soup.find_all('li', class_='ui-search-layout__item')
                if not cards: 
                    cards = soup.find_all('div', class_=lambda c: c and 'poly-card' in c)

                if not cards:
                    self.logger.warning(f"Nenhum anuncio localizado na pagina para: {termo_original}")
                    continue

                ofertas_validas = []
                termo_lower = termo_original.lower()
                busca_zero = any(w in termo_lower for w in ['zero', 'diet', 'light', 'sem açucar', 'sem acucar', 'sem açúcar'])
                marca_limpa = produto['marca'].lower()

                match_alvo = re.search(r'(\d+(?:[.,]\d+)?)\s*(ml|l)\b', termo_lower)
                qtd_alvo = float(match_alvo.group(1).replace(',', '.')) if match_alvo else None
                unit_alvo = match_alvo.group(2) if match_alvo else None

                for card in cards:
                    link_elem = card.find('a', href=True)
                    titulo_elem = card.find('h2') or card.find('h3') or link_elem
                    preco_frao = card.find('span', class_='andes-money-amount__fraction')
                    
                    if titulo_elem and preco_frao and link_elem:
                        titulo = titulo_elem.text.strip()
                        if not titulo: continue
                        
                        titulo_norm = titulo.lower()

                        if marca_limpa not in titulo_norm:
                            continue

                        if not busca_zero and any(w in titulo_norm for w in ['zero', 'diet', 'light', 'sem açucar', 'sem acucar', 'sem açúcar']):
                            continue

                        if qtd_alvo and unit_alvo:
                            match_item = re.search(r'(\d+(?:[.,]\d+)?)\s*(ml|l)\b', titulo_norm)
                            if match_item:
                                qtd_item = float(match_item.group(1).replace(',', '.'))
                                unit_item = match_item.group(2)
                                if qtd_item != qtd_alvo or unit_item != unit_alvo:
                                    continue
                            else:
                                continue

                        preco_texto = preco_frao.text.replace('.', '').strip()
                        preco_centavos = card.find('span', class_='andes-money-amount__cents')
                        centavos = preco_centavos.text.strip() if preco_centavos else "00"
                        preco_final = float(f"{preco_texto}.{centavos}")

                        link = link_elem['href']
                        dados_preco = self.normalizar_preco(titulo, preco_final)

                        ofertas_validas.append({
                            "titulo": titulo,
                            "preco": preco_final,
                            "link": link,
                            "dados_preco": dados_preco
                        })

                if not ofertas_validas:
                    self.logger.warning(f"Nenhum item atendeu aos criterios de validacao para: {termo_original}")
                    continue

                ofertas_validas.sort(key=lambda x: x['dados_preco']['preco_unitario'])

                encontrados = 0
                for oferta in ofertas_validas:
                    if encontrados >= 1:
                        break

                    self.dados_extraidos.append({
                        "data_extracao": datetime.now().isoformat(),
                        "site": self.nome_site,
                        "categoria": produto['categoria'],
                        "marca": produto['marca'],
                        "termo_buscado": termo_original,
                        "titulo_anuncio": oferta['titulo'],
                        "quantidade_embalagem": oferta['dados_preco']["quantidade_embalagem"],
                        "preco_total_anuncio": oferta['dados_preco']["preco_total_anuncio"],
                        "preco_unitario": oferta['dados_preco']["preco_unitario"],
                        "link": oferta['link']
                    })
                    encontrados += 1
                    self.logger.info(f"[SUCESSO] MELHOR PRECO CAPTURADO: {oferta['titulo']}")

            except Exception as e:
                self.logger.error(f"[ERRO] Erro operacional durante a automacao de {termo_original}: {e}")
        
        self.salvar_dados()
        if self.driver: 
            self.driver.quit()

if __name__ == "__main__":
    scraper = MercadoLivreScraper()
    scraper.extrair_dados()