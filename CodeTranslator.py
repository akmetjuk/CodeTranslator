from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
import re
from typing import List
import os
import httpx
import logging

file_name = ''
translatorService = 'http://libretranslate:5000'
matchThresholdValue = 90.0
exclude_lines: list[str] = [] # Lines to exclude from translation

# ---- Кастомний форматтер ----
class CustomFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        # локальний час
        dt = datetime.fromtimestamp(record.created)
        return dt.strftime("%Y-%m-%d %H:%M:%S +0000")

formatter = CustomFormatter("[%(asctime)s] [%(process)d] [%(levelname)s] %(message)s")
handler = logging.StreamHandler()
handler.setFormatter(formatter)

# ---- Налаштування root-логера ----
logging.basicConfig(handlers=[handler], level=logging.INFO)
logger = logging.getLogger(__name__)

def get_translator_service_url():
    ret = "http://libretranslate:5000"
    try:
        ret = os.getenv("translatorService", "http://libretranslate:5000")
        logger.info(f"Using translatorService = {ret}")
    except Exception as e:
        logger.error(f"Error getting translatorService env var, using default: {e}")    
    return ret

def matchThreshold():
    ret = 90.0
    try:
        ret = float(os.getenv("matchThreshold", "90.0"))
        logger.info(f"Using matchThreshold = {ret}")
    except ValueError:
        logger.error(f"Non-float matchThreshold value, using default 90.0")
    return ret

def load_lines_from_file(filepath: str) -> list[str]:
    lines = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                clean = line.strip()
                if clean:  # пропустити пусті рядки
                    lines.append(clean)
        logger.info(f"Loaded {len(lines)} lines to exclude from {filepath}")
    except Exception as e:
        logger.error(f"Could not load exclude lines from {filepath}: {e}")
    return lines

def set_Globals():
    global matchThresholdValue    
    global translatorService
    global exclude_lines

    exclude_lines = load_lines_from_file("exclude_lines.txt")
    translatorService = get_translator_service_url()
    matchThresholdValue = matchThreshold()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Before startup event
    logger.info("Starting up...")
    set_Globals()
    yield
    # After shutdown event
    logger.info("Shutting down...")

app = FastAPI(lifespan=lifespan)

class CodeRequest(BaseModel):
    code: str
    language: str  # "csharp", "js", or "sql"

def contains_cyrillic(text: str) -> bool:
    return bool(re.search(r'[\u0400-\u04FF]', text))

def is_excluded(line: str) -> bool:
    return any(exclude in line for exclude in exclude_lines)

async def detect_language(text: str) -> str:
    url = f"{translatorService}/detect"
    payload = {"q": text}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=10)
            response.raise_for_status()
            detections = response.json()
            if detections and isinstance(detections, list):
                # LibreTranslate returns a list of detections with confidence
                top = detections[0]
                if top.get("language") == "ru" and top.get("confidence", 0) > matchThresholdValue:
                    #logger.info(f"Detected language = {top.get("language")} with confidence {top.get('confidence')} > {matchThresholdValue}")
                    return "ru"
            return ""
        except Exception as e:
            logger.error(f"Detecting language rasied exception: {e}")
            return ""

async def translate_text(text: str, target_lang: str = "uk"):    
    # Only translate from Russian to Ukrainian 
    url = f"{translatorService}/translate"
    payload = {
        "q": text,
        "source": "ru",
        "target": target_lang
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return response.json().get("translatedText", "")
        except Exception as e:
            logger.error(f"translating text rasied exception: {e}")
            return ""
    # If not russian, return empty or original (here: empty)
    return ""

async def extract_comments_and_strings(code: str, language: str):
    results = []
    lines = code.splitlines()
    for idx, line in enumerate(lines, 1):
        matches = []
        if language.lower() in ("csharp", "js"):
            matches += re.findall(r'//.*', line)
            matches += re.findall(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', line)
        elif language.lower() == "sql":
            matches += re.findall(r'--.*', line)
            matches += re.findall(r'\'(?:\'\'|[^\'])*\'', line)
        for match in matches:
            if is_excluded(match):
                logger.info(f"{file_name} Excluded line {idx}: {match.strip()}")
            else:
                if contains_cyrillic(match):
                    detected_lang = await detect_language(match)
                    if detected_lang == "ru":
                        logger.warning(f"{file_name} Detected language = {detected_lang} in line {idx}".strip())
                        translation = await translate_text(match)
                        results.append({
                            "line": idx,
                            "original": match.strip(),
                            "suggest_Translation": translation
                        })
    translation = ""
    if language.lower() in ("csharp", "js", "sql"):
        multiline_pattern = r'/\*[\s\S]*?\*/'
        for m in re.finditer(multiline_pattern, code):
            comment = m.group()
            if is_excluded(comment):
                logger.info(f"{file_name} Excluded line {start_line}: {match.strip()}")
            else:
                if contains_cyrillic(comment):
                    detected_lang = await detect_language(comment)
                    if detected_lang == "ru":
                        start_line = code[:m.start()].count('\n') + 1
                        logger.warning(f"{file_name} Detected language = {detected_lang} in line {start_line}".strip())
                        translation = await translate_text(comment)
                        results.append({
                            "line": start_line,
                            "original": comment.strip(),
                            "suggest_Translation": translation
                        })
    return {"results": results}

def detect_language_by_extension(filename: str) -> str:
    ext = filename.lower().split('.')[-1]
    if ext in ["cs"]:
        return "csharp"
    elif ext in ["js"]:
        return "js"
    elif ext in ["sql"]:
        return "sql"
    else:
        return "unknown"

@app.post("/extract")
async def extract(request: CodeRequest):
    global file_name
    file_name = ''
    extracted = await extract_comments_and_strings(request.code, request.language)
    return {"extracted": extracted}

@app.post("/extractFile")
async def extract_file(file: UploadFile = File(...)):
    logger.info(f"Extracting code from file: {file.filename}")    
    contents = await file.read()
    try:
        code = contents.decode("utf-8")
    except UnicodeDecodeError:
        logger.warning("UTF-8 decode failed, trying cp1251...")
        code = contents.decode("cp1251")
    language = detect_language_by_extension(file.filename)
    global file_name
    file_name = file.filename   
    logger.info(f"{file_name} detected as {language}")
    if language == "unknown":
        return {"error": "Unsupported file extension"}
    
    logger.info(f"{file_name} start processing")
    extracted = await extract_comments_and_strings(code, language)
    logger.info(f"{file_name} finished processing")
    return {"extracted": extracted, "language": language}

@app.get("/")
def read_root():
    return {"message":"CodeTraslator API is running."}