import time
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup

from base_scraper import BaseScraper

class MercadoLivreScraper(BaseScraper):
    def __init__(self):
        super().__init__('MercadoLivre')
        self.driver = self._configurar_driver()

    def _configurar_driver(self):
        edge_options = Options()
        edge_options.add_argument("--disable-gpu")
        edge_options.add_argument("--window-size=1920,1080")
        edge_options.add_argument("--disable-blink-features=AutomationControlled")
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        edge_options.add_experimental_option('useAutomationExtension', False)
        
        self.logger.info("Inicializando o motor do Edge para o Mercado Livre...")
        driver = webdriver.Edge(options=edge_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver

    def _verificar_captcha(self, soup):
        titulo_pagina = soup.title.text.lower() if soup.title else ""
        if "verifique" in titulo_pagina or "robô" in titulo_pagina or "captcha" in titulo_pagina:
            return True
        return False

    def _limpar_termo(self, termo):
        # Substitui espacos por hifens, padrao de URL do ML
        termo_limpo = re.sub(r'\b(lata|pet)\b', '', termo, flags=re.IGNORECASE)
        termo_limpo = re.sub(r'\s+', ' ', termo_limpo).strip()
        return termo_limpo.replace(' ', '-')

    def _filtrar_melhor_resultado(self, termo_original, marca, resultados):
        if not resultados:
            return None
            
        termo_lower = termo_original.lower()
        marca_norm = marca.lower()
        marca_variacoes = [marca_norm, marca_norm.replace('-', ' '), marca_norm.replace('-', '')]
        
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
            
            # 1. Filtro Marca
            if not any(m in titulo_norm for m in marca_variacoes):
                continue
            
            # 2. Sabores Proibidos
            if any(re.search(rf'\b{s}\b', titulo_norm) for s in sabores_proibidos):
                continue
            
            # 3. Diet/Light/Zero
            is_zero = any(w in titulo_norm for w in ['zero', 'diet', 'light', 'sem açucar', 'sem açúcar'])
            if busca_zero and not is_zero: continue
            if not busca_zero and is_zero: continue
                
            # 4. Embalagem Lata/Pet
            is_lata_busca = 'lata' in termo_lower
            is_pet_busca = 'pet' in termo_lower or 'garrafa' in termo_lower
            is_lata_item = 'lata' in titulo_norm
            is_pet_item = 'pet' in titulo_norm or 'garrafa' in titulo_norm

            if is_lata_busca and is_pet_item: continue
            if is_pet_busca and is_lata_item: continue

            # 5. Volume Semantico
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
        cards = soup.find_all('li', class_='ui-search-layout__item')
        if not cards: 
            cards = soup.find_all('div', class_=lambda c: c and 'poly-card' in c)

        resultados_validos = []

        for card in cards:
            link_elem = card.find('a', href=True)
            titulo_elem = card.find('h2') or card.find('h3') or link_elem
            
            # Tratamento de Precos ML
            preco_elem = card.find('span', class_='andes-money-amount__fraction')
            
            if titulo_elem and preco_elem and link_elem:
                titulo = titulo_elem.text.strip()
                if not titulo: 
                    titulo = link_elem.text.strip()
                
                preco_texto = preco_elem.text.replace('.', '')
                try:
                    preco_float = float(preco_texto)
                except:
                    continue
                
                link = link_elem['href']

                resultados_validos.append({
                    "titulo": titulo,
                    "preco": preco_float,
                    "link": link
                })

        return resultados_validos

    def extrair_dados(self):
        produtos = self.carregar_produtos_alvo()
        
        if not produtos:
            self.logger.warning("[AVISO] A lista de produtos esta vazia.")
            if self.driver: self.driver.quit()
            return

        for produto in produtos:
            termo_original = produto['termo_busca']
            marca_alvo = produto['marca']
            termo_formatado = self._limpar_termo(termo_original)
            
            url = f"https://lista.mercadolivre.com.br/supermercado/{termo_formatado}"
            
            self.logger.info(f"Processando extracao para: {termo_original} | Marca: {marca_alvo}")
            
            try:
                self.driver.get(url)
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '.ui-search-layout__item, [class*="poly-card"]'))
                )
                time.sleep(2)
                
                html_renderizado = self.driver.page_source
                soup = BeautifulSoup(html_renderizado, 'html.parser')

                if self._verificar_captcha(soup):
                    self.logger.error(f"[ERRO] CAPTCHA detectado na busca por {termo_original}. O ML bloqueou o bot.")
                    time.sleep(10)
                    continue

                anuncios_brutos = self._extrair_anuncios_da_pagina(soup)

                if not anuncios_brutos:
                    self.logger.warning(f"[AVISO] Sem anuncios localizados na vitrine para {termo_original}.")
                    continue

                item_data = self._filtrar_melhor_resultado(termo_original, marca_alvo, anuncios_brutos)

                if item_data and item_data['preco']:
                    dados_preco = self.normalizar_preco(item_data['titulo'], item_data['preco'])
                    
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
                    self.logger.info(f"[SUCESSO] Item capturado: {item_data['titulo'][:40]}... | Preco Unitario: R${dados_preco['preco_unitario']}")
                else:
                    self.logger.warning(f"[AVISO] Nenhum item atendeu aos criterios de filtro para: {termo_original}")
            
            except Exception as e:
                self.logger.error(f"[ERRO] Falha inesperada durante a automacao de {termo_original}: {e}")
        
        self.salvar_dados()
        if self.driver: 
            self.driver.quit()

if __name__ == "__main__":
    MercadoLivreScraper().extrair_dados()