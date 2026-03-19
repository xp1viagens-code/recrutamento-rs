from flask import Flask, request, redirect, url_for, render_template, send_from_directory
import sqlite3, os, json
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/curriculos'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

os.makedirs('uploads/curriculos', exist_ok=True)
DB = 'recrutamento.db'

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS vagas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT NOT NULL, departamento TEXT, cidade TEXT,
        salario TEXT, beneficios TEXT, horario TEXT, descricao TEXT,
        status TEXT DEFAULT 'aberta', criada_em TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS scorecard_criterios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vaga_id INTEGER, nome TEXT NOT NULL, peso INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS candidatos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL, email TEXT, telefone TEXT, cidade TEXT,
        vaga_id INTEGER, curriculo_path TEXT,
        etapa TEXT DEFAULT 'curriculo', status TEXT DEFAULT 'em_analise',
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS triagem_ligacao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidato_id INTEGER UNIQUE,
        disponibilidade INTEGER DEFAULT 0, localizacao INTEGER DEFAULT 0,
        horario_vaga INTEGER DEFAULT 0, mora_cidade INTEGER DEFAULT 0,
        salario_confirmado INTEGER DEFAULT 0,
        observacoes TEXT, resultado TEXT, data_ligacao TEXT
    );
    CREATE TABLE IF NOT EXISTS entrevista (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidato_id INTEGER UNIQUE, data_entrevista TEXT, entrevistador TEXT,
        nota_entrevista_rh INTEGER, obs_entrevista TEXT, resultado_entrevista TEXT
    );
    CREATE TABLE IF NOT EXISTS testes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidato_id INTEGER, tipo TEXT, questao TEXT,
        opcoes TEXT, resposta_correta TEXT, resposta_candidato TEXT
    );
    CREATE TABLE IF NOT EXISTS resultado_testes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidato_id INTEGER UNIQUE,
        nota_comportamento REAL, nota_raciocinio REAL,
        nota_portugues REAL, nota_excel REAL,
        nota_total REAL, aprovado INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS debriefing (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidato_id INTEGER UNIQUE, gestor TEXT, parecer TEXT,
        resultado TEXT, data_debriefing TEXT
    );
    CREATE TABLE IF NOT EXISTS evp (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidato_id INTEGER UNIQUE, salario_ofertado TEXT,
        beneficios TEXT, data_inicio TEXT, mensagem TEXT,
        status TEXT DEFAULT 'enviada', resposta_candidato TEXT, data_resposta TEXT
    );
    """)
    conn.commit()
    conn.close()

init_db()

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _criar_testes_padrao(conn, cid):
    conn.execute("DELETE FROM testes WHERE candidato_id=?", (cid,))
    testes = [
        ("comportamento","Como você reage diante de um conflito com um colega de trabalho?",
         json.dumps(["Evito o conflito e deixo passar","Converso diretamente com o colega","Reclamo para o gestor imediatamente","Fico em silêncio e trabalho sozinho"],ensure_ascii=False),"B"),
        ("comportamento","O que você faz quando recebe uma tarefa com prazo apertado?",
         json.dumps(["Peço para adiar o prazo","Priorizo e me organizo para entregar","Entrego incompleto","Ignoro o prazo"],ensure_ascii=False),"B"),
        ("raciocinio","Se um produto custa R$80 e tem 25% de desconto, qual o preço final?",
         json.dumps(["R$55","R$60","R$65","R$70"]),"B"),
        ("raciocinio","Qual número completa a sequência: 2, 6, 12, 20, __?",
         json.dumps(["28","30","32","36"]),"B"),
        ("portugues","Qual a forma correta?",
         json.dumps(["Fazem dois anos","Faz dois anos","Fez dois anos","Fazia dois anos"]),"B"),
        ("portugues","Identifique a frase sem erro ortográfico:",
         json.dumps(["Excessão à regra","Exeção à regra","Exceção à regra","Excessão a regra"],ensure_ascii=False),"C"),
        ("excel","Qual fórmula soma os valores de A1 até A10 no Excel?",
         json.dumps(["=SOMA(A1,A10)","=SOMA(A1:A10)","=TOTAL(A1:A10)","=SUM(A1,A10)"]),"B"),
        ("excel","O que faz a função =PROCV() no Excel?",
         json.dumps(["Soma valores de uma coluna","Busca um valor em uma tabela e retorna um dado relacionado","Conta células preenchidas","Formata células automaticamente"],ensure_ascii=False),"B"),
    ]
    for tipo, questao, opcoes, correta in testes:
        conn.execute(
            "INSERT INTO testes (candidato_id,tipo,questao,opcoes,resposta_correta) VALUES (?,?,?,?,?)",
            (cid, tipo, questao, opcoes, correta))

# ─── RAIZ ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/uploads/curriculos/<filename>')
def uploaded_file(filename):
    return send_from_directory('uploads/curriculos', filename)

# ─── PORTAL DO CANDIDATO ─────────────────────────────────────────────────────

@app.route('/candidato')
def candidato_portal():
    conn = get_db()
    vagas = conn.execute("SELECT * FROM vagas WHERE status='aberta'").fetchall()
    conn.close()
    return render_template('candidato_portal.html', vagas=vagas)

@app.route('/candidato/inscricao', methods=['POST'])
def candidato_inscricao():
    nome     = request.form['nome']
    email    = request.form['email']
    telefone = request.form['telefone']
    cidade   = request.form['cidade']
    vaga_id  = request.form['vaga_id']
    f = request.files['curriculo']
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(f.filename)}"
    path = os.path.join('uploads/curriculos', filename)
    f.save(path)
    conn = get_db()
    conn.execute(
        "INSERT INTO candidatos (nome,email,telefone,cidade,vaga_id,curriculo_path) VALUES (?,?,?,?,?,?)",
        (nome, email, telefone, cidade, vaga_id, path))
    conn.commit()
    conn.close()
    return render_template('candidato_confirmacao.html', nome=nome)

@app.route('/candidato/testes/<int:cid>')
def testes_candidato(cid):
    conn = get_db()
    candidato  = conn.execute("SELECT * FROM candidatos WHERE id=?", (cid,)).fetchone()
    testes_raw = conn.execute("SELECT * FROM testes WHERE candidato_id=?", (cid,)).fetchall()
    resultado  = conn.execute("SELECT * FROM resultado_testes WHERE candidato_id=?", (cid,)).fetchone()
    conn.close()
    testes = []
    for t in testes_raw:
        d = dict(t)
        d['opcoes_list'] = json.loads(d['opcoes'])
        testes.append(d)
    return render_template('testes.html', candidato=candidato, testes=testes, resultado=resultado)

@app.route('/candidato/testes/<int:cid>/responder', methods=['POST'])
def responder_testes(cid):
    conn = get_db()
    testes = conn.execute("SELECT * FROM testes WHERE candidato_id=?", (cid,)).fetchall()
    acertos = {"comportamento":0,"raciocinio":0,"portugues":0,"excel":0}
    totais  = {"comportamento":0,"raciocinio":0,"portugues":0,"excel":0}
    for t in testes:
        resp = request.form.get(f"teste_{t['id']}", "")
        conn.execute("UPDATE testes SET resposta_candidato=? WHERE id=?", (resp, t['id']))
        totais[t['tipo']] += 1
        if resp == t['resposta_correta']:
            acertos[t['tipo']] += 1
    def pct(tipo):
        return round((acertos[tipo]/totais[tipo])*10, 1) if totais[tipo] else 0
    nc, nr, np_, ne = pct("comportamento"), pct("raciocinio"), pct("portugues"), pct("excel")
    total    = round((nc+nr+np_+ne)/4, 1)
    aprovado = 1 if total >= 6 else 0
    conn.execute(
        "INSERT OR REPLACE INTO resultado_testes (candidato_id,nota_comportamento,nota_raciocinio,nota_portugues,nota_excel,nota_total,aprovado) VALUES (?,?,?,?,?,?,?)",
        (cid, nc, nr, np_, ne, total, aprovado))
    etapa = "debriefing" if aprovado else "reprovado_testes"
    conn.execute("UPDATE candidatos SET etapa=? WHERE id=?", (etapa, cid))
    conn.commit()
    conn.close()
    return redirect(url_for('testes_candidato', cid=cid))

# ─── PAINEL RH ───────────────────────────────────────────────────────────────

@app.route('/rh')
def rh_dashboard():
    conn = get_db()
    vagas       = conn.execute("SELECT * FROM vagas ORDER BY id DESC").fetchall()
    total_c     = conn.execute("SELECT COUNT(*) FROM candidatos").fetchone()[0]
    em_processo = conn.execute("SELECT COUNT(*) FROM candidatos WHERE status='em_analise'").fetchone()[0]
    contratados = conn.execute("SELECT COUNT(*) FROM candidatos WHERE etapa='contratado'").fetchone()[0]
    conn.close()
    return render_template('rh_dashboard.html', vagas=vagas,
                           total_c=total_c, em_processo=em_processo, contratados=contratados)

# ─── VAGAS ───────────────────────────────────────────────────────────────────

@app.route('/rh/vagas/nova', methods=['GET','POST'])
def nova_vaga():
    if request.method == 'POST':
        conn = get_db()
        cur = conn.execute(
            "INSERT INTO vagas (titulo,departamento,cidade,salario,beneficios,horario,descricao) VALUES (?,?,?,?,?,?,?)",
            (request.form['titulo'], request.form.get('departamento',''),
             request.form.get('cidade',''), request.form.get('salario',''),
             request.form.get('beneficios',''), request.form.get('horario',''),
             request.form.get('descricao','')))
        vaga_id = cur.lastrowid
        clist = [c.strip() for c in request.form.get('criterios','').split('\n') if c.strip()]
        plist = [p.strip() for p in request.form.get('pesos','').split('\n') if p.strip()]
        for i, c in enumerate(clist):
            peso = int(plist[i]) if i < len(plist) and plist[i].isdigit() else 1
            conn.execute("INSERT INTO scorecard_criterios (vaga_id,nome,peso) VALUES (?,?,?)", (vaga_id,c,peso))
        conn.commit()
        conn.close()
        return redirect(url_for('vaga_detalhe', vaga_id=vaga_id))
    return render_template('vaga_form.html', vaga=None)

@app.route('/rh/vagas/<int:vaga_id>')
def vaga_detalhe(vaga_id):
    conn = get_db()
    vaga      = conn.execute("SELECT * FROM vagas WHERE id=?", (vaga_id,)).fetchone()
    criterios = conn.execute("SELECT * FROM scorecard_criterios WHERE vaga_id=?", (vaga_id,)).fetchall()
    candidatos= conn.execute(
        "SELECT c.*, v.titulo as vaga_titulo FROM candidatos c LEFT JOIN vagas v ON c.vaga_id=v.id WHERE c.vaga_id=? ORDER BY c.id DESC",
        (vaga_id,)).fetchall()
    conn.close()
    return render_template('vaga_detalhe.html', vaga=vaga, criterios=criterios, candidatos=candidatos)

# ─── CANDIDATOS ──────────────────────────────────────────────────────────────

@app.route('/rh/candidatos')
def listar_candidatos():
    etapa = request.args.get('etapa','')
    conn  = get_db()
    q     = "SELECT c.*, v.titulo as vaga_titulo FROM candidatos c LEFT JOIN vagas v ON c.vaga_id=v.id"
    params= []
    if etapa:
        q += " WHERE c.etapa=?"
        params.append(etapa)
    q += " ORDER BY c.id DESC"
    candidatos = conn.execute(q, params).fetchall()
    conn.close()
    return render_template('candidatos_lista.html', candidatos=candidatos, etapa_filtro=etapa)

@app.route('/rh/candidatos/<int:cid>')
def candidato_detalhe(cid):
    conn = get_db()
    c = conn.execute("""
        SELECT c.*, v.titulo as vaga_titulo, v.salario as vaga_salario,
               v.beneficios as vaga_beneficios, v.horario as vaga_horario,
               v.cidade as vaga_cidade
        FROM candidatos c LEFT JOIN vagas v ON c.vaga_id=v.id
        WHERE c.id=?""", (cid,)).fetchone()
    triagem    = conn.execute("SELECT * FROM triagem_ligacao WHERE candidato_id=?", (cid,)).fetchone()
    entrevista = conn.execute("SELECT * FROM entrevista WHERE candidato_id=?", (cid,)).fetchone()
    testes     = conn.execute("SELECT * FROM testes WHERE candidato_id=?", (cid,)).fetchall()
    resultado_t= conn.execute("SELECT * FROM resultado_testes WHERE candidato_id=?", (cid,)).fetchone()
    debriefing = conn.execute("SELECT * FROM debriefing WHERE candidato_id=?", (cid,)).fetchone()
    evp        = conn.execute("SELECT * FROM evp WHERE candidato_id=?", (cid,)).fetchone()
    conn.close()
    return render_template('candidato_detalhe.html', c=c, triagem=triagem,
                           entrevista=entrevista, testes=testes,
                           resultado_t=resultado_t, debriefing=debriefing, evp=evp)

# ─── TRIAGEM ─────────────────────────────────────────────────────────────────

@app.route('/rh/candidatos/<int:cid>/triagem', methods=['POST'])
def salvar_triagem(cid):
    conn = get_db()
    conn.execute("""INSERT OR REPLACE INTO triagem_ligacao
        (candidato_id,disponibilidade,localizacao,horario_vaga,mora_cidade,
         salario_confirmado,observacoes,resultado,data_ligacao)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (cid,
         1 if request.form.get('disponibilidade') else 0,
         1 if request.form.get('localizacao') else 0,
         1 if request.form.get('horario_vaga') else 0,
         1 if request.form.get('mora_cidade') else 0,
         1 if request.form.get('salario_confirmado') else 0,
         request.form.get('observacoes',''),
         request.form['resultado'],
         request.form.get('data_ligacao','')))
    etapa = "entrevista" if request.form['resultado'] == 'aprovado' else "reprovado_ligacao"
    conn.execute("UPDATE candidatos SET etapa=? WHERE id=?", (etapa, cid))
    conn.commit(); conn.close()
    return redirect(url_for('candidato_detalhe', cid=cid))

# ─── ENTREVISTA ──────────────────────────────────────────────────────────────

@app.route('/rh/candidatos/<int:cid>/entrevista', methods=['POST'])
def salvar_entrevista(cid):
    resultado = request.form['resultado_entrevista']
    conn = get_db()
    conn.execute("""INSERT OR REPLACE INTO entrevista
        (candidato_id,data_entrevista,entrevistador,nota_entrevista_rh,obs_entrevista,resultado_entrevista)
        VALUES (?,?,?,?,?,?)""",
        (cid, request.form.get('data_entrevista',''), request.form.get('entrevistador',''),
         request.form.get('nota_entrevista_rh', 0), request.form.get('obs_entrevista',''), resultado))
    if resultado == 'aprovado':
        _criar_testes_padrao(conn, cid)
        etapa = "testes"
    else:
        etapa = "reprovado_entrevista"
    conn.execute("UPDATE candidatos SET etapa=? WHERE id=?", (etapa, cid))
    conn.commit(); conn.close()
    return redirect(url_for('candidato_detalhe', cid=cid))

# ─── DEBRIEFING ──────────────────────────────────────────────────────────────

@app.route('/rh/candidatos/<int:cid>/debriefing', methods=['POST'])
def salvar_debriefing(cid):
    resultado = request.form['resultado']
    conn = get_db()
    conn.execute("""INSERT OR REPLACE INTO debriefing
        (candidato_id,gestor,parecer,resultado,data_debriefing)
        VALUES (?,?,?,?,?)""",
        (cid, request.form.get('gestor',''), request.form.get('parecer',''),
         resultado, request.form.get('data_debriefing','')))
    etapa = "evp" if resultado == 'aprovado' else "reprovado_debriefing"
    conn.execute("UPDATE candidatos SET etapa=? WHERE id=?", (etapa, cid))
    conn.commit(); conn.close()
    return redirect(url_for('candidato_detalhe', cid=cid))

# ─── EVP ─────────────────────────────────────────────────────────────────────

@app.route('/rh/candidatos/<int:cid>/evp', methods=['POST'])
def salvar_evp(cid):
    conn = get_db()
    conn.execute("""INSERT OR REPLACE INTO evp
        (candidato_id,salario_ofertado,beneficios,data_inicio,mensagem,status)
        VALUES (?,?,?,?,?,'enviada')""",
        (cid, request.form.get('salario_ofertado',''), request.form.get('beneficios',''),
         request.form.get('data_inicio',''), request.form.get('mensagem','')))
    conn.execute("UPDATE candidatos SET etapa='evp' WHERE id=?", (cid,))
    conn.commit(); conn.close()
    return redirect(url_for('candidato_detalhe', cid=cid))

@app.route('/rh/candidatos/<int:cid>/evp/resposta', methods=['POST'])
def resposta_evp(cid):
    resposta = request.form['resposta']
    conn = get_db()
    conn.execute("UPDATE evp SET resposta_candidato=?, status=?, data_resposta=? WHERE candidato_id=?",
                 (resposta, resposta, datetime.now().strftime("%Y-%m-%d"), cid))
    etapa = "contratado" if resposta == "aceita" else "recusou_evp"
    conn.execute("UPDATE candidatos SET etapa=? WHERE id=?", (etapa, cid))
    conn.commit(); conn.close()
    return redirect(url_for('candidato_detalhe', cid=cid))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(debug=False, host='0.0.0.0', port=port)


@app.route('/admin/seed-candidatos')
def seed_candidatos():
    conn = get_db()
    vaga = conn.execute("SELECT id FROM vagas WHERE titulo LIKE '%missor%' OR titulo LIKE '%assagem%'").fetchone()
    if not vaga:
        conn.close()
        return "Vaga nao encontrada", 404
    candidatos = [
        ("Ivana Larissa Alves de Sousa","Ivana.larissa13@hotmail.com","(81) 99734-2264","Caruaru, PE"),
        ("Wisleandro Maciel de Lima Macedo","wisleandromaciel9@hotmail.com","(81) 99392-7779","Caruaru, PE"),
        ("Yasmim Harumi Tanaka","Kimikotanaka234@gmail.com","(81) 98912-7610","Caruaru, PE"),
        ("Ariel Cavalcante","arixtincavalcante@gmail.com","(81) 921409217","Divinopolis"),
        ("Jhonatta Douglas Basilio dos Santos","jhonatta1997@hotmail.com","(81) 99153-6698","Caruaru, PE"),
    ]
    inseridos = []
    for nome, email, tel, cidade in candidatos:
        existe = conn.execute("SELECT id FROM candidatos WHERE email=?", (email,)).fetchone()
        if not existe:
            conn.execute("INSERT INTO candidatos (nome,email,telefone,cidade,vaga_id,etapa,status) VALUES (?,?,?,?,?,'curriculo','em_analise')",
                         (nome, email, tel, cidade, vaga['id']))
            inseridos.append(nome)
    conn.commit()
    conn.close()
    if inseridos:
        return "OK: " + ", ".join(inseridos)
    return "Todos ja cadastrados."
