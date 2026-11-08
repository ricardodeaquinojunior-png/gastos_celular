# -*- coding: utf-8 -*-
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
import calendar
import libsql
import matplotlib.pyplot as plt
import streamlit as st
import uuid

# Configuração da página para dispositivos móveis
st.set_page_config(
    page_title="Controle Financeiro - Cartões", page_icon="💳", layout="centered"
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


def conectar_banco():
  conn = None
  try:
    if "turso" in st.secrets:
      db_conf = st.secrets["turso"]
      conn = libsql.connect(db_conf["url"], auth_token=db_conf["auth_token"])
  except Exception:
    pass

  if conn is None:
    TURSO_URL = "https://controlegastos-jesraj.aws-us-east-1.turso.io"
    TURSO_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3OTIxNzI0NzEsImlkIjoiMDFhMTQ1YmUtZTAwMS03MWY5LTlmMWUtZmFkYTJkZDhhNmEyIiwia2lkIjoiODRpRll2SGxCQ01qVGxyWXVMR0xfUUtWY3E0N1dmWUVxRUxBSTdSNkFqQSIsInJpZCI6IjU1NmQ3ZmUxLTRjZTAtNGZlZi1hMTIzLTEzYzM0ODY5NDFhYiJ9.KqPYdc5g76qkjqBOqhkP3aF3PoLqhIUugJZG8-70X7_nuUv0L60yNxCmbyGNnUXBOeqCJ1_Gx039rl-dDloPCA"
    conn = libsql.connect(TURSO_URL, auth_token=TURSO_TOKEN)

  # Garante que a coluna atualizado_em existe na tabela lancamentos
  try:
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE lancamentos ADD COLUMN atualizado_em TEXT;")
    conn.commit()
    cursor.close()
  except Exception:
    pass

  return conn


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


def carregar_todas_subcategorias_com_categoria():
  """Retorna uma lista de subcategorias ordenadas alfabeticamente com suas respectivas categorias."""
  try:
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute("""
            SELECT s.id_subcategoria, s.descricao, c.id_categoria, c.descricao 
            FROM subcategorias s
            JOIN categorias c ON s.id_categoria = c.id_categoria
            ORDER BY s.descricao ASC;
        """)
    res = cursor.fetchall()
    cursor.close()
    conn.close()
    
    subs_lista = []
    if res:
      for row in res:
        subs_lista.append({
            "id_sub": str(row[0]),
            "sub_desc": row[1],
            "id_cat": str(row[2]),
            "cat_desc": row[3]
        })
    return subs_lista
  except Exception as e:
    st.error(f"Erro ao carregar subcategorias: {e}")
    return []


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


# --- Cabeçalho e Menu Superior ---
st.title("💳 Controle de Cartões")

menu = st.radio(
    "Navegação",
    [
        "➕ Nova Despesa Cartão",
        "💳 Faturas dos Cartões",
        "📊 Gráficos por Categoria",
    ],
    horizontal=True,
    label_visibility="collapsed",
)
st.divider()

# ==========================================
# ABA 1: FATURAS DOS CARTÕES
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
  st.subheader("💳 Faturas dos Cartões")

  cartoes_dict, _ = carregar_cartoes()
  if cartoes_dict:
    try:
      conn = conectar_banco()
      cursor = conn.cursor()
      cursor.execute("""
                SELECT l.valor, l.data_lancamento, l.descricao, c.nome, c.dia_fechamento 
                FROM lancamentos l
                JOIN cartoes c ON l.id_cartao = c.id
                WHERE l.id_cartao IS NOT NULL;
            """)
      todos_lanc_cartoes = cursor.fetchall()
      cursor.close()
      conn.close()

      faturas_por_cartao = {}
      if todos_lanc_cartoes:
        for row in todos_lanc_cartoes:
          val, ldata, ldesc, c_nome, c_fech = row[0], row[1], row[2], row[3], row[4]
          if not ldata:
            continue
          if isinstance(ldata, str):
            try:
              d_date = datetime.strptime(ldata.split()[0], "%Y-%m-%d").date()
            except ValueError:
              continue
          else:
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
                if isinstance(data_item, str):
                  data_item_fmt = data_item.split()[0]
                else:
                  data_item_fmt = (
                      data_item.strftime("%d/%m/%Y")
                      if hasattr(data_item, "strftime")
                      else str(data_item)
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
# ABA 2: NOVA DESPESA CARTÃO & CRUD
# ==========================================
elif menu == "➕ Nova Despesa Cartão":
  st.markdown("### 💳 Nova Despesa de Cartão & CRUD")

  aba_op_cartao = st.radio(
      "Ação Cartão", ["➕ Nova Despesa", "✏️ Gerenciar / Editar Despesas"], horizontal=True
  )
  st.divider()

  if aba_op_cartao == "➕ Nova Despesa":
    cartoes_dict, cartao_principal = carregar_cartoes()
    if not cartoes_dict:
      st.warning("Nenhum cartão encontrado. Verifique sua tabela de cartões.")
      st.stop()

    # 1. Seleção do Cartão por Radio (bolinhas)
    st.markdown("##### 💳 Despesas de Cartão")
    lista_nomes_cartoes = list(cartoes_dict.keys())
    cartao_selecionado = st.radio(
        "Selecione o Cartão",
        options=lista_nomes_cartoes,
        index=lista_nomes_cartoes.index(cartao_principal) if cartao_principal in lista_nomes_cartoes else 0,
        horizontal=True,
        label_visibility="collapsed"
    )

    # 2. Campo de Valor com máscara de moeda progressiva
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

    # 3. Campo Descrição
    descricao = st.text_input("📝 Descrição", placeholder="Ex: Supermercado, Uber...")

    # 4. Subcategorias em ordem alfabética e Categoria automática
    subs_lista = carregar_todas_subcategorias_com_categoria()
    sub_opcoes = [item["sub_desc"] for item in subs_lista] if subs_lista else []

    sub_selecionada = st.selectbox(
        "📂 Subcategoria",
        options=sub_opcoes,
        placeholder="Selecione a subcategoria..."
    )

    # Identificar a categoria correspondente à subcategoria escolhida
    id_cat = None
    id_sub = None
    cat_desc_exibicao = ""
    if sub_selecionada and subs_lista:
      item_encontrado = next((i for i in subs_lista if i["sub_desc"] == sub_selecionada), None)
      if item_encontrado:
        id_sub = item_encontrado["id_sub"]
        id_cat = item_encontrado["id_cat"]
        cat_desc_exibicao = item_encontrado["cat_desc"]

    st.text_input(
        "📂 Categoria (Preenchimento Automático)",
        value=cat_desc_exibicao,
        disabled=True
    )

    # 5. Data da compra
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
      elif not sub_selecionada:
        st.error("Selecione uma subcategoria.")
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
          agora_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

          if parcelado:
            valor_parcela = valor / qtd_parcelas
            for i in range(qtd_parcelas):
              data_parcela = data_compra + relativedelta(months=i)
              desc_parcela = f"{desc_base} ({i+1}/{qtd_parcelas})"
              novo_id = str(uuid.uuid4())
              cursor.execute(
                  """
                              INSERT INTO lancamentos (id, tipo, valor, recebido, data_lancamento, descricao, id_categoria, id_subcategoria, id_cartao, repeticoes, atualizado_em)
                              VALUES (?, 'Despesa', ?, 0, ?, ?, ?, ?, ?, ?, ?);
                          """,
                  (
                      novo_id,
                      valor_parcela,
                      data_parcela.strftime("%Y-%m-%d"),
                      desc_parcela,
                      id_cat,
                      id_sub,
                      id_cartao,
                      qtd_parcelas,
                      agora_ts,
                  ),
              )
            st.success(
                f"Despesa parcelada em {qtd_parcelas}x cadastrada com sucesso!"
            )
          else:
            novo_id = str(uuid.uuid4())
            cursor.execute(
                """
                          INSERT INTO lancamentos (id, tipo, valor, recebido, data_lancamento, descricao, id_categoria, id_subcategoria, id_cartao, repeticoes, atualizado_em)
                          VALUES (?, 'Despesa', ?, 0, ?, ?, ?, ?, ?, ?, ?);
                      """,
                (
                    novo_id,
                    valor,
                    data_compra.strftime("%Y-%m-%d"),
                    desc_base,
                    id_cat,
                    id_sub,
                    id_cartao,
                    1,
                    agora_ts,
                ),
            )
            st.success("✔ Despesa de cartão cadastrada com sucesso!")

          conn.commit()
          cursor.close()
          conn.close()
        except Exception as ex:
          st.error(f"Erro ao salvar no banco de dados: {ex}")

  else:  # Gerenciar / Editar Despesas de Cartão
    st.subheader("✏️ Gerenciar Despesas de Cartão")

    cartoes_dict, _ = carregar_cartoes()
    if not cartoes_dict:
      st.warning("Nenhum cartão cadastrado.")
    else:
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

      mes_selecionado_c = st.selectbox(
          "📅 Mês de Referência",
          options=lista_meses_opcoes,
          index=indice_atual,
          format_func=formatar_mes_pt,
          key="mes_filtro_cartao",
      )

      opcoes_filtro_cartoes = ["Todos os cartões"] + list(cartoes_dict.keys())
      cartao_filtro_escolhida = st.selectbox(
          "💳 Filtrar por Cartão",
          options=opcoes_filtro_cartoes,
          key="cartao_filtro_cartao",
      )

      try:
        conn = conectar_banco()
        cursor = conn.cursor()

        if cartao_filtro_escolhida == "Todos os cartões":
          cursor.execute(
              """
                  SELECT l.id, l.data_lancamento, l.descricao, c.nome, l.valor 
                  FROM lancamentos l
                  JOIN cartoes c ON l.id_cartao = c.id
                  WHERE l.id_cartao IS NOT NULL AND SUBSTR(l.data_lancamento, 1, 7) = ?
                  ORDER BY l.data_lancamento ASC;
              """,
              (mes_selecionado_c,),
          )
          lista_regs_cartao = cursor.fetchall()
        else:
          id_cartao_selecionado = cartoes_dict[cartao_filtro_escolhida]["id"]
          cursor.execute(
              """
                  SELECT l.id, l.data_lancamento, l.descricao, c.nome, l.valor 
                  FROM lancamentos l
                  JOIN cartoes c ON l.id_cartao = c.id
                  WHERE l.id_cartao = ? AND SUBSTR(l.data_lancamento, 1, 7) = ?
                  ORDER BY l.data_lancamento ASC;
              """,
              (id_cartao_selecionado, mes_selecionado_c),
          )
          lista_regs_cartao = cursor.fetchall()

        cursor.close()
        conn.close()

        if not lista_regs_cartao:
          st.info(
              "Nenhuma despesa de cartão encontrada para este mês e filtros"
              " selecionados."
          )
        else:
          opcoes_map_cartao = {}
          for row in lista_regs_cartao:
            lid, d_data, l_desc, c_nome, l_val = row
            d_fmt = (
                datetime.strptime(d_data.split()[0], "%Y-%m-%d").strftime(
                    "%d/%m/%Y"
                )
                if d_data
                else ""
            )
            rotulo = f"[{d_fmt}] {c_nome} | {l_desc} (R$ {float(l_val or 0):,.2f})"
            opcoes_map_cartao[rotulo] = lid

          escolha_lanc_cartao = st.selectbox(
              "Selecione uma despesa para alterar ou excluir",
              options=list(opcoes_map_cartao.keys()),
              key="select_lanc_cartao",
          )
          id_selecionado_cartao = opcoes_map_cartao[escolha_lanc_cartao]

          conn = conectar_banco()
          cursor = conn.cursor()
          cursor.execute(
              """
                  SELECT id, valor, data_lancamento, descricao, id_cartao, id_categoria, id_subcategoria
                  FROM lancamentos WHERE id = ?;
              """,
              (id_selecionado_cartao,),
          )
          reg_cartao_atual = cursor.fetchone()
          cursor.close()
          conn.close()

          if reg_cartao_atual:
            _, rc_val, rc_data, rc_desc, rc_cartao_id, rc_cat, rc_sub = (
                reg_cartao_atual
            )

            try:
              dt_parse_c = datetime.strptime(
                  rc_data.split()[0], "%Y-%m-%d"
              ).date()
            except Exception:
              dt_parse_c = date.today()

            st.markdown("---")
            st.markdown("### 📝 Editar ou Excluir Despesa de Cartão")

            nova_desc_c = st.text_input(
                "Descrição", value=rc_desc or "", key=f"edit_desc_{id_selecionado_cartao}"
            )
            novo_valor_c = st.number_input(
                "Valor (R$)",
                min_value=0.0,
                value=float(rc_val or 0.0),
                step=1.0,
                key=f"edit_val_{id_selecionado_cartao}",
            )
            nova_data_obj_c = st.date_input(
                "Data da Compra",
                value=dt_parse_c,
                format="DD/MM/YYYY",
                key=f"edit_data_{id_selecionado_cartao}",
            )

            col_bc1, col_bc2 = st.columns(2)
            with col_bc1:
              if st.button(
                  "💾 Salvar Alterações",
                  type="primary",
                  use_container_width=True,
                  key=f"btn_salvar_{id_selecionado_cartao}",
              ):
                try:
                  conn = conectar_banco()
                  cursor = conn.cursor()
                  agora_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                  cursor.execute(
                      """
                                  UPDATE lancamentos 
                                  SET descricao = ?, valor = ?, data_lancamento = ?, atualizado_em = ?
                                  WHERE id = ?;
                              """,
                      (
                          nova_desc_c,
                          novo_valor_c,
                          nova_data_obj_c.strftime("%Y-%m-%d"),
                          agora_ts,
                          id_selecionado_cartao,
                      ),
                  )
                  conn.commit()
                  cursor.close()
                  conn.close()
                  st.success("✔ Despesa de cartão atualizada com sucesso!")
                  st.rerun()
                except Exception as ex:
                  st.error(f"Erro ao atualizar: {ex}")

            with col_bc2:
              if st.button(
                  "🗑️ Excluir Despesa",
                  type="secondary",
                  use_container_width=True,
                  key=f"btn_excluir_{id_selecionado_cartao}",
              ):
                try:
                  conn = conectar_banco()
                  cursor = conn.cursor()
                  cursor.execute(
                      "DELETE FROM lancamentos WHERE id = ?;",
                      (id_selecionado_cartao,),
                  )
                  conn.commit()
                  cursor.close()
                  conn.close()
                  st.success("🗑️ Despesa excluída com sucesso!")
                  st.rerun()
                except Exception as ex:
                  st.error(f"Erro ao excluir: {ex}")

      except Exception as e:
        st.error(f"Erro ao carregar lista de despesas de cartão: {e}")

# ==========================================
# ABA 3: GRÁFICOS POR CATEGORIA E SUBCATEGORIA
# ==========================================
elif menu == "📊 Gráficos por Categoria":
  st.markdown("### 📊 Análise Gráfica")

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
  nomes_cartoes = ["Todos"]
  for cid, cnome, c_fech, c_venc in cartoes_db:
    map_cartoes[cnome] = str(cid)
    map_cartao_detalhes[str(cid)] = {
        "fechamento": c_fech or 24,
        "vencimento": c_venc or 1,
    }
    nomes_cartoes.append(cnome)

  sel_cartao = st.selectbox("💳 Cartão", options=nomes_cartoes)

  is_cartao = sel_cartao != "Todos"
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
          " WHERE id_cartao = ?;",
          (cartao_id,),
      )
      res_c = cursor_c.fetchone()
      cursor_c.close()
      conn_c.close()

      def para_date(val):
        if not val:
          return None
        if isinstance(val, str):
          try:
            return datetime.strptime(val.split()[0], "%Y-%m-%d").date()
          except ValueError:
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
      if not min_data:
        min_data = date.today() - relativedelta(months=3)
      if not max_data:
        max_data = date.today() + relativedelta(months=6)

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
      ciclos.append((rotulo, m_ref))

  if not ciclos:
    ciclos = [("Mês Atual", datetime.now().strftime("%Y-%m"))]

  sel_ciclo_txt = st.selectbox(
      "📅 Período / Ciclo", options=[c[0] for c in ciclos]
  )
  ciclo_selecionado = next(c for c in ciclos if c[0] == sel_ciclo_txt)

  st.divider()

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
                WHERE l.tipo = 'Despesa' AND l.id_cartao = ? 
                  AND l.data_lancamento >= ? AND l.data_lancamento <= ?
                GROUP BY c.id_categoria, c.descricao 
                ORDER BY SUM(l.valor) DESC;
            """,
          (
              cartao_id,
              d_ini.strftime("%Y-%m-%d") if hasattr(d_ini, "strftime") else str(d_ini),
              d_fim.strftime("%Y-%m-%d") if hasattr(d_fim, "strftime") else str(d_fim),
          ),
      )
      dados_cat = cursor_db.fetchall()
    else:
      # Para "Todos", iteramos pelos ciclos consolidados por mês baseados na data de lançamento
      _, mes_ref_val = ciclo_selecionado
      if isinstance(mes_ref_val, str):
        mes_ano_str = mes_ref_val
      else:
        mes_ano_str = mes_ref_val.strftime("%Y-%m")

      cursor_db.execute(
          """
                SELECT c.id_categoria, c.descricao, SUM(l.valor) 
                FROM lancamentos l
                JOIN categorias c ON l.id_categoria = c.id_categoria
                WHERE l.tipo = 'Despesa' AND l.id_cartao IS NOT NULL 
                  AND SUBSTR(l.data_lancamento, 1, 7) = ?
                GROUP BY c.id_categoria, c.descricao 
                ORDER BY SUM(l.valor) DESC;
            """,
          (mes_ano_str,),
      )
      dados_cat = cursor_db.fetchall()

    if dados_cat:
      cats = [item[1] for item in dados_cat]
      valores_cat = [float(item[2]) for item in dados_cat]
      soma_total = sum(valores_cat)

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
      else:
        st.info(f"📊 Total geral de gastos dos cartões: **{valor_fmt}**")

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

      nomes_cats_disponiveis = [item[1] for item in dados_cat]
      cat_escolhida_nome = st.selectbox(
          "🔍 Escolha a Categoria para ver as Subcategorias",
          options=nomes_cats_disponiveis,
      )
      cat_escolhida_id = next(
          item[0] for item in dados_cat if item[1] == cat_escolhida_nome
      )

      dados_sub = []
      if is_cartao and cartao_id:
        _, d_ini, d_fim = ciclo_selecionado
        cursor_db.execute(
            """
                    SELECT s.descricao, SUM(l.valor) 
                    FROM lancamentos l
                    JOIN subcategorias s ON l.id_subcategoria = s.id_subcategoria
                    WHERE l.tipo = 'Despesa' AND l.id_cartao = ? AND l.id_categoria = ?
                      AND l.data_lancamento >= ? AND l.data_lancamento <= ?
                    GROUP BY s.descricao ORDER BY SUM(l.valor) ASC;
                """,
            (
                cartao_id,
                cat_escolhida_id,
                d_ini.strftime("%Y-%m-%d") if hasattr(d_ini, "strftime") else str(d_ini),
                d_fim.strftime("%Y-%m-%d") if hasattr(d_fim, "strftime") else str(d_fim),
            ),
        )
        dados_sub = cursor_db.fetchall()
      else:
        _, mes_ref_val = ciclo_selecionado
        mes_ano_str = mes_ref_val if isinstance(mes_ref_val, str) else mes_ref_val.strftime("%Y-%m")
        cursor_db.execute(
            """
                    SELECT s.descricao, SUM(l.valor) 
                    FROM lancamentos l
                    JOIN subcategorias s ON l.id_subcategoria = s.id_subcategoria
                    WHERE l.tipo = 'Despesa' AND l.id_cartao IS NOT NULL AND l.id_categoria = ?
                      AND SUBSTR(l.data_lancamento, 1, 7) = ?
                    GROUP BY s.descricao ORDER BY SUM(l.valor) ASC;
                """,
            (cat_escolhida_id, mes_ano_str),
        )
        dados_sub = cursor_db.fetchall()

      if dados_sub:
        subs = [item[0] for item in dados_sub]
        valores_sub = [float(item[1]) for item in dados_sub]

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