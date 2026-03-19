"""
Script para cadastrar os 5 candidatos no sistema RecrutaFácil.
Execute: python cadastrar_candidatos.py
"""
import sqlite3, os

DB = "recrutamento.db"

if not os.path.exists(DB):
    print("❌ Arquivo recrutamento.db não encontrado.")
    print("   Execute este script na mesma pasta do main.py")
    exit(1)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

# Encontra a vaga de Emissor(a) de Passagens Aéreas
vagas = conn.execute("SELECT * FROM vagas").fetchall()
print("\n📋 Vagas cadastradas no sistema:")
for v in vagas:
    print(f"   [{v['id']}] {v['titulo']}")

vaga_id = None
for v in vagas:
    if "emissor" in v['titulo'].lower() or "passagem" in v['titulo'].lower() or "aérea" in v['titulo'].lower():
        vaga_id = v['id']
        print(f"\n✅ Vaga encontrada: [{vaga_id}] {v['titulo']}")
        break

if not vaga_id:
    print("\n⚠️  Vaga de Emissor(a) não encontrada automaticamente.")
    vaga_id = int(input("   Digite o ID da vaga manualmente: "))

# Lista dos 5 candidatos extraídos dos currículos
candidatos = [
    {
        "nome": "Ivana Larissa Alves de Sousa",
        "email": "Ivana.larissa13@hotmail.com",
        "telefone": "(81) 99734-2264",
        "cidade": "Caruaru, PE",
    },
    {
        "nome": "Wisleandro Maciel de Lima Macedo",
        "email": "wisleandromaciel9@hotmail.com",
        "telefone": "(81) 99392-7779",
        "cidade": "Caruaru, PE",
    },
    {
        "nome": "Yasmim Harumi Tanaka",
        "email": "Kimikotanaka234@gmail.com",
        "telefone": "(81) 98912-7610",
        "cidade": "Caruaru, PE",
    },
    {
        "nome": "Ariel Cavalcante",
        "email": "arixtincavalcante@gmail.com",
        "telefone": "(81) 921409217",
        "cidade": "Divinópolis",
    },
    {
        "nome": "Jhonatta Douglas Basílio dos Santos",
        "email": "jhonatta1997@hotmail.com",
        "telefone": "(81) 99153-6698",
        "cidade": "Caruaru, PE",
    },
]

print(f"\n👥 Cadastrando {len(candidatos)} candidatos...\n")

inseridos = 0
for c in candidatos:
    # Verifica se já existe pelo email
    existe = conn.execute(
        "SELECT id FROM candidatos WHERE email=? AND vaga_id=?",
        (c['email'], vaga_id)
    ).fetchone()

    if existe:
        print(f"   ⚠️  {c['nome']} — já cadastrado (id={existe['id']}), pulando.")
        continue

    cur = conn.execute(
        "INSERT INTO candidatos (nome, email, telefone, cidade, vaga_id, etapa, status) VALUES (?,?,?,?,?,'curriculo','em_analise')",
        (c['nome'], c['email'], c['telefone'], c['cidade'], vaga_id)
    )
    print(f"   ✅ {c['nome']} cadastrado (id={cur.lastrowid})")
    inseridos += 1

conn.commit()
conn.close()

print(f"\n🎉 Concluído! {inseridos} candidato(s) inserido(s) com sucesso.")
print("   Acesse o painel RH para ver os candidatos em: /rh/candidatos")
