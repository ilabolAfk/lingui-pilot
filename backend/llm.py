import json
import os
import sys
from pathlib import Path

import ollama

OLLAMA_HOST = "http://127.0.0.1:11434"
_client = ollama.Client(host=OLLAMA_HOST)

DEFAULT_MODEL = "qwen2.5:7b"


def _config_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


CONFIG_FILE = _config_dir() / "config.json"


def _load_active_model():
    try:
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if data.get("active_model"):
                return data["active_model"]
    except Exception:
        pass
    return DEFAULT_MODEL


ACTIVE_MODEL = _load_active_model()


def set_active_model(model):
    global ACTIVE_MODEL
    ACTIVE_MODEL = model
    try:
        data = {}
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data["active_model"] = model
        CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception:
        return False


def get_active_model():
    return ACTIVE_MODEL

# Recommended models the launcher can download (name, human label, size note).
MODEL_CATALOG = [
    {"model": "qwen2.5:7b-instruct", "label": "Qwen 2.5 7B — быстрая", "size": "~4.7 ГБ"},
    {"model": "qwen3:14b", "label": "Qwen 3 14B — сбалансированная", "size": "~9.3 ГБ"},
    {"model": "qwen2.5:7b", "label": "Qwen 2.5 7B — лёгкая", "size": "~4.7 ГБ"},
]


def list_installed_models():
    """Return names of locally installed Ollama models."""
    try:
        info = _client.list()
        return [m["model"] for m in info.get("models", [])]
    except Exception:
        return []


def check_model_installed(model):
    return model in list_installed_models()


def download_model(model):
    """Pull a model. Returns True on success, raises/False on failure."""
    try:
        _client.pull(model)
        return True
    except Exception:
        return False

LANGS = {
    "en": {
        "name": "English",
        "native": "English",
        "prompt_prefix": "You are a friendly English teacher. Speak ONLY in English at a level suitable for a language learner.",
    },
    "de": {
        "name": "German",
        "native": "Deutsch",
        "prompt_prefix": "You are a friendly German teacher. Speak ONLY in German at a level suitable for a language learner.",
    },
    "fr": {
        "name": "French",
        "native": "Français",
        "prompt_prefix": "You are a friendly French teacher. Speak ONLY in French at a level suitable for a language learner.",
    },
    "es": {
        "name": "Spanish",
        "native": "Español",
        "prompt_prefix": "You are a friendly Spanish teacher. Speak ONLY in Spanish at a level suitable for a language learner.",
    },
}


def chat_completion(messages, model=None):
    """Send a chat request to Ollama and return the assistant reply text."""
    if model is None:
        model = get_active_model()
    response = _client.chat(model=model, messages=messages)
    return response["message"]["content"].strip()


def build_teacher_system(lang, level="beginner"):
    info = LANGS.get(lang, LANGS["en"])
    return (
        f"{info['prompt_prefix']} The learner's level is {level}. "
        "Rules for your replies:\n"
        "1. Do NOT repeat or echo back the learner's own sentence verbatim.\n"
        "2. NEVER start or end every reply with formulaic praise like 'Well done!' "
        "or 'Great job!'. Vary your feedback naturally and only when it fits.\n"
        "3. Actually engage with the content of what the learner said: respond to "
        "the idea, ask a natural follow-up question, or keep the conversation going "
        "in an interesting direction.\n"
        "4. Weave in one small piece of vocabulary or a useful phrase, and briefly "
        "explain it.\n"
        "5. If the learner made a mistake, correct it once, gently and briefly.\n"
        "Keep replies to 2-4 sentences. Stay in character as a supportive teacher."
    )


def generate_exercises(lang, count=5, level="beginner"):
    """Ask the model to produce multiple-choice grammar exercises as JSON."""
    info = LANGS.get(lang, LANGS["en"])
    system = (
        f"You generate MULTIPLE-CHOICE grammar exercises in {info['name']}. "
        f"The learner level is {level}. Return ONLY valid JSON, no other text.\n"
        "Each exercise targets ONE specific grammar point (tenses, prepositions, "
        "articles, comparatives, plurals, phrasal verbs, question words, etc.).\n"
        "STRICT QUALITY RULES:\n"
        "1. There must be exactly ONE clearly correct answer; all three wrong "
        "options must be plausible but definitely wrong.\n"
        "2. Avoid ambiguity: every option must differ in meaning or grammar in a "
        "way that is NOT open to interpretation. Never rely on a specific image, "
        "color, object name or external context that the learner cannot see.\n"
        "3. Do not make articles the focus: 'apple' and 'an apple' must not be "
        "competing options. If the blank needs an article, include it in the "
        "correct answer, not as a separate ambiguous option.\n"
        "4. The wrong options must test real grammar alternatives (e.g. correct "
        "verb tense vs wrong tense, correct preposition vs wrong preposition), "
        "not random unrelated words.\n"
        "Format for each exercise object:\n"
        "{\"question\": \"<sentence with a blank __>\", "
        "\"options\": [\"<4 short choices>\"], "
        "\"answer\": \"<the exact text of the correct option>\", "
        "\"hint\": \"<short grammar explanation in Russian>\"}\n"
        "Return a JSON array of "
        + str(count)
        + " such objects. 'answer' must exactly equal one of the 'options'."
    )
    try:
        content = chat_completion(
            [{"role": "system", "content": system},
             {"role": "user", "content": "Generate the exercises."}]
        )
        start = content.find("[")
        end = content.rfind("]")
        if start == -1 or end == -1:
            return []
        data = json.loads(content[start : end + 1])
        return data if isinstance(data, list) else []
    except Exception:
        return []


LENGTH_PROMPTS = {
    "short": "a short story (about 6-8 short sentences)",
    "medium": "a medium-length story (about 10-12 short sentences)",
    "long": "a longer story (about 14-18 short sentences)",
}

GENRES = {
    "adventure": "adventure story",
    "fairy": "fairy tale",
    "detective": "detective story",
    "daily": "a story about everyday life",
    "science": "a science fiction story",
}


def generate_story(lang="en", theme="", level="beginner", words=None,
                   genre="adventure", length="medium"):
    """Ask the model to produce a reading story with glossary and questions."""
    info = LANGS.get(lang, LANGS["en"])
    lang_name = info["name"]
    vocabulary = ""
    if words:
        vocabulary = (
            "Try to include these words naturally: " + ", ".join(words) + ". "
        )
    genre_text = GENRES.get(genre, GENRES["adventure"])
    length_text = LENGTH_PROMPTS.get(length, LENGTH_PROMPTS["medium"])
    system = (
        f"You are writing {length_text} in **{lang_name}** (the target language) "
        f"for a {level}-level language learner. The genre is a {genre_text}.\n"
        "CRITICAL LANGUAGE RULE:\n"
        f"- The keys 'title', 'text' and every 'q' and 'a' inside 'questions' MUST "
        f"be written in {lang_name}, NOT in Russian, NOT in any other language.\n"
        "- Only the 'translation' field of each glossary entry may be given in "
        "Russian as the learner's native-language translation.\n"
        f"- If {lang_name} is English, the whole story must read as proper English, "
        f"never as Russian text.\n"
        "Return ONLY valid JSON, no other text.\n"
        "The JSON object must have exactly these keys:\n"
        "{\"title\": \"<short title in the target language>\", "
        "\"text\": \"<the story, following the requested length, in the target language>\", "
        "\"glossary\": [{\"word\":\"<taught word>\",\"translation\":\"<russian translation>\"}], "
        "\"questions\": [{\"q\":\"<question in target language>\",\"a\":\"<short answer in target language>\"}]}\n"
        "The glossary MUST contain 6-8 useful words from the story, not fewer. "
        "The questions MUST contain 5 comprehension questions, not fewer. "
        "Questions should be answerable from the text. Keep sentences short and clear."
    )
    user = (
        f"Write a {genre_text} completely in {lang_name}. {vocabulary}"
        "The title, the story text and the questions must all be in "
        f"{lang_name}; only glossary translations go in Russian."
    )
    if theme:
        user += f" Theme: {theme}."
    try:
        content = chat_completion(
            [{"role": "system", "content": system},
             {"role": "user", "content": user}]
        )
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1:
            return None
        data = json.loads(content[start : end + 1])
        return data
    except Exception:
        return None


CEFR_LEVELS = {
    "a1": "CEFR level A1 (beginner). Very simple sentences, basic vocabulary, present simple.",
    "a2": "CEFR level A2 (elementary). Simple everyday topics, past simple, basic future.",
    "b1": "CEFR level B1 (intermediate). Common topics, experience, plans, opinions, all main tenses.",
    "b2": "CEFR level B2 (upper-intermediate). Complex topics, conditionals, passive, idioms.",
    "c1": "CEFR level C1 (advanced). Abstract topics, nuance, complex structures, collocations.",
    "c2": "CEFR level C2 (proficient). Sophisticated register, precise idiom, near-native fluency.",
}

EXAM_TYPES = {
    "grammar": "GRAMMAR AND VOCABULARY multiple-choice: each item is a sentence with a blank __ and 4 choices (A-D), exactly one correct; the distractors must be plausible grammar/lexis errors at the target level.",
    "reading": "READING COMPREHENSION: provide a short passage in the target language appropriate to the level, then 3-4 multiple-choice questions (4 choices A-D each) whose answers are in the text.",
    "custom": "READING COMPREHENSION based on the learner's uploaded passage: ask 3-4 multiple-choice questions (4 choices A-D each) that can be answered from that exact text.",
}


def generate_exam(lang="en", level="b1", types=None, per_type=4, source_text=""):
    """Generate a full exam as a list of question sections."""
    info = LANGS.get(lang, LANGS["en"])
    lang_name = info["name"]
    type_list = types or ["grammar"]
    level_desc = CEFR_LEVELS.get(level, CEFR_LEVELS["b1"])

    type_specs = []
    for t in type_list:
        if t in EXAM_TYPES:
            type_specs.append(EXAM_TYPES[t])

    system = (
        f"You create a language EXAM in **{lang_name}** (the target language). "
        f"The exam level is {level_desc}\n"
        "CRITICAL LANGUAGE RULE:\n"
        f"- The 'q' fields, the 'passage' and the 'options' MUST all be written "
        f"in {lang_name}. Write them as a native {lang_name} speaker would.\n"
        f"- NEVER write them in Russian, unless {lang_name} itself is Russian.\n"
        "- ONLY 'title' and 'explanation' may be in Russian.\n"
        "Return ONLY valid JSON, no other text.\n"
        "The JSON is an array of sections, each with this shape:\n"
        "{\"type\": \"grammar|reading|custom\", "
        "\"title\": \"<section title in Russian>\", "
        "\"passage\": \"<text in target language only for reading/custom sections, empty string otherwise>\", "
        "\"questions\": [{\"q\": \"<question or sentence with __, in target language>\", "
        "\"options\": [\"<option A>\",\"<option B>\",\"<option C>\",\"<option D>\"], "
        "\"ans_index\": \"B\", "
        "\"answer\": \"<the exact text of the correct option, copied character for character>\", "
        "\"explanation\": \"<short Russian explanation>\"}]}\n"
        "STRICT RULES:\n"
        f"- All 'q', 'passage' and 'options' MUST be in {lang_name}.\n"
        "- Every question has EXACTLY 4 options.\n"
        "- Grammar type: each question is ONE natural sentence with EXACTLY ONE short "
        "blank __ . Each option is a SINGLE short word or short phrase that could fill "
        "the blank. Do NOT use two blanks and do NOT make options be pairs like "
        "'word1; and'. Keep the sentence and all options simple and realistic for "
        "the target level. The options should test ONE grammar/vocabulary point "
        "each (e.g. correct verb form vs wrong form).\n"
        "- Reading/custom type: each question is a normal comprehension question the "
        "learner can answer from the passage, with 4 simple single-fact options "
        "(A-D). Do not use blanks.\n"
        "- 'answer' must be copied exactly from the correct option; "
        "'ans_index' (one of A,B,C,D) must point to that same option.\n"
        "- Distractors are plausible but wrong at the target level; no ambiguity.\n"
        f"- Build one section for each type, in this order and count: {type_list} "
        f"with {per_type} questions each.\n"
        "For reading/custom, write a passage of 5-8 sentences."
    )
    user = (
        f"Create the exam in {lang_name}. Types={type_list}, "
        f"{per_type} questions each, level={level}. "
        "Remember: questions, passage and options must be in "
        f"{lang_name}, and 'answer' must exactly match one of the options."
    )
    if source_text:
        user += (
            "\n\nLEARNER'S OWN TEXT to base the custom section on (do not translate it, "
            "use it as the passage):\n" + source_text[:3000]
        )
    try:
        content = chat_completion(
            [{"role": "system", "content": system},
             {"role": "user", "content": user}]
        )
        start = content.find("[")
        end = content.rfind("]")
        if start == -1 or end == -1:
            return []
        data = json.loads(content[start : end + 1])
        return data if isinstance(data, list) else []
    except Exception:
        return []


# Mapping of CEFR level -> numeric grade used to score a result.
CEFR_GRADE = {
    "a1": 1, "a2": 2, "b1": 3, "b2": 4, "c1": 5, "c2": 6,
}