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
    """
    Extração específica para o leiaute da Domínio Sistemas.
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
    """
    Extração específica para o leiaute da Contmatic (utiliza 'Cód:' para empregado e 'Base I.R.R.F.' para base).
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

    # Divide o texto do PDF por blocos iniciados pelo padrão "Cód: <número>"[cite: 7]
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
        
        # Extração da Base I.R.R.F. específica do leiaute Contmatic[cite: 7]
        match_base = padrao_base_irrf.search(bloco)
        base_irrf = match_base.group(1).strip() if match_base else "0,00"
        
        # Extrair o nome do funcionário (geralmente na linha seguinte ou próxima ao Cód)
        linhas = [l.strip() for l in bloco.split("\n") if l.strip()]
        nome = "Funcionário"
        for i, linha in enumerate(linhas):
            if "Nome:" in linha:
                nome = linha.replace("Nome:", "").strip()
                break
            elif "Cód:" in linha and i + 1 < len(linhas):
                # Algumas linhas de cabeçalho podem vir separadas, tentamos pegar o texto logo após
                possivel_nome = linhas[i+1]
                if "Função:" in possivel_nome or len(possivel_nome) > 3:
                    nome = possivel_nome.split("Função:")[0].strip()
                    break

        # Como a Contmatic às vezes exibe resumos gerais no final, filtramos apenas os que têm código e base válidos
        if emp_id:
            dados_funcionarios.append({
                "Empresa": str(codigo_empresa).strip(),
                "Código Empregado": emp_id,
                "Funcionário": nome,
                "CPF": "N/D (Contmatic)", # Contmatic exibe em outros relatórios, mantido padrão estruturado
                "Competência": competencia.strip(),
                "Base IRRF": base_irrf,
                "Código Rubrica": str(codigo_rubrica).strip()
            })

    return pd.DataFrame(dados_funcionarios)

def gerar_linha_posicional(row):
    """
    Gera a linha em formato posicional padrão de importação:
    - 001-002 (2): Fixo "10"
    - 003-012 (10): Código do empregado
    - 013-018 (6): Competência ("AAAAMM")
    - 019-027 (9): Código da rubrica
    - 028-029 (2): Tipo do Processo "41"
    - 030-038 (9): Valor / Base IRRF (sem pontuação)
    - 039-048 (10): Empresa
    """
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

# Seletor de Modelo de Sistema atualizado com Contmatic
sistema_cliente = st.selectbox(
    "Selecione o Sistema / Layout do Cliente:",
    [
        "Domínio Sistemas (Thomson Reuters)",
        "Contmatic Phoenix"
    ]
>
)

col1, col2, col3 = st.columns(3)
with col1:
    codigo_empresa_input = st.text_input("Código da Empresa:", value="1")
with col2:
    codigo_rubrica = st.text_input("Código da Rubrica (TXT):", value="2000")
with col3:
    competencia_input = st.text_input("Competência (Ex: 06/2026):", value="06/2026")

arquivos_pdf = st.file_uploader("Selecione os arquivos PDF", type=["pdf"], accept_multiple_files=True)

if arquivos_pdf and st.button("Processar Extratos e Gerar Arquivos"):
    todos_dados = []
    
    for arquivo in arquivos_pdf:
        caminho_temp = os.path.join("temp", arquivo.name)
        os.makedirs("temp", exist_ok=True)
        with open(caminho_temp, "wb") as f:
            f.write(arquivo.getbuffer())
            
        # Direciona para o extrator correto de acordo com o sistema selecionado
        if "Domínio" in sistema_cliente:
            df_extrato = extrair_dados_extrato_dominio(caminho_temp, codigo_empresa_input, codigo_rubrica, competencia_input)
        elif "Contmatic" in sistema_cliente:
            df_extrato = extrair_dados_extrato_contmatic(caminho_temp, codigo_empresa_input, codigo_rubrica, competencia_input)
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
