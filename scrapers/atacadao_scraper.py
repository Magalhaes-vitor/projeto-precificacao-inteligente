import time
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from base_scraper import BaseScraper

class AtacadaoScraper(BaseScraper):
    def __init__(self):
        super().__init__('Atacadao')
        self.cep_padrao = "01310-100"
        self.driver = self._configurar_driver()

    def _configurar_driver(self):
        edge_options = Options()
        edge_options.add_argument("--disable-gpu")
        edge_options.add_argument("--window-size=1920,1080")
        edge_options.add_argument("--disable-blink-features=AutomationControlled")
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        self.logger.info("Inicializando motor do Edge para o Atacadão...")
        driver = webdriver.Edge(options=edge_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver

    def _definir_localizacao(self):
        self.logger.info(f"Iniciando fluxo de localização para o CEP: {self.cep_padrao}")
        try:
            # 1. Limpar banner de cookies
            self.driver.execute_script("""
                let cookieBtn = document.querySelector('.cc-allow, [class*="cookie"] button');
                if(cookieBtn) cookieBtn.click();
            """)
            time.sleep(1)

            # 2. Clicar no botão do header
            self.logger.info("A tentar abrir o popover de CEP...")
            self.driver.execute_script("""
                let btnCep = document.querySelector('button[data-testid="userZipCode"], button[data-testid="userZipCode-mobile"]');
                if(btnCep) btnCep.click();
            """)
            time.sleep(2)

            # 3. Clicar em "Informar Localização" dentro do popover
            self.driver.execute_script("""
                let botoes = document.querySelectorAll('button');
                for(let b of botoes){
                    if(b.innerText && b.innerText.toLowerCase().includes('informar localiza')){
                        b.click();
                        break;
                    }
                }
            """)
            time.sleep(3)

            # 4. Encontrar o input usando JS e focar
            encontrou_input = self.driver.execute_script("""
                let input = document.querySelector('input[placeholder*="CEP"], input[name*="cep"], input[name="postalCode"], input[type="tel"]');
                if(input){
                    input.focus();
                    input.click();
                    return true;
                }
                return false;
            """)

            if encontrou_input:
                ativo = self.driver.switch_to.active_element
                # Limpar campo
                for _ in range(15):
                    ativo.send_keys(Keys.BACKSPACE)
                    ativo.send_keys(Keys.DELETE)
                time.sleep(0.5)

                self.logger.info("A digitar o CEP...")
                for char in self.cep_padrao:
                    ativo.send_keys(char)
                    time.sleep(0.1)
                
                time.sleep(1.5)
                # Submeter
                self.driver.execute_script("""
                    let searchBtn = document.querySelector('button[aria-label*="Buscar"], button[aria-label*="Search"]');
                    if(searchBtn) searchBtn.click();
                """)
                time.sleep(1)
                ativo.send_keys(Keys.ENTER)
                time.sleep(6) # Aguarda lista
            else:
                self.logger.warning("Input de CEP não foi focado corretamente!")

            # 5. Confirmar loja
            self.logger.info("A tentar confirmar a loja...")
            self.driver.execute_script("""
                let botoes = document.querySelectorAll('button');
                for(let b of botoes){
                    let txt = (b.innerText || "").toLowerCase();
                    if((txt.includes('confirmar') || txt.includes('salvar') || txt.includes('entrar') || txt.includes('escolher')) && b.offsetParent !== null){
                        b.click();
                        break;
                    }
                }
            """)
            time.sleep(3)

            # 6. Remover overlays
            self.driver.execute_script("""
                let overlays = document.querySelectorAll('.fixed.inset-0, [role="dialog"]');
                overlays.forEach(o => o.remove());
            """)
            
            self.logger.info("Localização confirmada e ecrã libertado!")

        except Exception as e:
            self.logger.error(f"Erro no fluxo de localização: {e}")

    def _limpar_termo(self, termo):
        termo_limpo = re.sub(r'\b(lata|pet)\b', '', termo, flags=re.IGNORECASE)
        return re.sub(r'\s+', ' ', termo_limpo).strip()

    def _filtrar_melhor_resultado(self, termo_original, resultados):
        if not resultados:
            return None
            
        termo_lower = termo_original.lower()
        # Deteta se o utilizador pediu explicitamente uma versão "zero/diet/light"
        busca_zero = any(w in termo_lower for w in ['zero', 'diet', 'light', 'sem açucar', 'sem açúcar'])

        padrao_volume = re.search(r'(\d+(?:[.,]\d+)?)\s*(ml|l|kg|g|litros?)\b', termo_original, flags=re.IGNORECASE)
        volume_buscado = None
        if padrao_volume:
            numero = padrao_volume.group(1).replace(',', '.')
            unidade = padrao_volume.group(2).lower()
            if unidade.startswith('litro'): 
                unidade = 'l'
            volume_buscado = f"{numero}{unidade}"

        melhor_item = None
        
        for item in resultados:
            titulo_norm = item['titulo'].lower()
            titulo_norm = titulo_norm.replace('litros', 'l').replace('litro', 'l')
            titulo_norm = re.sub(r'(\d)\s+(ml|l|kg|g)\b', r'\1\2', titulo_norm) 
            
            # 1. Filtro de Negativos: Pula itens "Zero/Diet" se não foram pedidos
            is_zero = any(w in titulo_norm for w in ['zero', 'diet', 'light', 'sem açucar', 'sem açúcar'])
            if not busca_zero and is_zero:
                continue
                
            # 2. Filtro de Volume Exato
            if volume_buscado and not re.search(rf'\b{volume_buscado}\b', titulo_norm):
                continue
                
            melhor_item = item
            break
            
        # Fallback 1: Retorna o primeiro que bata o volume (se os filtros normais forem muito restritos)
        if not melhor_item and volume_buscado:
            for item in resultados:
                titulo_norm = item['titulo'].lower()
                titulo_norm = titulo_norm.replace('litros', 'l').replace('litro', 'l')
                titulo_norm = re.sub(r'(\d)\s+(ml|l|kg|g)\b', r'\1\2', titulo_norm) 
                if re.search(rf'\b{volume_buscado}\b', titulo_norm):
                    return item
                    
        # Fallback 2: Retorna o primeiro da lista
        return melhor_item if melhor_item else resultados[0]

    def extrair_dados(self):
        produtos = self.carregar_produtos_alvo()
        if not produtos: return

        try:
            self.driver.get("https://www.atacadao.com.br/")
            time.sleep(8) 
            
            self._definir_localizacao()

            for produto in produtos:
                termo_original = produto['termo_busca']
                termo_pesquisa = self._limpar_termo(termo_original)
                
                self.logger.info(f"A pesquisar: {termo_pesquisa} (Filtro por: {termo_original})")

                search_box = self.driver.execute_script("""
                    let input = document.querySelector('input[data-testid="store-input"], input[type="search"]');
                    if(input){
                        input.focus();
                        return input;
                    }
                    return null;
                """)

                if search_box:
                    ativo = self.driver.switch_to.active_element
                    ativo.send_keys(Keys.CONTROL + "a")
                    ativo.send_keys(Keys.BACKSPACE)
                    
                    for char in termo_pesquisa:
                        ativo.send_keys(char)
                        time.sleep(0.05)
                    
                    time.sleep(4) 

                    resultados_dropdown = self.driver.execute_script(r"""
                        let items = document.querySelectorAll('li, [role="option"], [data-testid*="suggestion"]');
                        let res = [];
                        for(let item of items){
                            let txt = item.innerText || "";
                            if(item.offsetParent !== null && txt.includes('R$')){
                                let linhas = txt.split('\n').map(l => l.trim()).filter(l => l.length > 0);
                                let priceMatch = txt.match(/R\$\s?(\d+[\.,]\d+)/);
                                if(priceMatch) {
                                    res.push({
                                        titulo: linhas[0],
                                        preco: priceMatch[1].replace(',', '.')
                                    });
                                }
                            }
                        }
                        return res;
                    """)

                    item_data = self._filtrar_melhor_resultado(termo_original, resultados_dropdown)

                    if item_data and item_data['preco']:
                        dados_norm = self.normalizar_preco(item_data['titulo'], float(item_data['preco']))

                        self.dados_extraidos.append({
                            "data_extracao": datetime.now().isoformat(),
                            "site": self.nome_site,
                            "categoria": produto['categoria'],
                            "marca": produto['marca'],
                            "termo_buscado": termo_original, 
                            "titulo_anuncio": item_data['titulo'],
                            "quantidade_embalagem": dados_norm["quantidade_embalagem"],
                            "preco_total_anuncio": dados_norm["preco_total_anuncio"],
                            "preco_unitario": dados_norm["preco_unitario"],
                            "link": "Extraído via Menu Dropdown"
                        })
                        self.logger.info(f"✅ Match Encontrado: {item_data['titulo']} | R${dados_norm['preco_unitario']}")
                    else:
                        self.logger.warning(f"❌ Produto não encontrado ou incompatível nas sugestões.")
                    
                    ativo.send_keys(Keys.ESCAPE)
                    time.sleep(1.5)
                else:
                    self.logger.error("❌ BARRA DE PESQUISA NÃO ENCONTRADA.")

        except Exception as e:
            self.logger.error(f"Erro na extração do Atacadão: {e}")
        finally:
            self.salvar_dados()
            if self.driver: self.driver.quit()

if __name__ == "__main__":
    AtacadaoScraper().extrair_dados()