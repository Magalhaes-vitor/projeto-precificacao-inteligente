import time
import re
import subprocess
import platform
import undetected_chromedriver as uc
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By


from base_scraper import BaseScraper

class PaoDeAcucarScraper(BaseScraper):
    def __init__(self):
        super().__init__('PaoDeAcucar')
        self.driver = self._configurar_driver()

    def _obter_versao_chrome(self):
        """Descobre a versão principal do Chrome (Funciona em Windows e Linux)."""
        try:
            if platform.system() == "Windows":
                # Comando para consultar o registo do Windows
                cmd = 'powershell -command "(Get-ItemProperty -Path Registry::HKEY_CURRENT_USER\\Software\\Google\\Chrome\\BLBeacon).version"'
                process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                output, _ = process.communicate()
                versao_completa = output.decode('utf-8').strip()
            else:
                # Comando para Linux (AWS Fargate)
                process = subprocess.Popen(['google-chrome', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                output, _ = process.communicate()
                versao_completa = output.decode('utf-8').strip()
            
            # Extrai apenas os primeiros números
            match = re.search(r'\d+', versao_completa)
            if match:
                versao = int(match.group(0))
                self.logger.info(f"Versão do Chrome detectada dinamicamente: {versao}")
                return versao
                
        except Exception as e:
            self.logger.warning(f"Erro ao detectar versão do Chrome: {e}")
        
        self.logger.warning("Não foi possível detectar a versão do Chrome. Usando padrão.")
        return None

    def _configurar_driver(self):
        """Configura o Chrome Indetetável para bypass de proteção sem usar Xvfb."""
        options = uc.ChromeOptions()
        
        # Flags essenciais para Fargate e modo Headless (Invisível)
        options.add_argument('--headless')
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        
        # Metodo contra estouro de RAM (OOM) no Fargate
        options.add_argument("--disable-site-isolation-trials")
        options.add_argument("--disable-features=IsolateOrigins,site-per-process")
        
        # Oculta logs do terminal
        options.add_argument("--log-level=3")
        
        self.logger.info("Inicializando o motor do Chrome (Undetected)...")
        
        # Arranca o driver indetetável
        versao_dinamica = self._obter_versao_chrome()
        
        if versao_dinamica:
            driver = uc.Chrome(options=options, headless=True, version_main=versao_dinamica)
        else:
            # Fallback caso algo falhe, ele tenta o comportamento normal
            driver = uc.Chrome(options=options, headless=True)
            
        return driver

    def _verificar_captcha(self, soup):
        titulo_pagina = soup.title.text.lower() if soup.title else ""
        if "robot check" in titulo_pagina or soup.find(id="captchacharacters"):
            return True
        return False

    def _resolver_desafio_altcha(self):
        """
        Analisa o DOM para detetar o escudo anti-bot (Altcha) do Pao de Acucar.
        Se encontrado, tenta interagir com a checkbox de validacao.
        """
        try:
            # 1. Verifica rapidamente se a mensagem de bloqueio esta no ecrã (fast fail)
            html = self.driver.page_source.lower()
            if "nosso sistema ficou curioso com o seu acesso" not in html and "altcha-container" not in html:
                return False # Não ha captcha, tudo ok!

            self.logger.warning("[AVISO] Desafio de WAF (Altcha) detetado no Pao de Acucar. Iniciando evasão...")
            
            # 2. Localiza o Shadow DOM ou o componente web do Altcha e a checkbox
            self.driver.execute_script("""
                // Tenta encontrar a checkbox padrão ou dentro de Web Components
                let checkbox = document.querySelector('#altcha_checkbox') || document.querySelector('input[type="checkbox"]');
                if(checkbox){
                    // Força um scroll ate ao elemento para garantir interacao
                    checkbox.scrollIntoView({behavior: "smooth", block: "center"});
                    
                    // Clica usando JavaScript para furar possíveis overlays
                    checkbox.click();
                } else {
                    // Tenta clicar no rotulo associado
                    let label = document.querySelector('label[for="altcha_checkbox"]');
                    if(label) label.click();
                }
            """)
            
            self.logger.info("[INFO] Clique de verificacao enviado. Aguardando a validacao de token do servidor...")
            
            # 3. O Altcha requer prova de trabalho criptográfica (PoW) que leva uns segundos no browser
            # Aguardamos ate 12 segundos para a página recarregar ou para a mensagem "Verificado!" aparecer
            tempo_espera = 0
            while tempo_espera < 12:
                time.sleep(2)
                html_atual = self.driver.page_source.lower()
                
                # Se encontrou a vitrine de produtos, ja passamos!
                if "cardstyled" in html_atual or "productcard" in html_atual:
                    self.logger.info("[SUCESSO] Desafio WAF superado. Redirecionamento completo.")
                    return True
                    
                tempo_espera += 2
                
            self.logger.warning("[AVISO] Tempo limite de evasao esgotado. A tentar prosseguir cego...")
            return True

        except Exception as e:
            self.logger.error(f"[ERRO] Falha ao tentar resolver o desafio Altcha: {e}")
            return False

    def _limpar_termo(self, termo):
        return re.sub(r'\s+', ' ', termo).strip()

    def _filtrar_melhor_resultado(self, termo_original, marca, resultados):
        if not resultados:
            return None
            
        termo_lower = termo_original.lower()
        marca_norm = marca.lower()
        marca_variacoes = [marca_norm, marca_norm.replace('-', ' '), marca_norm.replace('-', '')]

        # Tratamento especial para Coca-Cola 2L (Evitar rejeicao rigida)
        if 'coca' in termo_lower and '2l' in termo_lower:
            for item in resultados:
                t_norm = item['titulo'].lower().replace('-', ' ')
                if 'coca' in t_norm and re.search(r'\b2\s*(l|litros?)\b', t_norm):
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
            
            # 1. Filtro de Marca
            if not any(m in titulo_norm for m in marca_variacoes):
                continue
                
            # 2. Rejeicao de Sabores
            if any(re.search(rf'\b{s}\b', titulo_norm) for s in sabores_proibidos):
                continue
            
            # 3. Filtro Zero/Diet
            is_zero = any(w in titulo_norm for w in ['zero', 'diet', 'light', 'sem açucar', 'sem açúcar'])
            if busca_zero and not is_zero: continue
            if not busca_zero and is_zero: continue
            
            # 4. Lata vs Pet
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
        cards = soup.find_all('div', class_=lambda c: c and 'CardStyled' in c)
        resultados_validos = []
        
        for card in cards:
            if card.find('p', class_=lambda c: c and 'StockOutLabel' in c):
                continue 

            titulo_elem = card.find('a', class_=lambda c: c and 'Title' in c)
            if not titulo_elem: continue
            titulo = titulo_elem.text.strip()
            if not titulo: continue

            preco_elem = card.find('p', class_=lambda c: c and 'PriceValue' in c)
            if not preco_elem: continue
            
            preco_texto = preco_elem.text
            val = preco_texto.replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
            try:
                clean_val = ''.join(c for c in val if c.isdigit() or c == '.')
                preco_float = float(clean_val)
            except:
                continue
            
            if preco_float > 5000 or preco_float <= 0: continue

            link = titulo_elem.get('href', 'Link Indisponivel')
            if link.startswith('/'):
                link = f"https://www.paodeacucar.com{link}"
                
            resultados_validos.append({
                "titulo": titulo,
                "preco": preco_float,
                "link": link
            })
        
        unicos = {item['link']: item for item in resultados_validos if item['link'] != "Link Indisponivel"}.values()
        return list(unicos)

    def extrair_dados(self):
        produtos = self.carregar_produtos_alvo()
        if not produtos: return

        for produto in produtos:
            termo_original = produto['termo_busca']
            marca_alvo = produto['marca']
            termo_pesquisa = self._limpar_termo(termo_original)
            
            termo_formatado = termo_pesquisa.replace(' ', '%20') 
            url = f"https://www.paodeacucar.com/busca?w={termo_formatado}"
            
            self.logger.info(f"Processando extracao para: {termo_original} | Marca: {marca_alvo}")
            
            try:
                self.driver.get(url)
                time.sleep(4) 
                
                # ROTINA DE ANTI-BOT / CAPTCHA (ALTCHA)
                self._resolver_desafio_altcha()

                self.driver.execute_script("window.scrollBy(0, 400);")
                time.sleep(1)
                self.driver.execute_script("window.scrollBy(0, 400);")
                time.sleep(3)
                
                html_renderizado = self.driver.page_source
                soup = BeautifulSoup(html_renderizado, 'html.parser')

                resultados_brutos = self._extrair_anuncios_da_pagina(soup)

                if not resultados_brutos:
                    self.logger.warning(f"[AVISO] Sem anuncios localizados na vitrine para: {termo_original}.")
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
                    self.logger.info(f"[SUCESSO] Item capturado: {item_data['titulo'][:40]}... | Preco Unitario: R${dados_preco['preco_unitario']}")
                else:
                    self.logger.warning(f"[AVISO] Nenhum item atendeu aos criterios de filtro para: {termo_original}.")
            
            except Exception as e:
                self.logger.error(f"[ERRO] Falha inesperada durante a extracao: {e}")
        
        self.salvar_dados()
        if self.driver: 
            self.driver.quit()

if __name__ == "__main__":
    PaoDeAcucarScraper().extrair_dados()