import os
import re
import pandas as pd
import pdfplumber
import streamlit as st

# --- Configuração Inicial da Página ---
st.set_page_config(
    page_title="Extrator Inteligente de Base IRRF",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Estilização CSS: Fundo Escuro + Textos em Verde Esmeralda Neon ---
st.markdown("""
    <style>
    .stApp {
        background-color: #090d16;
        color: #00ffcc !important;
    }
    h1, h2, h3, h4, h5, h6, p, span, label, div, .stMarkdown, .stText {
        color: #00ffcc !important;
        font-family: 'Inter', sans-serif;
    }
    input, select, textarea {
        color: #00ffcc !important;
        background-color: #111827 !important;
        border-color: #00ffcc !important;
    }
    .stButton>button {
        border-radius: 12px;
        font-weight: 700;
        background: linear-gradient(135deg, #00ffcc 0%, #00b386 100%);
        color: #090d16 !important;
        border: none;
        padding: 0.6rem 1.4rem;
        box-shadow: 0 4px 15px rgba(0, 255, 204, 0.4);
        transition: all 0.3s ease;
        width: 100%;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #00b386 100%, #008060 100%);
        box-shadow: 0 6px 20px rgba(0, 255, 204, 0.6);
        transform: translateY(-2px);
    }
    .custom-card {
        background-color: #111827;
        padding: 1.5rem;
        border-radius: 16px;
        box-shadow: 0 4px 20px -2px rgba(0, 255, 204, 0.1);
        border: 1px solid rgba(0, 255, 204, 0.3);
        margin-bottom: 1rem;
    }
    [data-testid="stSidebar"] {
        background-color: #0d1322;
        color: #00ffcc !important;
        border-right: 1px solid rgba(0, 255, 204, 0.2);
    }
    [data-testid="stSidebar"] * {
        color: #00ffcc !important;
    }
    [data-testid="stMetricValue"] {
        color: #00ffcc !important;
        text-shadow: 0 0 10px rgba(0, 255, 204, 0.5);
    }
    [data-testid="stFileUploader"] {
        background-color: #111827;
        border: 2px dashed rgba(0, 255, 204, 0.4);
        border-radius: 12px;
        padding: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

def converter_competencia_aaamm(competencia_str):
    comp_limpa = re.sub(r'\D', '', competencia_str)
    if '/' in competencia_str:
        partes = competencia_str.split('/')
        if len(partes) == 2:
            mes, ano = partes[0].zfill(2), partes[1]
            return f"{ano}{mes}"
    if len(comp_limpa) == 6:
        mes = comp_limpa[:2]
        ano = comp_limpa[2:]
        return f"{ano}{mes}"
    return comp_limpa.zfill(6)[:6]

def extrator_fallback_universal(caminho_pdf, codigo_empresa, codigo_rubrica, competencia, nome_sistema):
    dados_funcionarios = []
    with pdfplumber.open(caminho_pdf) as pdf:
        texto_completo = "".join([p.extract_text() + "\n" for p in pdf.pages if p.extract_text()])
    
    if not texto_completo.strip():
        return pd.DataFrame()

    linhas = [l.strip() for l in texto_completo.split("\n") if l.strip()]
    padrao_valor = re.compile(r"([\d\.]+,\d{2})")
    
    emp_id = "1"
    nome = "Funcionário Geral"
    
    for idx, linha in enumerate(linhas):
        if any(termo in linha.upper() for termo in ["TOTAL", "PÁGINA", "CNPJ", "RELATÓRIO", "EMPRESA"]):
            continue
            
        valores = padrao_valor.findall(linha)
        if valores:
            partes_linha = linha.split()
            if partes_linha and partes_linha[0].isdigit() and len(partes_linha[0]) <= 5:
                emp_id = partes_linha[0]
                if len(partes_linha) > 1:
                    nome = " ".join([p for p in partes_linha[1:] if not padrao_valor.search(p)])
                    if not nome.strip():
                        nome = f"Funcionário {emp_id}"
            
            base_irrf = valores[-1]
            
            if not any(d.get('Código Empregado') == emp_id and d.get('Base IRRF') == base_irrf for d in dados_funcionarios):
                dados_funcionarios.append({
                    "Empresa": str(codigo_empresa).strip(),
                    "Código Empregado": emp_id,
                    "Funcionário": nome[:40],
                    "CPF": f"N/D ({nome_sistema})",
                    "Competência": competencia.strip(),
                    "Base IRRF": base_irrf,
                    "Código Rubrica": str(codigo_rubrica).strip()
                })
                
    return pd.DataFrame(dados_funcionarios)

def extrair_dados_extrato_exactus(caminho_pdf, codigo_empresa="1", codigo_rubrica="2000", competencia=""):
    try:
        dados_funcionarios = []
        with pdfplumber.open(caminho_pdf) as pdf:
            texto_completo = "".join([p.extract_text() + "\n" for p in pdf.pages if p.extract_text()])
        if not texto_completo.strip(): 
            return pd.DataFrame()

        partes_texto = re.split(r"(?=\d{4,5}\.\d{3}\s*-)", texto_completo)
        padrao_cabecalho = re.compile(r"^(\d{4,5}\.\d{3})\s*-\s*(.+)", re.IGNORECASE)
        padrao_cpf = re.compile(r"CPF\s*(\d{3}\.\d{3}\.\d{3}-\d{2})", re.IGNORECASE)

        for bloco in partes_texto:
            if not bloco.strip(): 
                continue
            if "TOTAL GERAL" in bloco.upper() or "RESUMO TRIBUTÁRIO" in bloco.upper():
                continue
            
            linhas = [l.strip() for l in bloco.split("\n") if l.strip()]
            if not linhas:
                continue

            match_cab = padrao_cabecalho.search(linhas[0])
            if not match_cab:
                continue

            emp_id = match_cab.group(1).strip()
            nome_func = match_cab.group(2).strip()

            match_cpf = padrao_cpf.search(bloco)
            cpf = match_cpf.group(1).strip() if match_cpf else "N/D (Exactus)"

            # Varredura refinada para encontrar a linha "IRRF R.M." e capturar o valor associado (ex: 1.984,27)
            base_irrf = "0,00"
            for i, linha in enumerate(linhas):
                if "IRRF R.M." in linha.upper():
                    # Procura todos os valores monetários na linha do IRRF R.M. ou logo abaixo
                    valores_linha = re.findall(r"([\d\.]+,\d{2})", linha)
                    if valores_linha:
                        # Pega o último valor numérico da linha de IRRF R.M. (geralmente o valor da base/rendimento)
                        base_irrf = valores_linha[-1]
                        break
                    elif i + 1 < len(linhas):
                        valores_prox = re.findall(r"([\d\.]+,\d{2})", linhas[i + 1])
                        if valores_prox:
                            base_irrf = valores_prox[-1]
                            break

            if emp_id and not any(d.get('Código Empregado') == emp_id for d in dados_funcionarios):
                dados_funcionarios.append({
                    "Empresa": str(codigo_empresa).strip(),
                    "Código Empregado": emp_id,
                    "Funcionário": nome_func[:40],
                    "CPF": cpf,
                    "Competência": competencia.strip(),
                    "Base IRRF": base_irrf,
                    "Código Rubrica": str(codigo_rubrica).strip()
                })

        df = pd.DataFrame(dados_funcionarios)
        if df.empty:
            return extrator_fallback_universal(caminho_pdf, codigo_empresa, codigo_rubrica, competencia, "Exactus")
        return df
    except Exception:
        return extrator_fallback_universal(caminho_pdf, codigo_empresa, codigo_rubrica, competencia, "Exactus")

def extrair_dados_extrato_iob(caminho_pdf, codigo_empresa="1", codigo_rubrica="2000", competencia=""):
    try:
        dados_funcionarios = []
        with pdfplumber.open(caminho_pdf) as pdf:
            texto_completo = "".join([p.extract_text() + "\n" for p in pdf.pages if p.extract_text()])
        if not texto_completo.strip(): 
            return pd.DataFrame()

        partes_texto = re.split(r"(?=Funcionário:\s*\d+)", texto_completo, flags=re.IGNORECASE)
        padrao_func = re.compile(r"Funcionário:\s*(\d+)\s*(?:-|[A-ZÀ-Ú\s]+)?([A-ZÀ-Ú\s]+)", re.IGNORECASE)

        for bloco in partes_texto:
            if not bloco.strip(): 
                continue
            if "TOTAL GERAL" in bloco.upper() or "TOTALIZAÇÃO DA FOLHA" in bloco.upper():
                continue
            
            match_func = padrao_func.search(bloco)
            if not match_func: 
                continue
            
            emp_id = match_func.group(1).strip()
            linha_func = bloco.split('\n')[0] if '\n' in bloco else bloco
            if '-' in linha_func:
                partes_nome = linha_func.split('-')
                if len(partes_nome) >= 2:
                    nome_completo = partes_nome[1].split("Adm:")[0].split("Função:")[0].strip()
                else:
                    nome_completo = "Funcionário"
            else:
                nome_completo = "Funcionário"
            nome_limpo = " ".join(nome_completo.split())

            base_irrf = "0,00"
            pos_base = bloco.find("Base Bruta de IRRF")
            if pos_base != -1:
                trecho_apos = bloco[pos_base:]
                match_val = re.search(r"([\d\.]+,\d{2})", trecho_apos)
                if match_val:
                    base_irrf = match_val.group(1)

            if emp_id and not any(d.get('Código Empregado') == emp_id for d in dados_funcionarios):
                dados_funcionarios.append({
                    "Empresa": str(codigo_empresa).strip(),
                    "Código Empregado": emp_id,
                    "Funcionário": nome_limpo[:40],
                    "CPF": "N/D (IOB)",
                    "Competência": competencia.strip(),
                    "Base IRRF": base_irrf,
                    "Código Rubrica": str(codigo_rubrica).strip()
                })

        df = pd.DataFrame(dados_funcionarios)
        if df.empty:
            return extrator_fallback_universal(caminho_pdf, codigo_empresa, codigo_rubrica, competencia, "IOB")
        return df
    except Exception:
        return extrator_fallback_universal(caminho_pdf, codigo_empresa, codigo_rubrica, competencia, "IOB")

def extrair_dados_extrato_dominio(caminho_pdf, codigo_empresa="1", codigo_rubrica="2000", competencia=""):
    try:
        dados_funcionarios = []
        with pdfplumber.open(caminho_pdf) as pdf:
            texto_completo = "".join([p.extract_text() + "\n" for p in pdf.pages if p.extract_text()])
        if not texto_completo.strip(): return pd.DataFrame()
        partes_texto = re.split(r"(?=Empr\.?:?\s*\d+)", texto_completo, flags=re.IGNORECASE)
        padrao_emp = re.compile(r"Empr\.?:?\s*(\d+)", re.IGNORECASE)
        padrao_cpf = re.compile(r"(\d{3}\.\d{3}\.\d{3}-\d{2})")
        padrao_base_irrf = re.compile(r"(?:Base\s*(?:de\s*Cálculo\s*)?(?:do\s*)?IRRF|Base\s*Calc\.?\s*IRRF|IRRF\s*Base)[:\s\n]*([\d\.]+,\d{2})", re.IGNORECASE)
        for bloco in partes_texto:
            if not bloco.strip(): continue
            match_emp, match_cpf = padrao_emp.search(bloco), padrao_cpf.search(bloco)
            if not match_cpf: continue
            
            emp_id = match_emp.group(1).strip() if match_emp else "1"
            cpf = match_cpf.group(1).strip()
            
            match_base = padrao_base_irrf.search(bloco)
            base_irrf = match_base.group(1).strip() if match_base else "0,00"
            linhas = [l.strip() for l in bloco.split("\n") if l.strip()]
            nome = "Funcionário"
            for linha in linhas:
                if "Empr" in linha or "Empresa" in linha:
                    txt_limpo = re.sub(r"Empr\.?:?\s*\d+", "", linha, flags=re.IGNORECASE).strip()
                    if len(txt_limpo) > 2:
                        nome = txt_limpo
                        break
            if not any(d.get('CPF') == cpf and d.get('Código Empregado') == emp_id for d in dados_funcionarios):
                dados_funcionarios.append({
                    "Empresa": str(codigo_empresa).strip(), "Código Empregado": emp_id,
                    "Funcionário": nome, "CPF": cpf, "Competência": competencia.strip(),
                    "Base IRRF": base_irrf, "Código Rubrica": str(codigo_rubrica).strip()
                })
        df = pd.DataFrame(dados_funcionarios)
        if df.empty:
            return extrator_fallback_universal(caminho_pdf, codigo_empresa, codigo_rubrica, competencia, "Domínio")
        return df
    except Exception:
        return extrator_fallback_universal(caminho_pdf, codigo_empresa, codigo_rubrica, competencia, "Domínio")

def extrair_dados_extrato_contmatic(caminho_pdf, codigo_empresa="1", codigo_rubrica="2000", competencia=""):
    try:
        dados_funcionarios = []
        with pdfplumber.open(caminho_pdf) as pdf:
            texto_completo = "".join([p.extract_text() + "\n" for p in pdf.pages if p.extract_text()])
        if not texto_completo.strip(): return pd.DataFrame()
        partes_texto = re.split(r"(?=Cód:\s*\d+)", texto_completo, flags=re.IGNORECASE)
        padrao_cod = re.compile(r"Cód:\s*(\d+)", re.IGNORECASE)
        padrao_base_irrf = re.compile(r"Base\s*I\.R\.R\.F\.?:?[\s\n]*([\d\.]+,\d{2})", re.IGNORECASE)
        for bloco in partes_texto:
            if not bloco.strip(): continue
            match_cod = padrao_cod.search(bloco)
            if not match_cod: continue
            
            emp_id = match_cod.group(1).strip()
            match_base = padrao_base_irrf.search(bloco)
            base_irrf = match_base.group(1).strip() if match_base else "0,00"
            linhas = [l.strip() for l in bloco.split("\n") if l.strip()]
            nome = "Funcionário"
            for i, linha in enumerate(linhas):
                if "Nome:" in linha:
                    nome = linha.replace("Nome:", "").strip()
                    break
                elif "Cód:" in linha and i + 1 < len(linhas):
                    possivel_nome = linhas[i+1]
                    if "Função:" in possivel_nome or len(possivel_nome) > 3:
                        nome = possivel_nome.split("Função:")[0].strip()
                        break
            if emp_id:
                dados_funcionarios.append({
                    "Empresa": str(codigo_empresa).strip(), "Código Empregado": emp_id,
                    "Funcionário": nome, "CPF": "N/D (Contmatic)", "Competência": competencia.strip(),
                    "Base IRRF": base_irrf, "Código Rubrica": str(codigo_rubrica).strip()
                })
        df = pd.DataFrame(dados_funcionarios)
        if df.empty:
            return extrator_fallback_universal(caminho_pdf, codigo_empresa, codigo_rubrica, competencia, "Contmatic")
        return df
    except Exception:
        return extrator_fallback_universal(caminho_pdf, codigo_empresa, codigo_rubrica, competencia, "Contmatic")

def extrair_dados_extrato_alterdata(caminho_pdf, codigo_empresa="1", codigo_rubrica="2000", competencia=""):
    try:
        dados_funcionarios = []
        with pdfplumber.open(caminho_pdf) as pdf:
            texto_completo = "".join([p.extract_text() + "\n" for p in pdf.pages if p.extract_text()])
        if not texto_completo.strip(): return pd.DataFrame()
        partes_bloco = re.split(r"(?=\b\d{5}\b.*?(\d{3}\.\d{3}\.\d{3}-\d{2}))", texto_completo, flags=re.DOTALL)
        padrao_empregado_cpf = re.compile(r"\b(\d{5})\b.*?(\d{3}\.\d{3}\.\d{3}-\d{2})")
        padrao_base_irrf_estrito = re.compile(r"Base\s*IRRF\s*[:\s]*([\d\.]+,\d{2})", re.IGNORECASE)
        for bloco in partes_bloco:
            if not bloco.strip(): continue
            match_emp_cpf = padrao_empregado_cpf.search(bloco)
            if not match_emp_cpf: continue
            
            emp_id = match_emp_cpf.group(1).strip()
            cpf = match_emp_cpf.group(2).strip()
            
            linhas = [l.strip() for l in bloco.split("\n") if l.strip()]
            nome = "Funcionário"
            for linha in linhas:
                if cpf in linha:
                    resto = linha.replace(cpf, "").strip()
                    if len(resto) > 2:
                        nome = resto
                        break
            base_irrf = "0,00"
            match_base = padrao_base_irrf_estrito.search(bloco)
            if match_base:
                base_irrf = match_base.group(1).strip()
            if emp_id and not any(d.get('CPF') == cpf and d.get('Código Empregado') == emp_id for d in dados_funcionarios):
                dados_funcionarios.append({
                    "Empresa": str(codigo_empresa).strip(), "Código Empregado": emp_id,
                    "Funcionário": nome, "CPF": cpf, "Competência": competencia.strip(),
                    "Base IRRF": base_irrf, "Código Rubrica": str(codigo_rubrica).strip()
                })
        df = pd.DataFrame(dados_funcionarios)
        if df.empty:
            return extrator_fallback_universal(caminho_pdf, codigo_empresa, codigo_rubrica, competencia, "Alterdata")
        return df
    except Exception:
        return extrator_fallback_universal(caminho_pdf, codigo_empresa, codigo_rubrica, competencia, "Alterdata")

def extrair_dados_extrato_sci(caminho_pdf, codigo_empresa="1", codigo_rubrica="2000", competencia=""):
    try:
        dados_funcionarios = []
        with pdfplumber.open(caminho_pdf) as pdf:
            texto_completo = "".join([p.extract_text() + "\n" for p in pdf.pages if p.extract_text()])
        if not texto_completo.strip(): 
            return pd.DataFrame()

        linhas = [l.strip() for l in texto_completo.split("\n") if l.strip()]
        i = 0
        while i < len(linhas):
            linha = linhas[i]
            if "ADMITIDO EM" in linha.upper():
                match_func = re.search(r"^(\d+)\s+(.+?)\s+Admitido em", linha, re.IGNORECASE)
                if match_func:
                    emp_id = match_func.group(1).strip()
                    nome_func = match_func.group(2).strip()
                    nome_func = re.sub(r"\s+\d+\s*\d*$", "", nome_func).strip()
                    
                    base_irrf = "0,00"
                    j = i
                    while j < len(linhas) and (j == i or "ADMITIDO EM" not in linhas[j].upper()):
                        linha_atual = linhas[j]
                        if "IR ->" in linha_atual.upper():
                            partes_ir = linha_atual.upper().split("IR ->")
                            if len(partes_ir) > 1:
                                val_match = re.findall(r"([\d\.]+,\d{2})", partes_ir[1])
                                if val_match:
                                    base_irrf = val_match[0]
                                    break
                            elif j + 1 < len(linhas):
                                val_match_prox = re.findall(r"([\d\.]+,\d{2})", linhas[j+1])
                                if val_match_prox:
                                    base_irrf = val_match_prox[0]
                                    break
                        j += 1
                        
                    if not any(d.get('Código Empregado') == emp_id and d.get('Base IRRF') == base_irrf for d in dados_funcionarios):
                        dados_funcionarios.append({
                            "Empresa": str(codigo_empresa).strip(),
                            "Código Empregado": emp_id,
                            "Funcionário": nome_func[:40],
                            "CPF": "N/D (SCI)",
                            "Competência": competencia.strip(),
                            "Base IRRF": base_irrf,
                            "Código Rubrica": str(codigo_rubrica).strip()
                        })
            i += 1

        df = pd.DataFrame(dados_funcionarios)
        if df.empty:
            return extrator_fallback_universal(caminho_pdf, codigo_empresa, codigo_rubrica, competencia, "SCI")
        return df
    except Exception:
        return extrator_fallback_universal(caminho_pdf, codigo_empresa, codigo_rubrica, competencia, "SCI")

def extrair_dados_extrato_prosol(caminho_pdf, codigo_empresa="1", codigo_rubrica="2000", competencia=""):
    try:
        dados_funcionarios = []
        with pdfplumber.open(caminho_pdf) as pdf:
            texto_completo = "".join([p.extract_text() + "\n" for p in pdf.pages if p.extract_text()])
        if not texto_completo.strip(): return pd.DataFrame()
        linhas = [l.strip() for l in texto_completo.split("\n") if l.strip()]
        emp_id, nome, base_irrf = None, "Funcionário", "0,00"
        padrao_codigo_nome = re.compile(r"^(\d+)-([A-ZÀ-Ú\s]+)", re.IGNORECASE)
        padrao_base_irrf_prosol = re.compile(r"0105\s+BASE\s+DE\s+CALCULO\s+I\.R\.R\.F\.?", re.IGNORECASE)
        padrao_valor = re.compile(r"([\d\.]+,\d{2})")
        i = 0
        while i < len(linhas):
            linha = linhas[i]
            match_cod_nome = padrao_codigo_nome.search(linha)
            if match_cod_nome:
                emp_id = match_cod_nome.group(1).strip()
                nome = match_cod_nome.group(2).strip()
                base_irrf = "0,00"
            if padrao_base_irrf_prosol.search(linha):
                valores_encontrados = padrao_valor.findall(linha)
                if not valores_encontrados and i + 1 < len(linhas):
                    valores_encontrados = padrao_valor.findall(linhas[i+1])
                if valores_encontrados:
                    base_irrf = valores_encontrados[1] if len(valores_encontrados) >= 2 else valores_encontrados[0]
                if emp_id:
                    dados_funcionarios.append({
                        "Empresa": str(codigo_empresa).strip(), "Código Empregado": emp_id,
                        "Funcionário": nome, "CPF": "N/D (Prosol)", "Competência": competencia.strip(),
                        "Base IRRF": base_irrf, "Código Rubrica": str(codigo_rubrica).strip()
                    })
            i += 1
        df = pd.DataFrame(dados_funcionarios)
        if df.empty:
            return extrator_fallback_universal(caminho_pdf, codigo_empresa, codigo_rubrica, competencia, "Prosol")
        return df
    except Exception:
        return extrator_fallback_universal(caminho_pdf, codigo_empresa, codigo_rubrica, competencia, "Prosol")

def extrair_dados_extrato_questor(caminho_pdf, codigo_empresa="1", codigo_rubrica="2000", competencia=""):
    try:
        dados_funcionarios = []
        with pdfplumber.open(caminho_pdf) as pdf:
            texto_completo = "".join([p.extract_text() + "\n" for p in pdf.pages if p.extract_text()])
        if not texto_completo.strip(): return pd.DataFrame()
        partes_texto = re.split(r"(?=Func:\s*\n?\d+)", texto_completo, flags=re.IGNORECASE)
        padrao_func = re.compile(r"Func:\s*\n?(\d+)\s+([A-ZÀ-Ú\s]+)", re.IGNORECASE)
        padrao_base_impostos_irrf = re.compile(r"Base\s+Impostos.*?IRRF\s+([\d\.]+,\d{2})", re.IGNORECASE | re.DOTALL)
        for bloco in partes_texto:
            if not bloco.strip(): continue
            match_func = padrao_func.search(bloco)
            if not match_func: continue
            
            emp_id = match_func.group(1).strip()
            nome = match_func.group(2).strip()
            
            match_base = padrao_base_impostos_irrf.search(bloco)
            base_irrf = match_base.group(1).strip() if match_base else "0,00"
            if emp_id and not any(d.get('Código Empregado') == emp_id for d in dados_funcionarios):
                dados_funcionarios.append({
                    "Empresa": str(codigo_empresa).strip(), "Código Empregado": emp_id,
                    "Funcionário": nome, "CPF": "N/D (Questor)", "Competência": competencia.strip(),
                    "Base IRRF": base_irrf, "Código Rubrica": str(codigo_rubrica).strip()
                })
        df = pd.DataFrame(dados_funcionarios)
        if df.empty:
            return extrator_fallback_universal(caminho_pdf, codigo_empresa, codigo_rubrica, competencia, "Questor")
        return df
    except Exception:
        return extrator_fallback_universal(caminho_pdf, codigo_empresa, codigo_rubrica, competencia, "Questor")

def extrair_dados_extrato_cucafresca(caminho_pdf, codigo_empresa="1", codigo_rubrica="2000", competencia=""):
    try:
        dados_funcionarios = []
        with pdfplumber.open(caminho_pdf) as pdf:
            texto_completo = "".join([p.extract_text() + "\n" for p in pdf.pages if p.extract_text()])
        if not texto_completo.strip(): return pd.DataFrame()
        partes_texto = re.split(r"(?=\b\d+\s+[A-ZÀ-Ú\s]+\s+\d{4}-\d{2})", texto_completo, flags=re.IGNORECASE)
        padrao_emp_nome = re.compile(r"(\d+)\s+([A-ZÀ-Ú\s]+?)\s+(\d{4}-\d{2})", re.IGNORECASE)
        padrao_cpf = re.compile(r"CPF:\s*(\d{3}\.\d{3}\.\d{3}-\d{2})", re.IGNORECASE)
        for bloco in partes_texto:
            if not bloco.strip(): continue
            match_emp_nome = padrao_emp_nome.search(bloco)
            if not match_emp_nome: continue
            
            emp_id = match_emp_nome.group(1).strip()
            nome = match_emp_nome.group(2).strip()
            
            match_cpf = padrao_cpf.search(bloco)
            cpf = match_cpf.group(1).strip() if match_cpf else "N/D (Cuca Fresca)"
            base_irrf = "0,00"
            linhas = [l.strip() for l in bloco.split("\n") if l.strip()]
            for i, linha in enumerate(linhas):
                if "Salário Base" in linha or "Base FGTS" in linha or "Base IRRF" in linha:
                    textos_para_analisar = [linha]
                    if i + 1 < len(linhas): textos_para_analisar.append(linhas[i+1])
                    if i + 2 < len(linhas): textos_para_analisar.append(linhas[i+2])
                    todos_valores = []
                    for t in textos_para_analisar:
                        encontrados = re.findall(r"([\d\.]+,\d{2})", t)
                        if encontrados: todos_valores.extend(encontrados)
                    if len(todos_valores) >= 5:
                        base_irrf = todos_valores[4] if len(todos_valores) >= 5 else todos_valores[-3]
                        break
                    elif todos_valores:
                        base_irrf = todos_valores[-1]
                        break
            if emp_id and not any(d.get('Código Empregado') == emp_id and d.get('CPF') == cpf for d in dados_funcionarios):
                dados_funcionarios.append({
                    "Empresa": str(codigo_empresa).strip(), "Código Empregado": emp_id,
                    "Funcionário": nome, "CPF": cpf, "Competência": competencia.strip(),
                    "Base IRRF": base_irrf, "Código Rubrica": str(codigo_rubrica).strip()
                })
        df = pd.DataFrame(dados_funcionarios)
        if df.empty:
            return extrator_fallback_universal(caminho_pdf, codigo_empresa, codigo_rubrica, competencia, "Cuca Fresca")
        return df
    except Exception:
        return extrator_fallback_universal(caminho_pdf, codigo_empresa, codigo_rubrica, competencia, "Cuca Fresca")

def gerar_linha_posicional(row):
    f_fixo = "10"
    f_emp = str(row['Código Empregado']).zfill(10)[:10]
    f_comp = converter_competencia_aaamm(row['Competência'])
    f_rubrica = str(row['Código Rubrica']).zfill(9)[:9]
    f_proc = "41"
    val_limpo = re.sub(r'[^\d]', '', str(row['Base IRRF']))
    f_valor = val_limpo.zfill(9)[:9]
    f_empresa = str(row['Empresa']).zfill(10)[:10]
    return f"{f_fixo}{f_emp}{f_comp}{f_rubrica}{f_proc}{f_valor}{f_empresa}\n"

# --- Sidebar ---
with st.sidebar:
    st.markdown("### ⚙️ Painel de Controle")
    sistema_cliente = st.selectbox(
        "🏢 Sistema / Leiaute:",
        ["Questor", "Domínio (Thomson Reuters)", "Contmatic Phoenix", "Alterdata", "SCI Contábil", "Prosol", "Cuca Fresca", "Exactus", "IOB"]
    )
    st.markdown("---")
    codigo_empresa_input = st.text_input("🔢 Código da Empresa:", value="1")
    codigo_rubrica = st.text_input("🏷️ Código da Rubrica (TXT):", value="2000")
    competencia_input = st.text_input("📅 Competência (MM/AAAA):", value="09/2026")

# --- Interface Principal ---
st.title("⚡ Extrator Inteligente de Base IRRF")
st.markdown("Transforme extratos de folha de pagamento em **layouts TXT posicionais e planilhas de conferência** com inteligência e precisão em segundos.")

st.markdown('<div class="custom-card">', unsafe_allow_html=True)
st.markdown("### 📂 Upload de Extratos (PDF)")
arquivos_pdf = st.file_uploader("Arraste ou selecione os arquivos PDF aqui", type=["pdf"], accept_multiple_files=True, label_visibility="collapsed")
st.markdown('</div>', unsafe_allow_html=True)

# Inicializa o session_state para persistir os dados editados sem resetar
if "df_editado" not in st.session_state:
    st.session_state.df_editado = None

if arquivos_pdf and st.button("🚀 Processar Extratos e Gerar Arquivos"):
    todos_dados = []
    with st.spinner("Processando arquivos com inteligência de leiaute... Por favor, aguarde ⏳"):
        for arquivo in arquivos_pdf:
            caminho_temp = os.path.join("temp", arquivo.name)
            os.makedirs("temp", exist_ok=True)
            with open(caminho_temp, "wb") as f:
                f.write(arquivo.getbuffer())
                
            if "Questor" in sistema_cliente:
                df_extrato = extrair_dados_extrato_questor(caminho_temp, codigo_empresa_input, codigo_rubrica, competencia_input)
            elif "Domínio" in sistema_cliente:
                df_extrato = extrair_dados_extrato_dominio(caminho_temp, codigo_empresa_input, codigo_rubrica, competencia_input)
            elif "Contmatic" in sistema_cliente:
                df_extrato = extrair_dados_extrato_contmatic(caminho_temp, codigo_empresa_input, codigo_rubrica, competencia_input)
            elif "Alterdata" in sistema_cliente:
                df_extrato = extrair_dados_extrato_alterdata(caminho_temp, codigo_empresa_input, codigo_rubrica, competencia_input)
            elif "SCI" in sistema_cliente:
                df_extrato = extrair_dados_extrato_sci(caminho_temp, codigo_empresa_input, codigo_rubrica, competencia_input)
            elif "Prosol" in sistema_cliente:
                df_extrato = extrair_dados_extrato_prosol(caminho_temp, codigo_empresa_input, codigo_rubrica, competencia_input)
            elif "Cuca Fresca" in sistema_cliente:
                df_extrato = extrair_dados_extrato_cucafresca(caminho_temp, codigo_empresa_input, codigo_rubrica, competencia_input)
            elif "Exactus" in sistema_cliente:
                df_extrato = extrair_dados_extrato_exactus(caminho_temp, codigo_empresa_input, codigo_rubrica, competencia_input)
            elif "IOB" in sistema_cliente:
                df_extrato = extrair_dados_extrato_iob(caminho_temp, codigo_empresa_input, codigo_rubrica, competencia_input)
            else:
                df_extrato = pd.DataFrame()
                
            if not df_extrato.empty:
                df_extrato["Arquivo Origem"] = arquivo.name
                todos_dados.append(df_extrato)
            os.remove(caminho_temp)
            
    if todos_dados:
        df_bruto = pd.concat(todos_dados, ignore_index=True)
        if df_bruto.empty:
            st.warning("⚠️ Nenhum dado foi extraído. Verifique se o PDF contém texto legível (não escaneado como imagem).")
            st.session_state.df_editado = None
        else:
            st.session_state.df_editado = df_bruto
    else:
        st.warning("⚠ Nenhum dado válido foi encontrado nos arquivos enviados. Certifique-se de que os PDFs contêm texto selecionável (e não são imagens digitalizadas/scaneadas).")
        st.session_state.df_editado = None

# Exibição da tabela e central de downloads baseada no session_state
if st.session_state.df_editado is not None and not st.session_state.df_editado.empty:
    st.success(f"🎉 Processamento concluído com sucesso! {len(st.session_state.df_editado)} registros mapeados.")
    st.markdown("### 📊 Prévia dos Dados Extraídos")
    st.info("💡 **Dica:** Você pode alterar o **Código Empregado** ou qualquer outra informação clicando diretamente nas células da tabela abaixo antes de baixar os arquivos!")
    
    df_final = st.data_editor(st.session_state.df_editado, use_container_width=True, num_rows="dynamic", key="editor_dados")
    
    output_csv = "extrato_irrf_consolidado.csv"
    df_final.to_csv(output_csv, index=False, sep=";", encoding="utf-8-sig")
    
    output_txt = "importacao_irrf.txt"
    with open(output_txt, "w", encoding="utf-8") as f:
        for _, row in df_final.iterrows():
            f.write(gerar_linha_posicional(row))

    st.markdown("### 📥 Central de Downloads")
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        with open(output_csv, "rb") as f:
            st.download_button("📥 Baixar Planilha de Conferência (CSV)", data=f, file_name=output_csv, mime="text/csv")
    with col_dl2:
        with open(output_txt, "r", encoding="utf-8") as f:
            st.download_button("📄 Baixar TXT Posicional (Leiaute)", data=f, file_name=output_txt, mime="text/plain")
