import sqlite3

# Conecta ao banco local
conn = sqlite3.connect("controle_gastos.db")
cursor = conn.cursor()

# Altera o journal_mode para WAL
cursor.execute("PRAGMA journal_mode=WAL;")

# Confirma e fecha
conn.commit()
conn.close()

print("Banco de dados alterado para o modo WAL com sucesso!")