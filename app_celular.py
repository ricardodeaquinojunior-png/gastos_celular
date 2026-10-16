from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import calendar
import psycopg2
import streamlit as st
import matplotlib.pyplot as plt

# Configuração da página para dispositivos móveis
st.set_page_config(
    page_title="Controle Financeiro", page_icon="💰", layout="centered"
)


# Dicionário seguro para converter meses em português sem corromper anos
meses_pt = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}


# Função de conexão inteligente (com fallback direto para a sua string de conexão)
def conectar_banco():
  try:
    if "supabase" in st.secrets:
      db_conf = st.secrets["supabase"]
      return psycopg2.connect(
          host=db_conf["host"],
          database=db_conf["database"],
          user=db_conf["user"],
          password=db_conf["password"],
          port=db_conf["port"],
      )
  except Exception:
    pass

  # Conexão direta padrão para funcionamento local imediato
  DATABASE_URL = "postgresql://postgres:gPAc6c9P+_ZV2u$@db.vihsucqqzeaestnynffz.supabase.co:5432/postgres"
  return psycopg2.connect(DATABASE_URL)


# --- Funções de Consulta ao Banco ---
def carregar_cartoes():
  try:
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nome, dia_fechamento, principal FROM cartoes ORDER BY nome;"
    )
    res = cursor.fetchall()
    cursor.close()
    conn.close()

    cartoes = {}
    principal = None
    if res:
      for row in res:
        cid = str(row[0])
        cnome = row[1]
        fechamento = row[2] if len(row) > 2 and row[2] is not None else 24
        is_principal = row[3] if len(row) > 3 and row[3] is not None else False

        cartoes[cnome] = {"id": cid, "fechamento": fechamento}
        if is_principal:
          principal = cnome

    if not principal and cartoes:
      principal = list(cartoes.keys())[0]

    return cartoes, principal
  except Exception as e:
    st.error(f"Erro ao carregar cartões: {e}")
    return {}, None


def carregar_categorias():
  try:
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute("SELECT id_categoria, descricao FROM categorias ORDER BY descricao;")
    res = cursor.fetchall()
    cursor.close()
    conn.close()
    cats = {}
    if res:
      for row in res:
        cats[row[1]] = str(row[0])
    return cats
  except Exception as e:
    st.error(f"Erro ao carregar categorias: {e}")
    return {}


def carregar_subcategorias(id_categoria):
  if not id_categoria:
    return {}
  try:
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id_subcategoria, descricao FROM subcategorias WHERE id_categoria = %s ORDER BY descricao;",
        (id_categoria,),
    )
    res = cursor.fetchall()
    cursor.close()
    conn.close()
    subs = {}
    if res:
      for row in res:
        subs[row[1]] = str(row[0])
    return subs
  except Exception as e:
    st.error(f"Erro ao carregar subcategorias: {e}")
    return {}


def calcular_ciclo_fatura(d_date, dia_fechamento):
  f_dia = min(dia_fechamento, calendar.monthrange(d_date.year, d_date.month)[1])
  if d_date.day > f_dia:
    r_next = d_date + relativedelta(months=1)
    r_ano, r_mes = r_next.year, r_next.month
  else:
    r_ano, r_mes = d_date.year, d_date.month

  max_dia_fim = calendar.monthrange(r_ano, r_mes)[1]
  fim_dia = min(dia_fechamento, max_dia_fim)
  fim = date(r_ano, r_mes, fim_dia)
  inicio = fim - relativedelta(months=1) + relativedelta(days=1)
  return inicio, fim


# --- Cabeçalho e Menu Superior Discreto ---
st.title("💰 Meu Controle")

menu = st.radio(
    "Navegação",
    ["➕ Nova Despesa", "💳 Faturas dos Cartões", "📊 Gráficos por Categoria"],
    horizontal=True,
    label_visibility="collapsed",
)
st.divider()

# ==========================================
# ABA 1: FATURAS DOS CARTÕES (Por Período)
# ==========================================
if menu == "💳 Faturas dos Cartões":
  hoje = datetime.now()
  lista_meses_opcoes = []
  for i in range(-3, 4):
    m_ref = hoje + relativedelta(months=i)
    lista_meses_opcoes.append(m_ref.strftime("%Y-%m"))


  def formatar_mes_pt(ano_mes):
    ano, mes = ano_mes.split("-")
    return f"{meses_pt.get(int(mes), mes)} de {ano}"


  mes_atual_str = hoje.strftime("%Y-%m")
  indice_atual = (
      lista_meses_opcoes.index(mes_atual_str)
      if mes_atual_str in lista_meses_opcoes
      else 3
  )

  mes_selecionado = st.selectbox(
      "📅 Selecionar Período da Fatura (Mês)",
      options=lista_meses_opcoes,
      index=indice_atual,
      format_func=formatar_mes_pt,
  )

  st.divider()
  st.subheader("💳 Faturas dos Cartões (Regra de Período)")

  cartoes_dict, _ = carregar_cartoes()
  if cartoes_dict:
    try:
      conn = conectar_banco()
      cursor = conn.cursor()
      cursor.execute(
          """
                SELECT l.valor, l.data_lancamento, l.descricao, c.nome, c.dia_fechamento 
                FROM lancamentos l
                JOIN cartoes c ON l.id_cartao = c.id
                WHERE l.id_cartao IS NOT NULL;
            """
      )
      todos_lanc_cartoes = cursor.fetchall()
      cursor.close()
      conn.close()

      faturas_por_cartao = {}
      if todos_lanc_cartoes:
        for row in todos_lanc_cartoes:
          val, ldata, ldesc, c_nome, c_fech = (
              row[0],
              row[1],
              row[2],
              row[3],
              row[4],
          )
          if not ldata:
            continue
          d_date = ldata.date() if hasattr(ldata, "date") else ldata
          fechamento = c_fech or 24

          inicio_ciclo, fim_ciclo = calcular_ciclo_fatura(d_date, fechamento)
          ciclo_ano_mes = fim_ciclo.strftime("%Y-%m")

          if ciclo_ano_mes == mes_selecionado:
            if c_nome not in faturas_por_cartao:
              faturas_por_cartao[c_nome] = {
                  "total": 0.0,
                  "inicio": inicio_ciclo,
                  "fim": fim_ciclo,
                  "itens": [],
              }
            faturas_por_cartao[c_nome]["total"] += float(val or 0)
            faturas_por_cartao[c_nome]["itens"].append((ldata, ldesc, val))

      if faturas_por_cartao:
        for c_nome, info in faturas_por_cartao.items():
          periodo_txt = (
              f"Período: {info['inicio'].strftime('%d/%m/%Y')} a"
              f" {info['fim'].strftime('%d/%m/%Y')}"
          )
          st.metric(
              label=f"Cartão: {c_nome} ({periodo_txt})",
              value=f"R$ {info['total']:,.2f}",
          )

          with st.expander(f"🔍 Detalhes da fatura - {c_nome}"):
            if info["itens"]:
              itens_ordenados = sorted(
                  info["itens"],
                  key=lambda x: x[0] if x[0] else datetime.min,
                  reverse=True,
              )
              for data_item, desc_item, val_item in itens_ordenados:
                data_item_fmt = (
                    datetime.strptime(str(data_item), "%Y-%m-%d").strftime(
                        "%d/%m/%Y"
                    )
                    if data_item
                    else ""
                )
                st.markdown(
                    f"**{data_item_fmt}** - {desc_item}: `R$"
                    f" {float(val_item or 0):,.2f}`"
                )
            else:
              st.info("Nenhum lançamento neste período para este cartão.")
          st.write("")
      else:
        st.info("Nenhuma fatura calculada para este período específico.")

    except Exception as e:
      st.error(f"Erro ao calcular faturas: {e}")
  else:
    st.info("Nenhum cartão cadastrado.")

# ==========================================
# ABA 2: NOVA DESPESA CARTÃO (Padrão de Abertura)
# ==========================================
elif menu == "➕ Nova Despesa":
  st.markdown("### 💳 Nova despesa cartão")

  if "raw_valor" not in st.session_state:
    st.session_state.raw_valor = ""
  if "input_valor_formatado" not in st.session_state:
    st.session_state.input_valor_formatado = "R$ 0,00"
  if "valor_numerico" not in st.session_state:
    st.session_state.valor_numerico = 0.0


  def formatar_moeda_input():
    digitos = "".join(
        filter(str.isdigit, st.session_state.get("raw_valor", ""))
    )
    if not digitos:
      st.session_state.input_valor_formatado = "R$ 0,00"
      st.session_state.valor_numerico = 0.0
      st.session_state.raw_valor = ""
      return

    val_int = int(digitos)
    val_float = val_int / 100.0
    st.session_state.valor_numerico = val_float
    formatado = (
        f"R$ {val_float:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )
    st.session_state.input_valor_formatado = formatado
    st.session_state.raw_valor = formatado


  st.text_input(
      "Valor da despesa cartão (R$)",
      value=st.session_state.input_valor_formatado,
      key="raw_valor",
      on_change=formatar_moeda_input,
      placeholder="Digite apenas os números...",
  )

  valor = st.session_state.valor_numerico

  if "str_data_compra" not in st.session_state:
    st.session_state.str_data_compra = datetime.now().strftime("%d/%m/%Y")

  col_d1, col_d2 = st.columns(2)
  with col_d1:
    if st.button("📅 Hoje", use_container_width=True):
      st.session_state.str_data_compra = datetime.now().strftime("%d/%m/%Y")
  with col_d2:
    if st.button("↩️ Ontem", use_container_width=True):
      ontem = datetime.now().date() - timedelta(days=1)
      st.session_state.str_data_compra = ontem.strftime("%d/%m/%Y")

  str_data_digitada = st.text_input(
      "Data da Compra (DD/MM/AAAA)",
      value=st.session_state.str_data_compra,
      max_chars=10,
      placeholder="DD/MM/AAAA",
  )
  st.session_state.str_data_compra = str_data_digitada

  try:
    data_compra = datetime.strptime(str_data_digitada, "%d/%m/%Y").date()
  except ValueError:
    st.error("Formato de data inválido! Utilize estritamente DD/MM/AAAA.")
    data_compra = None

  descricao = st.text_input("📝 Descrição", placeholder="Ex: Supermercado, Uber...")

  cartoes_dict, cartao_principal = carregar_cartoes()
  if not cartoes_dict:
    st.warning("Nenhum cartão encontrado. Verifique sua tabela de cartões.")
    st.stop()

  cartao_selecionado = st.selectbox(
      "💳 Cartão de Crédito",
      options=list(cartoes_dict.keys()),
      index=(
          list(cartoes_dict.keys()).index(cartao_principal)
          if cartao_principal in cartoes_dict
          else 0
      ),
  )

  cats_dict = carregar_categorias()
  cat_selecionada = st.selectbox(
      "📂 Categoria", options=list(cats_dict.keys()) if cats_dict else []
  )

  id_cat = cats_dict.get(cat_selecionada) if cat_selecionada else None
  subs_dict = carregar_subcategorias(id_cat)
  sub_selecionada = st.selectbox(
      "📂 Subcategoria", options=list(subs_dict.keys()) if subs_dict else []
  )
  id_sub = subs_dict.get(sub_selecionada) if sub_selecionada else None

  parcelado = st.checkbox("🔁 Despesa Parcelada")
  qtd_parcelas = 1
  if parcelado:
    qtd_parcelas = st.selectbox(
        "Número de parcelas",
        options=list(range(2, 13)),
        format_func=lambda x: f"{x}x",
    )

  st.divider()

  if st.button("✔ Cadastrar Despesa", type="primary", use_container_width=True):
    if not descricao.strip():
      st.error("Por favor, preencha a descrição da despesa.")
    elif not cat_selecionada:
      st.error("Selecione uma categoria.")
    elif not data_compra:
      st.error("Corrija o formato da data antes de salvar.")
    elif valor <= 0:
      st.error("O valor da despesa deve ser maior que zero.")
    else:
      try:
        id_cartao = cartoes_dict[cartao_selecionado]["id"]
        conn = conectar_banco()
        cursor = conn.cursor()
        desc_base = descricao.strip()

        if parcelado:
          valor_parcela = valor / qtd_parcelas
          for i in range(qtd_parcelas):
            data_parcela = data_compra + relativedelta(months=i)
            desc_parcela = f"{desc_base} ({i+1}/{qtd_parcelas})"
            cursor.execute(
                """
                            INSERT INTO lancamentos (tipo, valor, recebido, data_lancamento, descricao, id_categoria, id_subcategoria, id_cartao, repeticoes)
                            VALUES ('Despesa', %s, FALSE, %s, %s, %s, %s, %s, %s);
                        """,
                (
                    valor_parcela,
                    data_parcela.strftime("%Y-%m-%d"),
                    desc_parcela,
                    id_cat,
                    id_sub,
                    id_cartao,
                    qtd_parcelas,
                ),
            )
          st.success(
              f"Despesa parcelada em {qtd_parcelas}x cadastrada com sucesso!"
          )
        else:
          cursor.execute(
              """
                        INSERT INTO lancamentos (tipo, valor, recebido, data_lancamento, descricao, id_categoria, id_subcategoria, id_cartao, repeticoes)
                        VALUES ('Despesa', %s, FALSE, %s, %s, %s, %s, %s, %s);
                    """,
              (
                  valor,
                  data_compra.strftime("%Y-%m-%d"),
                  desc_base,
                  id_cat,
                  id_sub,
                  id_cartao,
                  1,
              ),
          )
          st.success("✔ Despesa de cartão cadastrada com sucesso!")

        conn.commit()
        cursor.close()
        conn.close()
      except Exception as ex:
        st.error(f"Erro ao salvar no banco de dados: {ex}")

# ==========================================
# ABA 3: GRÁFICOS POR CATEGORIA E SUBCATEGORIA
# ==========================================
elif menu == "📊 Gráficos por Categoria":
  st.markdown("### 📊 Análise Gráfica")

  # 1. Carregar Cartões para o Filtro Mobile
  try:
    conn_g = conectar_banco()
    cursor_g = conn_g.cursor()
    cursor_g.execute(
        "SELECT id, nome, dia_fechamento, dia_vencimento FROM cartoes ORDER BY"
        " nome;"
    )
    cartoes_db = cursor_g.fetchall()
    cursor_g.close()
    conn_g.close()
  except Exception:
    cartoes_db = []

  map_cartoes = {}
  map_cartao_detalhes = {}
  nomes_cartoes = ["Todos", "Despesas Gerais (Sem Cartão)"]
  for cid, cnome, c_fech, c_venc in cartoes_db:
    map_cartoes[cnome] = str(cid)
    map_cartao_detalhes[str(cid)] = {
        "fechamento": c_fech or 24,
        "vencimento": c_venc or 1,
    }
    nomes_cartoes.append(cnome)

  sel_cartao = st.selectbox("💳 Cartão / Origem", options=nomes_cartoes)

  # 2. Gerar Ciclos de Fatura formatados corretamente em português
  is_cartao = sel_cartao not in ["Todos", "Despesas Gerais (Sem Cartão)"]
  cartao_id = map_cartoes.get(sel_cartao) if is_cartao else None

  ciclos = []
  if is_cartao and cartao_id:
    detalhes = map_cartao_detalhes.get(cartao_id, {"fechamento": 24})
    fechamento_dia = detalhes["fechamento"]
    try:
      conn_c = conectar_banco()
      cursor_c = conn_c.cursor()
      cursor_c.execute(
          "SELECT MIN(data_lancamento), MAX(data_lancamento) FROM lancamentos"
          " WHERE id_cartao = %s;",
          (cartao_id,),
      )
      res_c = cursor_c.fetchone()
      cursor_c.close()
      conn_c.close()

      def para_date(val):
        if not val:
          return None
        if hasattr(val, "date"):
          return val.date()
        return val

      min_data = (
          para_date(res_c[0])
          if res_c and res_c[0]
          else date.today() - relativedelta(months=3)
      )
      max_data = (
          para_date(res_c[1])
          if res_c and res_c[1]
          else date.today() + relativedelta(months=6)
      )

      curr_date = date(min_data.year, min_data.month, 1)
      end_date = date(max_data.year, max_data.month, 1) + relativedelta(
          months=2
      )

      while curr_date <= end_date:
        r_ano = curr_date.year
        r_mes = curr_date.month
        max_d_fim = calendar.monthrange(r_ano, r_mes)[1]
        data_fim = date(r_ano, r_mes, min(fechamento_dia, max_d_fim))
        data_ini = data_fim - relativedelta(months=1) + relativedelta(days=1)
        
        # Formatação limpa segura baseada no dicionário numérico
        mes_nome = meses_pt.get(data_fim.month, str(data_fim.month))
        rotulo = (
            f"Fatura {mes_nome}/{data_fim.year} ({data_ini.strftime('%d/%m/%Y')}"
            f" a {data_fim.strftime('%d/%m/%Y')})"
        )
        ciclos.append((rotulo, data_ini, data_fim))
        curr_date += relativedelta(months=1)
    except Exception:
      pass
  else:
    hoje = date.today()
    for i in range(-3, 12):
      m_ref = hoje + relativedelta(months=i)
      mes_nome = meses_pt.get(m_ref.month, str(m_ref.month))
      rotulo = f"{mes_nome} de {m_ref.year}"
      ciclos.append((rotulo, m_ref.strftime("%Y-%m")))

  if not ciclos:
    ciclos = [("Mês Atual", datetime.now().strftime("%Y-%m"))]

  sel_ciclo_txt = st.selectbox(
      "📅 Período / Ciclo", options=[c[0] for c in ciclos]
  )
  ciclo_selecionado = next(c for c in ciclos if c[0] == sel_ciclo_txt)

  st.divider()

  # 3. Consulta ao Banco para os Gráficos
  try:
    conn_db = conectar_banco()
    cursor_db = conn_db.cursor()

    dados_cat = []
    if is_cartao and cartao_id:
      _, d_ini, d_fim = ciclo_selecionado
      cursor_db.execute(
          """
                SELECT c.id_categoria, c.descricao, SUM(l.valor) 
                FROM lancamentos l
                JOIN categorias c ON l.id_categoria = c.id_categoria
                WHERE l.tipo = 'Despesa' AND l.id_cartao = %s 
                  AND l.data_lancamento >= %s AND l.data_lancamento <= %s
                GROUP BY c.id_categoria, c.descricao 
                ORDER BY SUM(l.valor) DESC;
            """,
          (cartao_id, d_ini, d_fim),
      )
      dados_cat = cursor_db.fetchall()

    elif sel_cartao == "Despesas Gerais (Sem Cartão)":
      _, mes_ano_str = ciclo_selecionado
      cursor_db.execute(
          """
                SELECT c.id_categoria, c.descricao, SUM(l.valor) 
                FROM lancamentos l
                JOIN categorias c ON l.id_categoria = c.id_categoria
                WHERE l.tipo = 'Despesa' AND l.id_cartao IS NULL 
                  AND TO_CHAR(l.data_lancamento, 'YYYY-MM') = %s
                GROUP BY c.id_categoria, c.descricao 
                ORDER BY SUM(l.valor) DESC;
            """,
          (mes_ano_str,),
      )
      dados_cat = cursor_db.fetchall()

    else:
      _, mes_ano_str = ciclo_selecionado
      ano_sel, mes_sel = map(int, mes_ano_str.split("-"))
      acumulador_cats = {}

      for cid, det in map_cartao_detalhes.items():
        fechamento_dia = det["fechamento"]
        ref_date = date(
            ano_sel,
            mes_sel,
            min(15, calendar.monthrange(ano_sel, mes_sel)[1]),
        )
        d_ini, d_fim = calcular_ciclo_fatura(ref_date, fechamento_dia)
        cursor_db.execute(
            """
                    SELECT c.id_categoria, c.descricao, SUM(l.valor) 
                    FROM lancamentos l
                    JOIN categorias c ON l.id_categoria = c.id_categoria
                    WHERE l.tipo = 'Despesa' AND l.id_cartao = %s 
                      AND l.data_lancamento >= %s AND l.data_lancamento <= %s
                    GROUP BY c.id_categoria, c.descricao;
                """,
            (cid, d_ini, d_fim),
        )
        for cat_id, cat_desc, val in cursor_db.fetchall():
          v_f = float(val or 0)
          if cat_id in acumulador_cats:
            acumulador_cats[cat_id][1] += v_f
          else:
            acumulador_cats[cat_id] = [cat_desc, v_f]

      cursor_db.execute(
          """
                SELECT c.id_categoria, c.descricao, SUM(l.valor) 
                FROM lancamentos l
                JOIN categorias c ON l.id_categoria = c.id_categoria
                WHERE l.tipo = 'Despesa' AND l.id_cartao IS NULL 
                  AND TO_CHAR(l.data_lancamento, 'YYYY-MM') = %s
                GROUP BY c.id_categoria, c.descricao;
            """,
          (mes_ano_str,),
      )
      for cat_id, cat_desc, val in cursor_db.fetchall():
        v_f = float(val or 0)
        if cat_id in acumulador_cats:
          acumulador_cats[cat_id][1] += v_f
        else:
          acumulador_cats[cat_id] = [cat_desc, v_f]

      dados_cat = [
          (cid, dados[0], dados[1]) for cid, dados in acumulador_cats.items()
      ]
      dados_cat.sort(key=lambda x: x[2], reverse=True)

    if dados_cat:
      cats = [item[1] for item in dados_cat]
      valores_cat = [float(item[2]) for item in dados_cat]
      soma_total = sum(valores_cat)

      # Texto informativo do total
      valor_fmt = (
          f"R$ {soma_total:,.2f}"
          .replace(",", "X")
          .replace(".", ",")
          .replace("X", ".")
      )
      if is_cartao:
        st.info(
            f"💳 Total das despesas do cartão **{sel_cartao}**: **{valor_fmt}**"
        )
      elif sel_cartao == "Despesas Gerais (Sem Cartão)":
        st.info(
            f"📂 Total das despesas gerais no período: **{valor_fmt}**"
        )
      else:
        st.info(
            f"📊 Total geral de gastos (cartões + gerais): **{valor_fmt}**"
        )

      # Gráfico 1: Barras Verticais (Categorias)
      fig1, ax1 = plt.subplots(figsize=(8, 4.5))
      bars1 = ax1.bar(
          cats,
          valores_cat,
          color=["#2B6CB0", "#319795", "#D69E2E", "#DD6B20", "#C53030"],
      )
      ax1.set_title(
          f"Despesas por Categoria ({sel_cartao})",
          fontsize=10,
          fontweight="bold",
          color="#1A365D",
      )
      ax1.tick_params(axis="x", labelsize=8, rotation=30)
      ax1.tick_params(axis="y", labelsize=8)
      ax1.grid(axis="y", linestyle=":", alpha=0.6)

      for bar in bars1:
        h = bar.get_height()
        ax1.annotate(
            f"R$ {h:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=7,
            fontweight="bold",
            rotation=25,
        )

      fig1.tight_layout()
      st.pyplot(fig1)

      # Seleção interativa da Categoria para ver as Subcategorias no celular
      nomes_cats_disponiveis = [item[1] for item in dados_cat]
      cat_escolhida_nome = st.selectbox(
          "🔍 Escolha a Categoria para ver as Subcategorias",
          options=nomes_cats_disponiveis,
      )
      cat_escolhida_id = next(
          item[0] for item in dados_cat if item[1] == cat_escolhida_nome
      )

      # Buscar Subcategorias
      dados_sub = []
      if is_cartao and cartao_id:
        _, d_ini, d_fim = ciclo_selecionado
        cursor_db.execute(
            """
                    SELECT s.descricao, SUM(l.valor) 
                    FROM lancamentos l
                    JOIN subcategorias s ON l.id_subcategoria = s.id_subcategoria
                    WHERE l.tipo = 'Despesa' AND l.id_cartao = %s AND l.id_categoria = %s
                      AND l.data_lancamento >= %s AND l.data_lancamento <= %s
                    GROUP BY s.descricao ORDER BY SUM(l.valor) ASC;
                """,
            (cartao_id, cat_escolhida_id, d_ini, d_fim),
        )
        dados_sub = cursor_db.fetchall()
      elif sel_cartao == "Despesas Gerais (Sem Cartão)":
        _, mes_ano_str = ciclo_selecionado
        cursor_db.execute(
            """
                    SELECT s.descricao, SUM(l.valor) 
                    FROM lancamentos l
                    JOIN subcategorias s ON l.id_subcategoria = s.id_subcategoria
                    WHERE l.tipo = 'Despesa' AND l.id_cartao IS NULL AND l.id_categoria = %s
                      AND TO_CHAR(l.data_lancamento, 'YYYY-MM') = %s
                    GROUP BY s.descricao ORDER BY SUM(l.valor) ASC;
                """,
            (cat_escolhida_id, mes_ano_str),
        )
        dados_sub = cursor_db.fetchall()
      else:
        _, mes_ano_str = ciclo_selecionado
        ano_sel, mes_sel = map(int, mes_ano_str.split("-"))
        acumulador_subs = {}

        for cid, det in map_cartao_detalhes.items():
          fechamento_dia = det["fechamento"]
          ref_date = date(
              ano_sel,
              mes_sel,
              min(15, calendar.monthrange(ano_sel, mes_sel)[1]),
          )
          d_ini, d_fim = calcular_ciclo_fatura(ref_date, fechamento_dia)
          cursor_db.execute(
              """
                        SELECT s.descricao, SUM(l.valor) 
                        FROM lancamentos l
                        JOIN subcategorias s ON l.id_subcategoria = s.id_subcategoria
                        WHERE l.tipo = 'Despesa' AND l.id_cartao = %s AND l.id_categoria = %s
                          AND l.data_lancamento >= %s AND l.data_lancamento <= %s
                        GROUP BY s.descricao;
                    """,
              (cid, cat_escolhida_id, d_ini, d_fim),
          )
          for sub_desc, val in cursor_db.fetchall():
            v_f = float(val or 0)
            if sub_desc in acumulador_subs:
              acumulador_subs[sub_desc] += v_f
            else:
              acumulador_subs[sub_desc] = v_f

        cursor_db.execute(
            """
                    SELECT s.descricao, SUM(l.valor) 
                    FROM lancamentos l
                    JOIN subcategorias s ON l.id_subcategoria = s.id_subcategoria
                    WHERE l.tipo = 'Despesa' AND l.id_cartao IS NULL AND l.id_categoria = %s
                      AND TO_CHAR(l.data_lancamento, 'YYYY-MM') = %s
                    GROUP BY s.descricao;
                """,
            (cat_escolhida_id, mes_ano_str),
        )
        for sub_desc, val in cursor_db.fetchall():
          v_f = float(val or 0)
          if sub_desc in acumulador_subs:
            acumulador_subs[sub_desc] += v_f
          else:
            acumulador_subs[sub_desc] = v_f

        dados_sub = [
            (s_desc, s_val) for s_desc, s_val in acumulador_subs.items()
        ]
        dados_sub.sort(key=lambda x: x[1])

      if dados_sub:
        subs = [item[0] for item in dados_sub]
        valores_sub = [float(item[1]) for item in dados_sub]

        # Gráfico 2: Barras Horizontais (Subcategorias)
        fig2, ax2 = plt.subplots(figsize=(8, 4))
        bars2 = ax2.barh(subs, valores_sub, color="#805AD5")
        ax2.set_title(
            f"Subcategorias de: {cat_escolhida_nome}",
            fontsize=10,
            fontweight="bold",
            color="#1A365D",
        )
        ax2.tick_params(axis="both", labelsize=8)
        ax2.grid(axis="x", linestyle=":", alpha=0.6)

        for bar in bars2:
          w = bar.get_width()
          ax2.annotate(
              f"R$ {w:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
              xy=(w, bar.get_y() + bar.get_height() / 2),
              xytext=(5, 0),
              textcoords="offset points",
              ha="left",
              va="center",
              fontsize=8,
              fontweight="bold",
          )

        fig2.tight_layout()
        st.pyplot(fig2)
      else:
        st.info(f"Nenhuma subcategoria registrada para '{cat_escolhida_nome}'.")

    else:
      st.info("Nenhuma despesa encontrada para este filtro e período.")

    cursor_db.close()
    conn_db.close()
  except Exception as e:
    st.error(f"Erro ao gerar gráficos: {e}")