RECIBOS MODO MÃE - V5

Inclui:
- Login com utilizador e password
- Clientes guardados
- Histórico de resumos
- Exportação PDF
- Pré-preenchimento com base no último recibo do cliente
- Preparado para base de dados online

INSTALAR NO PC:
1) Abrir CMD nesta pasta
2) Instalar dependências:
   pip install -r requirements.txt
3) Copiar .env.example para .env
4) Alterar ADMIN_PASSWORD no ficheiro .env
5) Executar:
   python app.py
6) Abrir:
   http://127.0.0.1:5000

LOGIN PADRÃO:
Utilizador: mae
Password: a que colocares no .env

ACESSO EXTERNO TEMPORÁRIO:
1) Deixar python app.py aberto
2) Noutra janela:
   ngrok http 5000
3) Abrir o link https gerado pelo ngrok

GUARDAR DADOS ONLINE:
Opção simples/profissional: colocar a app num serviço como Render, Railway ou PythonAnywhere.
Depois alterar DATABASE_URL para uma base de dados PostgreSQL desses serviços.

Exemplo DATABASE_URL:
postgresql://utilizador:password@servidor:5432/base

Nota: para PostgreSQL será necessário instalar também psycopg2-binary.
