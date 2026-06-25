import time
import re
import subprocess
import platform
import undetected_chromedriver as uc
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

    def _definir_localizacao(self):
        self.logger.info(f"Iniciando fluxo de localizacao para o CEP: {self.cep_padrao}")
        try:
            # 1. Limpar banner de cookies
            self.driver.execute_script("""
                let cookieBtn = document.querySelector('.cc-allow, [class*="cookie"] button');
                if(cookieBtn) cookieBtn.click();
            """)
            time.sleep(1)

            # 2. Clicar no botão do header
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
                for _ in range(15):
                    ativo.send_keys(Keys.BACKSPACE)
                    ativo.send_keys(Keys.DELETE)
                time.sleep(0.5)

                for char in self.cep_padrao:
                    ativo.send_keys(char)
                    time.sleep(0.1)
                
                time.sleep(1.5)
                self.driver.execute_script("""
                    let searchBtn = document.querySelector('button[aria-label*="Buscar"], button[aria-label*="Search"]');
                    if(searchBtn) searchBtn.click();
                """)
                time.sleep(1)
                ativo.send_keys(Keys.ENTER)
                time.sleep(6) 
            else:
                self.logger.warning("[AVISO] Input de CEP nao foi focado corretamente.")

            # 5. Confirmar loja
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
            
            self.logger.info("[SUCESSO] Localizacao confirmada e ecra libertado.")

        except Exception as e:
            self.logger.error(f"[ERRO] Falha no fluxo de localizacao: {e}")

    def _limpar_termo(self, termo):
        termo_limpo = re.sub(r'\b(lata|pet)\b', '', termo, flags=re.IGNORECASE)
        return re.sub(r'\s+', ' ', termo_limpo).strip()

    def _filtrar_melhor_resultado(self, termo_original, marca, resultados):
        if not resultados:
            return None
            
        termo_lower = termo_original.lower()
        marca_norm = marca.lower()
        marca_variacoes = [marca_norm, marca_norm.replace('-', ' '), marca_norm.replace('-', '')]
        
        # Tratamento especial para Coca-Cola 2L
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

            # 5. Volume Semântico
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

    def extrair_dados(self):
        produtos = self.carregar_produtos_alvo()
        if not produtos: return

        try:
            self.driver.get("https://www.atacadao.com.br/")
            time.sleep(8) 
            
            self._definir_localizacao()

            for produto in produtos:
                termo_original = produto['termo_busca']
                marca_alvo = produto['marca']
                termo_pesquisa = self._limpar_termo(termo_original)
                
                self.logger.info(f"Processando: {termo_pesquisa} | Marca: {marca_alvo}")

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

                    item_data = self._filtrar_melhor_resultado(termo_original, marca_alvo, resultados_dropdown)

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
                            "link": "Extraido via Menu Dropdown"
                        })
                        self.logger.info(f"[SUCESSO] Item capturado: {item_data['titulo'][:30]}... | Preco Unitario: R${dados_norm['preco_unitario']}")
                    else:
                        self.logger.warning(f"[AVISO] Nenhum item atendeu aos criterios para: {termo_original}")
                    
                    ativo.send_keys(Keys.ESCAPE)
                    time.sleep(1.5)
                else:
                    self.logger.error("[ERRO] Barra de pesquisa nao encontrada.")

        except Exception as e:
            self.logger.error(f"[ERRO] Falha na extracao do Atacadao: {e}")
        finally:
            self.salvar_dados()
            if self.driver: self.driver.quit()

if __name__ == "__main__":
    AtacadaoScraper().extrair_dados()