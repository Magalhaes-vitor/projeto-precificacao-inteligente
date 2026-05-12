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
    Scraper focado na extração de preços do e-commerce Tenda Atacado.
    
    Desafios técnicos superados nesta classe:
    1. Single Page Application (SPA): Requer tempos de espera dinâmicos.
    2. Bloqueio Geográfico (CEP): O site exige um CEP válido antes de exibir preços.
    3. Proteção de Máscara React: Impede injeção via `.send_keys()` comum.
       Solução: Utilização de "Digitação Fantasma" (JavaScript Focus + ActionChains)
       para simular eventos nativos de teclado na DOM (Document Object Model).
    """

    def __init__(self):
        super().__init__('TendaAtacado')
        # CEP da região central de São Paulo utilizado como baseline para precificação
        self.cep_padrao = "01001000" 
        self.driver = self._configurar_driver()

    def _configurar_driver(self):
        """
        Instancia e configura o navegador Microsoft Edge.
        Mantém o modo visual ativo (não-headless) para evitar bloqueios severos
        de provedores anti-bot na camada de rede.
        """
        edge_options = Options()
        edge_options.add_argument("--disable-gpu")
        edge_options.add_argument("--window-size=1920,1080")
        
        # Flags para ofuscação do motor de automação (Evasão de Anti-Bot)
        edge_options.add_argument("--disable-blink-features=AutomationControlled")
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        edge_options.add_experimental_option('useAutomationExtension', False)
        
        self.logger.info("Inicializando motor do Edge para ingestão do Tenda Atacado...")
        driver = webdriver.Edge(options=edge_options)
        
        # Remove a assinatura 'webdriver' do objeto navigator do navegador
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver

    def extrair_dados(self):
        """
        Orquestra o fluxo de navegação, resolução do pop-up de CEP e
        extração dos metadados dos produtos na vitrine.
        """
        produtos = self.carregar_produtos_alvo()
        
        if not produtos:
            self.logger.warning("Lista de produtos alvo (config_produtos.json) está vazia.")
            if self.driver: 
                self.driver.quit()
            return

        # Controle de sessão: O CEP só precisa ser resolvido na primeira requisição
        cep_resolvido = False

        for produto in produtos:
            termo_formatado = produto['termo_busca'].replace(' ', '+') 
            url = f"https://www.tendaatacado.com.br/busca?q={termo_formatado}"
            
            self.logger.info(f"Iniciando raspagem para: {produto['termo_busca']}")
            
            try:
                self.driver.get(url)
                
                # ==========================================
                # BLOCO 1: BYPASS DO POP-UP DE CEP
                # ==========================================
                if not cep_resolvido:
                    self.logger.info("Aguardando carregamento da SPA e pop-up regional...")
                    time.sleep(10)
                    
                    # 1.1 Limpeza de tela (Banners de Cookie)
                    try:
                        self.logger.info("Verificando a existência de banners de consentimento (LGPD)...")
                        botoes_cookie = self.driver.find_elements(
                            By.XPATH, 
                            "//button[contains(translate(text(), 'ACEITAR', 'aceitar'), 'aceitar') or contains(translate(text(), 'ENTENDI', 'entendi'), 'entendi')]"
                        )
                        for btn in botoes_cookie:
                            if btn.is_displayed():
                                self.driver.execute_script("arguments[0].click();", btn)
                                time.sleep(1)
                                break
                    except Exception:
                        pass # Continua o fluxo caso não encontre o banner
                    
                    # 1.2 Localização precisa do Input de CEP via JS
                    self.logger.info("Injetando script localizador para o campo de CEP...")
                    script_acha_input = """
                        let inputs = document.querySelectorAll('input');
                        for(let i=0; i<inputs.length; i++){
                            let el = inputs[i];
                            let rect = el.getBoundingClientRect();
                            // Valida se o elemento possui dimensão real na tela (não está oculto)
                            if(rect.width > 0 && rect.height > 0){
                                let ph = (el.placeholder || '').toLowerCase();
                                let nm = (el.name || '').toLowerCase();
                                
                                // Falso positivo: Ignora a barra de busca principal
                                if(ph.includes('busca') || ph.includes('procurando') || nm.includes('search')) continue;
                                
                                // Match condicional para o campo de CEP
                                if(ph.includes('cep') || nm.includes('cep') || ph.includes('000')) return el;
                            }
                        }
                        return null;
                    """
                    campo_cep = self.driver.execute_script(script_acha_input)

                    if campo_cep:
                        self.logger.info("🎯 Input localizado! Executando bypass de máscara (Digitação Fantasma)...")
                        
                        try:
                            # Traz o elemento para o centro da tela, foca e clica nativamente
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].focus(); arguments[0].click();", campo_cep)
                            time.sleep(1)

                            # Limpa o input sem disparar eventos React anômalos
                            actions = ActionChains(self.driver)
                            actions.key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).send_keys(Keys.BACKSPACE).perform()
                            time.sleep(0.5)

                            # Digitação fluida simulando I/O humano para acionar a máscara da interface
                            actions = ActionChains(self.driver)
                            for digito in self.cep_padrao:
                                actions.send_keys(digito)
                                actions.pause(0.2)
                            actions.perform()

                            time.sleep(1)
                            ActionChains(self.driver).send_keys(Keys.ENTER).perform()
                            
                            # Fallback: Caso o ENTER não submeta o formulário, aciona o botão via JS
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

                            self.logger.info("Bypass concluído. Aguardando a vitrine de produtos renderizar...")
                            time.sleep(10)
                            cep_resolvido = True
                        except Exception as e:
                            self.logger.error(f"Falha na execução da digitação fantasma: {e}")
                    else:
                        self.logger.warning("Campo de CEP não detectado. A extração pode retornar vazia.")
                else:
                    # Pausa padrão para paginações subsequentes
                    time.sleep(8) 
                
                # ==========================================
                # BLOCO 2: PARSING DO HTML (BEAUTIFUL SOUP)
                # ==========================================
                html_renderizado = self.driver.page_source
                soup = BeautifulSoup(html_renderizado, 'html.parser')

                # Mapeamento do DOM baseado nas classes de produção do Tenda
                anuncios = soup.find_all('div', class_=lambda c: c and 'ProductCardShowcase' in c)

                if not anuncios:
                    self.logger.warning(f"Sem anúncios localizados no DOM para: {produto['termo_busca']}.")
                    continue

                encontrados = 0
                for anuncio in anuncios:
                    # Limita a amostra aos 2 primeiros cards relevantes
                    if encontrados >= 2:
                        break
                        
                    link_elem = anuncio.find('a', href=True)
                    titulo_elem = anuncio.find(class_=lambda c: c and 'TitleCardComponent' in c)
                    preco_elem = anuncio.find(class_=lambda c: c and 'SimplePriceComponent' in c)
                    
                    if titulo_elem and preco_elem and link_elem:
                        titulo = titulo_elem.text.strip()
                        
                        # Sanitização da string monetária para casting em Float
                        preco_texto = preco_elem.text.replace('R$', '').replace('un', '').replace('\xa0', '').replace('.', '').replace(',', '.').strip()
                        preco_texto = ''.join(c for c in preco_texto if c.isdigit() or c == '.')
                        
                        link = link_elem['href']
                        if link.startswith('/'):
                            link = f"https://www.tendaatacado.com.br{link}"
                        
                        # Estruturação da feature table (Camada Bronze)
                        self.dados_extraidos.append({
                            "data_extracao": datetime.now().isoformat(),
                            "site": self.nome_site,
                            "categoria": produto['categoria'],
                            "marca": produto['marca'],
                            "termo_buscado": produto['termo_busca'],
                            "titulo_anuncio": titulo,
                            "preco_extraido": float(preco_texto) if preco_texto else 0.0,
                            "link": link
                        })
                        encontrados += 1
                        self.logger.info(f"✅ Extraído: {titulo[:30]}... - R${preco_texto}")
                    else:
                        if encontrados == 0: 
                            self.logger.warning("Inconsistência nas classes CSS do card.")
            
            except Exception as e:
                self.logger.error(f"Exceção fatal durante o processo de {produto['termo_busca']}: {e}")
        
        # Consolida os dados em arquivo local (JSON)
        self.salvar_dados()
        
        # Tear down da automação
        if self.driver: 
            self.driver.quit()


# Entrypoint para testes isolados do módulo
if __name__ == "__main__":
    scraper = TendaAtacadoScraper()
    scraper.extrair_dados()