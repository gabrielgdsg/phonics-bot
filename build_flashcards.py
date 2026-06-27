"""
Fonetismo em Português Brasileiro — Gerador de Flashcards PDF
Tries DB first (DATABASE_URL env var), falls back to hardcoded data.

Layout: A4, cartões contínuos (lições emendadas), sem instruções.
Frente = letra/palavra/frase. Verso = cor da lição + nome (para cortar e colar).

Usage:
    DATABASE_URL=postgresql://... python build_flashcards.py [output.pdf]
    python build_flashcards.py [output.pdf]
"""
import colorsys
import os
import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

PW, PH = A4
COLS, ROWS = 2, 5
CARDS_PER_PAGE = COLS * ROWS
LM, TM = 0.4 * inch, 0.35 * inch
GAP_X, GAP_Y = 0.12 * inch, 0.06 * inch
CW = (PW - 2 * LM - GAP_X) / COLS
CH = (PH - 2 * TM - GAP_Y * (ROWS - 1)) / ROWS

LESSONS = [
    (1,"Vogal A",["A"],["ANA","ASA","AI","AVÓ","ALÔ"],[],
     "ANA no começo — nome curto, som 'ah'. ÁGUA vem na lição 18 com o som GU."),
    (2,"Vogal E",["E"],["ELA","PÉ","É"],[],
     "Compare com A: 'ah' vs 'eh'. A diferença é a lição toda."),
    (3,"Vogal I",["I"],["IRMÃ","ILHA","ISSO"],[],
     "Jogo: fale um som, ela aponta para o cartão certo entre A, E, I."),
    (4,"Vogal O",["O"],["OI","OVO","OLHO"],[],
     "OI é perfeito — ela fala toda hora. Mostre a palavra OI."),
    (5,"Vogal U",["U"],["UVA","UM","URSO"],[],
     "Segure uma uva real. Agora você tem as 5 vogais!"),
    (6,"Revisão das 5 Vogais",[],["A","E","I","O","U"],[],
     "Sem letra nova. Cartões no chão — ela corre para o som certo."),
    (7,"Consoante M",["M"],["MÃE","MÃO","MIAU","MEIA","MASSA"],
     ["AMO A MÃE.","MIAU MIAU.","MAMÃE ME AMA."],
     "MÃE é a palavra mais poderosa. Una: M...Ã...E = MÃE."),
    (8,"Consoante P",["P"],["PAI","PÉ","PIA","PATA"],
     ["AMO O PAI.","PATA DA NINA.","PULA, PAPAI!"],
     "NINA é a cachorrinha. PAI: ela fala dezenas de vezes por dia."),
    (9,"Consoante B",["B"],["BOLA","BEBÊ","BOCA","BABA"],
     ["BATI NA BOLA.","O BEBÊ BABA."],
     "Role uma bola dizendo B-O-L-A a cada rolada."),
    (10,"Consoante T",["T"],["TATU","TETO","BOTA","TEIA","TESTA"],
     ["TEIA NO TETO.","TOCA A TESTA.","TON TON.","TON TON CAIU."],
     "TPR: toca a testa, bate na porta (ton ton). TEIA e TETO nos cartões."),
    (11,"Consoante D",["D"],["DEDO","DADO","DOIS","DINDA"],
     ["O DEDO DÓI.","A DINDA DORME.","TOCA O DEDO."],
     "DINDA = avó. Toque o dedo dela dizendo D-E-D-O."),
    (12,"Consoante V",["V"],["VACA","VELA","VOVÓ","VENTO"],
     ["A VACA FAZ MUU.","AMO A VOVÓ.","SOPRA!"],
     "VOVÓ: ver o nome escrito é mágico. SOPRA! — TPR com o vento."),
    (13,"Consoante F",["F"],["FADA","FOCA","FOFA","FOME"],
     ["A FADA VOA.","TÔ COM FOME.","CADÊ A NINA?"],
     "TPR: braços abertos na fada. Leia TÔ COM FOME como ela fala."),
    (14,"Consoante N",["N"],["NINA","NARIZ","NADA","NUVEM"],
     ["A NINA NADA.","APONTA O NARIZ.","OLHA A NUVEM!"],
     "TPR: aponta o nariz, olha o céu. NINA é a cachorrinha."),
    (15,"Revisão Geral — Lições 7 a 14",[],
     ["MÃE","PAI","BOLA","DEDO","VACA","FADA","NINA","NARIZ"],
     ["PAI TEM BOLA.","EU AMO A MAMÃE.","CADÊ O PAPAI?"],
     "Sem letra nova. Note quais palavras ela hesita — revise amanhã."),
    (16,"Consoante L",["L"],["LOBO","BOLO","LAMA","LUA","LATA"],
     ["O LOBO UIVA.","QUERO BOLO!","LAVA A MÃO."],
     "BOLO é ótimo motivador. LUA é linda para sessão noturna."),
    (17,"Consoante C (CA CO CU)",["C"],["CAMA","COPO","CUBO","CASA"],
     ["A CASA É NOSSA.","VAI PARA A CAMA.","O COPO CAI."],
     "APENAS CA CO CU agora. CE CI têm som diferente — chegam depois."),
    (18,"Consoante G (GA GO GU)",["G"],["GATO","GOTA","GALO","GU","GOL","ÁGUA"],
     ["O GATO MIA.","O GALO CANTA.","GU FEZ GOL.","CAIU UMA GOTA."],
     "ÁGUA agora — som GU. Mostre no copo: Á-GUA."),
    (19,"Consoante R (som suave)",["R"],["FORA","LAURA","PERA","DURO"],
     ["VAMOS LÁ FORA!","OI, LAURA!","COME A PERA."],
     "LAURA é ela. R suave APENAS entre vogais."),
    (20,"Consoante S",["S"],["SAPO","SUCO","SOPA","SOLA"],
     ["O SAPO PULA.","COME A SOPA.","BATE PALMA."],
     "TPR: pula, finge comer, bate palmas. SAPO PULA é música folclórica!"),
    (21,"Revisão + Frases Completas",[],
     ["GATO","SAPO","CAMA","LEÃO","BOLO","MESA"],
     ["O GATO DORME NA CAMA.","O SAPO PULA NA LAMA.","O BOLO É DA MÃE."],
     "Passe o dedo sob cada palavra. Ela está lendo frases!"),
    (22,"Dígrafo LH",["LH"],["FILHA","FOLHA","OLHA","GALHO"],
     ["OLHA O GATO!","A FOLHA CAI.","É MINHA FILHA."],
     "OLHA! — use em momentos reais hoje. LH é único do português."),
    (23,"Dígrafo NH",["NH"],["NINHO","BANHO","MINHA"],
     ["HORA DO BANHO!","É MINHA BOLA.","DORME NO NINHO."],
     "HORA DO BANHO — dito todos os dias. Momento de reconhecimento poderoso."),
    (24,"Dígrafo CH",["CH"],["CHÃO","CHUVA","BICHO","CHAVE"],
     ["A CHUVA CAI.","CAI NO CHÃO.","QUE BICHO É?"],
     "CAI NO CHÃO — ela vive isso. Conecte ao momento real."),
    (25,"Letra X (som CH)",["X"],["XÍCARA","XALE","PEIXE","CAIXA","ROXO"],
     ["O PEIXE NADA.","O PEIXE NA CAIXA.","OLHA O ROXO!"],
     "X tem 4 sons em português — ensine APENAS o som ch/sh por ora."),
    (26,"J e G Suave (GE GI)",["J","GE","GI"],
     ["GEGÊ","GELO","GIRAFA","JACARÉ","JOGO"],
     ["A GIRAFA COME.","TOCA O GELO!","JOGO COM PAPAI."],
     "J e G antes de E ou I fazem o mesmo som suave."),
    (27,"Cedilha Ç",["Ç"],["MAÇÃ","AÇAÍ","TAÇA","ALMOÇO"],
     ["COME A MAÇÃ.","QUERO AÇAÍ!","HORA DO ALMOÇO!"],
     "Ç sempre soa como S. O gancho embaixo é o sinal."),
    (28,"Vogais Nasais: ÃO, EM, IM",["ÃO","EM","IM"],
     ["MÃO","PÃO","BEM","SIM","TEM"],
     ["SIM, EU QUERO.","PÃO COM MEL.","MÃO DA MÃE."],
     "Segure a mão dela: MÃO DA MÃE. Zumba o som nasal: mmm-ÃO."),
    (29,"Vogais Nasais: OM, UM, AN",["OM","UM","AN"],
     ["BOM","UM","BANCO","DANÇA"],
     ["BOM DIA!","BOA NOITE!","HORA DA DANÇA!"],
     "BOM DIA! — comece cada sessão com essa frase num cartão."),
    (30,"Revisão de Todos os Dígrafos",[],
     ["FILHO","BANHO","CHUVA","MAÇÃ","GIRAFA","MÃO","BOM","SIM"],
     ["O FILHO TOMA BANHO.","A CHUVA CAI NA MÃO.","OBRIGADO!"],
     "Sem conteúdo novo. Ela escolhe um cartão, vira, lê. Comemore cada acerto."),
    (31,"Letras Minúsculas — Parte 1",[],
     ["mãe","pai","bola","gato","sapo","cama"],
     ["o gato dorme.","pula, nina!","eu amo mamãe."],
     "Mostre MÃE / mãe lado a lado: 'mesma palavra, roupa diferente.'"),
    (32,"Letras Minúsculas + Leitura Livre",[],
     ["filho","banho","chuva","maçã","girafa","leão"],
     ["o filho toma banho.","até logo!","a girafa come a folha."],
     "Parabéns! Estágio 1 completo. Leia livros ilustrados juntos agora."),
]

DIGRAPHS = {"LH", "NH", "CH", "ÃO", "EM", "IM", "OM", "UM", "AN", "GE", "GI"}

# 32 cores distintas (uma por lição) — tons pastéis para leitura no verso
LESSON_COLORS = [
    colors.HexColor(
        "#%02x%02x%02x" % tuple(int(c * 255) for c in colorsys.hls_to_rgb((n - 1) / 32.0, 0.78, 0.52))
    )
    for n in range(1, 33)
]


def load_from_db(url):
    try:
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(url)
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT num,title,words,sentences FROM lessons WHERE lang='pt' ORDER BY num")
        rows = cur.fetchall()
        conn.close()
        if not rows:
            return None
        db_nums = {r["num"] for r in rows}
        out = []
        for r in rows:
            ws = list(r["words"] or [])
            letters = [w for w in ws if (len(w) <= 2 and w == w.upper() and w.isalpha()) or w in DIGRAPHS]
            words = [w for w in ws if w not in letters]
            out.append({
                "num": r["num"],
                "title": r["title"],
                "letters": letters,
                "words": words,
                "sentences": list(r["sentences"] or []),
            })
        for row in LESSONS:
            if row[0] not in db_nums:
                print(f"   ℹ️  Lição {row[0]} não está no DB — usando fallback")
                out.append({
                    "num": row[0], "title": row[1], "letters": row[2],
                    "words": row[3], "sentences": row[4],
                })
        out.sort(key=lambda x: x["num"])
        print(f"✅ {len(rows)} lições do DB, {len(LESSONS) - len(rows)} do fallback")
        return out
    except Exception as e:
        print(f"⚠️  DB error: {e} — usando fallback.")
        return None


def get_lessons():
    url = os.environ.get("DATABASE_URL")
    if url:
        print("🔌 Conectando ao DB...")
        r = load_from_db(url)
        if r:
            return r
    else:
        print("ℹ️  Sem DATABASE_URL — usando dados locais.")
    return [
        {"num": r[0], "title": r[1], "letters": r[2], "words": r[3], "sentences": r[4]}
        for r in LESSONS
    ]


def card_positions():
    out = []
    for r in range(ROWS):
        for c in range(COLS):
            x = LM + c * (CW + GAP_X)
            y = PH - TM - (r + 1) * CH - r * GAP_Y
            out.append((x, y))
    return out


def wrap(text, max_chars):
    words, lines, line = text.split(), [], []
    for word in words:
        line.append(word)
        if len(" ".join(line)) > max_chars:
            if len(line) > 1:
                lines.append(" ".join(line[:-1]))
                line = [word]
    lines.append(" ".join(line))
    return [ln for ln in lines if ln]


def collect_cards(lessons):
    """Todas as lições em sequência — só cartões de leitura (sem cabeçalho nem nota)."""
    cards = []
    for lesson in lessons:
        num, title = lesson["num"], lesson["title"]
        for letter in lesson.get("letters", []):
            cards.append({"lesson_num": num, "lesson_title": title, "content": letter, "style": "letter"})
        for word in lesson.get("words", []):
            cards.append({"lesson_num": num, "lesson_title": title, "content": word, "style": "word"})
        for sentence in lesson.get("sentences", []):
            cards.append({"lesson_num": num, "lesson_title": title, "content": sentence, "style": "sentence"})
    return cards


def draw_cut_marks(c, x, y):
    m = 4
    c.setStrokeColor(colors.HexColor("#BBBBBB"))
    c.setLineWidth(0.25)
    for dx, dy, sx, sy in [
        (0, CH, m, 0), (CW, CH, -m, 0), (0, 0, m, 0), (CW, 0, -m, 0),
        (0, CH, 0, -m), (0, 0, 0, m), (CW, CH, 0, -m), (CW, 0, 0, m),
    ]:
        c.line(x + dx, y + dy, x + dx + sx, y + dy + sy)


def draw_front(c, x, y, card):
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#CCCCCC"))
    c.setLineWidth(0.5)
    c.rect(x, y, CW, CH, fill=1)
    cx, cy = x + CW / 2, y + CH / 2
    content, style = card["content"], card["style"]
    if style == "letter":
        fs = 72 if len(content) == 1 else 48 if len(content) <= 2 else 32
        c.setFillColor(colors.HexColor("#1A237E"))
        c.setFont("Helvetica-Bold", fs)
        c.drawCentredString(cx, cy - fs * 0.3, content)
    elif style == "word":
        fs = 40 if len(content) <= 4 else 32 if len(content) <= 6 else 24 if len(content) <= 9 else 18
        c.setFillColor(colors.HexColor("#1B5E20"))
        c.setFont("Helvetica-Bold", fs)
        c.drawCentredString(cx, cy - 10, content)
    else:
        lines = wrap(content, 18)
        fs = 22 if len(lines) <= 2 else 19 if len(lines) <= 3 else 16
        c.setFillColor(colors.HexColor("#4A148C"))
        c.setFont("Helvetica-Bold", fs)
        lh = fs + 5
        sy = cy + len(lines) * lh / 2 - fs
        for i, ln in enumerate(lines):
            c.drawCentredString(cx, sy - i * lh, ln)
    draw_cut_marks(c, x, y)


def draw_back(c, x, y, card):
    num = card["lesson_num"]
    title = card["lesson_title"]
    fill = LESSON_COLORS[(num - 1) % len(LESSON_COLORS)]
    c.setFillColor(fill)
    c.setStrokeColor(colors.HexColor("#999999"))
    c.setLineWidth(0.5)
    c.rect(x, y, CW, CH, fill=1)
    cx, cy = x + CW / 2, y + CH / 2
    c.setFillColor(colors.HexColor("#1A1A1A"))
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(cx, cy + 14, f"Lição {num}")
    lines = wrap(title, 22)
    fs = 13 if len(lines) == 1 else 11 if len(lines) == 2 else 9
    c.setFont("Helvetica-Bold", fs)
    lh = fs + 3
    sy = cy - 8 - (len(lines) - 1) * lh / 2
    for i, ln in enumerate(lines):
        c.drawCentredString(cx, sy - i * lh, ln)
    draw_cut_marks(c, x, y)


def draw_page_batch(cv, batch, draw_fn):
    positions = card_positions()
    for slot, card in enumerate(batch):
        x, y = positions[slot]
        draw_fn(cv, x, y, card)


def draw_pages(cv, cards, draw_fn):
    for i in range(0, len(cards), CARDS_PER_PAGE):
        batch = cards[i : i + CARDS_PER_PAGE]
        draw_page_batch(cv, batch, draw_fn)
        cv.showPage()


def separator_page(cv):
    cv.setFillColor(colors.HexColor("#333333"))
    cv.setFont("Helvetica-Bold", 16)
    cv.drawCentredString(PW / 2, PH / 2 + 20, "VERSOS")
    cv.setFont("Helvetica", 11)
    cv.drawCentredString(
        PW / 2, PH / 2 - 10,
        "Imprima as páginas seguintes atrás das frentes (mesma ordem) para cortar e colar.",
    )
    cv.drawCentredString(
        PW / 2, PH / 2 - 28,
        "Cada cor = uma lição — junte frente e verso pela cor.",
    )
    cv.showPage()


def build(lessons, out):
    cards = collect_cards(lessons)
    cv = canvas.Canvas(out, pagesize=A4)
    cv.setTitle("Fonetismo em Português Brasileiro — Estágio 1")

    draw_pages(cv, cards, draw_front)
    separator_page(cv)
    draw_pages(cv, cards, draw_back)

    cv.save()
    front_pages = (len(cards) + CARDS_PER_PAGE - 1) // CARDS_PER_PAGE
    pages = front_pages * 2 + 1
    wc = sum(len(L.get("words", [])) for L in lessons)
    sc = sum(len(L.get("sentences", [])) for L in lessons)
    print(f"✅ Salvo: {out}")
    print(f"   {len(cards)} cartões | {wc} palavras | {sc} frases | {pages} páginas A4")
    print("   Seção 1 = frentes | Seção 2 = versos coloridos (mesma ordem)")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "fonetismo_portugues_estagio1.pdf"
    print("🇧🇷 Fonetismo em Português Brasileiro — Gerador de Flashcards")
    print("=" * 60)
    lessons = get_lessons()
    print(f"📚 Gerando PDF com {len(lessons)} lições...")
    build(lessons, out)
