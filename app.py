# -*- coding: utf-8 -*-
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from zoneinfo import ZoneInfo
import calendar
import libsql
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

  # Garante que colunas de controle essenciais existem
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
st.title("💳 Despesas de Cartão")

menu = st.radio(
    "Navegação",
    [
        "➕ Despesas de Cartão",
        "💳 Faturas dos Cartões",
        "⚙️ Categorias e Subcategorias",
    ],
    horizontal=True,
    label_visibility="collapsed",
)
st.divider()

# ==========================================
# ABA 1: DESPESAS DE CARTÃO (NOVO LANÇAMENTO & RESUMO)
# ==========================================
if menu == "➕ Despesas de Cartão":
  cartoes_dict, cartao_principal = carregar_cartoes()
  if not cartoes_dict:
    st.warning("Nenhum cartão encontrado. Verifique sua tabela de cartões.")
    st.stop()

  # 1. Seleção do Cartão por Radio (bolinhas)
  st.markdown("##### 💳 Selecione o Cartão")
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
    st.session_state.str_data_compra = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y")

  col_d1, col_d2 = st.columns(2)
  with col_d1:
    if st.button("📅 Hoje", use_container_width=True):
      st.session_state.str_data_compra = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y")
  with col_d2:
    if st.button("↩️ Ontem", use_container_width=True):
      ontem = datetime.now(ZoneInfo("America/Sao_Paulo")).date() - timedelta(days=1)
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
        
        fuso_br = ZoneInfo("America/Sao_Paulo")
        agora_ts = datetime.now(fuso_br).strftime("%Y-%m-%d %H:%M:%S")

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

  # ==========================================
  # SEÇÃO DE RESUMO ABAIXO DO CADASTRO
  # ==========================================
  st.divider()
  st.markdown("### 📋 Resumo das Despesas por Período")

  hoje = datetime.now(ZoneInfo("America/Sao_Paulo"))
  lista_meses_opcoes = []
  for i in range(-3, 4):
    m_ref = hoje + relativedelta(months=i)
    lista_meses_opcoes.append(m_ref.strftime("%Y-%m"))

  def formatar_mes_pt(ano_mes):
    ano, mes = ano_mes.split("-")
    return f"{meses_pt.get(int(mes), mes)} de {ano}"

  mes_atual_str = hoje.strftime("%Y-%m")
  indice_atual = lista_meses_opcoes.index(mes_atual_str) if mes_atual_str in lista_meses_opcoes else 3

  mes_resumo_sel = st.selectbox(
      "📅 Período de Referência (Mês)",
      options=lista_meses_opcoes,
      index=indice_atual,
      format_func=formatar_mes_pt,
      key="resumo_mes_sel"
  )

  opcoes_cartao_resumo = ["Todos os cartões"] + list(cartoes_dict.keys())
  cartao_escolhido_resumo = st.selectbox("💳 Filtrar Cartão (Resumo)", options=opcoes_cartao_resumo, key="resumo_cartao_sel")

  try:
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT l.valor, l.data_lancamento, c.nome, 
               cat.descricao, sub.descricao
        FROM lancamentos l
        JOIN cartoes c ON l.id_cartao = c.id
        LEFT JOIN categorias cat ON l.id_categoria = cat.id_categoria
        LEFT JOIN subcategorias sub ON l.id_subcategoria = sub.id_subcategoria
        WHERE l.id_cartao IS NOT NULL;
    """)
    todos_lancamentos = cursor.fetchall()
    cursor.close()
    conn.close()
  except Exception as e:
    st.error(f"Erro ao carregar despesas para o resumo: {e}")
    todos_lancamentos = []

  lancamentos_filtrados = []
  totais_por_cartao = {}

  for row in todos_lancamentos:
    val, ldata, cnome, cat_desc, sub_desc = row
    if not ldata:
      continue
    try:
      d_date = datetime.strptime(ldata.split()[0], "%Y-%m-%d").date()
    except ValueError:
      continue

    fechamento_cartao = cartoes_dict.get(cnome, {}).get("fechamento", 24)
    inicio_ciclo, fim_ciclo = calcular_ciclo_fatura(d_date, fechamento_cartao)
    ciclo_ano_mes = fim_ciclo.strftime("%Y-%m")

    if ciclo_ano_mes == mes_resumo_sel:
      if cnome not in totais_por_cartao:
        totais_por_cartao[cnome] = {"total": 0.0, "inicio": inicio_ciclo, "fim": fim_ciclo}
      totais_por_cartao[cnome]["total"] += float(val or 0)

      if cartao_escolhido_resumo == "Todos os cartões" or cartao_escolhido_resumo == cnome:
        lancamentos_filtrados.append({
            "valor": float(val or 0),
            "cat_desc": cat_desc or "Sem Categoria",
            "sub_desc": sub_desc or "Sem Subcategoria"
        })

  if cartao_escolhido_resumo == "Todos os cartões" and totais_por_cartao:
    st.markdown("#### 📊 Totais por Cartão no Período:")
    for cnome, info in totais_por_cartao.items():
      p_inicio = info["inicio"].strftime('%d/%m/%Y')
      p_fim = info["fim"].strftime('%d/%m/%Y')
      val_cartao_fmt = f"R$ {info['total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
      st.markdown(f"- **{cnome}** (Período: {p_inicio} a {p_fim}): **{val_cartao_fmt}**")
    st.divider()

  agregado = {}
  total_geral = 0.0

  for item in lancamentos_filtrados:
    c_desc = item["cat_desc"]
    s_desc = item["sub_desc"]
    v = item["valor"]
    total_geral += v

    if c_desc not in agregado:
      agregado[c_desc] = {"total": 0.0, "subs": {}}
    agregado[c_desc]["total"] += v

    if s_desc not in agregado[c_desc]["subs"]:
      agregado[c_desc]["subs"][s_desc] = 0.0
    agregado[c_desc]["subs"][s_desc] += v

  if agregado:
    html_resumo = "<div style='font-family: sans-serif; font-size: 14px;'>"
    
    for c_desc, c_data in sorted(agregado.items(), key=lambda x: x[1]["total"], reverse=True):
      cat_total_fmt = f"{c_data['total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
      
      html_resumo += f"""<div style="display: flex; justify-content: space-between; font-weight: bold; margin-top: 6px; margin-bottom: 2px;">
<span>{c_desc}</span>
<span>{cat_total_fmt}</span>
</div>"""
      
      for s_desc, s_val in sorted(c_data["subs"].items(), key=lambda x: x[1], reverse=True):
        sub_val_fmt = f"{s_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        html_resumo += f"""<div style="display: flex; justify-content: space-between; padding-left: 16px; font-size: 13px; margin-bottom: 2px; color: #444;">
<span>{s_desc}</span>
<span>{sub_val_fmt}</span>
</div>"""
      
      html_resumo += "<hr style='margin: 6px 0; border: none; border-top: 1px solid #e0e0e0;'>"
    
    html_resumo += "</div>"
    st.markdown(html_resumo, unsafe_allow_html=True)

    total_geral_fmt = f"{total_geral:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    st.markdown(f"### **Total Geral: {total_geral_fmt}**")
  else:
    st.info("Nenhuma despesa encontrada para este cartão/período.")

# ==========================================
# ABA 2: FATURAS DOS CARTÕES
# ==========================================
elif menu == "💳 Faturas dos Cartões":
  hoje = datetime.now(ZoneInfo("America/Sao_Paulo"))
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
# ABA 3: CRUD DE CATEGORIAS E SUBCATEGORIAS
# ==========================================
elif menu == "⚙️ Categorias e Subcategorias":
  st.markdown("### ⚙️ Gerenciamento de Categorias e Subcategorias")
  
  aba_cat, aba_sub = st.tabs(["📁 Gerenciar Categorias", "📂 Gerenciar Subcategorias"])

  fuso_br = ZoneInfo("America/Sao_Paulo")
  agora_ts = datetime.now(fuso_br).strftime("%Y-%m-%d %H:%M:%S")

  # --- GESTÃO DE CATEGORIAS ---
  with aba_cat:
    st.markdown("#### ➕ Nova Categoria")
    nova_cat_desc = st.text_input("Descrição da Categoria", placeholder="Ex: Alimentação, Lazer...", key="input_nova_cat")
    
    if st.button("Cadastrar Categoria", type="primary"):
      if not nova_cat_desc.strip():
        st.error("Informe a descrição da categoria.")
      else:
        try:
          conn = conectar_banco()
          cursor = conn.cursor()
          novo_id_cat = str(uuid.uuid4())
          cursor.execute(
              "INSERT INTO categorias (id_categoria, created_at, descricao, atualizado_em) VALUES (?, ?, ?, ?);",
              (novo_id_cat, agora_ts, nova_cat_desc.strip(), agora_ts)
          )
          conn.commit()
          cursor.close()
          conn.close()
          st.success("Categoria cadastrada com sucesso!")
          st.rerun()
        except Exception as ex:
          st.error(f"Erro ao salvar categoria: {ex}")

    st.divider()
    st.markdown("#### 📋 Categorias Cadastradas")
    try:
      conn = conectar_banco()
      cursor = conn.cursor()
      cursor.execute("SELECT id_categoria, descricao FROM categorias ORDER BY descricao ASC;")
      cats_db = cursor.fetchall()
      cursor.close()
      conn.close()

      if cats_db:
        for cid_cat, cdesc in cats_db:
          with st.expander(f"📁 {cdesc}"):
            edit_cat_desc = st.text_input("Editar Descrição", value=cdesc, key=f"edit_cat_{cid_cat}")
            col_e1, col_e2 = st.columns(2)
            with col_e1:
              if st.button("💾 Salvar Alteração", key=f"btn_salv_cat_{cid_cat}"):
                try:
                  conn = conectar_banco()
                  cursor = conn.cursor()
                  cursor.execute("UPDATE categorias SET descricao = ?, atualizado_em = ? WHERE id_categoria = ?;", (edit_cat_desc.strip(), agora_ts, cid_cat))
                  conn.commit()
                  cursor.close()
                  conn.close()
                  st.success("Categoria atualizada!")
                  st.rerun()
                except Exception as ex:
                  st.error(f"Erro ao atualizar: {ex}")
            with col_e2:
              if st.button("🗑️ Excluir", key=f"btn_del_cat_{cid_cat}", type="secondary"):
                try:
                  conn = conectar_banco()
                  cursor = conn.cursor()
                  cursor.execute("DELETE FROM categorias WHERE id_categoria = ?;", (cid_cat,))
                  conn.commit()
                  cursor.close()
                  conn.close()
                  st.success("Categoria excluída!")
                  st.rerun()
                except Exception as ex:
                  st.error(f"Erro ao excluir (verifique se há dependências): {ex}")
      else:
        st.info("Nenhuma categoria cadastrada.")
    except Exception as e:
      st.error(f"Erro ao carregar categorias: {e}")

  # --- GESTÃO DE SUBCATEGORIAS ---
  with aba_sub:
    st.markdown("#### ➕ Nova Subcategoria")
    
    try:
      conn = conectar_banco()
      cursor = conn.cursor()
      cursor.execute("SELECT id_categoria, descricao FROM categorias ORDER BY descricao ASC;")
      lista_cats_select = cursor.fetchall()
      cursor.close()
      conn.close()
    except Exception:
      lista_cats_select = []

    if not lista_cats_select:
      st.warning("Cadastre ao menos uma categoria antes de gerenciar subcategorias.")
    else:
      cat_dict_map = {row[1]: row[0] for row in lista_cats_select}
      cat_escolhida_para_sub = st.selectbox("Selecione a Categoria Pai", options=list(cat_dict_map.keys()), key="select_cat_pai")
      nova_sub_desc = st.text_input("Descrição da Subcategoria", placeholder="Ex: Supermercado, Restaurante...", key="input_nova_sub")

      if st.button("Cadastrar Subcategoria", type="primary"):
        if not nova_sub_desc.strip():
          st.error("Informe a descrição da subcategoria.")
        else:
          try:
            id_cat_pai = cat_dict_map[cat_escolhida_para_sub]
            conn = conectar_banco()
            cursor = conn.cursor()
            novo_id_sub = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO subcategorias (id_subcategoria, created_at, descricao, id_categoria, atualizado_em) VALUES (?, ?, ?, ?, ?);",
                (novo_id_sub, agora_ts, nova_sub_desc.strip(), id_cat_pai, agora_ts)
            )
            conn.commit()
            cursor.close()
            conn.close()
            st.success("Subcategoria cadastrada com sucesso!")
            st.rerun()
          except Exception as ex:
            st.error(f"Erro ao salvar subcategoria: {ex}")

    st.divider()
    st.markdown("#### 📋 Subcategorias Cadastradas")
    subs_com_cat = carregar_todas_subcategorias_com_categoria()
    
    if subs_com_cat:
      for item in subs_com_cat:
        sid = item["id_sub"]
        sdesc = item["sub_desc"]
        scat_desc = item["cat_desc"]
        scat_id = item["id_cat"]

        with st.expander(f"📂 {sdesc} (Categoria: {scat_desc})"):
          edit_sub_desc = st.text_input("Editar Descrição", value=sdesc, key=f"edit_sub_{sid}")
          
          cat_opcoes_map = {row[1]: row[0] for row in lista_cats_select}
          cat_atual_nome = scat_desc
          nova_cat_pai_escolhida = st.selectbox(
              "Alterar Categoria", 
              options=list(cat_opcoes_map.keys()), 
              index=list(cat_opcoes_map.keys()).index(cat_atual_nome) if cat_atual_nome in cat_opcoes_map else 0,
              key=f"edit_sub_cat_{sid}"
          )
          novo_id_cat_pai = cat_opcoes_map[nova_cat_pai_escolhida]

          col_s1, col_s2 = st.columns(2)
          with col_s1:
            if st.button("💾 Salvar Alteração", key=f"btn_salv_sub_{sid}"):
              try:
                conn = conectar_banco()
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE subcategorias SET descricao = ?, id_categoria = ?, atualizado_em = ? WHERE id_subcategoria = ?;",
                    (edit_sub_desc.strip(), novo_id_cat_pai, agora_ts, sid)
                )
                conn.commit()
                cursor.close()
                conn.close()
                st.success("Subcategoria atualizada!")
                st.rerun()
              except Exception as ex:
                st.error(f"Erro ao atualizar: {ex}")
          with col_s2:
            if st.button("🗑️ Excluir", key=f"btn_del_sub_{sid}", type="secondary"):
              try:
                conn = conectar_banco()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM subcategorias WHERE id_subcategoria = ?;", (sid,))
                conn.commit()
                cursor.close()
                conn.close()
                st.success("Subcategoria excluída!")
                st.rerun()
              except Exception as ex:
                st.error(f"Erro ao excluir: {ex}")
    else:
      st.info("Nenhuma subcategoria cadastrada.")