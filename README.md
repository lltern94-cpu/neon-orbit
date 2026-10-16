# AI Photo Enhancer — Telegram-бот

Бот улучшает качество фотографий: увеличивает разрешение, слегка повышает резкость, снижает шум и сохраняет естественные цвета. Управление идёт через inline-кнопки, без лишних команд.

Если установлены Real-ESRGAN, PyTorch и файл модели, используется AI-апскейл. Иначе бот честно применяет запасной алгоритм OpenCV/Pillow и **не пишет**, что фото обработано нейросетью.

## Что умеет бот

- Главное меню с кнопками «Улучшить фото», «Настройки», «Помощь»
- Приём JPG, PNG и WEBP (фото или документ)
- Выбор масштаба ×2 / ×4 для каждого снимка
- Сохранение масштаба по умолчанию отдельно для каждого пользователя
- Корректная работа с прозрачностью PNG
- Ограничение размера файлов и выходного изображения
- Несколько пользователей одновременно: сессии изолированы

---

## 1. Установка Python (Windows)

1. Скачай Python 3.11 или новее: https://www.python.org/downloads/windows/
2. При установке отметь **Add python.exe to PATH**.
3. Открой терминал Cursor (`Ctrl+`` `) или PowerShell и проверь версии:

```powershell
python --version
pip --version
```

Ожидается вывод вида `Python 3.11.x` (подойдёт и 3.12+).

Если команда `python` не находится, попробуй:

```powershell
py --version
py -m pip --version
```

Дальше в инструкции заменяй `python` на `py`, если так работает у тебя.

---

## 2. Создание виртуального окружения

В терминале перейди в папку проекта:

```powershell
cd C:\Users\pab75\neon-orbit
python -m venv .venv
```

Активируй окружение:

```powershell
.\.venv\Scripts\Activate.ps1
```

После активации в начале строки появится `(.venv)`.

Если PowerShell запрещает скрипты:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Альтернатива через cmd.exe:

```cmd
.venv\Scripts\activate.bat
```

---

## 3. Установка зависимостей

Базовая (рабочая) установка — без тяжёлого PyTorch:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Проверка, что модули импортируются:

```powershell
python -c "import aiogram, cv2, PIL, dotenv; print('OK', aiogram.__version__)"
```

---

## 4. Создание бота в Telegram (@BotFather)

1. Открой Telegram и найди [@BotFather](https://t.me/BotFather).
2. Отправь `/newbot`.
3. Укажи имя (например `AI Photo Enhancer`) и username (должен заканчиваться на `bot`).
4. Скопируй токен вида `123456789:AAH...`. **Никому его не отправляй и не вставляй в код.**

По желанию: `/setdescription` и `/setuserpic` у BotFather.

---

## 5. Файл `.env`

Скопируй шаблон и открой его в редакторе:

```powershell
copy .env.example .env
notepad .env
```

Замени значение:

```
TELEGRAM_BOT_TOKEN=вставь_токен_от_BotFather
```

Остальные параметры можно не менять. Файл `.env` уже в `.gitignore` и не должен попадать в git.

---

## 6. Запуск бота из терминала Cursor

Убедись, что виртуальное окружение активно, затем:

```powershell
python bot.py
```

В логах должно появиться что-то вроде:

```
Бот запущен. Ожидание обновлений...
```

и сообщение, доступен ли Real-ESRGAN. **Токен в логах не печатается.**

Открой своего бота в Telegram, нажми `/start` и пользуйся кнопками.

Остановка: `Ctrl+C` в терминале.

---

## 7. Частые ошибки

### `TELEGRAM_BOT_TOKEN не задан`

- Нет файла `.env` или токен пустой.
- Решение: `copy .env.example .env` и вставь токен.

### `Unauthorized` / `401`

- Токен неверный или отозван.
- Решение: новый токен у BotFather (`/token` или `/revoke`) и обнови `.env`.

### `Conflict: terminated by other getUpdates`

- Этот бот уже запущен в другом окне/на другом компьютере.
- Решение: останови второй процесс (`Ctrl+C`) и запусти один экземпляр.

### PowerShell: `не удаётся загрузить файл Activate.ps1`

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### `pip` не найден

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Бот не отвечает

- Процесс `python bot.py` должен быть запущен.
- Проверь интернет.
- Напиши `/start` ещё раз.
- Убедись, что в `.env` нет кавычек и пробелов вокруг токена.

### «Файл слишком большой»

- Лимит по умолчанию 15 МБ (`MAX_FILE_SIZE_MB`).
- Telegram тоже ограничивает размер файлов для ботов.

### «Изображение слишком большое для выбранного масштаба»

- ×4 сильно увеличивает число пикселей. Возьми ×2 или фото меньшего размера.

### OpenCV / DLL errors на Windows

```powershell
pip uninstall opencv-python opencv-python-headless -y
pip install opencv-python-headless
```

---

## 8. Real-ESRGAN (необязательно)

Базовый бот **уже работает** без нейросети. AI-апскейл включается, только если установлены пакеты **и** файл весов.

### Что нужно

1. PyTorch: https://pytorch.org/get-started/locally/  
   Пример для CPU (команда с сайта может отличаться):

```powershell
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

Для NVIDIA CUDA выбирай команду с официального сайта под свою версию CUDA.

2. Пакеты Real-ESRGAN:

```powershell
pip install basicsr realesrgan facexlib gfpgan
```

На части сборок `basicsr` капризничает. Если установка падает, бот продолжит работать на OpenCV/Pillow.

3. Файл модели, например **RealESRGAN_x4plus.pth**:

   - Создай папку:

```powershell
mkdir models
```

   - Скачай веса с официального репозитория Real-ESRGAN (раздел *Pretrained Models*) и положи файл в `models\RealESRGAN_x4plus.pth`.
   - Либо укажи путь в `.env`:

```
REALESRGAN_MODEL_PATH=C:\path\to\RealESRGAN_x4plus.pth
```

4. Перезапусти бота. В логе должно быть `Real-ESRGAN доступен`.  
   В подписи к результату пользователь увидит, что использован Real-ESRGAN. Если модели нет — подпись явно скажет про запасной алгоритм.

Real-ESRGAN требует много RAM/VRAM. Для слабого ПК оставь запасной режим.

---

## Структура проекта

| Файл | Назначение |
|------------------|
| `bot.py` | Запуск, меню, callback-кнопки, приём фото |
| `image_processor.py` | Апскейл, резкость, шум, прозрачность |
| `keyboards.py` | Inline-клавиатуры |
| `sessions.py` | Настройки и файлы каждого пользователя |
| `config.py` | Чтение `.env` |
| `.env.example` | Шаблон секретов |
| `requirements.txt` | Зависимости |

## Разработка

После правок достаточно перезапустить `python bot.py`. Временные файлы пишутся в `tmp/` и удаляются после обработки, в том числе при ошибках.
