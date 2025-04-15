import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from passlib.hash import bcrypt
import os

DB_PATH = "cotacoes.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

st.set_page_config(page_title="Portal de Cotações", layout="wide")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS fornecedores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT UNIQUE,
        senha TEXT,
        tipo TEXT DEFAULT 'fornecedor'
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS cotacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rubrica TEXT,
        data_criacao TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS itens_cotacao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cotacao_id INTEGER,
        item TEXT,
        descricao TEXT,
        unidade TEXT,
        quantidade INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS respostas_itens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER,
        fornecedor TEXT,
        preco REAL,
        prazo TEXT,
        condicoes TEXT,
        anexo TEXT,
        data_resposta TEXT
    )
    """)

    # Usuários de exemplo
    if not cur.execute("SELECT * FROM fornecedores WHERE usuario = 'admin'").fetchone():
        cur.execute("INSERT INTO fornecedores (usuario, senha, tipo) VALUES (?, ?, ?)",
                    ("admin", bcrypt.hash("admin123"), "admin"))

    if not cur.execute("SELECT * FROM fornecedores WHERE usuario = 'fornecedor1'").fetchone():
        cur.execute("INSERT INTO fornecedores (usuario, senha, tipo) VALUES (?, ?, ?)",
                    ("fornecedor1", bcrypt.hash("123456"), "fornecedor"))

    conn.commit()
    conn.close()


def login():
    st.sidebar.title("🔐 Login")
    username = st.sidebar.text_input("Usuário")
    password = st.sidebar.text_input("Senha", type="password")
    if st.sidebar.button("Entrar"):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT senha, tipo FROM fornecedores WHERE usuario = ?", (username,))
        row = cur.fetchone()
        conn.close()
        if row and bcrypt.verify(password, row[0]):
            return username, row[1]
        else:
            st.sidebar.error("Usuário ou senha inválidos.")
    return None, None


def importar_excel(file):
    df = pd.read_excel(file)
    if not set(["Item", "Rubrica", "Descrição", "Unidade de Medida", "Quantidade"]).issubset(df.columns):
        st.error("Arquivo inválido. Verifique as colunas exigidas.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    for rubrica in df["Rubrica"].unique():
        cotacao_data = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("INSERT INTO cotacoes (rubrica, data_criacao) VALUES (?, ?)", (rubrica, cotacao_data))
        cotacao_id = cur.lastrowid

        for _, row in df[df["Rubrica"] == rubrica].iterrows():
            cur.execute("""
                INSERT INTO itens_cotacao (cotacao_id, item, descricao, unidade, quantidade)
                VALUES (?, ?, ?, ?, ?)
            """, (cotacao_id, row["Item"], row["Descrição"], row["Unidade de Medida"], int(row["Quantidade"])))

    conn.commit()
    conn.close()
    st.success("Cotações importadas com sucesso!")


def listar_cotacoes():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM cotacoes ORDER BY id DESC")
    return cur.fetchall()


def listar_itens(cotacao_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM itens_cotacao WHERE cotacao_id = ?", (cotacao_id,))
    return cur.fetchall()


def registrar_resposta(item_id, fornecedor, preco, prazo, condicoes, anexo):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO respostas_itens (item_id, fornecedor, preco, prazo, condicoes, anexo, data_resposta)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (item_id, fornecedor, preco, prazo, condicoes, anexo, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()


def respostas_por_item(item_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM respostas_itens WHERE item_id = ?", (item_id,))
    return cur.fetchall()


# =====================
# INTERFACE PRINCIPAL
# =====================
init_db()
usuario, tipo = login()

if usuario:
    st.success(f"Bem-vindo, {usuario} ({tipo})")

    if tipo == "admin":
        st.title("📊 Painel Administrativo")

        st.subheader("📥 Importar Excel de Solicitações")
        file = st.file_uploader("Escolha o arquivo Excel", type=["xlsx"])
        if file:
            importar_excel(file)

        st.subheader("📋 Cotações Cadastradas")
        cotacoes = listar_cotacoes()
        for cotacao in cotacoes:
            with st.expander(f"Cotação Rubrica {cotacao['rubrica']} (ID {cotacao['id']})"):
                itens = listar_itens(cotacao['id'])
                for item in itens:
                    st.markdown(f"**{item['item']} - {item['descricao']}** ({item['quantidade']} {item['unidade']})")
                    respostas = respostas_por_item(item['id'])
                    if respostas:
                        df = pd.DataFrame(respostas)
                        df['preco'] = df['preco'].astype(float)
                        df = df.sort_values("preco")
                        st.dataframe(df[["fornecedor", "preco", "prazo", "condicoes"]])
                        st.markdown(f"🟢 **Menor preço:** R$ {df.iloc[0]['preco']:.2f} por {df.iloc[0]['fornecedor']}")
                    else:
                        st.warning("Nenhuma resposta recebida.")

    elif tipo == "fornecedor":
        st.title("📝 Responder Cotações")
        cotacoes = listar_cotacoes()
        for cotacao in cotacoes:
            with st.expander(f"Cotação Rubrica {cotacao['rubrica']} (ID {cotacao['id']})"):
                itens = listar_itens(cotacao['id'])
                for item in itens:
                    st.markdown(f"**{item['item']} - {item['descricao']}** ({item['quantidade']} {item['unidade']})")
                    preco = st.number_input("Preço Unitário", min_value=0.0, format="%.2f", key=f"preco_{item['id']}")
                    prazo = st.text_input("Prazo de entrega", key=f"prazo_{item['id']}")
                    cond = st.text_input("Condições de pagamento", key=f"cond_{item['id']}")
                    anexo = st.file_uploader("Anexo (opcional)", type=["pdf", "docx"], key=f"anexo_{item['id']}")
                    anexo_path = ""
                    if anexo:
                        anexo_path = os.path.join(UPLOAD_DIR, f"{usuario}_{item['id']}_{anexo.name}")
                        with open(anexo_path, "wb") as f:
                            f.write(anexo.read())
                    if st.button("Enviar resposta", key=f"btn_{item['id']}"):
                        registrar_resposta(item['id'], usuario, preco, prazo, cond, anexo_path)
                        st.success("Resposta registrada com sucesso!")
