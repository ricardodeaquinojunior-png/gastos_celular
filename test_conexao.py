import asyncio
import libsql_client

# Configurações de acesso ao Turso (convertendo para https para o client HTTP)
TURSO_URL = "https://controlegastos-jesraj.aws-us-east-1.turso.io"
TURSO_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3OTIxNzI0NzEsImlkIjoiMDFhMTQ1YmUtZTAwMS03MWY5LTlmMWUtZmFkYTJkZDhhNmEyIiwia2lkIjoiODRpRll2SGxCQ01qVGxyWXVMR0xfUUtWY3E0N1dmWUVxRUxBSTdSNkFqQSIsInJpZCI6IjU1NmQ3ZmUxLTRjZTAtNGZlZi1hMTIzLTEzYzM0ODY5NDFhYiJ9.KqPYdc5g76qkjqBOqhkP3aF3PoLqhIUugJZG8-70X7_nuUv0L60yNxCmbyGNnUXBOeqCJ1_Gx039rl-dDloPCA"


async def testar_conexao_e_dados():
  print("Tentando conectar ao banco de dados do Turso via libsql-client...")
  try:
    # Cria o cliente assíncrono do Turso
    async with libsql_client.create_client(
        url=TURSO_URL, auth_token=TURSO_TOKEN
    ) as client:

      # 1. Testa a versão do SQLite/Turso
      result_ver = await client.execute("SELECT sqlite_version();")
      versao = result_ver.rows[0][0]
      print("\n✅ Conexão realizada com sucesso!")
      print(f"Versão do SQLite (Turso): {versao}\n")

      # 2. Busca dados da tabela lancamentos
      print("Consultando os últimos lançamentos na tabela 'lancamentos'...")
      resultado = await client.execute("SELECT * FROM lancamentos LIMIT 10;")

      colunas = resultado.columns
      registros = resultado.rows

      print(f"\n📊 Colunas encontradas: {colunas}")
      print(f"📁 Total de registros retornados nesta amostra: {len(registros)}\n")

      if registros:
        print("--- ÚLTIMOS LANÇAMENTOS ---")
        for i, reg in enumerate(registros, 1):
          print(f"Registro {i}: {reg}")
      else:
        print("⚠️ A tabela 'lancamentos' foi encontrada, mas está vazia.")

    print("\nConexão fechada com segurança.")

  except Exception as e:
    print("\n❌ Erro ao conectar ou consultar o banco de dados:")
    print(e)


if __name__ == "__main__":
  asyncio.run(testar_conexao_e_dados())