import time
import re
from datetime import datetime

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.edge.options import Options

from base_scraper import BaseScraper

class AmazonScraper(BaseScraper):
    def __init__(self):
        super().__init__('Amazon')
        self.driver = self._configurar_driver()

    def _configurar_driver(self):
        edge_options = Options()
        edge_options.add_argument("--disable-gpu")
        edge_options.add_argument("--window-size=1920,1080")
        edge_options.add_argument("--disable-blink-features=AutomationControlled")
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        edge_options.add_experimental_option('useAutomationExtension', False)
        edge_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        self.logger.info("Inicializando o motor do Edge para a Amazon...")
        driver = webdriver.Edge(options=edge_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver

    def _verificar_captcha(self, soup):
        titulo_pagina = soup.title.text.lower() if soup.title else ""
        if "robot check" in titulo_pagina or soup.find(id="captchacharacters"):
            return True
        return False

    def _limpar_termo(self, termo):
        termo_limpo = re.sub(r'\b(lata|pet)\b', '', termo, flags=re.IGNORECASE)
        return re.sub(r'\s+', ' ', termo_limpo).strip()

    def _filtrar_melhor_resultado(self, termo_original, marca, resultados):
        if not resultados:
            return None
            
        termo_lower = termo_original.lower()
        marca_norm = marca.lower()
        marca_variacoes = [marca_norm, marca_norm.replace('-', ' '), marca_norm.replace('-', '')]
        
        # Override manual rigoroso para Coca-Cola 2L Original
        if 'coca' in termo_lower and '2l' in termo_lower:
            for item in resultados:
                t_norm = item['titulo'].lower().replace('-', ' ')
                if 'coca cola original 2 l' in t_norm or 'coca cola original 2l' in t_norm.replace('2 l', '2l') or 'coca cola 2 litros' in t_norm:
                    if not any(w in t_norm for w in ['zero', 'diet', 'sem açúcar', 'sem acucar', 'café', 'cafe']):
                        return item

        busca_zero = any(w in termo_lower for w in ['zero', 'diet', 'light', 'sem açucar', 'sem açúcar'])
        
        sabores_comuns = ['café', 'cafe', 'cherry', 'baunilha', 'limão', 'limao', 'laranja', 'maracuja', 'morango', 'uva', 'guaraná', 'guarana']
        sabores_proibidos = [s for s in sabores_comuns if s not in termo_lower]

        padrao_volume = re.search(r'(\d+(?:[.,]\d+)?)\s*(ml|l|kg|g|litros?)\b', termo_original, flags=re.IGNORECASE)
        vol_buscado_val = -1
        tipo_medida = None
        
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
            v_n = padrao_volume.group(1)
            v_u = padrao_volume.group(2).lower()
            vol_buscado_val, tipo_medida = extrair_medida(v_n, v_u)

        for item in resultados:
            titulo_norm = item['titulo'].lower()
            
            if not any(m in titulo_norm for m in marca_variacoes):
                continue
            
            if any(re.search(rf'\b{s}\b', titulo_norm) for s in sabores_proibidos):
                continue
            
            is_zero = any(w in titulo_norm for w in ['zero', 'diet', 'light', 'sem açucar', 'sem açúcar'])
            if busca_zero and not is_zero: continue
            if not busca_zero and is_zero: continue
                
            is_lata_busca = 'lata' in termo_lower
            is_pet_busca = 'pet' in termo_lower or 'garrafa' in termo_lower
            is_lata_item = 'lata' in titulo_norm
            is_pet_item = 'pet' in titulo_norm or 'garrafa' in titulo_norm

            if is_lata_busca and is_pet_item: continue
            if is_pet_busca and is_lata_item: continue

            titulo_norm_medida = titulo_norm.replace('litros', 'l').replace('litro', 'l')
            titulo_norm_medida = re.sub(r'(\d)\s+(ml|l|kg|g)\b', r'\1\2', titulo_norm_medida) 
            
            if vol_buscado_val > 0:
                vols_no_titulo = re.findall(r'\b(\d+(?:[.,]\d+)?)(ml|l|kg|g)\b', titulo_norm_medida)
                
                achou_vol_correto = False
                tem_vol_errado = False
                
                for vn, vu in vols_no_titulo:
                    v_val, v_tipo = extrair_medida(vn, vu)
                    if v_tipo == tipo_medida and v_val > 0:
                        if v_val == vol_buscado_val:
                            achou_vol_correto = True
                        else:
                            tem_vol_errado = True
                
                if not achou_vol_correto:
                    continue
                if tem_vol_errado:
                    continue
                
            return item 
            
        return None

    def _extrair_anuncios_da_pagina(self, soup):
        cards = soup.find_all('div', {'data-component-type': 's-search-result'})
        resultados_validos = []
        
        for card in cards:
            h2_elem = card.find('h2')
            if not h2_elem: continue
            
            titulo = h2_elem.text.strip()
            if not titulo: continue

            preco_float = 0.0
            
            preco_elem = card.find('span', class_='a-price')
            if preco_elem:
                offscreen = preco_elem.find('span', class_='a-offscreen')
                if offscreen:
                    pt = offscreen.text.replace('R$', '').replace('.', '').replace(',', '.').strip()
                    try: preco_float = float(pt)
                    except: pass
            
            if preco_float == 0.0:
                sec_offer = card.find('div', {'data-cy': 'secondary-offer-recipe'})
                if sec_offer:
                    spans = sec_offer.find_all('span', class_='a-color-base')
                    for s in spans:
                        txt = s.text.strip()
                        if 'R$' in txt and '/' not in txt:
                            val = txt.replace('R$', '').replace('\xa0', '').replace('&nbsp;', '').replace(' ', '').replace('.', '').replace(',', '.')
                            clean_val = ''.join(c for c in val if c.isdigit() or c == '.')
                            try:
                                pf = float(clean_val)
                                if pf > 0:
                                    preco_float = pf
                                    break
                            except:
                                pass

            if preco_float > 5000 or preco_float <= 0: continue

            link_a = h2_elem.find('a', href=True)
            if not link_a:
                link_a = card.find('a', class_='a-link-normal', href=True)
                
            link = link_a['href'] if link_a else "Link Indisponível"
            if link.startswith('/'):
                link = f"https://www.amazon.com.br{link}"
                
            resultados_validos.append({
                "titulo": titulo,
                "preco": preco_float,
                "link": link
            })
        
        unicos = {item['link']: item for item in resultados_validos if item['link'] != "Link Indisponível"}.values()
        return list(unicos)

    def extrair_dados(self):
        produtos = self.carregar_produtos_alvo()
        if not produtos: return

        for produto in produtos:
            termo_original = produto['termo_busca']
            marca_alvo = produto['marca']
            termo_pesquisa = self._limpar_termo(termo_original)
            
            termo_formatado = termo_pesquisa.replace(' ', '+') 
            url = f"https://www.amazon.com.br/s?k={termo_formatado}&i=grocery"
            
            self.logger.info(f"Iniciando busca: {termo_original}")
            
            try:
                self.driver.get(url)
                time.sleep(3)
                
                if self._verificar_captcha(BeautifulSoup(self.driver.page_source, 'html.parser')):
                    self.logger.error("[ERRO] CAPTCHA detectado. Pausa de seguranca aplicada.")
                    time.sleep(10)
                    continue
                
                self.driver.execute_script("window.scrollBy(0, 500);")
                time.sleep(1.5)
                self.driver.execute_script("window.scrollBy(0, 800);")
                time.sleep(1.5)
                
                html_renderizado = self.driver.page_source
                soup = BeautifulSoup(html_renderizado, 'html.parser')

                resultados_brutos = self._extrair_anuncios_da_pagina(soup)

                if not resultados_brutos:
                    self.logger.warning(f"[AVISO] Nenhum anuncio carregado na vitrine para: {termo_original}.")
                    continue

                item_data = self._filtrar_melhor_resultado(termo_original, marca_alvo, resultados_brutos)

                if item_data and item_data['preco']:
                    dados_preco = self.normalizar_preco(item_data['titulo'], float(item_data['preco']))
                    
                    self.dados_extraidos.append({
                        "data_extracao": datetime.now().isoformat(),
                        "site": self.nome_site,
                        "categoria": produto['categoria'],
                        "marca": produto['marca'],
                        "termo_buscado": termo_original,
                        "titulo_anuncio": item_data['titulo'],
                        "quantidade_embalagem": dados_preco["quantidade_embalagem"],
                        "preco_total_anuncio": dados_preco["preco_total_anuncio"],
                        "preco_unitario": dados_preco["preco_unitario"],
                        "link": item_data['link']
                    })
                    self.logger.info(f"[SUCESSO] Item capturado: {item_data['titulo'][:30]}... | Preco Unitario: R${dados_preco['preco_unitario']}")
                else:
                    self.logger.warning(f"[AVISO] Nenhum item atendeu aos criterios de filtro para: {termo_original}")
            
            except Exception as e:
                self.logger.error(f"[ERRO] Falha inesperada durante a extracao: {e}")
        
        self.salvar_dados()
        if self.driver: self.driver.quit()

if __name__ == "__main__":
    AmazonScraper().extrair_dados()