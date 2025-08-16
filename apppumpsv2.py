import streamlit as st
import pandas as pd
from fpdf import FPDF
import math
import time
import numpy as np

# --- Dicionário de Fluidos com suas propriedades (Massa Específica e Viscosidade Cinemática) ---
# Massa Específica (rho) em kg/m³
# Viscosidade Cinemática (nu) em m²/s
FLUIDOS = {
    "Água a 20°C": {"rho": 998.2, "nu": 1.004e-6},
    "Etanol a 20°C": {"rho": 789.0, "nu": 1.51e-6},
    "Glicerina a 20°C": {"rho": 1261.0, "nu": 1.49e-3},
    "Óleo Leve (genérico)": {"rho": 880.0, "nu": 1.5e-5}
}

# --- Funções de Cálculo de Engenharia ---

def calcular_perda_carga(vazao_m3h, diametro_mm, comprimento_m, rugosidade_mm, k_total, fluido_selecionado):
    """
    Calcula a perda de carga usando a equação de Darcy-Weisbach.
    Retorna um dicionário com os resultados.
    """
    if diametro_mm <= 0:
        return {"principal": float('inf'), "localizada": float('inf'), "velocidade": float('inf')}

    # Conversões
    vazao_m3s = vazao_m3h / 3600
    diametro_m = diametro_mm / 1000
    rugosidade_m = rugosidade_mm / 1000
    
    # Propriedades do fluido
    nu = FLUIDOS[fluido_selecionado]["nu"]
    
    # Cálculos intermediários
    area = (math.pi * diametro_m**2) / 4
    velocidade = vazao_m3s / area
    
    # Número de Reynolds
    reynolds = (velocidade * diametro_m) / nu if nu > 0 else 0
    
    # Fator de atrito (f) - Usando a fórmula explícita de Swamee-Jain
    fator_atrito = 0
    if reynolds > 4000: # Regime turbulento
        # Adicionado tratamento para evitar log de zero ou negativo
        termo_log = (rugosidade_m / (3.7 * diametro_m)) + (5.74 / reynolds**0.9)
        if termo_log > 0:
            fator_atrito = 0.25 / (math.log10(termo_log))**2
    elif reynolds > 0: # Regime laminar (aproximação)
        fator_atrito = 64 / reynolds
        
    # Perda de carga principal (atrito na tubulação)
    perda_carga_principal = fator_atrito * (comprimento_m / diametro_m) * (velocidade**2 / (2 * 9.81))
    
    # Perda de carga localizada (acessórios)
    perda_carga_localizada = k_total * (velocidade**2 / (2 * 9.81))
    
    return {
        "principal": perda_carga_principal,
        "localizada": perda_carga_localizada,
        "velocidade": velocidade
    }

def calcular_analise_energetica(vazao_m3h, h_man, eficiencia_bomba, eficiencia_motor, horas_dia, custo_kwh, fluido_selecionado):
    """Realiza todos os cálculos de potência, consumo e custo."""
    rho = FLUIDOS[fluido_selecionado]["rho"]
    g = 9.81
    vazao_m3s = vazao_m3h / 3600

    potencia_hidraulica_W = vazao_m3s * rho * g * h_man
    potencia_eixo_W = potencia_hidraulica_W / eficiencia_bomba if eficiencia_bomba > 0 else 0
    potencia_eletrica_W = potencia_eixo_W / eficiencia_motor if eficiencia_motor > 0 else 0
    
    potencia_eletrica_kW = potencia_eletrica_W / 1000
    
    consumo_diario_kWh = potencia_eletrica_kW * horas_dia
    custo_anual = (consumo_diario_kWh * 365) * custo_kwh

    return {
        "potencia_eletrica_kW": potencia_eletrica_kW,
        "consumo_mensal_kWh": consumo_diario_kWh * 30,
        "custo_mensal": (consumo_diario_kWh * 30) * custo_kwh,
        "custo_anual": custo_anual
    }

def gerar_sugestoes(eficiencia_bomba, eficiencia_motor, custo_anual, velocidade):
    """Gera uma lista de sugestões de melhoria."""
    sugestoes = []
    if velocidade > 3.0:
        sugestoes.append(f"ALERTA: A velocidade do fluido ({velocidade:.2f} m/s) é alta, o que causa perdas de carga elevadas e risco de erosão. Considere aumentar o diâmetro da tubulação.")
    elif velocidade < 0.5:
        sugestoes.append(f"ATENÇÃO: A velocidade do fluido ({velocidade:.2f} m/s) é baixa, o que pode levar à sedimentação de sólidos na tubulação (se aplicável).")
    
    if eficiencia_bomba < 0.6:
        sugestoes.append("Eficiência da bomba abaixo de 60%. Considere a substituição por um modelo mais moderno e eficiente.")
    if eficiencia_motor < 0.85:
        sugestoes.append("Eficiência do motor abaixo de 85%. Motores de alto rendimento (IR3+) podem gerar grande economia.")
    if custo_anual > 5000:
        sugestoes.append("Se a vazão for variável, um inversor de frequência pode reduzir drasticamente o consumo de energia.")
    sugestoes.append("Realize manutenções preventivas, verifique vazamentos e o estado dos rotores e selos da bomba.")
    return sugestoes

# --- Função para Geração de PDF ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Relatório de Análise Energética de Bombeamento', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')
        
    def chapter_title(self, title):
        self.set_font('Arial', 'B', 11)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(2)

    def chapter_body(self, data):
        self.set_font('Arial', '', 10)
        for key, value in data.items():
            self.cell(80, 7, f"  {key}:", 0, 0)
            self.cell(0, 7, str(value), 0, 1)
        self.ln(5)

def criar_relatorio_pdf(inputs, resultados, sugestoes):
    pdf = PDF()
    pdf.add_page()
    
    pdf.chapter_title("Parâmetros de Entrada")
    pdf.chapter_body(inputs)
    
    pdf.chapter_title("Resultados da Análise")
    pdf.chapter_body(resultados)
    
    pdf.chapter_title("Sugestões de Melhoria")
    pdf.set_font('Arial', '', 10)
    for i, sugestao in enumerate(sugestoes):
        pdf.multi_cell(0, 5, f"- {sugestao}")
        pdf.ln(2)
        
    return bytes(pdf.output())

def gerar_grafico_diametro_custo(diametro_base_mm, h_geometrica, **kwargs):
    """Gera os dados para o gráfico de Custo Anual vs. Diâmetro da Tubulação."""
    # Criar uma faixa de diâmetros para analisar, em mm
    diametros_mm = np.linspace(max(25, diametro_base_mm * 0.5), diametro_base_mm * 2, num=20)
    custos_anuais = []

    for d_mm in diametros_mm:
        # Calcular perda de carga para o novo diâmetro
        perdas = calcular_perda_carga(diametro_mm=d_mm, **kwargs)
        h_man_calculado = h_geometrica + perdas["principal"] + perdas["localizada"]

        # Calcular custo energético para essa perda de carga
        resultado_energia = calcular_analise_energetica(h_man=h_man_calculado, **kwargs)
        custos_anuais.append(resultado_energia['custo_anual'])

    chart_data = pd.DataFrame({
        'Diâmetro da Tubulação (mm)': diametros_mm,
        'Custo Anual de Energia (R$)': custos_anuais
    })
    return chart_data


# --- Interface do Aplicativo Streamlit ---

st.set_page_config(layout="wide", page_title="Análise de Sistemas de Bombeamento")
st.title("💧 Análise Avançada de Sistemas de Bombeamento")

# --- Barra Lateral para Entradas ---
with st.sidebar:
    st.header("⚙️ Parâmetros do Sistema")
    
    fluido_selecionado = st.selectbox("Selecione o Fluido", list(FLUIDOS.keys()))
    vazao = st.number_input("Vazão Desejada (m³/h)", min_value=0.1, value=50.0, step=1.0)
    
    tipo_calculo_h = st.radio("Cálculo da Altura Manométrica", 
                             ["Informar manualmente", "Calcular a partir da tubulação"],
                             key="tipo_h")
    
    h_man_total = 0
    h_geometrica = 0
    diam_tub = 100.0 # Default value
    
    if tipo_calculo_h == "Informar manualmente":
        h_man_total = st.number_input("Altura Manométrica Total (m)", min_value=1.0, value=30.0, step=0.5)
        # Forçar um valor de velocidade como N/A quando o cálculo não for feito
        velocidade_fluido = None
    else:
        with st.expander("Dados para Cálculo da Perda de Carga"):
            h_geometrica = st.number_input("Altura Geométrica (desnível) (m)", min_value=0.0, value=15.0)
            comp_tub = st.number_input("Comprimento da Tubulação (m)", min_value=1.0, value=100.0)
            diam_tub = st.number_input("Diâmetro Interno da Tubulação (mm)", min_value=1.0, value=100.0)
            rug_tub = st.number_input("Rugosidade do Material (mm)", min_value=0.001, value=0.15, format="%.3f")
            k_total_acessorios = st.number_input("Soma dos Coeficientes de Perda (K) dos Acessórios", min_value=0.0, value=5.0)
            
    st.header("🔧 Eficiência dos Equipamentos")
    rend_bomba = st.slider("Eficiência da Bomba (%)", 10, 100, 70)
    rend_motor = st.slider("Eficiência do Motor (%)", 50, 100, 90)
    
    st.header("🗓️ Operação e Custo")
    horas_por_dia = st.number_input("Horas de Operação por Dia", 1.0, 24.0, 8.0, 0.5)
    tarifa_energia = st.number_input("Custo da Energia (R$/kWh)", 0.10, 2.00, 0.75, 0.01, format="%.2f")

# --- Lógica Principal e Exibição de Resultados ---
col1, col2 = st.columns([0.6, 0.4])

with col1:
    st.header("📊 Resultados da Análise")
    
    # Cálculos
    if tipo_calculo_h == "Calcular a partir da tubulação":
        perdas_dict = calcular_perda_carga(vazao, diam_tub, comp_tub, rug_tub, k_total_acessorios, fluido_selecionado)
        h_man_total = h_geometrica + perdas_dict["principal"] + perdas_dict["localizada"]
        velocidade_fluido = perdas_dict["velocidade"]
        
        st.subheader("Altura Manométrica e Velocidade Calculadas")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Altura Total", f"{h_man_total:.2f} m")
        c2.metric("Perda Principal", f"{perdas_dict['principal']:.2f} m")
        c3.metric("Perda Localizada", f"{perdas_dict['localizada']:.2f} m")
        c4.metric("Velocidade", f"{velocidade_fluido:.2f} m/s")
    
    resultados = calcular_analise_energetica(vazao, h_man_total, rend_bomba/100, rend_motor/100, horas_por_dia, tarifa_energia, fluido_selecionado)

    st.subheader("Potências e Custos")
    c1, c2, c3 = st.columns(3)
    c1.metric("Potência Elétrica", f"{resultados['potencia_eletrica_kW']:.2f} kW")
    c2.metric("Custo Mensal", f"R$ {resultados['custo_mensal']:.2f}")
    c3.metric("Custo Anual", f"R$ {resultados['custo_anual']:.2f}")
    
    # Só mostra o gráfico se o cálculo for baseado na tubulação
    if tipo_calculo_h == "Calcular a partir da tubulação":
        st.subheader("Gráfico: Custo Anual de Energia vs. Diâmetro da Tubulação")
        
        # Parâmetros para passar para as funções de cálculo dentro do loop do gráfico
        params_grafico_perda_carga = {
            'vazao_m3h': vazao, 'comprimento_m': comp_tub, 
            'rugosidade_mm': rug_tub, 'k_total': k_total_acessorios, 
            'fluido_selecionado': fluido_selecionado
        }
        params_grafico_energia = {
            'vazao_m3h': vazao, 'eficiencia_bomba': rend_bomba/100, 
            'eficiencia_motor': rend_motor/100, 'horas_dia': horas_por_dia, 
            'custo_kwh': tarifa_energia, 'fluido_selecionado': fluido_selecionado
        }
        
        # Junta os dois dicionários de parâmetros
        params_gerais = {**params_grafico_perda_carga, **params_grafico_energia}
        
        chart_data = gerar_grafico_diametro_custo(diam_tub, h_geometrica, **params_gerais)
        st.line_chart(chart_data.set_index('Diâmetro da Tubulação (mm)'))
        st.caption("O gráfico ilustra como o custo de energia diminui com o aumento do diâmetro da tubulação, devido à menor perda de carga.")

with col2:
    st.header("💡 Sugestões e Relatório")
    if velocidade_fluido is not None:
        sugestoes = gerar_sugestoes(rend_bomba/100, rend_motor/100, resultados['custo_anual'], velocidade_fluido)
        for sugestao in sugestoes:
            st.info(sugestao)
    else:
        st.info("As sugestões detalhadas sobre a velocidade do fluido aparecerão quando você escolher 'Calcular a partir da tubulação'.")
    
    st.header("📄 Gerar Relatório")
    
    inputs_relatorio = {
        "Fluido": fluido_selecionado, "Vazão": f"{vazao} m³/h",
        "Altura Manométrica Total": f"{h_man_total:.2f} m",
        "Eficiência da Bomba": f"{rend_bomba}%", "Eficiência do Motor": f"{rend_motor}%",
        "Horas/Dia": f"{horas_por_dia} h", "Tarifa": f"R$ {tarifa_energia:.2f}/kWh"
    }
    if velocidade_fluido is not None:
        inputs_relatorio["Velocidade do Fluido"] = f"{velocidade_fluido:.2f} m/s"

    resultados_relatorio = {
        "Potência Elétrica Consumida": f"{resultados['potencia_eletrica_kW']:.2f} kW",
        "Custo Mensal": f"R$ {resultados['custo_mensal']:.2f}",
        "Custo Anual": f"R$ {resultados['custo_anual']:.2f}"
    }

    pdf_bytes = criar_relatorio_pdf(inputs_relatorio, resultados_relatorio, sugestoes if velocidade_fluido is not None else [])
    
    timestr = time.strftime("%Y%m%d-%H%MS")
    st.download_button(
        label="Download do Relatório em PDF",
        data=pdf_bytes,
        file_name=f"Relatorio_Bombeamento_{timestr}.pdf",
        mime="application/octet-stream"
    )
