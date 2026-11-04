from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .db import (
    add_card,
    list_cards,
    delete_card,
    due_cards,
    review_card,
    create_chat,
    list_chats,
    chat_history,
    add_message,
    init_db,
)
from .llm import (chat_completion, build_teacher_system, generate_exercises,
                  generate_story, generate_exam, DEFAULT_MODEL, LANGS,
                  MODEL_CATALOG, list_installed_models, download_model,
                  get_active_model, set_active_model)
from .extract import extract_from_bytes

import os
import sys


def _base_dir():
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass and os.path.isdir(os.path.join(meipass, "static")):
            return Path(meipass)
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


from pathlib import Path

BASE = _base_dir()

app = FastAPI(title="LinguaPilot")

app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")


@app.on_event("startup")
def startup():
    init_db()


# ---------- Cards ----------

class CardIn(BaseModel):
    word: str
    translation: str
    lang: str = "en"


@app.get("/api/cards")
def get_cards(lang: str = "en"):
    return list_cards(lang)


@app.post("/api/cards")
def post_card(card: CardIn):
    cid = add_card(card.word, card.translation, card.lang)
    return {"id": cid}


@app.delete("/api/cards/{card_id}")
def remove_card(card_id: int):
    delete_card(card_id)
    return {"ok": True}


@app.get("/api/cards/due")
def due(lang: str = "en"):
    return due_cards(lang)


class ReviewIn(BaseModel):
    quality: int


@app.post("/api/cards/{card_id}/review")
def post_review(card_id: int, review: ReviewIn):
    result = review_card(card_id, review.quality)
    if result is None:
        raise HTTPException(status_code=404, detail="Card not found")
    return result


# ---------- Chat ----------

class ChatIn(BaseModel):
    lang: str = "en"
    title: str = ""


class MessageIn(BaseModel):
    role: str
    content: str
    lang: str = "en"


@app.get("/api/chats")
def get_chats():
    return list_chats()


@app.post("/api/chats")
def post_chat(chat: ChatIn):
    cid = create_chat(chat.lang, chat.title)
    return {"id": cid}


@app.get("/api/chats/{chat_id}/messages")
def get_messages(chat_id: int):
    return chat_history(chat_id)


@app.post("/api/chats/{chat_id}/messages")
def post_message(chat_id: int, msg: MessageIn):
    add_message(chat_id, msg.role, msg.content)
    history = chat_history(chat_id)
    system = build_teacher_system(msg.lang)
    messages = [{"role": "system", "content": system}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history]
    reply = chat_completion(messages)
    add_message(chat_id, "assistant", reply)
    return {"role": "assistant", "content": reply}


# ---------- Exercises ----------

class ExerciseIn(BaseModel):
    lang: str = "en"
    count: int = 5
    level: str = "beginner"


@app.post("/api/exercises")
def get_exercises(req: ExerciseIn):
    items = generate_exercises(req.lang, req.count, req.level)
    return {"exercises": items}


class StoryIn(BaseModel):
    lang: str = "en"
    theme: str = ""
    level: str = "beginner"
    words: list[str] = []
    genre: str = "adventure"
    length: str = "medium"


@app.post("/api/story")
def get_story(req: StoryIn):
    story = generate_story(req.lang, req.theme, req.level, req.words,
                           req.genre, req.length)
    if story is None:
        raise HTTPException(status_code=502, detail="Failed to generate story")
    return story


# ---------- Exam ----------

class ExamIn(BaseModel):
    lang: str = "en"
    level: str = "b1"
    types: list[str] = ["grammar"]
    per_type: int = 4
    source_text: str = ""


@app.post("/api/exam")
def get_exam(req: ExamIn):
    sections = generate_exam(req.lang, req.level, req.types,
                             req.per_type, req.source_text)
    return {"sections": sections}


@app.post("/api/extract")
async def extract_text(file: UploadFile = File(...), use_ocr: bool = False,
                       ocr_lang: str = "eng"):
    data = await file.read()
    text = extract_from_bytes(data, file.filename or "", use_ocr=use_ocr,
                              lang=ocr_lang)
    return {"text": text, "filename": file.filename}


# ---------- Models ----------

class ModelIn(BaseModel):
    model: str


@app.get("/api/models")
def get_models():
    installed = list_installed_models()
    catalog = []
    for m in MODEL_CATALOG:
        catalog.append({
            "model": m["model"],
            "label": m["label"],
            "size": m["size"],
            "installed": m["model"] in installed,
        })
    return {"catalog": catalog, "installed": installed, "default": DEFAULT_MODEL}


@app.get("/api/models/status")
def model_status():
    return {"default": DEFAULT_MODEL,
            "active": get_active_model(),
            "installed": list_installed_models()}


@app.post("/api/models/active")
def set_active(req: ModelIn):
    if req.model not in list_installed_models():
        raise HTTPException(status_code=404, detail="Model not installed")
    ok = set_active_model(req.model)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to save model choice")
    return {"active": get_active_model()}


@app.post("/api/models/pull")
def pull_model(req: ModelIn):
    ok = download_model(req.model)
    if not ok:
        raise HTTPException(status_code=502, detail="Failed to pull model")
    return {"model": req.model, "ok": True}


# ---------- Langs / meta ----------

@app.get("/api/langs")
def langs():
    return {code: info["name"] for code, info in LANGS.items()}


@app.get("/")
def index():
    return FileResponse(BASE / "static" / "index.html")