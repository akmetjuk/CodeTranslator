# CodeTranslator

**CodeTranslator** — це Python FastAPI сервіс для автоматичного пошуку коментарів і рядків з кирилицею у коді (C#, JS, SQL), а також їх перекладу з російської на українську за допомогою LibreTranslate.  
Проєкт легко розгортається через Docker Compose разом із власним екземпляром LibreTranslate.

---

## 🚀 Швидкий старт

### 1. Клонування та запуск

```bash
git clone https://github.com/ВАШ_ЛОГІН/CodeTranslator.git
cd CodeTranslator
docker compose up --build
```

- FastAPI сервіс буде доступний на [http://localhost:8101](http://localhost:8101)
- LibreTranslate — на [http://localhost:5000](http://localhost:5000)

---

## 🛠️ Доступні API

### 1. `POST /extract`

**Опис:**  
Виділяє всі коментарі та рядки з кирилицею з коду, повертає їх рядок, номер рядка та переклад (якщо це російська).

**Тіло запиту (JSON):**
```json
{
  "code": "// Коментар\nvar s = 'Ошибка!';",
  "language": "js"
}
```

**Відповідь:**
```json
{
  "extracted": {
    "results": [
      {
        "line": 1,
        "original": "// Коментар",
        "suggest_Translation": ""
      },
      {
        "line": 2,
        "original": "'Ошибка!'",
        "suggest_Translation": "'Помилка!'"
      }
    ]
  }
}
```

---

### 2. `POST /extractFile`

**Опис:**  
Те саме, але приймає файл з кодом. Мова визначається автоматично за розширенням файлу.

**curl-приклад:**
```bash
curl -X POST "http://localhost:8101/extractFile" ^
  -H "accept: application/json" ^
  -F "file=@yourfile.sql"
```

**Відповідь:**
```json
{
  "extracted": {
    "results": [
      {
        "line": 10,
        "original": "'Недопустимый код валюты '",
        "suggest_Translation": "'Неприпустимий код валюти '"
      }
    ]
  },
  "language": "sql"
}
```
## Фрази виключень

У сервісі тепер доступна функціональність **фраз виключень**.  
Список фраз зберігається у файлі `exclude_lines.txt` та зчитується автоматично при старті сервісу.  
Якщо вхідний рядок містить одну з фраз із цього списку – такий рядок вважається виключеним та не обробляється.
---

## 📦 Docker Compose

```yaml
services:
  coretranslator:
    build:
      context: .
      dockerfile: ./Dockerfile
    ports:
      - 8101:8101

  libretranslate:
    image: libretranslate/libretranslate
    ports:
      - "5000:5000"
    environment:
      - LT_LOAD_ONLY=en,ru,uk
```

---

## 📝 Підтримувані мови коду

- C# (`.cs`)
- JavaScript (`.js`)
- SQL (`.sql`)

---

## 📄 Ліцензія

MIT

---

**Зворотній зв’язок, баги та ідеї — через Issues або Pull Requests!**
