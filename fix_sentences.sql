-- Portuguese course: words + sentences update
-- Run on Railway → PostgreSQL → Query tab

UPDATE lessons SET
  words = ARRAY['ANA','ASA','AI','AVÓ','ALÔ'],
  tips = 'ANA no começo. ÁGUA vem na lição 18 com o som GU. ALÔ na hora de telefone.'
WHERE lang = 'pt' AND num = 1;

UPDATE lessons SET
  title = 'Consoante M',
  words = ARRAY['MÃE','MÃO','MIAU','MEIA','MASSA'],
  sentences = ARRAY['AMO A MÃE.','MIAU MIAU.','MAMÃE ME AMA.'],
  tips = 'Som ''mm'' — lábios fechados depois abre. MÃE é a palavra mais poderosa. Una: M...Ã...E = MÃE.'
WHERE lang = 'pt' AND num = 7;

UPDATE lessons SET
  words = ARRAY['PAI','PÉ','PIA','PATA'],
  sentences = ARRAY['AMO O PAI.','PATA DA NINA.','PULA, PAPAI!'],
  tips = 'Som ''p'' — pequeno sopro de ar. NINA é a cachorrinha. Pratique MÃE + PAI lado a lado.'
WHERE lang = 'pt' AND num = 8;

UPDATE lessons SET
  words = ARRAY['BOLA','BEBÊ','BOCA','BABA'],
  sentences = ARRAY['BATI NA BOLA.','O BEBÊ BABA.'],
  tips = 'Som ''b'' — como P mas com voz. Role uma bola dizendo B-O-L-A.'
WHERE lang = 'pt' AND num = 9;

UPDATE lessons SET
  title = 'Consoante T',
  words = ARRAY['TATU','TETO','BOTA','TEIA','TESTA'],
  sentences = ARRAY['TEIA NO TETO.','TOCA A TESTA.','TON TON.','TON TON CAIU.'],
  tips = 'Som ''t'' — língua no céu da boca. Revise M P B antes. Aponte para a TESTA dela.'
WHERE lang = 'pt' AND num = 10;

UPDATE lessons SET
  words = ARRAY['DEDO','DADO','DOIS','DINDA'],
  sentences = ARRAY['O DEDO DÓI.','A DINDA DORME.','TOCA O DEDO.'],
  tips = 'Som ''d'' — como T mas com voz. DINDA = avó. Toque o dedo dela dizendo D-E-D-O.'
WHERE lang = 'pt' AND num = 11;

UPDATE lessons SET
  words = ARRAY['VACA','VELA','VOVÓ','VENTO'],
  sentences = ARRAY['A VACA FAZ MUU.','AMO A VOVÓ.','SOPRA!'],
  tips = 'Som ''v'' — dente no lábio de baixo, vibrando. VOVÓ: ver o nome escrito é mágico.'
WHERE lang = 'pt' AND num = 12;

UPDATE lessons SET
  sentences = ARRAY['A FADA VOA.','TÔ COM FOME.','CADÊ A NINA?'],
  tips = 'Som ''f'' — mesma boca que V, sem vibração. Leia TO COM FOME como ela fala no dia a dia.'
WHERE lang = 'pt' AND num = 13;

UPDATE lessons SET
  words = ARRAY['NINA','NARIZ','NADA','NUVEM'],
  sentences = ARRAY['A NINA NADA.','APONTA O NARIZ.','OLHA A NUVEM!'],
  tips = 'Som ''n'' — som sai pelo nariz. NINA é a cachorrinha. Aponte para o NARIZ dela.'
WHERE lang = 'pt' AND num = 14;

UPDATE lessons SET
  title = 'Revisão Geral — Lições 7 a 14',
  words = ARRAY['MÃE','PAI','BOLA','DEDO','VACA','FADA','NINA','NARIZ'],
  sentences = ARRAY['PAI TEM BOLA.','EU AMO A MAMÃE.','CADÊ O PAPAI?'],
  tips = 'Sem letra nova. Revise M P B T D V F N. Note quais palavras ela hesita.'
WHERE lang = 'pt' AND num = 15;

UPDATE lessons SET
  words = ARRAY['LOBO','BOLO','LAMA','LUA','LATA'],
  sentences = ARRAY['O LOBO UIVA.','QUERO BOLO!','LAVA A MÃO.'],
  tips = 'Som ''l'' — ponta da língua no céu. BOLO é ótimo motivador.'
WHERE lang = 'pt' AND num = 16;

UPDATE lessons SET
  words = ARRAY['CAMA','COPO','CUBO','CASA'],
  sentences = ARRAY['A CASA É NOSSA.','VAI PARA A CAMA.','O COPO CAI.'],
  tips = 'Som k duro APENAS antes de A O U. NÃO introduza CE ou CI — lição 26.'
WHERE lang = 'pt' AND num = 17;

UPDATE lessons SET
  words = ARRAY['GATO','GOTA','GALO','GU','GOL','ÁGUA'],
  sentences = ARRAY['O GATO MIA.','O GALO CANTA.','GU FEZ GOL.','CAIU UMA GOTA.'],
  tips = 'Som g duro APENAS antes de A O U. GU é o apelido do dindo.'
WHERE lang = 'pt' AND num = 18;

UPDATE lessons SET
  words = ARRAY['FORA','LAURA','PERA','DURO'],
  sentences = ARRAY['VAMOS LÁ FORA!','OI, LAURA!','COME A PERA.'],
  tips = 'R suave entre vogais. LAURA é ela. O R forte (RATO) fica para o Estágio 2.'
WHERE lang = 'pt' AND num = 19;

UPDATE lessons SET
  words = ARRAY['SAPO','SUCO','SOPA','SOLA'],
  sentences = ARRAY['O SAPO PULA.','COME A SOPA.','BATE PALMA.'],
  tips = 'Som ''s'' — ar entre os dentes. SAPO PULA é música folclórica.'
WHERE lang = 'pt' AND num = 20;

UPDATE lessons SET
  words = ARRAY['FILHA','FOLHA','OLHA','GALHO'],
  sentences = ARRAY['OLHA O GATO!','A FOLHA CAI.','É MINHA FILHA.'],
  tips = 'LH é único do português. Use OLHA em momentos reais hoje.'
WHERE lang = 'pt' AND num = 22;

UPDATE lessons SET
  words = ARRAY['NINHO','BANHO','MINHA'],
  sentences = ARRAY['HORA DO BANHO!','É MINHA BOLA.','DORME NO NINHO.'],
  tips = 'NH nasal. HORA DO BANHO — mostre o cartão na hora do banho.'
WHERE lang = 'pt' AND num = 23;

UPDATE lessons SET
  sentences = ARRAY['O PEIXE NADA.','O PEIXE NA CAIXA.','OLHA O ROXO!'],
  tips = 'X hoje APENAS som ch/sh. PEIXE NA CAIXA — cena concreta com brinquedo.'
WHERE lang = 'pt' AND num = 25;

UPDATE lessons SET
  words = ARRAY['GEGÊ','GELO','GIRAFA','JACARÉ','JOGO'],
  sentences = ARRAY['A GIRAFA COME.','TOCA O GELO!','JOGO COM PAPAI.'],
  tips = 'J e G antes de E ou I fazem o mesmo som suave.'
WHERE lang = 'pt' AND num = 26;

UPDATE lessons SET
  words = ARRAY['MAÇÃ','AÇAÍ','TAÇA','ALMOÇO'],
  sentences = ARRAY['COME A MAÇÃ.','QUERO AÇAÍ!','HORA DO ALMOÇO!'],
  tips = 'Ç sempre soa como S. Segure uma maçã de verdade.'
WHERE lang = 'pt' AND num = 27;

UPDATE lessons SET
  words = ARRAY['MÃO','PÃO','BEM','SIM','TEM'],
  sentences = ARRAY['SIM, EU QUERO.','PÃO COM MEL.','MÃO DA MÃE.'],
  tips = 'Vogais nasais. Segure a mão dela: MÃO DA MÃE.'
WHERE lang = 'pt' AND num = 28;

UPDATE lessons SET
  words = ARRAY['BOM','UM','BANCO','DANÇA'],
  sentences = ARRAY['BOM DIA!','BOA NOITE!','HORA DA DANÇA!'],
  tips = 'Mais vogais nasais. Comece cada sessão com BOM DIA! num cartão.'
WHERE lang = 'pt' AND num = 29;

UPDATE lessons SET
  sentences = ARRAY['o gato dorme.','pula, nina!','eu amo mamãe.'],
  tips = 'Minúsculas: mesma palavra, roupa diferente. Mostre MÃE / mãe lado a lado.'
WHERE lang = 'pt' AND num = 31;

UPDATE lessons SET
  sentences = ARRAY['o filho toma banho.','até logo!','a girafa come a folha.'],
  tips = 'Última lição do Estágio 1. Depois leia livros ilustrados juntos.'
WHERE lang = 'pt' AND num = 32;

-- Verify
SELECT num, title, words, sentences FROM lessons
WHERE lang = 'pt' AND num BETWEEN 7 AND 32
ORDER BY num;
