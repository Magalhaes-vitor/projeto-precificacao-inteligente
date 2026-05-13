import time
import re
from datetime import datetime

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

from base_scraper import BaseScraper

class ZeDeliveryScraper(BaseScraper):
    def __init__(self):
        super().__init__('ZeDelivery')
        self.endereco_padrao = "Avenida Paulista, 1000, São Paulo" 
        self.driver = self._configurar_driver()

    def _configurar_driver(self):
        edge_options = Options()
        edge_options.add_argument("--disable-gpu")
        edge_options.add_argument("--window-size=1920,1080")
        edge_options.add_argument("--disable-blink-features=AutomationControlled")
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        self.logger.info("Inicializando motor do Edge para o Zé Delivery...")
        driver = webdriver.Edge(options=edge_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver

    def extrair_dados(self):
        produtos = self.carregar_produtos_alvo()
        if not produtos: return

        sessao_configurada = False

        for produto in produtos:
            self.logger.info(f"Iniciando raspagem para: {produto['termo_busca']}")
            
            try:
                if not sessao_configurada:
                    self.driver.get("https://www.ze.delivery/")
                    time.sleep(8)
                    
                    # 1. RESOLVER O AGE GATE
                    self.driver.execute_script("""
                        let btns = document.querySelectorAll('button');
                        for(let b of btns){
                            if(b.innerText.toLowerCase().includes('sim') || b.innerText.includes('18')){
                                b.click(); break;
                            }
                        }
                    """)
                    time.sleep(3)

                    # 2. RESOLVER A LOCALIZAÇÃO
                    self.logger.info("Iniciando rotina de localização...")
                    self.driver.execute_script("""
                        let btns = document.querySelectorAll('button, div');
                        for(let b of btns){
                            let txt = b.innerText.toLowerCase();
                            if(b.offsetParent !== null && (txt.includes('informar endereço') || txt.includes('onde você está'))){
                                b.click(); break;
                            }
                        }
                    """)
                    time.sleep(4)

                    input_addr = self.driver.execute_script("""
                        let inputs = document.querySelectorAll('input');
                        for(let i=inputs.length-1; i>=0; i--){
                            if(inputs[i].offsetParent !== null && inputs[i].type === 'text'){ return inputs[i]; }
                        }
                        return null;
                    """)
                    
                    if input_addr:
                        input_addr.click()
                        time.sleep(1)
                        ativo = self.driver.switch_to.active_element
                        ativo.send_keys(Keys.CONTROL + "a")
                        ativo.send_keys(Keys.BACKSPACE)
                        time.sleep(0.5)
                        for char in self.endereco_padrao:
                            ativo.send_keys(char); time.sleep(0.05)
                        
                        time.sleep(6)
                        ActionChains(self.driver).move_to_element_with_offset(ativo, 0, 65).click().perform()
                        time.sleep(5)
                        
                        # Preenchimento de Complemento
                        self.logger.info("Preenchendo Complemento...")
                        self.driver.execute_script("""
                            let inputs = document.querySelectorAll('input');
                            for(let i of inputs){
                                let ph = i.placeholder.toLowerCase();
                                if(ph.includes('complemento') || ph.includes('apto') || ph.includes('casa')){
                                    i.focus(); i.click();
                                }
                            }
                        """)
                        time.sleep(1)
                        self.driver.switch_to.active_element.send_keys("Casa")
                        time.sleep(2)
                            
                        # Confirmar
                        clicou_final = self.driver.execute_script("""
                            let btns = document.querySelectorAll('button');
                            for(let b of btns){
                                let txt = b.innerText.toLowerCase();
                                if(b.offsetParent !== null && !b.disabled && (txt.includes('ver produtos') || txt.includes('confirmar'))){
                                    b.click(); return true;
                                }
                            }
                            return false;
                        """)
                        
                        if clicou_final:
                            self.logger.info("🚀 Sucesso! Acesso ao catálogo liberado.")
                            sessao_configurada = True
                            time.sleep(10) # Tempo extra para o catálogo carregar
                        else:
                            self.driver.switch_to.active_element.send_keys(Keys.ENTER)
                            sessao_configurada = True
                            time.sleep(8)

# ==========================================
                # BUSCA DE PRODUTOS (VITRINE) - LEITURA DIRETA DO MENU
                # ==========================================
                if sessao_configurada:
                    # ---> LÓGICA DE LIMPEZA <---
                    categoria = produto.get('categoria', '')
                    termo_original = produto.get('termo_busca', '')
                    
                    # 1. Remove a categoria ignorando maiúsculas/minúsculas
                    termo_limpo = re.sub(re.escape(categoria), '', termo_original, flags=re.IGNORECASE)
                    # 2. Remove as palavras "Lata" e "Pet" (como palavras inteiras \b)
                    termo_limpo = re.sub(r'\b(lata|pet)\b', '', termo_limpo, flags=re.IGNORECASE)
                    # 3. Limpa espaços duplos gerados pela remoção das palavras
                    termo_limpo = re.sub(r'\s+', ' ', termo_limpo).strip()

                    self.logger.info(f"Pesquisando: {termo_limpo} (reduzido de: {termo_original})...")
                    
                    # Tática Sniper: Tenta clicar no ícone de busca ou no input
                    search_script = """
                        let inputs = document.querySelectorAll('input');
                        for(let i of inputs){
                            let ph = (i.placeholder || "").toLowerCase();
                            let id = (i.id || "").toLowerCase();
                            if(i.offsetParent !== null && (ph.includes('busque') || ph.includes('pesquisar') || id.includes('search'))){
                                i.focus(); i.click(); return i;
                            }
                        }
                        let searchBtn = document.querySelector('div[id*="search"], button[id*="search"]');
                        if(searchBtn) { searchBtn.click(); return document.querySelector('input'); }
                        return null;
                    """
                    search_input = self.driver.execute_script(search_script)

                    if search_input:
                        time.sleep(1)
                        ativo_busca = self.driver.switch_to.active_element
                        ativo_busca.send_keys(Keys.CONTROL + "a")
                        ativo_busca.send_keys(Keys.BACKSPACE)
                        
                        # Digita o termo limpo
                        for char in termo_limpo:
                            ativo_busca.send_keys(char)
                            time.sleep(0.1)
                        
                        # Espera o Zé Delivery processar a busca e abrir o menu com os preços
                        time.sleep(4) 
                        
                        self.logger.info("Lendo dados diretamente do menu suspenso...")
                        
                        # ---> CORREÇÃO: Pega estritamente a primeira linha de item do menu <---
                        texto_item = self.driver.execute_script("""
                            let items = document.querySelectorAll('li, [role="option"]');
                            for(let item of items){
                                let txt = item.innerText || "";
                                // Garante que estamos pegando a primeira linha que contém um preço
                                if(item.offsetParent !== null && txt.includes('R$')){
                                    return txt;
                                }
                            }
                            return null;
                        """)
                        
                        if texto_item:
                            # Divide o texto do único item em linhas para pegar o título
                            linhas = [linha.strip() for linha in texto_item.split('\n') if linha.strip()]
                            titulo_anuncio = linhas[0] if linhas else termo_limpo
                            
                            precos_encontrados = re.findall(r'R\$\s?(\d+[\.,]\d+)', texto_item)
                            
                            if precos_encontrados:
                                # ---> CORREÇÃO: Pega o PRIMEIRO preço retornado na string daquele item <---
                                preco_str = precos_encontrados[0].replace(',', '.')
                                preco_float = float(preco_str)
                                
                                dados_preco = self.normalizar_preco(titulo_anuncio, preco_float)
                                
                                self.dados_extraidos.append({
                                    "data_extracao": datetime.now().isoformat(),
                                    "site": self.nome_site,
                                    "categoria": produto['categoria'],
                                    "marca": produto['marca'],
                                    "termo_buscado": termo_limpo, 
                                    "titulo_anuncio": titulo_anuncio,
                                    "quantidade_embalagem": dados_preco["quantidade_embalagem"],
                                    "preco_total_anuncio": dados_preco["preco_total_anuncio"],
                                    "preco_unitario": dados_preco["preco_unitario"],
                                    "link": "Extraído via Menu de Busca"
                                })
                                self.logger.info(f"✅ Extraído do menu: {titulo_anuncio} | R${dados_preco['preco_unitario']}")
                            else:
                                self.logger.warning(f"Nenhum preço formatado encontrado no menu para {produto['marca']}.")
                        else:
                            self.logger.warning(f"Menu de sugestões não carregou ou produto fora de estoque para {produto['marca']}.")
                        
                        # Fecha o menu suspenso para a próxima busca
                        ativo_busca.send_keys(Keys.ESCAPE)
                        time.sleep(2)
                    else:
                        self.logger.warning(f"Barra de busca não encontrada para {produto['marca']}.")

            except Exception as e:
                self.logger.error(f"Erro em {produto['termo_busca']}: {e}")
        
        self.salvar_dados()
        if self.driver: self.driver.quit()

if __name__ == "__main__":
    ZeDeliveryScraper().extrair_dados()