import time
from datetime import datetime

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

from base_scraper import BaseScraper


class TendaAtacadoScraper(BaseScraper):
    """
    Scraper para o e-commerce Tenda Atacado.
    Lida com proteção de CEP via injeção JavaScript e ActionChains.
    """

    def __init__(self):
        super().__init__('TendaAtacado')
        self.cep_padrao = "01001000" 
        self.driver = self._configurar_driver()

    def _configurar_driver(self):
        edge_options = Options()
        edge_options.add_argument("--disable-gpu")
        edge_options.add_argument("--window-size=1920,1080")
        
        edge_options.add_argument("--disable-blink-features=AutomationControlled")
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        edge_options.add_experimental_option('useAutomationExtension', False)
        
        self.logger.info("Inicializando motor do Edge (Tenda Atacado)...")
        driver = webdriver.Edge(options=edge_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver

    def extrair_dados(self):
        produtos = self.carregar_produtos_alvo()
        
        if not produtos:
            self.logger.warning("Lista de produtos alvo está vazia.")
            if self.driver: self.driver.quit()
            return

        cep_resolvido = False

        for produto in produtos:
            termo_formatado = produto['termo_busca'].replace(' ', '+') 
            url = f"https://www.tendaatacado.com.br/busca?q={termo_formatado}"
            
            self.logger.info(f"Iniciando raspagem para: {produto['termo_busca']}")
            
            try:
                self.driver.get(url)
                
                # ROTINA DE BYPASS DE CEP
                if not cep_resolvido:
                    self.logger.info("Aguardando carregamento da SPA...")
                    time.sleep(10)
                    
                    try:
                        botoes_cookie = self.driver.find_elements(By.XPATH, "//button[contains(translate(text(), 'ACEITAR', 'aceitar'), 'aceitar') or contains(translate(text(), 'ENTENDI', 'entendi'), 'entendi')]")
                        for btn in botoes_cookie:
                            if btn.is_displayed():
                                self.driver.execute_script("arguments[0].click();", btn)
                                time.sleep(1)
                                break
                    except Exception:
                        pass 
                    
                    script_acha_input = """
                        let inputs = document.querySelectorAll('input');
                        for(let i=0; i<inputs.length; i++){
                            let el = inputs[i];
                            let rect = el.getBoundingClientRect();
                            if(rect.width > 0 && rect.height > 0){
                                let ph = (el.placeholder || '').toLowerCase();
                                let nm = (el.name || '').toLowerCase();
                                if(ph.includes('busca') || ph.includes('procurando') || nm.includes('search')) continue;
                                if(ph.includes('cep') || nm.includes('cep') || ph.includes('000')) return el;
                            }
                        }
                        return null;
                    """
                    campo_cep = self.driver.execute_script(script_acha_input)

                    if campo_cep:
                        try:
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].focus(); arguments[0].click();", campo_cep)
                            time.sleep(1)

                            actions = ActionChains(self.driver)
                            actions.key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).send_keys(Keys.BACKSPACE).perform()
                            time.sleep(0.5)

                            actions = ActionChains(self.driver)
                            for digito in self.cep_padrao:
                                actions.send_keys(digito)
                                actions.pause(0.2)
                            actions.perform()

                            time.sleep(1)
                            ActionChains(self.driver).send_keys(Keys.ENTER).perform()
                            
                            script_clica_btn = """
                                let btns = document.querySelectorAll('button');
                                for(let i=0; i<btns.length; i++){
                                    let txt = btns[i].innerText.toLowerCase();
                                    if(btns[i].offsetParent !== null && (txt.includes('confirmar') || txt.includes('salvar') || txt.includes('entrar'))){
                                        btns[i].click();
                                        return true;
                                    }
                                }
                                return false;
                            """
                            self.driver.execute_script(script_clica_btn)
                            time.sleep(10)
                            cep_resolvido = True
                        except Exception as e:
                            self.logger.error(f"Falha na digitação fantasma: {e}")
                else:
                    time.sleep(8) 
                
                # PARSING DO HTML
                html_renderizado = self.driver.page_source
                soup = BeautifulSoup(html_renderizado, 'html.parser')

                anuncios = soup.find_all('div', class_=lambda c: c and 'ProductCardShowcase' in c)

                if not anuncios:
                    self.logger.warning(f"Sem anúncios localizados para: {produto['termo_busca']}.")
                    continue

                encontrados = 0
                for anuncio in anuncios:
                    if encontrados >= 2:
                        break
                        
                    link_elem = anuncio.find('a', href=True)
                    titulo_elem = anuncio.find(class_=lambda c: c and 'TitleCardComponent' in c)
                    preco_elem = anuncio.find(class_=lambda c: c and 'SimplePriceComponent' in c)
                    
                    if titulo_elem and preco_elem and link_elem:
                        titulo = titulo_elem.text.strip()
                        preco_texto = preco_elem.text.replace('R$', '').replace('un', '').replace('\xa0', '').replace('.', '').replace(',', '.').strip()
                        preco_texto = ''.join(c for c in preco_texto if c.isdigit() or c == '.')
                        
                        preco_float = float(preco_texto) if preco_texto else 0.0
                        
                        # UTILIZAÇÃO DA REGEX DA CLASSE MÃE
                        dados_preco = self.normalizar_preco(titulo, preco_float)
                        
                        link = link_elem['href']
                        if link.startswith('/'):
                            link = f"https://www.tendaatacado.com.br{link}"
                        
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
                self.logger.error(f"Exceção fatal: {e}")
        
        self.salvar_dados()
        if self.driver: 
            self.driver.quit()

if __name__ == "__main__":
    scraper = TendaAtacadoScraper()
    scraper.extrair_dados()