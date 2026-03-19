from flask import Flask, request, redirect, url_for, render_template, send_from_directory
import os, json, psycopg2, psycopg2.extras
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/curriculos'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

os.makedirs('uploads/curriculos', exist_ok=True)

def get_db():
    conn = psycopg2.connect(os.environ['DATABASE_URL'], sslmode='require')
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS vagas (
        id SERIAL PRIMARY KEY,
        titulo TEXT NOT NULL, departamento TEXT, cidade TEXT,
        salario TEXT, beneficios TEXT, horario TEXT, descricao TEXT,
        status TEXT DEFAULT 'aberta', criada_em TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS scorecard_criterios (
        id SERIAL PRIMARY KEY,
        vaga_id INTEGER, nome TEXT NOT NULL, peso INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS candidatos (
        id SERIAL PRIMARY KEY,
        nome TEXT NOT NULL, email TEXT, telefone TEXT, cidade TEXT,
        vaga_id INTEGER, curriculo_path TEXT,
        etapa TEXT DEFAULT 'curriculo', status TEXT DEFAULT 'em_analise',
        criado_em TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS triagem_ligacao (
        id SERIAL PRIMARY KEY,
        candidato_id INTEGER UNIQUE,
        disponibilidade INTEGER DEFAULT 0, localizacao INTEGER DEFAULT 0,
        horario_vaga INTEGER DEFAULT 0, mora_cidade INTEGER DEFAULT 0,
        salario_confirmado INTEGER DEFAULT 0,
        observacoes TEXT, resultado TEXT, data_ligacao TEXT
    );
    CREATE TABLE IF NOT EXISTS entrevista (
        id SERIAL PRIMARY KEY,
        candidato_id INTEGER UNIQUE, data_entrevista TEXT, entrevistador TEXT,
        nota_entrevista_rh INTEGER, obs_entrevista TEXT, resultado_entrevista TEXT
    );
    CREATE TABLE IF NOT EXISTS testes (
        id SERIAL PRIMARY KEY,
        candidato_id INTEGER, tipo TEXT, questao TEXT,
        opcoes TEXT, resposta_correta TEXT, resposta_candidato TEXT
    );
    CREATE TABLE IF NOT EXISTS resultado_testes (
        id SERIAL PRIMARY KEY,
        candidato_id INTEGER UNIQUE,
        nota_comportamento REAL, nota_raciocinio REAL,
        nota_portugues REAL, nota_excel REAL,
        nota_total REAL, aprovado INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS debriefing (
        id SERIAL PRIMARY KEY,
        candidato_id INTEGER UNIQUE, gestor TEXT, parecer TEXT,
        resultado TEXT, data_debriefing TEXT
    );
    CREATE TABLE IF NOT EXISTS evp (
        id SERIAL PRIMARY KEY,
        candidato_id INTEGER UNIQUE, salario_ofertado TEXT,
        beneficios TEXT, data_inicio TEXT, mensagem TEXT,
        status TEXT DEFAULT 'enviada', resposta_candidato TEXT, data_resposta TEXT
    );
    """)
    conn.commit()
    cur.close()
    conn.close()

init_db()

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def fetchall(conn, sql, params=()):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return rows

def fetchone(conn, sql, params=()):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(sql, params)
    row = cur.fetchone()
    cur.close()
    return row

def execute(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql, params)
    lastid = None
    if cur.description:
        try:
            lastid = cur.fetchone()[0]
        except:
            pass
    conn.commit()
    cur.close()
    return lastid

def q(sql):
    """Convert SQLite ? placeholders to PostgreSQL %s"""
    return sql.replace('?', '%s')

def upsert_triagem(conn, cid, disp, loc, hor, mora, sal, obs, resultado, data):
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO triagem_ligacao
            (candidato_id,disponibilidade,localizacao,horario_vaga,mora_cidade,
             salario_confirmado,observacoes,resultado,data_ligacao)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (candidato_id) DO UPDATE SET
            disponibilidade=EXCLUDED.disponibilidade,
            localizacao=EXCLUDED.localizacao,
            horario_vaga=EXCLUDED.horario_vaga,
            mora_cidade=EXCLUDED.mora_cidade,
            salario_confirmado=EXCLUDED.salario_confirmado,
            observacoes=EXCLUDED.observacoes,
            resultado=EXCLUDED.resultado,
            data_ligacao=EXCLUDED.data_ligacao
    """, (cid, disp, loc, hor, mora, sal, obs, resultado, data))
    conn.commit(); cur.close()

def upsert_entrevista(conn, cid, data_e, entre, nota, obs, resultado):
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO entrevista (candidato_id,data_entrevista,entrevistador,nota_entrevista_rh,obs_entrevista,resultado_entrevista)
        VALUES (%s,%s,%s,%s,%s,%s)
        ON CONFLICT (candidato_id) DO UPDATE SET
            data_entrevista=EXCLUDED.data_entrevista,
            entrevistador=EXCLUDED.entrevistador,
            nota_entrevista_rh=EXCLUDED.nota_entrevista_rh,
            obs_entrevista=EXCLUDED.obs_entrevista,
            resultado_entrevista=EXCLUDED.resultado_entrevista
    """, (cid, data_e, entre, nota, obs, resultado))
    conn.commit(); cur.close()

def upsert_resultado_testes(conn, cid, nc, nr, np_, ne, total, aprovado):
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO resultado_testes (candidato_id,nota_comportamento,nota_raciocinio,nota_portugues,nota_excel,nota_total,aprovado)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (candidato_id) DO UPDATE SET
            nota_comportamento=EXCLUDED.nota_comportamento,
            nota_raciocinio=EXCLUDED.nota_raciocinio,
            nota_portugues=EXCLUDED.nota_portugues,
            nota_excel=EXCLUDED.nota_excel,
            nota_total=EXCLUDED.nota_total,
            aprovado=EXCLUDED.aprovado
    """, (cid, nc, nr, np_, ne, total, aprovado))
    conn.commit(); cur.close()

def upsert_debriefing(conn, cid, gestor, parecer, resultado, data):
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO debriefing (candidato_id,gestor,parecer,resultado,data_debriefing)
        VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT (candidato_id) DO UPDATE SET
            gestor=EXCLUDED.gestor, parecer=EXCLUDED.parecer,
            resultado=EXCLUDED.resultado, data_debriefing=EXCLUDED.data_debriefing
    """, (cid, gestor, parecer, resultado, data))
    conn.commit(); cur.close()

def upsert_evp(conn, cid, sal, ben, inicio, msg):
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO evp (candidato_id,salario_ofertado,beneficios,data_inicio,mensagem,status)
        VALUES (%s,%s,%s,%s,%s,'enviada')
        ON CONFLICT (candidato_id) DO UPDATE SET
            salario_ofertado=EXCLUDED.salario_ofertado,
            beneficios=EXCLUDED.beneficios,
            data_inicio=EXCLUDED.data_inicio,
            mensagem=EXCLUDED.mensagem,
            status='enviada'
    """, (cid, sal, ben, inicio, msg))
    conn.commit(); cur.close()

def _criar_testes_padrao(conn, cid):
    cur = conn.cursor()
    cur.execute("DELETE FROM testes WHERE candidato_id=%s", (cid,))
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
        cur.execute("INSERT INTO testes (candidato_id,tipo,questao,opcoes,resposta_correta) VALUES (%s,%s,%s,%s,%s)",
                    (cid, tipo, questao, opcoes, correta))
    conn.commit(); cur.close()

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
    vagas = fetchall(conn, "SELECT * FROM vagas WHERE status='aberta'")
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
    execute(conn, "INSERT INTO candidatos (nome,email,telefone,cidade,vaga_id,curriculo_path) VALUES (%s,%s,%s,%s,%s,%s)",
            (nome, email, telefone, cidade, vaga_id, path))
    conn.close()
    return render_template('candidato_confirmacao.html', nome=nome)

@app.route('/candidato/testes/<int:cid>')
def testes_candidato(cid):
    conn = get_db()
    candidato  = fetchone(conn, "SELECT * FROM candidatos WHERE id=%s", (cid,))
    testes_raw = fetchall(conn, "SELECT * FROM testes WHERE candidato_id=%s", (cid,))
    resultado  = fetchone(conn, "SELECT * FROM resultado_testes WHERE candidato_id=%s", (cid,))
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
    testes = fetchall(conn, "SELECT * FROM testes WHERE candidato_id=%s", (cid,))
    acertos = {"comportamento":0,"raciocinio":0,"portugues":0,"excel":0}
    totais  = {"comportamento":0,"raciocinio":0,"portugues":0,"excel":0}
    cur = conn.cursor()
    for t in testes:
        resp = request.form.get(f"teste_{t['id']}", "")
        cur.execute("UPDATE testes SET resposta_candidato=%s WHERE id=%s", (resp, t['id']))
        totais[t['tipo']] += 1
        if resp == t['resposta_correta']:
            acertos[t['tipo']] += 1
    conn.commit(); cur.close()
    def pct(tipo):
        return round((acertos[tipo]/totais[tipo])*10, 1) if totais[tipo] else 0
    nc, nr, np_, ne = pct("comportamento"), pct("raciocinio"), pct("portugues"), pct("excel")
    total    = round((nc+nr+np_+ne)/4, 1)
    aprovado = 1 if total >= 6 else 0
    upsert_resultado_testes(conn, cid, nc, nr, np_, ne, total, aprovado)
    etapa = "debriefing" if aprovado else "reprovado_testes"
    execute(conn, "UPDATE candidatos SET etapa=%s WHERE id=%s", (etapa, cid))
    conn.close()
    return redirect(url_for('testes_candidato', cid=cid))

# ─── PAINEL RH ───────────────────────────────────────────────────────────────

@app.route('/rh')
def rh_dashboard():
    conn = get_db()
    vagas       = fetchall(conn, "SELECT * FROM vagas ORDER BY id DESC")
    total_c     = fetchone(conn, "SELECT COUNT(*) as n FROM candidatos")['n']
    em_processo = fetchone(conn, "SELECT COUNT(*) as n FROM candidatos WHERE status='em_analise'")['n']
    contratados = fetchone(conn, "SELECT COUNT(*) as n FROM candidatos WHERE etapa='contratado'")['n']
    conn.close()
    return render_template('rh_dashboard.html', vagas=vagas,
                           total_c=total_c, em_processo=em_processo, contratados=contratados)

# ─── VAGAS ───────────────────────────────────────────────────────────────────

@app.route('/rh/vagas/nova', methods=['GET','POST'])
def nova_vaga():
    if request.method == 'POST':
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO vagas (titulo,departamento,cidade,salario,beneficios,horario,descricao) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (request.form['titulo'], request.form.get('departamento',''),
             request.form.get('cidade',''), request.form.get('salario',''),
             request.form.get('beneficios',''), request.form.get('horario',''),
             request.form.get('descricao','')))
        vaga_id = cur.fetchone()[0]
        conn.commit()
        clist = [c.strip() for c in request.form.get('criterios','').split('\n') if c.strip()]
        plist = [p.strip() for p in request.form.get('pesos','').split('\n') if p.strip()]
        for i, c in enumerate(clist):
            peso = int(plist[i]) if i < len(plist) and plist[i].isdigit() else 1
            cur.execute("INSERT INTO scorecard_criterios (vaga_id,nome,peso) VALUES (%s,%s,%s)", (vaga_id,c,peso))
        conn.commit(); cur.close(); conn.close()
        return redirect(url_for('vaga_detalhe', vaga_id=vaga_id))
    return render_template('vaga_form.html', vaga=None)

@app.route('/rh/vagas/<int:vaga_id>')
def vaga_detalhe(vaga_id):
    conn = get_db()
    vaga      = fetchone(conn, "SELECT * FROM vagas WHERE id=%s", (vaga_id,))
    criterios = fetchall(conn, "SELECT * FROM scorecard_criterios WHERE vaga_id=%s", (vaga_id,))
    candidatos= fetchall(conn,
        "SELECT c.*, v.titulo as vaga_titulo FROM candidatos c LEFT JOIN vagas v ON c.vaga_id=v.id WHERE c.vaga_id=%s ORDER BY c.id DESC",
        (vaga_id,))
    conn.close()
    return render_template('vaga_detalhe.html', vaga=vaga, criterios=criterios, candidatos=candidatos)

# ─── CANDIDATOS ──────────────────────────────────────────────────────────────

@app.route('/rh/candidatos')
def listar_candidatos():
    etapa = request.args.get('etapa','')
    conn  = get_db()
    if etapa:
        candidatos = fetchall(conn,
            "SELECT c.*, v.titulo as vaga_titulo FROM candidatos c LEFT JOIN vagas v ON c.vaga_id=v.id WHERE c.etapa=%s ORDER BY c.id DESC",
            (etapa,))
    else:
        candidatos = fetchall(conn,
            "SELECT c.*, v.titulo as vaga_titulo FROM candidatos c LEFT JOIN vagas v ON c.vaga_id=v.id ORDER BY c.id DESC")
    conn.close()
    return render_template('candidatos_lista.html', candidatos=candidatos, etapa_filtro=etapa)

@app.route('/rh/candidatos/<int:cid>')
def candidato_detalhe(cid):
    conn = get_db()
    c = fetchone(conn, """
        SELECT c.*, v.titulo as vaga_titulo, v.salario as vaga_salario,
               v.beneficios as vaga_beneficios, v.horario as vaga_horario,
               v.cidade as vaga_cidade
        FROM candidatos c LEFT JOIN vagas v ON c.vaga_id=v.id
        WHERE c.id=%s""", (cid,))
    triagem    = fetchone(conn, "SELECT * FROM triagem_ligacao WHERE candidato_id=%s", (cid,))
    entrevista = fetchone(conn, "SELECT * FROM entrevista WHERE candidato_id=%s", (cid,))
    testes     = fetchall(conn, "SELECT * FROM testes WHERE candidato_id=%s", (cid,))
    resultado_t= fetchone(conn, "SELECT * FROM resultado_testes WHERE candidato_id=%s", (cid,))
    debriefing = fetchone(conn, "SELECT * FROM debriefing WHERE candidato_id=%s", (cid,))
    evp        = fetchone(conn, "SELECT * FROM evp WHERE candidato_id=%s", (cid,))
    conn.close()
    return render_template('candidato_detalhe.html', c=c, triagem=triagem,
                           entrevista=entrevista, testes=testes,
                           resultado_t=resultado_t, debriefing=debriefing, evp=evp)

# ─── TRIAGEM ─────────────────────────────────────────────────────────────────

@app.route('/rh/candidatos/<int:cid>/triagem', methods=['POST'])
def salvar_triagem(cid):
    conn = get_db()
    upsert_triagem(conn, cid,
        1 if request.form.get('disponibilidade') else 0,
        1 if request.form.get('localizacao') else 0,
        1 if request.form.get('horario_vaga') else 0,
        1 if request.form.get('mora_cidade') else 0,
        1 if request.form.get('salario_confirmado') else 0,
        request.form.get('observacoes',''),
        request.form['resultado'],
        request.form.get('data_ligacao',''))
    etapa = "entrevista" if request.form['resultado'] == 'aprovado' else "reprovado_ligacao"
    execute(conn, "UPDATE candidatos SET etapa=%s WHERE id=%s", (etapa, cid))
    conn.close()
    return redirect(url_for('candidato_detalhe', cid=cid))

# ─── ENTREVISTA ──────────────────────────────────────────────────────────────

@app.route('/rh/candidatos/<int:cid>/entrevista', methods=['POST'])
def salvar_entrevista(cid):
    resultado = request.form['resultado_entrevista']
    conn = get_db()
    upsert_entrevista(conn, cid,
        request.form.get('data_entrevista',''), request.form.get('entrevistador',''),
        request.form.get('nota_entrevista_rh', 0), request.form.get('obs_entrevista',''), resultado)
    if resultado == 'aprovado':
        _criar_testes_padrao(conn, cid)
        etapa = "testes"
    else:
        etapa = "reprovado_entrevista"
    execute(conn, "UPDATE candidatos SET etapa=%s WHERE id=%s", (etapa, cid))
    conn.close()
    return redirect(url_for('candidato_detalhe', cid=cid))

# ─── DEBRIEFING ──────────────────────────────────────────────────────────────

@app.route('/rh/candidatos/<int:cid>/debriefing', methods=['POST'])
def salvar_debriefing(cid):
    resultado = request.form['resultado']
    conn = get_db()
    upsert_debriefing(conn, cid,
        request.form.get('gestor',''), request.form.get('parecer',''),
        resultado, request.form.get('data_debriefing',''))
    etapa = "evp" if resultado == 'aprovado' else "reprovado_debriefing"
    execute(conn, "UPDATE candidatos SET etapa=%s WHERE id=%s", (etapa, cid))
    conn.close()
    return redirect(url_for('candidato_detalhe', cid=cid))

# ─── EVP ─────────────────────────────────────────────────────────────────────

@app.route('/rh/candidatos/<int:cid>/evp', methods=['POST'])
def salvar_evp(cid):
    conn = get_db()
    upsert_evp(conn, cid,
        request.form.get('salario_ofertado',''), request.form.get('beneficios',''),
        request.form.get('data_inicio',''), request.form.get('mensagem',''))
    execute(conn, "UPDATE candidatos SET etapa='evp' WHERE id=%s", (cid,))
    conn.close()
    return redirect(url_for('candidato_detalhe', cid=cid))

@app.route('/rh/candidatos/<int:cid>/evp/resposta', methods=['POST'])
def resposta_evp(cid):
    resposta = request.form['resposta']
    conn = get_db()
    execute(conn, "UPDATE evp SET resposta_candidato=%s, status=%s, data_resposta=%s WHERE candidato_id=%s",
            (resposta, resposta, datetime.now().strftime("%Y-%m-%d"), cid))
    etapa = "contratado" if resposta == "aceita" else "recusou_evp"
    execute(conn, "UPDATE candidatos SET etapa=%s WHERE id=%s", (etapa, cid))
    conn.close()
    return redirect(url_for('candidato_detalhe', cid=cid))

# ─── SEED CANDIDATOS ─────────────────────────────────────────────────────────

@app.route('/admin/seed-candidatos')
def seed_candidatos():
    conn = get_db()
    vaga = fetchone(conn, "SELECT id FROM vagas WHERE titulo ILIKE '%emissor%' OR titulo ILIKE '%passagem%'")
    if not vaga:
        conn.close()
        return "Vaga nao encontrada. Crie a vaga primeiro em /rh/vagas/nova", 404
    candidatos = [
        ("Ivana Larissa Alves de Sousa","Ivana.larissa13@hotmail.com","(81) 99734-2264","Caruaru, PE"),
        ("Wisleandro Maciel de Lima Macedo","wisleandromaciel9@hotmail.com","(81) 99392-7779","Caruaru, PE"),
        ("Yasmim Harumi Tanaka","Kimikotanaka234@gmail.com","(81) 98912-7610","Caruaru, PE"),
        ("Ariel Cavalcante","arixtincavalcante@gmail.com","(81) 921409217","Divinopolis"),
        ("Jhonatta Douglas Basilio dos Santos","jhonatta1997@hotmail.com","(81) 99153-6698","Caruaru, PE"),
    ]
    inseridos = []
    for nome, email, tel, cidade in candidatos:
        existe = fetchone(conn, "SELECT id FROM candidatos WHERE email=%s", (email,))
        if not existe:
            execute(conn, "INSERT INTO candidatos (nome,email,telefone,cidade,vaga_id,etapa,status) VALUES (%s,%s,%s,%s,%s,'curriculo','em_analise')",
                    (nome, email, tel, cidade, vaga['id']))
            inseridos.append(nome)
    conn.close()
    if inseridos:
        return "OK: " + ", ".join(inseridos)
    return "Todos ja cadastrados."

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(debug=False, host='0.0.0.0', port=port)
