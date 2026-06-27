-- Últimas alterações de palavras e frases
-- Rode no Railway → PostgreSQL → Query tab

UPDATE lessons SET
  words = ARRAY['ANA','ASA','AI','AVÓ','ALÔ'],
  tips = 'ANA no começo. ÁGUA vem na lição 18 com o som GU. ALÔ na hora de telefone.'
WHERE lang = 'pt' AND num = 1;

UPDATE lessons SET
  sentences = ARRAY['TEIA NO TETO.','TOCA A TESTA.','TON TON.','TON TON CAIU.']
WHERE lang = 'pt' AND num = 10;

UPDATE lessons SET
  words = ARRAY['GATO','GOTA','GALO','GU','GOL','ÁGUA'],
  sentences = ARRAY['O GATO MIA.','O GALO CANTA.','GU FEZ GOL.','CAIU UMA GOTA.']
WHERE lang = 'pt' AND num = 18;

UPDATE lessons SET sentences = ARRAY['VAMOS LÁ FORA!','OI, LAURA!','COME A PERA.']
WHERE lang = 'pt' AND num = 19;

UPDATE lessons SET sentences = ARRAY['O SAPO PULA.','COME A SOPA.','BATE PALMA.']
WHERE lang = 'pt' AND num = 20;

UPDATE lessons SET sentences = ARRAY['o gato dorme.','pula, nina!','eu amo mamãe.']
WHERE lang = 'pt' AND num = 31;

SELECT num, words, sentences FROM lessons
WHERE lang = 'pt' AND num IN (1,10,18,19,20,31) ORDER BY num;
