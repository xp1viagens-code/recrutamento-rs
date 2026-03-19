# RecrutaFácil — Sistema de Recrutamento e Seleção

Sistema completo de R&S em Python (FastAPI) com portal do candidato e painel RH.

## Fluxo do processo seletivo

1. **Currículo** — Candidato se cadastra e envia PDF pelo portal
2. **Ligação de triagem** — RH avalia: disponibilidade, localização, horário, cidade, salário
3. **Entrevista presencial** — RH entrevista e registra nota
4. **Testes online** — Comportamento, Raciocínio Lógico, Português, Excel (múltipla escolha)
5. **Debriefing com gestores** — RH registra o parecer da reunião
6. **EVP (Proposta)** — RH envia proposta; candidato aceita ou recusa
7. **Contratado** ✓

## Como rodar

### 1. Instalar dependências
```bash
pip install -r requirements.txt
```

### 2. Iniciar o servidor
```bash
uvicorn main:app --reload --port 8000
```

### 3. Acessar no navegador
- **Página inicial:** http://localhost:8000
- **Portal do candidato:** http://localhost:8000/candidato
- **Painel RH:** http://localhost:8000/rh

## Estrutura de arquivos

```
recrutamento/
├── main.py                    # Aplicação FastAPI (rotas e lógica)
├── requirements.txt           # Dependências Python
├── recrutamento.db            # Banco de dados SQLite (criado automaticamente)
├── uploads/
│   └── curriculos/            # PDFs dos candidatos
├── templates/
│   ├── base.html              # Layout base com navegação
│   ├── index.html             # Página inicial
│   ├── candidato_portal.html  # Portal do candidato
│   ├── candidato_confirmacao.html
│   ├── candidato_detalhe.html # Ficha completa do candidato (RH)
│   ├── candidatos_lista.html  # Lista de candidatos (RH)
│   ├── testes.html            # Página de testes (candidato)
│   ├── rh_dashboard.html      # Painel principal do RH
│   ├── vaga_form.html         # Criação de vaga + scorecard
│   └── vaga_detalhe.html      # Detalhe da vaga
└── static/                    # Arquivos estáticos (CSS/JS extras)
```

## Banco de dados

SQLite local, criado automaticamente na primeira execução. Tabelas:
- `vagas` — vagas abertas com descrição e configurações
- `scorecard_criterios` — critérios por vaga com pesos
- `candidatos` — cadastro e etapa atual
- `triagem_ligacao` — resultado da ligação de triagem
- `entrevista` — dados e nota da entrevista presencial
- `testes` — questões por candidato (geradas automaticamente)
- `resultado_testes` — notas por área
- `debriefing` — parecer do gestor
- `evp` — proposta enviada e resposta do candidato
