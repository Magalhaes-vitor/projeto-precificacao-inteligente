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
        
        self.logger.info("Inicializando motor do Edge para o Ze Delivery...")
        driver = webdriver.Edge(options=edge_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver

    def _limpar_termo(self, termo):
        termo_limpo = re.sub(r'\b(lata|pet)\b', '', termo, flags=re.IGNORECASE)
        return re.sub(r'\s+', ' ', termo_limpo).strip()

    def _filtrar_melhor_resultado(self, termo_original, marca, texto_anuncio):
        if not texto_anuncio:
            return False
            
        termo_lower = termo_original.lower()
        marca_norm = marca.lower()
        marca_variacoes = [marca_norm, marca_norm.replace('-', ' '), marca_norm.replace('-', '')]
        titulo_norm = texto_anuncio.lower()

        if not any(m in titulo_norm for m in marca_variacoes):
            return False
            
        if 'coca' in termo_lower and '2l' in termo_lower:
            t_norm = titulo_norm.replace('-', ' ')
            if 'coca' in t_norm and re.search(r'\b2\s*(l|litros?)\b', t_norm):
                if not any(w in t_norm for w in ['zero', 'diet', 'sem açúcar', 'sem acucar', 'café', 'cafe']):
                    return True
                return False

        sabores_comuns = ['café', 'cafe', 'cherry', 'baunilha', 'limão', 'limao', 'laranja', 'maracuja', 'morango', 'uva', 'guaraná', 'guarana']
        sabores_proibidos = [s for s in sabores_comuns if s not in termo_lower]
        if any(re.search(rf'\b{s}\b', titulo_norm) for s in sabores_proibidos):
            return False
        
        busca_zero = any(w in termo_lower for w in ['zero', 'diet', 'light', 'sem açucar', 'sem açúcar'])
        is_zero = any(w in titulo_norm for w in ['zero', 'diet', 'light', 'sem açucar', 'sem açúcar'])
        if busca_zero and not is_zero: return False
        if not busca_zero and is_zero: return False

        is_lata_busca = 'lata' in termo_lower
        is_pet_busca = 'pet' in termo_lower or 'garrafa' in termo_lower
        is_lata_item = 'lata' in titulo_norm
        is_pet_item = 'pet' in titulo_norm or 'garrafa' in titulo_norm

        if is_lata_busca and is_pet_item: return False
        if is_pet_busca and is_lata_item: return False

        padrao_volume = re.search(r'(\d+(?:[.,]\d+)?)\s*(ml|l|kg|g|litros?)\b', termo_original, flags=re.IGNORECASE)
        
        def extrair_medida(v_num_str, v_unit):
            try:
                val = float(v_num_str.replace(',', '.'))
                if v_unit == 'l' or v_unit.startswith('litro'): return val * 1000, 'ml'
                if v_unit == 'ml': return val, 'ml'
                if v_unit == 'kg': return val * 1000, 'g'
                if v_unit == 'g': return val, 'g'
                return -1, None
            except:
                return -1, None

        if padrao_volume:
            vol_buscado_val, tipo_medida = extrair_medida(padrao_volume.group(1), padrao_volume.group(2).lower())
            
            titulo_norm_medida = titulo_norm.replace('litros', 'l').replace('litro', 'l')
            titulo_norm_medida = re.sub(r'(\d)\s+(ml|l|kg|g)\b', r'\1\2', titulo_norm_medida) 
            
            if vol_buscado_val > 0:
                vols_no_titulo = re.findall(r'\b(\d+(?:[.,]\d+)?)(ml|l|kg|g)\b', titulo_norm_medida)
                achou_vol_correto = False
                tem_vol_errado = False
                
                for vn, vu in vols_no_titulo:
                    v_val, v_tipo = extrair_medida(vn, vu)
                    if v_tipo == tipo_medida and v_val > 0:
                        if v_val == vol_buscado_val: achou_vol_correto = True
                        else: tem_vol_errado = True
                
                if not achou_vol_correto or tem_vol_errado:
                    return False
                    
        return True

    def extrair_dados(self):
        produtos = self.carregar_produtos_alvo()
        if not produtos: return

        sessao_configurada = False

        for produto in produtos:
            termo_original = produto['termo_busca']
            marca_alvo = produto['marca']
            self.logger.info(f"Processando busca: {termo_original} | Marca: {marca_alvo}")
            
            try:
                if not sessao_configurada:
                    self.driver.get("https://www.ze.delivery/")
                    time.sleep(8)
                    
                    self.driver.execute_script("""
                        let btns = document.querySelectorAll('button');
                        for(let b of btns){
                            if(b.innerText.toLowerCase().includes('sim') || b.innerText.includes('18')){
                                b.click(); break;
                            }
                        }
                    """)
                    time.sleep(3)

                    self.logger.info("Iniciando rotina de localizacao...")
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
                            self.logger.info("[SUCESSO] Acesso ao catalogo liberado.")
                            sessao_configurada = True
                            time.sleep(10) 
                        else:
                            self.driver.switch_to.active_element.send_keys(Keys.ENTER)
                            sessao_configurada = True
                            time.sleep(8)

                if sessao_configurada:
                    categoria = produto.get('categoria', '')
                    termo_limpo = re.sub(re.escape(categoria), '', termo_original, flags=re.IGNORECASE)
                    termo_limpo = re.sub(r'\b(lata|pet)\b', '', termo_limpo, flags=re.IGNORECASE)
                    termo_limpo = re.sub(r'\s+', ' ', termo_limpo).strip()

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
                        
                        for char in termo_limpo:
                            ativo_busca.send_keys(char)
                            time.sleep(0.1)
                        
                        time.sleep(4) 
                        
                        texto_item = self.driver.execute_script("""
                            let items = document.querySelectorAll('li, [role="option"]');
                            for(let item of items){
                                let txt = item.innerText || "";
                                if(item.offsetParent !== null && txt.includes('R$')){
                                    return txt;
                                }
                            }
                            return null;
                        """)
                        
                        if texto_item:
                            linhas = [linha.strip() for linha in texto_item.split('\n') if linha.strip()]
                            
                            # IGNORAR SELOS DE DESCONTO E PRECOS PARA ACHAR O TITULO REAL
                            titulo_anuncio = termo_limpo
                            for linha in linhas:
                                # Pula selos como "-12%"
                                if re.match(r'^-\d+\s*%$', linha): continue
                                # Pula badges promocionais curtos
                                if linha.lower() in ['novo', 'oferta', 'promoção', 'desconto']: continue
                                # Pula preços
                                if 'R$' in linha: continue
                                
                                titulo_anuncio = linha
                                break
                            
                            passou_filtro = self._filtrar_melhor_resultado(termo_original, marca_alvo, titulo_anuncio)
                            
                            if passou_filtro:
                                precos_encontrados = re.findall(r'R\$\s?(\d+[\.,]\d+)', texto_item)
                                if precos_encontrados:
                                    # Pega o menor preco se houver preco antigo cortado
                                    precos_floats = [float(p.replace(',', '.')) for p in precos_encontrados]
                                    preco_float = min(precos_floats)
                                    
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
                                        "link": "Extraido via Menu de Busca"
                                    })
                                    self.logger.info(f"[SUCESSO] Item capturado: {titulo_anuncio} | R${dados_preco['preco_unitario']}")
                                else:
                                    self.logger.warning(f"[AVISO] Nenhum preco formatado encontrado no menu para {marca_alvo}.")
                            else:
                                self.logger.warning(f"[AVISO] Item sugerido foi rejeitado pelo Filtro Semantico: {titulo_anuncio}")
                        else:
                            self.logger.warning(f"[AVISO] Menu de sugestoes nao carregou ou fora de estoque para {marca_alvo}.")
                        
                        ativo_busca.send_keys(Keys.ESCAPE)
                        time.sleep(2)
                    else:
                        self.logger.error(f"[ERRO] Barra de busca nao encontrada para {marca_alvo}.")

            except Exception as e:
                self.logger.error(f"[ERRO] Falha em {termo_original}: {e}")
        
        self.salvar_dados()
        if self.driver: self.driver.quit()

if __name__ == "__main__":
    ZeDeliveryScraper().extrair_dados()