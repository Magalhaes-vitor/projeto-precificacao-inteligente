import time
import re
from datetime import datetime

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.edge.options import Options

from base_scraper import BaseScraper

class TendaAtacadoScraper(BaseScraper):
    def __init__(self):
        super().__init__('TendaAtacado')
        self.driver = self._configurar_driver()

    def _configurar_driver(self):
        edge_options = Options()
        edge_options.add_argument("--disable-gpu")
        edge_options.add_argument("--window-size=1920,1080")
        edge_options.add_argument("--disable-blink-features=AutomationControlled")
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        edge_options.add_experimental_option('useAutomationExtension', False)
        
        self.logger.info("Inicializando motor do Edge para o Tenda Atacado...")
        driver = webdriver.Edge(options=edge_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver

    def _fechar_modais_iniciais(self):
        self.logger.info("A aguardar a renderizacao para fechar modais e carregar a pagina...")
        # O PAUSA INICIAL DE 5 SEGUNDOS É VITAL AQUI PARA A ARQUITETURA VTEX!
        time.sleep(5)
        
        try:
            self.driver.execute_script("""
                let btns = document.querySelectorAll('button');
                for(let b of btns){
                    let txt = (b.innerText || '').toLowerCase();
                    if(txt.includes('aceitar') || txt.includes('entendi')){
                        b.click();
                    }
                }
            """)
            time.sleep(1)
        except:
            pass 
            
        try:
            self.driver.execute_script("""
                let closeBtn = document.querySelector('img.svg-ico_close_with_circle');
                if(closeBtn) closeBtn.click();
                
                let modalBtns = document.querySelectorAll('[role="dialog"] button, [class*="modal"] button, [class*="Backdrop"] button');
                for (let btn of modalBtns) {
                    if (btn.querySelector('svg') || btn.querySelector('img[src*="close"]')) {
                        btn.click();
                    }
                }
            """)
            time.sleep(2)
        except:
            pass

        try:
            self.driver.execute_script("""
                let overlays = document.querySelectorAll('[role="dialog"], [class*="modal"], [class*="overlay"], [class*="Backdrop"], .modal-open, .modal-backdrop');
                overlays.forEach(o => { try { o.remove(); } catch(e){} });
                
                document.body.classList.remove('modal-open');
                document.body.style.overflow = 'auto';
                document.body.style.paddingRight = '0px';
            """)
        except:
            pass

    def _limpar_termo(self, termo):
        termo_limpo = re.sub(r'\b(lata|pet)\b', '', termo, flags=re.IGNORECASE)
        return re.sub(r'\s+', ' ', termo_limpo).strip()

    def _filtrar_melhor_resultado(self, termo_original, marca, resultados):
        if not resultados:
            return None
            
        termo_lower = termo_original.lower()
        marca_norm = marca.lower()
        marca_variacoes = [marca_norm, marca_norm.replace('-', ' '), marca_norm.replace('-', '')]
        
        # Override manual para a Coca-Cola
        if 'coca' in termo_lower and '2l' in termo_lower:
            for item in resultados:
                t_norm = item['titulo'].lower().replace('-', ' ')
                if 'coca' in t_norm and re.search(r'\b2\s*(l|litros?)\b', t_norm):
                    if not any(w in t_norm for w in ['zero', 'diet', 'sem açúcar', 'sem acucar', 'café', 'cafe']):
                        return item

        busca_zero = any(w in termo_lower for w in ['zero', 'diet', 'light', 'sem açucar', 'sem açúcar'])
        sabores_comuns = ['café', 'cafe', 'cherry', 'baunilha', 'limão', 'limao', 'laranja', 'uva', 'guaraná']
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
            
            if not any(m in titulo_norm for m in marca_variacoes): continue
            if any(re.search(rf'\b{s}\b', titulo_norm) for s in sabores_proibidos): continue
            
            is_zero = any(w in titulo_norm for w in ['zero', 'diet', 'light', 'sem açucar', 'sem açúcar'])
            if busca_zero and not is_zero: continue
            if not busca_zero and is_zero: continue

            # Lata vs Pet
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
                        if v_val == vol_buscado_val: achou_vol_correto = True
                        else: tem_vol_errado = True
                
                if not achou_vol_correto or tem_vol_errado: continue
                
            return item
            
        return None

    def _extrair_anuncios_da_pagina(self, soup):
        anuncios = soup.find_all('div', class_=lambda c: c and 'ProductCardShowcase' in c)
        resultados_validos = []
        
        for anuncio in anuncios:
            link_elem = anuncio.find('a', href=True)
            titulo_elem = anuncio.find(class_=lambda c: c and 'TitleCardComponent' in c)
            preco_elem = anuncio.find(class_=lambda c: c and 'SimplePriceComponent' in c)
            
            if titulo_elem and preco_elem and link_elem:
                titulo = titulo_elem.text.strip()
                preco_raw = preco_elem.text.replace('R$', '').replace('un', '').replace('\xa0', '').replace(',', '.')
                preco_texto = ''.join(c for c in preco_raw if c.isdigit() or c == '.')
                
                try:
                    preco_float = float(preco_texto)
                except:
                    continue
                
                if preco_float <= 0: continue

                link = link_elem['href']
                if link.startswith('/'): link = f"https://www.tendaatacado.com.br{link}"
                    
                resultados_validos.append({
                    "titulo": titulo,
                    "preco": preco_float,
                    "link": link
                })
        
        return resultados_validos

    def extrair_dados(self):
        produtos = self.carregar_produtos_alvo()
        if not produtos: return

        for produto in produtos:
            termo_original = produto['termo_busca']
            marca_alvo = produto['marca']
            termo_formatado = self._limpar_termo(termo_original).replace(' ', '+') 
            url = f"https://www.tendaatacado.com.br/busca?q={termo_formatado}"
            
            self.logger.info(f"Processando busca: {termo_original}")
            
            try:
                self.driver.get(url)
                
                # ROTINA VITRAL RESTAURADA: O Tenda Atacado tem Lazy Loading que requer que a
                # primeira pausa seja ANTES da limpeza e o scroll DEPOIS da limpeza!
                self._fechar_modais_iniciais()
                self.driver.execute_script("window.scrollTo(0, 300);")
                time.sleep(2)
                self.driver.execute_script("window.scrollTo(0, 600);")
                time.sleep(1)
                
                html_renderizado = self.driver.page_source
                soup = BeautifulSoup(html_renderizado, 'html.parser')

                anuncios_brutos = self._extrair_anuncios_da_pagina(soup)

                if not anuncios_brutos:
                    self.logger.warning(f"[AVISO] Nenhum anuncio localizado para: {termo_original}.")
                    continue

                item_data = self._filtrar_melhor_resultado(termo_original, marca_alvo, anuncios_brutos)

                if item_data:
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
                    self.logger.info(f"[SUCESSO] Item capturado: {item_data['titulo'][:30]}... | R${dados_preco['preco_unitario']}")
                else:
                    self.logger.warning(f"[AVISO] Nenhum item atendeu aos criterios para: {termo_original}")
            
            except Exception as e:
                self.logger.error(f"[ERRO] Falha inesperada: {e}")
        
        self.salvar_dados()
        if self.driver: self.driver.quit()

if __name__ == "__main__":
    TendaAtacadoScraper().extrair_dados()
