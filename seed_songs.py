#!/usr/bin/env python3
"""Seed starter Portuguese children's songs. Run once; add more via SONGS_AND_TIPS_GENERATION.md."""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from bot import get_db  # noqa: E402

SONGS = [
    {
        "title": "Sapo Cururu",
        "lyrics": (
            "Sapo cururu na beira do rio\n"
            "Quando o sapo canta ó maninha\n"
            "Vem ver o sapo que é muito engraçado\n"
            "Ele pula, ele nada, ele é muito feliz"
        ),
        "chords": (
            "G              C\n"
            "Sapo cururu na beira do rio\n"
            "D                    G\n"
            "Quando o sapo canta ó maninha"
        ),
        "vocabulary_tips": (
            "🎵 *Sapo Cururu*\n\n"
            "📖 *Palavras desta música*\n"
            "• **sapo** — o bichinho verde que pula\n"
            "• **rio** — água que corre\n"
            "• **canta** — faz som com a boca\n\n"
            "🎸 *Dicas para tocar no violão*\n"
            "• Ritmo devagar, batida para baixo\n"
            "• Tom de G maior, sem capo\n"
            "• Deixe ela pular quando cantar \"sapo\"\n\n"
            "🗣️ *Como cantar com ela*\n"
            "• Faça careta de sapo no \"cururu\"\n"
            "• Ela bate palma no refrão\n\n"
            "🎮 *Brincadeira*\n"
            "• Pulem como sapo pelo cômodo\n\n"
            "🌱 *O que ela aprende*\n"
            "• Animais, rimas, ritmo"
        ),
        "youtube_url": "https://www.youtube.com/watch?v=0VZ6AZD2yAw",
        "category": "classic",
    },
    {
        "title": "O Sapo Não Lava o Pé",
        "lyrics": (
            "O sapo não lava o pé\n"
            "Não lava porque não quer\n"
            "Ele mora lá na lagoa\n"
            "Porque é muito bem assim"
        ),
        "chords": (
            "G\n"
            "O sapo não lava o pé\n"
            "C              G\n"
            "Não lava porque não quer"
        ),
        "vocabulary_tips": (
            "🎵 *O Sapo Não Lava o Pé*\n\n"
            "📖 *Palavras*\n"
            "• **lava** — limpa com água\n"
            "• **pé** — parte do corpo\n"
            "• **lagoa** — água parada\n\n"
            "🎸 *Violão*\n"
            "• Duas batidas por compasso, bem simples\n\n"
            "🗣️ *Cantar*\n"
            "• Mostre o pé na hora de cantar\n\n"
            "🎮 *Brincadeira*\n"
            "• Pulem e finjam ser sapo na \"lagoa\" (toalha no chão)\n\n"
            "🌱 *Aprende*\n"
            "• Corpo, humor, fonema S (lição 20!)"
        ),
        "youtube_url": "https://www.youtube.com/watch?v=KpHTxD1o2A0",
        "category": "phonics",
    },
    {
        "title": "Atirei o Pau no Gato",
        "lyrics": (
            "Atirei o pau no gato\n"
            "Mas o gato não morreu\n"
            "Dona Chica admirou-se\n"
            "Do berro que o gato deu"
        ),
        "chords": (
            "G\n"
            "Atirei o pau no gato\n"
            "C         G\n"
            "Mas o gato não morreu"
        ),
        "vocabulary_tips": (
            "🎵 *Atirei o Pau no Gato*\n\n"
            "📖 *Palavras*\n"
            "• **gato** — animal de estimação\n"
            "• **miau** — som do gato\n\n"
            "🎸 *Violão*\n"
            "• Versão bem devagar para bebê — sem assustar!\n\n"
            "🗣️ *Cantar*\n"
            "• Faça \"miau\" no final\n\n"
            "🎮 *Brincadeira*\n"
            "• Finjam ser gato e cachorro (Nina!)\n\n"
            "🌱 *Aprende*\n"
            "• Animais, rimas, memória auditiva"
        ),
        "youtube_url": "https://www.youtube.com/watch?v=8vXoI7lUroQ",
        "category": "classic",
    },
    {
        "title": "Borboletinha",
        "lyrics": (
            "Borboletinha tá na cozinha\n"
            "Fazendo chocolate para a madrinha\n"
            "Poti poti, perepoti\n"
            "A borboletinha já saiu"
        ),
        "chords": (
            "G\n"
            "Borboletinha tá na cozinha\n"
            "C              G\n"
            "Fazendo chocolate para a madrinha"
        ),
        "vocabulary_tips": (
            "🎵 *Borboletinha*\n\n"
            "📖 *Palavras*\n"
            "• **borboleta** — inseto colorido que voa\n"
            "• **cozinha** — onde a mamãe cozinha\n\n"
            "🎸 *Violão*\n"
            "• Batida leve; capo na 2ª casa se quiser tom mais agudo\n\n"
            "🗣️ *Cantar*\n"
            "• Braços abertos voando na \"borboletinha\"\n\n"
            "🎮 *Brincadeira*\n"
            "• Voem pela casa fazendo \"poti poti\"\n\n"
            "🌱 *Aprende*\n"
            "• Movimento, imaginação, rimas"
        ),
        "youtube_url": "https://www.youtube.com/watch?v=3YqPKLZF_WU",
        "category": "classic",
    },
    {
        "title": "Caranguejo é Peixe",
        "lyrics": (
            "Caranguejo é peixe éh\n"
            "Caranguejo não é peixe não\n"
            "Caranguejo é peixe éh\n"
            "Caranguejo não é peixe não"
        ),
        "chords": (
            "G\n"
            "Caranguejo é peixe éh\n"
            "C         G\n"
            "Caranguejo não é peixe não"
        ),
        "vocabulary_tips": (
            "🎵 *Caranguejo é Peixe*\n\n"
            "📖 *Palavras*\n"
            "• **caranguejo** — bichinho do mar que anda de lado\n"
            "• **peixe** — nada na água\n\n"
            "🎸 *Violão*\n"
            "• Ritmo de marcha, bem repetitivo\n\n"
            "🗣️ *Cantar*\n"
            "• Andem de lado como caranguejo!\n\n"
            "🎮 *Brincadeira*\n"
            "• Lado a lado pelo corredor\n\n"
            "🌱 *Aprende*\n"
            "• Rimaa, coordenação, risada"
        ),
        "youtube_url": "https://www.youtube.com/watch?v=0tCWz0z0p0Y",
        "category": "movement",
    },
]


def main() -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM songs WHERE lang = 'pt'")
            existing = int(cur.fetchone()["n"])
            if existing > 0:
                print(f"songs already seeded ({existing}) — skipping.")
                return
            for s in SONGS:
                cur.execute(
                    """
                    INSERT INTO songs (
                        lang, title, lyrics, chords, vocabulary_tips,
                        youtube_url, age_min, age_max, category
                    ) VALUES ('pt', %s, %s, %s, %s, %s, 12, 72, %s)
                    """,
                    (
                        s["title"],
                        s["lyrics"],
                        s["chords"],
                        s["vocabulary_tips"],
                        s["youtube_url"],
                        s["category"],
                    ),
                )
            cur.execute("SELECT COUNT(*) AS n FROM songs WHERE lang = 'pt'")
            print(f"songs in DB: {cur.fetchone()['n']}")
        conn.commit()


if __name__ == "__main__":
    main()
