import os
import re
import pandas as pd
import pdfplumber
import streamlit as st

# --- Configuração Inicial da Página ---
st.set_page_config(
    page_title="Extrator Inteligente de IRRF",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Estilização CSS: Fundo Escuro + Textos em Verde Esmeralda Neon ---
st.markdown("""
    <style>
    /* Fundo geral da aplicação - Escuro Profundo */
    .stApp {
        background-color: #090d16;
        color: #00ffcc !important;
    }
    
    /* Forçar todas as palavras, títulos, subtítulos e textos em Verde Neon */
    h1, h2, h3, h4, h5, h6, p, span, label, div, .stMarkdown, .stText {
        color: #00ffcc !important;
        font-family: 'Inter', sans-serif;
    }
    
    /* Inputs, textos digitados e selects com texto verde */
    input, select, textarea {
        color: #00ffcc !important;
        background-color: #111827 !important;
        border-color: #00ffcc !important;
    }

    /* Botões modernos com gradiente em Verde Esmeralda Neon */
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
        background: linear-gradient(135deg, #00b386 0%, #008060 100%);
        box-shadow: 0 6px 20px rgba(0, 255, 204, 0.6);
        transform: translateY(-2px);
    }
    
    /* Cartões / Containers personalizados com borda neon suave */
    .custom-card {
        background-color: #111827;
        padding: 1.5rem;
        border-radius: 16px;
        box-shadow: 0 4px 20px -2px rgba(0, 255, 204, 0.1);
        border: 1px solid rgba(0, 255, 204, 0.3);
        margin-bottom: 1rem;
    }
    
    /* Ajustes da barra lateral escura */
    [data-testid="stSidebar"] {
        background-color: #0d1322;
        color: #00ffcc !important;
        border-right: 1px solid rgba(0, 255, 204, 0.2);
    }
    [data-testid="stSidebar"] * {
        color: #00ffcc !important;
    }
    
    /* Métricas e caixas de destaque */
    [data-testid="stMetricValue"] {
        color: #00ffcc !important;
        text-shadow: 0 0 10px rgba(0, 255, 204, 0.5);
    }
    
    /* File Uploader customizado */
    [data-testid="stFileUploader"] {
        background-color: #111827;
        border: 2px dashed rgba(0, 255, 204, 0.4);
        border-radius: 12px;
        padding: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

def converter_competencia_aaamm(competencia_str):
    """Converte MM/AAAA para AAAAMM conforme o leiaute."""
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

def extrair_dados_extrato_dominio(caminho_pdf, codigo_empresa="1", codigo_rubrica="2000", competencia=""):
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
        if not match_emp or not match_cpf: continue
        emp_id, cpf = match_emp.group(1).strip(), match_cpf.group(1).strip()
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
                "Empresa": str(codigo_empresa).strip(),
                "Código Empregado": emp_id,
                "Funcionário": nome,
                "CPF": cpf,
                "Competência": competencia.strip(),
                "Base IRRF": base_irrf,
                "Código Rubrica": str(codigo_rubrica).strip()
            })
    return pd.DataFrame(dados_funcionarios)

def extrair_dados_extrato_contmatic(caminho_pdf, codigo_empresa="1", codigo_rubrica="2000", competencia=""):
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
                "Empresa": str(codigo_empresa).strip(),
                "Código Empregado": emp_id,
                "Funcionário": nome,
                "CPF": "N/D (Contmatic)",
                "Competência": competencia.strip(),
                "Base IRRF": base_irrf,
                "Código Rubrica": str(codigo_rubrica).strip()
            })
    return pd.DataFrame(dados_funcionarios)

def extrair_dados_extrato_alterdata(caminho_pdf, codigo_empresa="1", codigo_rubrica="2000", competencia=""):
    dados_funcionarios = []
    with pdfplumber.open(caminho_pdf) as pdf:
        texto_completo = "".join([p.extract_text() + "\n" for p in pdf.pages if p.extract_text()])

    if not texto_completo.strip(): return pd.DataFrame()

    linhas = [l.strip() for l in texto_completo.split("\n") if l.strip()]
    emp_id, nome, cpf, base_irrf = None, "Funcionário", "N/D", "0,00"
    padrao_empregado_cpf = re.compile(r"\b(\d{5})\b.*?(\d{3}\.\d{3}\.\d{3}-\d{2})")
    padrao_cpf_isolado = re.compile(r"(\d{3}\.\d{3}\.\d{3}-\d{2})")
    padrao_base_irrf_estrito = re.compile(r"Base\s*IRRF\s*[:\s]*([\d\.]+,\d{2})", re.IGNORECASE)

    for linha in linhas:
        match_emp_cpf = padrao_empregado_cpf.search(linha)
        if match_emp_cpf:
            if emp_id and base_irrf != "0,00":
                dados_funcionarios.append({
                    "Empresa": str(codigo_empresa).strip(), "Código Empregado": emp_id,
                    "Funcionário": nome, "CPF": cpf, "Competência": competencia.strip(),
                    "Base IRRF": base_irrf, "Código Rubrica": str(codigo_rubrica).strip()
                })
                base_irrf = "0,00"
            emp_id, cpf = match_emp_cpf.group(1).strip(), match_emp_cpf.group(2).strip()
            resto = padrao_empregado_cpf.sub("", linha).strip()
            if len(resto) > 2: nome = resto
            continue

        match_cpf_iso = padrao_cpf_isolado.search(linha)
        if match_cpf_iso and cpf == "N/D": cpf = match_cpf_iso.group(1).strip()

        match_base = padrao_base_irrf_estrito.search(linha)
        if match_base:
            base_irrf = match_base.group(1).strip()
            if emp_id and not any(d.get('CPF') == cpf and d.get('Código Empregado') == emp_id for d in dados_funcionarios):
                dados_funcionarios.append({
                    "Empresa": str(codigo_empresa).strip(), "Código Empregado": emp_id,
                    "Funcionário": nome, "CPF": cpf, "Competência": competencia.strip(),
                    "Base IRRF": base_irrf, "Código Rubrica": str(codigo_rubrica).strip()
                })
    return pd.DataFrame(dados_funcionarios)

def extrair_dados_extrato_sci(caminho_pdf, codigo_empresa="1", codigo_rubrica="2000", competencia=""):
    dados_funcionarios = []
    with pdfplumber.open(caminho_pdf) as pdf:
        texto_completo = "".join([p.extract_text() + "\n" for p in pdf.pages if p.extract_text()])

    if not texto_completo.strip(): return pd.DataFrame()

    linhas = [l.strip() for l in texto_completo.split("\n") if l.strip()]
    emp_id, nome, base_irrf = None, "Funcionário", "0,00"
    padrao_codigo_nome = re.compile(r"^(\d+)\s+([A-ZÀ-Ú\s]+)", re.IGNORECASE)
    padrao_ir_sci = re.compile(r"IR\s*->\s*([\d\.]+,\d{2})", re.IGNORECASE)

    for linha in linhas:
        match_cod_nome = padrao_codigo_nome.search(linha)
        if match_cod_nome and not "IR ->" in linha and not "TOTAL" in linha.upper() and not "Página" in linha:
            if emp_id and base_irrf != "0,00":
                dados_funcionarios.append({
                    "Empresa": str(codigo_empresa).strip(), "Código Empregado": emp_id,
                    "Funcionário": nome, "CPF": "N/D (SCI)", "Competência": competencia.strip(),
                    "Base IRRF": base_irrf, "Código Rubrica": str(codigo_rubrica).strip()
                })
                base_irrf = "0,00"
            emp_id, nome = match_cod_nome.group(1).strip(), match_cod_nome.group(2).strip()
            continue

        match_ir = padrao_ir_sci.search(linha)
        if match_ir:
            base_irrf = match_ir.group(1).strip()
            if emp_id:
                dados_funcionarios.append({
                    "Empresa": str(codigo_empresa).strip(), "Código Empregado": emp_id,
                    "Funcionário": nome, "CPF": "N/D (SCI)", "Competência": competencia.strip(),
                    "Base IRRF": base_irrf, "Código Rubrica": str(codigo_rubrica).strip()
                })
                emp_id, base_irrf = None, "0,00"
    return pd.DataFrame(dados_funcionarios)

def extrair_dados_extrato_prosol(caminho_pdf, codigo_empresa="1", codigo_rubrica="2000", competencia=""):
    """
    Abordagem ajustada e validada para o leiaute da Prosol:
    - Captura o código do empregado e isola estritamente a linha '0105 BASE DE CALCULO I.R.R.F.'
    - Pega com precisão o valor monetário correto da terceira coluna (ex: 2.329,50).
    """
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
                    "Empresa": str(codigo_empresa).strip(),
                    "Código Empregado": emp_id,
                    "Funcionário": nome,
                    "CPF": "N/D (Prosol)",
                    "Competência": competencia.strip(),
                    "Base IRRF": base_irrf,
                    "Código Rubrica": str(codigo_rubrica).strip()
                })
        i += 1
    return pd.DataFrame(dados_funcionarios)

def extrair_dados_extrato_questor(caminho_pdf, codigo_empresa="1", codigo_rubrica="2000", competencia=""):
    """
    Extrator dedicado ao leiaute do sistema Questor:
    - Captura o código do empregado após o campo 'Func:'
    - Captura a base de IRRF estritamente dentro do quadro 'Base Impostos', na linha 'IRRF' coluna 'Normal'.
    """
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
                "Empresa": str(codigo_empresa).strip(),
                "Código Empregado": emp_id,
                "Funcionário": nome,
                "CPF": "N/D (Questor)",
                "Competência": competencia.strip(),
                "Base IRRF": base_irrf,
                "Código Rubrica": str(codigo_rubrica).strip()
            })
            
    return pd.DataFrame(dados_funcionarios)

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

# --- Layout da Interface (Sidebar) ---
with st.sidebar:
    st.markdown("### ⚙️ Painel de Controle")
    st.markdown("Configure os parâmetros de exportação dos dados contábeis.")
    
    sistema_cliente = st.selectbox(
        "🏢 Sistema / Leiaute:",
        [
            "Questor",
            "Domínio (Thomson Reuters)",
            "Contmatic Phoenix",
            "Alterdata",
            "SCI Contábil",
            "Prosol"
        ]
    )
    
    st.markdown("---")
    codigo_empresa_input = st.text_input("🔢 Código da Empresa:", value="1")
    codigo_rubrica = st.text_input("🏷️ Código da Rubrica (TXT):", value="2000")
    competencia_input = st.text_input("📅 Competência (MM/AAAA):", value="05/2026")
    
    st.markdown("---")
    st.markdown("💡 *Dica: Você pode enviar múltiplos PDFs de uma só vez.*")

# --- Layout Principal (Header & Conteúdo) ---
st.title("⚡ Extrator Inteligente de Base IRRF")
st.markdown("Transforme extratos de folha de pagamento em **layouts TXT posicionais e planilhas de conferência** com inteligência e precisão em segundos.")

# Cartão Principal de Upload
st.markdown('<div class="custom-card">', unsafe_allow_html=True)
st.markdown("### 📂 Upload de Extratos (PDF)")
arquivos_pdf = st.file_uploader("Arraste ou selecione os arquivos PDF aqui", type=["pdf"], accept_multiple_files=True, label_visibility="collapsed")
st.markdown('</div>', unsafe_allow_html=True)

if arquivos_pdf:
    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.metric(label="📄 Arquivos Selecionados", value=len(arquivos_pdf))
    with col_info2:
        st.metric(label="⚙️ Sistema Ativo", value=sistema_cliente.split()[0])
    with col_info3:
        st.metric(label="📅 Competência Alvo", value=competencia_input)

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
            else:
                df_extrato = pd.DataFrame()
                
            if not df_extrato.empty:
                df_extrato["Arquivo Origem"] = arquivo.name
                todos_dados.append(df_extrato)
            
            os.remove(caminho_temp)
            
    if todos_dados:
        df_final = pd.concat(todos_dados, ignore_index=True)
        
        if df_final.empty:
            st.warning("⚠ Nenhum dado foi extraído. Verifique se o PDF corresponde ao leiaute selecionado.")
        else:
            st.success(f"🎉 Processamento concluído com sucesso! {len(df_final)} registros mapeados.")
            
            # Exibição Visual Moderna dos Dados
            st.markdown("### 📊 Prévia dos Dados Extraídos")
            st.dataframe(df_final, use_container_width=True)
            
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
                    st.download_button(
                        label="📥 Baixar Planilha de Conferência (CSV)",
                        data=f,
                        file_name=output_csv,
                        mime="text/csv"
                    )
                    
            with col_dl2:
                with open(output_txt, "r", encoding="utf-8") as f:
                    st.download_button(
                        label="📄 Baixar TXT Posicional (Leiaute)",
                        data=f,
                        file_name=output_txt,
                        mime="text/plain"
                    )
    else:
        st.warning("⚠️ Nenhum dado válido foi encontrado nos arquivos enviados.")
