#!/usr/bin/env python3
"""
Parse pt_enrichments_all.txt, patch stale word/sentence references, emit load_enrichments.sql.

Usage:
  .venv/bin/python load_enrichments.py
  .venv/bin/python load_enrichments.py /path/to/pt_enrichments_all.txt
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DEFAULT_INPUT = Path.home() / "Downloads" / "pt_enrichments_all.txt"
OUT_SQL = Path(__file__).parent / "load_enrichments.sql"
OUT_TXT = Path(__file__).parent / "pt_enrichments_patched.txt"

LESSON_WORDS: dict[int, str] = {
    1: "ANA, ASA, AI, AVÓ, ALÔ",
    8: "PAI, PÉ, PIA, PATA",
    11: "DEDO, DADO, DOIS, DINDA",
    18: "GATO, GOTA, GALO, GU, GOL, ÁGUA",
}

FRASES: dict[int, str] = {
    7: """## 🎵 Frases e sentenças

**AMO A MÃE.** — Aponte para você ao ler MÃE, coloque a mão no coração ao ler AMO. Passe o dedo sob cada palavra.

**MIAU MIAU.** — Leia com voz de gato, exagerando cada sílaba. Peça que ela "leia" junto fazendo o som de gato.

**MAMÃE ME AMA.** — Aponte para você ao ler MAMÃE, abrace-a ao ler ME AMA. Frase afetiva que ela ouve na vida real.
""",
    8: """## 🎵 Frases e sentenças

**AMO O PAI.** — Aponte para o pai ao ler PAI, mão no coração ao ler AMO.

**PATA DA NINA.** — Aponte para a pata da cachorrinha (ou figura) ao ler. NINA é a cachorrinha — âncora afetiva.

**PULA, PAPAI!** — Leia com energia e pule junto. TPR: o movimento fixa a frase.
""",
    9: """## 🎵 Frases e sentenças

**BATI NA BOLA.** — Bata na bola a cada sílaba enquanto lê. Ação + leitura = memória dupla.

**O BEBÊ BABA.** — Leia com expressão divertida. Se ela rir, ela vai querer reler.
""",
    10: """## 🎵 Frases e sentenças

**TEIA NO TETO.** — Aponte para o teto ao ler TETO. Mostre figura de teia ao ler TEIA.

**TOCA A TESTA.** — Toque a testa dela ao ler. TPR direto — ela faz antes de ler sozinha.

**TON TON.** — Bata na porta ou na mesa ao ler. Som onomatopaico que ela já conhece.

**TON TON CAIU.** — Leia com expressão de surpresa. Frase-síntese com T e movimento.
""",
    11: """## 🎵 Frases e sentenças

**O DEDO DÓI.** — Faça expressão de dor leve ao ler DÓI. Aponte para o dedo.

**A DINDA DORME.** — Aponte para a avó (foto ou ao vivo) ao ler DINDA. DINDA = avó.

**TOCA O DEDO.** — Toque o dedo dela ao ler. Imperativo TPR — ela obedece antes de decodificar.
""",
    12: """## 🎵 Frases e sentenças

**A VACA FAZ MUU.** — Faça o mugido ao chegar em MUU.

**AMO A VOVÓ.** — Aponte para a foto da avó ao ler VOVÓ, mão no coração ao ler AMO.

**SOPRA!** — Sopre junto ao ler. TPR com o vento da lição — frase de uma palavra, máximo impacto.
""",
    13: """## 🎵 Frases e sentenças

**A FADA VOA.** — Braços abertos, imite voar ao ler VOA. TPR + verbo novo.

**TÔ COM FOME.** — Leia na hora da refeição. Frase como ela fala — não corrija para "estou".

**CADÊ A NINA?** — Olhe em volta procurando a cachorrinha. NINA ancora a lição N que vem depois.
""",
    14: """## 🎵 Frases e sentenças

**A NINA NADA.** — Gesto de nadar ao ler NADA. Aponte para a Nina ao ler NINA.

**APONTA O NARIZ.** — Aponte o nariz dela ao ler. Imperativo TPR — ela faz o gesto.

**OLHA A NUVEM!** — Aponte para o céu ou algodão ao ler NUVEM. Exclamação natural de criança.
""",
    16: """## 🎵 Frases e sentenças

**O LOBO UIVA.** — Faça o uivo ao ler UIVA. Performance > leitura passiva.

**QUERO BOLO!** — Leia com entusiasmo. Se tiver bolo, melhor ainda.

**LAVA A MÃO.** — Vá à pia e lave as mãos ao ler. Rotina real = âncora permanente.
""",
    17: """## 🎵 Frases e sentenças

**A CASA É NOSSA.** — Gesto amplo de "tudo isso" ao ler CASA.

**VAI PARA A CAMA.** — Leia na hora de dormir, caminhando até a cama. TPR de rotina.

**O COPO CAI.** — Deixe um copo de plástico cair com segurança ao ler CAI.
""",
    18: """## 🎵 Frases e sentenças

**O GATO MIA.** — Faça o miau ao ler MIA (não "miau" — o verbo na frase).

**O GALO CANTA.** — COCORICÓ ao ler CANTA.

**GU FEZ GOL.** — Aponte para o Dindo/GU ao ler GU. Comemore o gol com gesto.

**CAIU UMA GOTA.** — Pingue água no braço ao ler GOTA. ÁGUA e GU se encontram aqui.
""",
    19: """## 🎵 Frases e sentenças

**VAMOS LÁ FORA!** — Caminhe em direção à porta ao ler. Imperativo de movimento.

**OI, LAURA!** — Aponte para ela ao ler LAURA. OI ela já conhece da lição 4.

**COME A PERA.** — Ofereça a fruta ao ler. Âncora gustativa.
""",
    20: """## 🎵 Frases e sentenças

**O SAPO PULA.** — Faça o sapo pular enquanto lê.

**COME A SOPA.** — Leia na hora da refeição, fingindo comer.

**BATE PALMA.** — Bata palmas ao ler. Uma palavra, ação imediata.
""",
}


def parse_lessons(text: str) -> dict[int, str]:
    """Split file into lesson number → body (from header through next separator)."""
    pattern = re.compile(
        r"^-{64}\nLIÇÃO (\d+) —[^\n]+\nWords:[^\n]*\n-{64}\n",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(text))
    lessons: dict[int, str] = {}
    for i, m in enumerate(matches):
        num = int(m.group(1))
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        lessons[num] = text[start:end].rstrip()
    return lessons


def replace_frases_section(body: str, new_block: str) -> str:
    return re.sub(
        r"## 🎵 Frases e sentenças\n\n.*?(?=\n## )",
        new_block.rstrip() + "\n\n",
        body,
        count=1,
        flags=re.DOTALL,
    )


def patch_lesson(num: int, body: str) -> str:
    if num in LESSON_WORDS:
        body = re.sub(
            r"^Words: .+$",
            f"Words: {LESSON_WORDS[num]}",
            body,
            count=1,
            flags=re.MULTILINE,
        )

    if num in FRASES:
        body = replace_frases_section(body, FRASES[num])

    if num == 1:
        body = body.replace(
            "**AVÓ** — Use foto ou chamada de vídeo com a avó real. O vínculo emocional ancora a memória da palavra.\n\n"
            "**ÁGUA** — Mostre o copo, a torneira, a garrafa. Diga \"Á-GU-A\" devagar apontando para o cartão e depois para o objeto.\n\n"
            "**AVIÃO** — Use um avião de brinquedo ou aponte para um no céu. Faça o som de motor \"rrrmmmm\" e diga A-VI-ÃO.",
            "**ANA** — Diga o nome com carinho ou mostre foto. O A no início é o som \"ah\" puro — nome curto, fácil de decodificar.\n\n"
            "**AVÓ** — Use foto ou chamada de vídeo com a avó real. O vínculo emocional ancora a memória da palavra.\n\n"
            "**ALÔ** — Na hora de ligar para alguém, mostre o cartão e diga \"ALÔ!\" O gesto de telefone + o som do A fixam a palavra.",
        )
        body = body.replace(
            "Cada vez que passarem por um objeto com A (água, almofada, avental, armário), pousem e digam \"Ah! ÁGUA!\" ou o que for, apontando.",
            "Cada vez que passarem por algo com som A (almofada, armário, avó, ANA), pousem e digam a palavra apontando.",
        )
        body = body.replace(
            "água, avião, asa de borboleta",
            "avó, asa de borboleta, ALÔ no telefone",
        )

    if num == 8:
        body = body.replace("**PATO**", "**PATA**")
        body = body.replace("PA-TO", "PA-TA")
        body = body.replace("PATO", "PATA")
        body = body.replace("grasnar", "andar de patinha")
        body = body.replace("grasno", "quac-quac de patinha")
        body = body.replace("brinquedo de pato", "pata da Nina ou figura de pato")
        body = body.replace("brinque de pato", "imitem a Nina andando de patinha")

    if num == 11:
        body = body.replace("DINDO", "DINDA")
        body = body.replace("DIN-DO", "DIN-DA")
        body = body.replace("padrinho", "avó")
        body = body.replace("Padrinho", "Avó")

    if num == 17:
        body = body.replace(
            "Encha de água e diga \"COPO de ÁGUA\" — revisão natural de ÁGUA da lição 1.",
            "Encha de suco ou água e diga \"CO-PO!\" (ÁGUA com som GU vem na lição 18).",
        )

    if num == 18:
        body = body.replace(
            "**GU** — Aponte para o padrinho (Dindo) e diga \"GU!\" com carinho. O apelido pessoal é uma das âncoras mais poderosas possíveis — ela já chama ele assim. Ver o nome escrito vai causar reconhecimento imediato.\n\n"
            "**GOTA**",
            "**GU** — Aponte para o Dindo e diga \"GU!\" com carinho. O apelido pessoal ancora o som GU.\n\n"
            "**GOL** — Brinque de bola ou assista futebol com o GU: \"GU FEZ GOL!\" O G duro + emoção do jogo fixam a palavra.\n\n"
            "**ÁGUA** — Mostre no copo ou torneira: \"Á-GUA!\" — aqui ela aprende o som GU dentro da palavra (veio da lição 1 removida de propósito).\n\n"
            "**GOTA**",
        )
        body = body.replace("padrinho", "Dindo")
        body = body.replace("GU É MEU DINDO", "GU FEZ GOL")
        body = body.replace("Aponte para o padrinho ao ler GU e DINDO", "Comemore o gol com o GU")

    return body


def to_sql(num: int, body: str) -> str:
    tag = f"enrich_{num}"
    return (
        f"UPDATE lessons SET enrichment = ${tag}$\n{body}\n${tag}$\n"
        f"WHERE lang = 'pt' AND num = {num};\n"
    )


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    if not src.exists():
        sys.exit(f"Input not found: {src}")

    raw = src.read_text(encoding="utf-8")
    lessons = parse_lessons(raw)
    if len(lessons) != 32:
        sys.exit(f"Expected 32 lessons, found {len(lessons)}: {sorted(lessons)}")

    patched: dict[int, str] = {}
    for num in range(1, 33):
        patched[num] = patch_lesson(num, lessons[num])

    # Rebuild full patched file (skip file header before lesson 1)
    header_end = raw.find("-" * 64)
    header = raw[:header_end] if header_end > 0 else ""
    full_txt = header + "\n\n".join(patched[n] for n in range(1, 33))
    if raw.rstrip().endswith("=" * 64):
        full_txt += "\n\n" + "=" * 64 + "\nFIM DO CURSO — ESTÁGIO 1 COMPLETO\n" + "=" * 64 + "\n"
    OUT_TXT.write_text(full_txt, encoding="utf-8")

    sql_parts = [
        "-- Load all 32 PT lesson enrichments (patched for current words/sentences)",
        "-- Run on Railway → PostgreSQL → Query tab",
        "-- Generated by load_enrichments.py",
        "",
    ]
    for num in range(1, 33):
        sql_parts.append(to_sql(num, patched[num]))
        sql_parts.append("")

    sql_parts.append(
        "SELECT num, title, LEFT(enrichment, 80) AS preview\n"
        "FROM lessons WHERE lang = 'pt' ORDER BY num;\n"
    )
    OUT_SQL.write_text("\n".join(sql_parts), encoding="utf-8")
    print(f"Wrote {OUT_TXT} ({len(patched)} lessons)")
    print(f"Wrote {OUT_SQL}")


if __name__ == "__main__":
    main()
