import os
import re
import pandas as pd
import pdfplumber
import streamlit as st

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
        texto_completo = ""
        for pagina in pdf.pages:
            texto_extraido = pagina.extract_text()
            if texto_extraido:
                texto_completo += texto_extraido + "\n"

    if not texto_completo.strip():
        return pd.DataFrame()

    partes_texto = re.split(r"(?=Empr\.?:?\s*\d+)", texto_completo, flags=re.IGNORECASE)
    padrao_emp = re.compile(r"Empr\.?:?\s*(\d+)", re.IGNORECASE)
    padrao_cpf = re.compile(r"(\d{3}\.\d{3}\.\d{3}-\d{2})")
    padrao_base_irrf = re.compile(
        r"(?:Base\s*(?:de\s*Cálculo\s*)?(?:do\s*)?IRRF|Base\s*Calc\.?\s*IRRF|IRRF\s*Base)[:\s\n]*([\d\.]+,\d{2})", 
        re.IGNORECASE
    )

    for bloco in partes_texto:
        if not bloco.strip():
            continue
        match_emp = padrao_emp.search(bloco)
        match_cpf = padrao_cpf.search(bloco)
        if not match_emp or not match_cpf:
            continue
        emp_id = match_emp.group(1).strip()
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
        texto_completo = ""
        for pagina in pdf.pages:
            texto_extraido = pagina.extract_text()
            if texto_extraido:
                texto_completo += texto_extraido + "\n"

    if not texto_completo.strip():
        return pd.DataFrame()

    partes_texto = re.split(r"(?=Cód:\s*\d+)", texto_completo, flags=re.IGNORECASE)
    padrao_cod = re.compile(r"Cód:\s*(\d+)", re.IGNORECASE)
    padrao_base_irrf = re.compile(r"Base\s*I\.R\.R\.F\.?:?[\s\n]*([\d\.]+,\d{2})", re.IGNORECASE)

    for bloco in partes_texto:
        if not bloco.strip():
            continue
        match_cod = padrao_cod.search(bloco)
        if not match_cod:
            continue
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
        texto_completo = ""
        for pagina in pdf.pages:
            texto_extraido = pagina.extract_text()
            if texto_extraido:
                texto_completo += texto_extraido + "\n"

    if not texto_completo.strip():
        return pd.DataFrame()

    linhas = [l.strip() for l in texto_completo.split("\n") if l.strip()]
    
    emp_id = None
    nome = "Funcionário"
    cpf = "N/D"
    base_irrf = "0,00"

    padrao_empregado_cpf = re.compile(r"\b(\d{5})\b.*?(\d{3}\.\d{3}\.\d{3}-\d{2})")
    padrao_cpf_isolado = re.compile(r"(\d{3}\.\d{3}\.\d{3}-\d{2})")
    padrao_base_irrf_estrito = re.compile(r"Base\s*IRRF\s*[:\s]*([\d\.]+,\d{2})", re.IGNORECASE)

    for linha in linhas:
        match_emp_cpf = padrao_empregado_cpf.search(linha)
        if match_emp_cpf:
            if emp_id and base_irrf != "0,00":
                dados_funcionarios.append({
                    "Empresa": str(codigo_empresa).strip(),
                    "Código Empregado": emp_id,
                    "Funcionário": nome,
                    "CPF": cpf,
                    "Competência": competencia.strip(),
                    "Base IRRF": base_irrf,
                    "Código Rubrica": str(codigo_rubrica).strip()
                })
                base_irrf = "0,00"

            emp_id = match_emp_cpf.group(1).strip()
            cpf = match_emp_cpf.group(2).strip()
            resto = padrao_empregado_cpf.sub("", linha).strip()
            if len(resto) > 2:
                nome = resto
            continue

        match_cpf_iso = padrao_cpf_isolado.search(linha)
        if match_cpf_iso and cpf == "N/D":
            cpf = match_cpf_iso.group(1).strip()

        match_base = padrao_base_irrf_estrito.search(linha)
        if match_base:
            base_irrf = match_base.group(1).strip()
            if emp_id:
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

    st.write(f"DEBUG - Total de registros extraídos da Alterdata: {len(dados_funcionarios)}")
    return pd.DataFrame(dados_funcionarios)

def extrair_dados_extrato_sci(caminho_pdf, codigo_empresa="1", codigo_rubrica="2000", competencia=""):
    dados_funcionarios = []
    
    with pdfplumber.open(caminho_pdf) as pdf:
        texto_completo = ""
        for pagina in pdf.pages:
            texto_extraido = pagina.extract_text()
            if texto_extraido:
                texto_completo += texto_extraido + "\n"

    if not texto_completo.strip():
        return pd.DataFrame()

    linhas = [l.strip() for l in texto_completo.split("\n") if l.strip()]
    
    emp_id = None
    nome = "Funcionário"
    base_irrf = "0,00"

    padrao_codigo_nome = re.compile(r"^(\d+)\s+([A-ZÀ-Ú\s]+)", re.IGNORECASE)
    padrao_ir_sci = re.compile(r"IR\s*->\s*([\d\.]+,\d{2})", re.IGNORECASE)

    for linha in linhas:
        match_cod_nome = padrao_codigo_nome.search(linha)
        if match_cod_nome and not "IR ->" in linha and not "TOTAL" in linha.upper() and not "Página" in linha:
            if emp_id and base_irrf != "0,00":
                dados_funcionarios.append({
                    "Empresa": str(codigo_empresa).strip(),
                    "Código Empregado": emp_id,
                    "Funcionário": nome,
                    "CPF": "N/D (SCI)",
                    "Competência": competencia.strip(),
                    "Base IRRF": base_irrf,
                    "Código Rubrica": str(codigo_rubrica).strip()
                })
                base_irrf = "0,00"
            
            emp_id = match_cod_nome.group(1).strip()
            nome = match_cod_nome.group(2).strip()
            continue

        match_ir = padrao_ir_sci.search(linha)
        if match_ir:
            base_irrf = match_ir.group(1).strip()
            if emp_id:
                dados_funcionarios.append({
                    "Empresa": str(codigo_empresa).strip(),
                    "Código Empregado": emp_id,
                    "Funcionário": nome,
                    "CPF": "N/D (SCI)",
                    "Competência": competencia.strip(),
                    "Base IRRF": base_irrf,
                    "Código Rubrica": str(codigo_rubrica).strip()
                })
                emp_id = None
                base_irrf = "0,00"

    st.write(f"DEBUG - Total de registros extraídos da SCI: {len(dados_funcionarios)}")
    return pd.DataFrame(dados_funcionarios)

def extrair_dados_extrato_prosol(caminho_pdf, codigo_empresa="1", codigo_rubrica="2000", competencia=""):
    """
    Abordagem ajustada para o leiaute da Prosol:
    - Captura o código do empregado situado antes do nome (ex: '000000002-JOSE C').
    - Captura a base do IRRF associada à descrição 'BASE DE CALCULO I.R.R.F.'.
    """
    dados_funcionarios = []
    
    with pdfplumber.open(caminho_pdf) as pdf:
        texto_completo = ""
        for pagina in pdf.pages:
            texto_extraido = pagina.extract_text()
            if texto_extraido:
                texto_completo += texto_extraido + "\n"

    if not texto_completo.strip():
        return pd.DataFrame()

    linhas = [l.strip() for l in texto_completo.split("\n") if l.strip()]
    
    emp_id = None
    nome = "Funcionário"
    base_irrf = "0,00"

    padrao_codigo_nome = re.compile(r"^(\d+)-([A-ZÀ-Ú\s]+)", re.IGNORECASE)
    padrao_base_irrf_prosol = re.compile(r"BASE\s*DE\s*CALCULO\s*I\.R\.R\.F\.?", re.IGNORECASE)
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
            if not valores_encontrados and i + 2 < len(linhas):
                valores_encontrados = padrao_valor.findall(linhas[i+2])
            
            if valores_encontrados:
                base_irrf = valores_encontrados[-1]
            
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

    st.write(f"DEBUG - Total de registros extraídos da Prosol: {len(dados_funcionarios)}")
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

# --- Interface Gráfica com Streamlit ---
st.title("Extrator de Base IRRF - Leiaute de Importação TXT")
st.write("Selecione o sistema do cliente, configure os parâmetros e faça o upload dos extratos em PDF.")

sistema_cliente = st.selectbox(
    "Selecione o Sistema / Layout do Cliente:",
    [
        "Domínio Sistemas (Thomson Reuters)",
        "Contmatic Phoenix",
        "Alterdata",
        "SCI (Sistemas Contábeis)",
        "Prosol"
    ]
)

col1, col2, col3 = st.columns(3)
with col1:
    codigo_empresa_input = st.text_input("Código da Empresa:", value="1")
with col2:
    codigo_rubrica = st.text_input("Código da Rubrica (TXT):", value="2000")
with col3:
    competencia_input = st.text_input("Competência (Ex: 06/2026):", value="08/2026")

arquivos_pdf = st.file_uploader("Selecione os arquivos PDF", type=["pdf"], accept_multiple_files=True)

if arquivos_pdf and st.button("Processar Extratos e Gerar Arquivos"):
    todos_dados = []
    
    for arquivo in arquivos_pdf:
        caminho_temp = os.path.join("temp", arquivo.name)
        os.makedirs("temp", exist_ok=True)
        with open(caminho_temp, "wb") as f:
            f.write(arquivo.getbuffer())
            
        with pdfplumber.open(caminho_temp) as pdf:
            texto_completo = ""
            for pagina in pdf.pages:
                texto_extraido = pagina.extract_text()
                if texto_extraido:
                    texto_completo += texto_extraido + "\n"
        
        st.info(f"Depuração - Texto extraído do arquivo ({arquivo.name}):")
        st.code(texto_completo[:1200] if texto_completo else "Nenhum texto extraído deste PDF!")
            
        if "Domínio" in sistema_cliente:
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
            st.warning("Nenhum dado foi extraído. Verifique se o PDF corresponde ao leiaute selecionado.")
        else:
            st.success(f"Processamento concluído com sucesso usando o layout: {sistema_cliente}!")
            st.dataframe(df_final)
            
            output_csv = "extrato_irrf_consolidado.csv"
            df_final.to_csv(output_csv, index=False, sep=";", encoding="utf-8-sig")
            
            output_txt = "importacao_irrf.txt"
            with open(output_txt, "w", encoding="utf-8") as f:
                for _, row in df_final.iterrows():
                    linha_posicional = gerar_linha_posicional(row)
                    f.write(linha_posicional)

            col_dl1, col_dl2 = st.columns(2)
            
            with col_dl1:
                with open(output_csv, "rb") as f:
                    st.download_button(
                        label="Baixar Planilha de Conferência (CSV)",
                        data=f,
                        file_name=output_csv,
                        mime="text/csv"
                    )
                    
            with col_dl2:
                with open(output_txt, "r", encoding="utf-8") as f:
                    st.download_button(
                        label="Baixar TXT Posicional (Leiaute)",
                        data=f,
                        file_name=output_txt,
                        mime="text/plain"
                    )
    else:
        st.warning("Nenhum dado válido foi encontrado nos arquivos enviados.")
