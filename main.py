from flask import Flask, request, redirect, url_for, render_template, jsonify, send_from_directory
import os, json, re, psycopg2, psycopg2.extras
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/curriculos'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
os.makedirs('uploads/curriculos', exist_ok=True)

# ─── DB ──────────────────────────────────────────────────────────────────────

def get_db():
    return psycopg2.connect(os.environ['DATABASE_URL'], sslmode='require')

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
    try:
        if 'RETURNING' in sql.upper():
            lastid = cur.fetchone()[0]
    except:
        pass
    conn.commit()
    cur.close()
    return lastid

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS candidatos (
        id SERIAL PRIMARY KEY,
        nome TEXT, email TEXT, telefone TEXT, cidade TEXT,
        formacao TEXT, experiencias TEXT, habilidades TEXT, resumo TEXT,
        curriculo_path TEXT, texto_curriculo TEXT,
        etapa TEXT DEFAULT 'curriculo',
        criado_em TIMESTAMP DEFAULT NOW()
    );
    """)
    conn.commit()
    cur.close()
    conn.close()

init_db()

# ─── EXTRAÇÃO SEM IA ─────────────────────────────────────────────────────────

def extrair_texto_pdf(path):
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return '\n'.join(p.extract_text() or '' for p in pdf.pages).strip()
    except Exception as e:
        print(f"Erro PDF: {e}")
        return ""

def extrair_dados_texto(texto):
    dados = {'nome':'','email':'','telefone':'','cidade':'',
             'formacao':'','experiencias':'','habilidades':'','resumo':''}
    linhas = [l.strip() for l in texto.split('\n') if l.strip()]

    # Email
    m = re.search(r'[\w\.\-\+]+@[\w\.\-]+\.\w+', texto)
    if m: dados['email'] = m.group()

    # Telefone
    m = re.search(r'(\(?\d{2}\)?\s?[\d\s\.\-]{7,13}\d)', texto)
    if m: dados['telefone'] = re.sub(r'\s+', ' ', m.group()).strip()

    # Cidade/Estado
    estados = r'(PE|SP|RJ|MG|BA|CE|RS|PR|SC|GO|DF|ES|AM|PA|MA|PI|AL|SE|RN|PB|MT|MS|RO|AC|AP|RR|TO)'
    m = re.search(r'([A-ZÀ-Ú][a-zà-ú]+(?:\s[A-ZÀ-Ú][a-zà-ú]+)*)\s*[,\-–/]\s*' + estados, texto)
    if m: dados['cidade'] = m.group().strip()

    # Nome — primeira linha que parece nome próprio
    for linha in linhas[:10]:
        limpa = re.sub(r'[^A-Za-zÀ-úÃãÕõÂâÊêÔôÁáÉéÍíÓóÚú\s]', '', linha).strip()
        palavras = limpa.split()
        skip_words = ['curriculo','curriculum','vitae','objetivo','email','telefone',
                      'fone','rua','avenida','formacao','educacao','experiencia']
        if (2 <= len(palavras) <= 6 and
            all(2 <= len(p) <= 25 for p in palavras) and
            sum(1 for p in palavras if p[0].isupper()) >= 2 and
            not any(sw in limpa.lower() for sw in skip_words)):
            dados['nome'] = limpa
            break

    # Seções por palavras-chave
    mapa = {
        'formacao':     ['forma', 'educa', 'acadê', 'gradu', 'ensino', 'instrução'],
        'experiencias': ['experi', 'profiss', 'histórico', 'cargo', 'empresa', 'emprego'],
        'habilidades':  ['habilid', 'compet', 'conhec', 'skill', 'qualific', 'ferrament'],
        'resumo':       ['resumo', 'objetivo', 'perfil', 'sobre mim', 'apresent'],
    }
    secao_atual = None
    conteudo = {k: [] for k in mapa}

    for linha in linhas:
        ll = linha.lower()
        achou = False
        for sec, kws in mapa.items():
            if any(kw in ll for kw in kws) and len(linha) < 70:
                secao_atual = sec
                achou = True
                break
        if not achou and secao_atual and len(linha) > 3:
            conteudo[secao_atual].append(linha)

    for k, v in conteudo.items():
        if v:
            dados[k] = ' | '.join(v[:6])

    return dados

# ─── ROTAS ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return redirect(url_for('rh_candidatos'))

@app.route('/uploads/curriculos/<filename>')
def uploaded_file(filename):
    return send_from_directory('uploads/curriculos', filename)

@app.route('/rh')
def rh_candidatos():
    conn = get_db()
    candidatos = fetchall(conn, "SELECT * FROM candidatos ORDER BY criado_em DESC")
    conn.close()
    return render_template('rh.html', candidatos=candidatos)

@app.route('/rh/upload', methods=['POST'])
def rh_upload():
    if 'curriculo' not in request.files:
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400
    f = request.files['curriculo']
    if not f.filename.lower().endswith('.pdf'):
        return jsonify({'erro': 'Apenas PDF é aceito'}), 400

    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(f.filename)}"
    path = os.path.join('uploads/curriculos', filename)
    f.save(path)

    texto = extrair_texto_pdf(path)
    dados = extrair_dados_texto(texto) if texto else {
        'nome':'','email':'','telefone':'','cidade':'',
        'formacao':'','experiencias':'','habilidades':'','resumo':''
    }

    conn = get_db()
    cid = execute(conn,
        """INSERT INTO candidatos
           (nome,email,telefone,cidade,formacao,experiencias,habilidades,resumo,curriculo_path,texto_curriculo)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (dados['nome'], dados['email'], dados['telefone'], dados['cidade'],
         dados['formacao'], dados['experiencias'], dados['habilidades'],
         dados['resumo'], path, texto[:5000]))
    conn.close()
    return jsonify({'ok': True, 'id': cid, 'dados': dados})

@app.route('/rh/candidatos/<int:cid>')
def rh_candidato_detalhe(cid):
    conn = get_db()
    c = fetchone(conn, "SELECT * FROM candidatos WHERE id=%s", (cid,))
    conn.close()
    return render_template('candidato_detalhe.html', c=c)

@app.route('/rh/candidatos/<int:cid>/editar', methods=['POST'])
def rh_candidato_editar(cid):
    conn = get_db()
    execute(conn,
        "UPDATE candidatos SET nome=%s,email=%s,telefone=%s,cidade=%s,formacao=%s,experiencias=%s,habilidades=%s,resumo=%s WHERE id=%s",
        (request.form.get('nome',''), request.form.get('email',''),
         request.form.get('telefone',''), request.form.get('cidade',''),
         request.form.get('formacao',''), request.form.get('experiencias',''),
         request.form.get('habilidades',''), request.form.get('resumo',''), cid))
    conn.close()
    return redirect(url_for('rh_candidato_detalhe', cid=cid))

@app.route('/rh/candidatos/<int:cid>/deletar', methods=['POST'])
def rh_candidato_deletar(cid):
    conn = get_db()
    execute(conn, "DELETE FROM candidatos WHERE id=%s", (cid,))
    conn.close()
    return redirect(url_for('rh_candidatos'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(debug=False, host='0.0.0.0', port=port)
