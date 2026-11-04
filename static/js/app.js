const state = {
    lang: 'en',
    currentTab: 'chat',
    chatId: null,
    cardIndex: 0,
    dueList: [],
    showTranslation: false,
    exercises: [],
    stories: [],
};

const $ = (id) => document.getElementById(id);

// ---------- Language/tabs ----------
async function loadModels() {
    try {
        const res = await fetch('api/models/status');
        const data = await res.json();
        const installed = data.installed || [];
        const sel = $('modelSelect');
        sel.innerHTML = installed
            .map((m) => {
                const active = m === data.active ? ' selected' : '';
                return `<option value="${m}"${active}>${m}${m === data.active ? ' (текущая)' : ''}</option>`;
            })
            .join('');
        if (!installed.length) {
            sel.innerHTML = '<option value="">Нет моделей</option>';
        }
        sel.addEventListener('change', async () => {
            const model = sel.value;
            if (!model) return;
            try {
                await fetch('api/models/active', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model }),
                });
                loadModels();
            } catch (e) {
                console.error('set model failed', e);
            }
        });
    } catch (e) {
        console.error('load models failed', e);
    }
}

async function loadLangs() {
    const res = await fetch('api/langs');
    const langs = await res.json();
    const sel = $('langSelect');
    sel.innerHTML = Object.entries(langs)
        .map(([code, name]) => `<option value="${code}">${name}</option>`)
        .join('');
    sel.value = state.lang;
    sel.addEventListener('change', () => {
        state.lang = sel.value;
        initChat();
        loadCards();
        loadDueCount();
    });
}

document.querySelectorAll('.tab').forEach((btn) => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach((b) => b.classList.remove('active'));
        document.querySelectorAll('.view').forEach((v) => v.classList.remove('active'));
        btn.classList.add('active');
        state.currentTab = btn.dataset.tab;
        const view = document.getElementById(btn.dataset.tab);
        if (view) view.classList.add('active');
    });
});

// ---------- Chat ----------
async function initChat() {
    const res = await fetch('api/chats');
    const chats = await res.json();
    state.chatId = chats.find((c) => c.lang === state.lang)?.id || null;
    if (!state.chatId) {
        const cre = await fetch('api/chats', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lang: state.lang, title: state.lang }),
        });
        const data = await cre.json();
        state.chatId = data.id;
    }
    $('chatWindow').innerHTML = '';
}

function appendMsg(role, content) {
    const div = document.createElement('div');
    div.className = `msg ${role}`;
    div.textContent = content;
    $('chatWindow').appendChild(div);
    $('chatWindow').scrollTop = $('chatWindow').scrollHeight;
}

async function sendChat() {
    const input = $('chatText');
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    appendMsg('user', text);
    const btn = $('chatSend');
    btn.disabled = true;
    const typing = document.createElement('div');
    typing.className = 'msg assistant muted';
    typing.textContent = 'печатает...';
    $('chatWindow').appendChild(typing);
    try {
        const res = await fetch(`api/chats/${state.chatId}/messages`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ role: 'user', content: text, lang: state.lang }),
        });
        typing.remove();
        if (!res.ok) throw new Error('server error');
        const data = await res.json();
        appendMsg('assistant', data.content);
    } catch (e) {
        typing.remove();
        appendMsg('error', 'Ошибка связи с ИИ. Проверьте, что Ollama запущена.');
    } finally {
        btn.disabled = false;
    }
}

// ---------- Cards ----------
async function loadCards() {
    const res = await fetch(`api/cards?lang=${state.lang}`);
    const cards = await res.json();
    const list = $('cardList');
    list.innerHTML = '';
    cards.forEach((c) => {
        const li = document.createElement('li');
        li.innerHTML = `<div><b>${escapeHtml(c.word)}</b> — ${escapeHtml(c.translation)}
            <span class="card-en">повт. ${c.repetitions}</span></div>
            <button class="del" data-id="${c.id}">✕</button>`;
        li.querySelector('.del').addEventListener('click', async () => {
            await fetch(`api/cards/${c.id}`, { method: 'DELETE' });
            loadCards();
            loadDueCount();
        });
        list.appendChild(li);
    });
}

async function loadDueCount() {
    const res = await fetch(`api/cards/due?lang=${state.lang}`);
    const due = await res.json();
    $('dueCount').textContent = `${due.length} карточек на сегодня`;
}

async function addCard() {
    const word = $('newWord').value.trim();
    const trans = $('newTrans').value.trim();
    if (!word || !trans) return;
    await fetch('api/cards', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ word, translation: trans, lang: state.lang }),
    });
    $('newWord').value = '';
    $('newTrans').value = '';
    loadCards();
    loadDueCount();
}

async function startLearning() {
    const res = await fetch(`api/cards/due?lang=${state.lang}`);
    state.dueList = await res.json();
    state.cardIndex = 0;
    state.showTranslation = false;
    if (!state.dueList.length) {
        $('flashcard').classList.remove('hidden');
        $('flashcard').querySelector('.card-face').textContent = 'Нет карточек на сегодня. Добавьте новые!';
        $('cardActions').classList.add('hidden');
        return;
    }
    $('flashcard').classList.remove('hidden');
    $('cardActions').classList.add('hidden');
    renderFlashCard();
}

function renderFlashCard() {
    const card = state.dueList[state.cardIndex];
    const face = $('flashcard').querySelector('.card-face');
    face.textContent = state.showTranslation ? card.translation : card.word;
}

$('flashcard').addEventListener('click', () => {
    if (!state.dueList.length) return;
    state.showTranslation = !state.showTranslation;
    if (state.showTranslation) $('cardActions').classList.remove('hidden');
    renderFlashCard();
});

document.querySelectorAll('#cardActions button').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const q = parseInt(btn.dataset.q, 10);
        const card = state.dueList[state.cardIndex];
        await fetch(`api/cards/${card.id}/review`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ quality: q }),
        });
        state.cardIndex++;
        state.showTranslation = false;
        if (state.cardIndex >= state.dueList.length) {
            $('flashcard').querySelector('.card-face').textContent = 'Сессия завершена! 🎉';
            $('cardActions').classList.add('hidden');
        } else {
            renderFlashCard();
        }
        loadCards();
        loadDueCount();
    });
});

// ---------- Exercises ----------
async function generateExercises() {
    $('genExercises').disabled = true;
    $('exerciseArea').innerHTML = '<p class="muted">Генерация... (может занять время)</p>';
    try {
        const res = await fetch('api/exercises', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                lang: state.lang,
                count: 5,
                level: $('exLevel').value,
            }),
        });
        const data = await res.json();
        state.exercises = data.exercises;
        renderExercises();
    } catch (e) {
        $('exerciseArea').innerHTML = '<p class="ex-err">Не удалось сгенерировать упражнения.</p>';
    } finally {
        $('genExercises').disabled = false;
    }
}

function renderExercises() {
    const area = $('exerciseArea');
    area.innerHTML = '';
    state.exercises.forEach((ex, i) => {
        const block = document.createElement('div');
        block.className = 'exercise';
        block.innerHTML = `
            <div class="q">${i + 1}. ${escapeHtml(ex.question)}</div>
            <div class="ex-options" id="exOpts${i}"></div>
            <div class="ex-hint" id="hint${i}" style="display:none">${escapeHtml(ex.hint || '')}</div>
            <div id="verdict${i}"></div>`;
        const opts = block.querySelector(`#exOpts${i}`);
        const options = ex.options && ex.options.length ? ex.options : [ex.answer];
        options.forEach((opt, oi) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'ex-opt';
            btn.dataset.oi = oi;
            btn.textContent = opt;
            btn.addEventListener('click', () => selectExerciseOption(i, oi));
            opts.appendChild(btn);
        });
        block.querySelector('.q').dataset.ex = i;
        area.appendChild(block);
    });
}

function selectExerciseOption(i, oi) {
    const ex = state.exercises[i];
    state.selectedOption = state.selectedOption || {};
    state.selectedOption[i] = oi;
    const opts = $('exOpts' + i).querySelectorAll('.ex-opt');
    opts.forEach((o) => {
        o.classList.remove('ex-selected');
        o.classList.remove('ex-correct');
        o.classList.remove('ex-wrong');
        o.style.pointerEvents = '';
        o.disabled = false;
    });
    opts[oi].classList.add('ex-selected');
    const selectedText = opts[oi].textContent.trim().toLowerCase();
    const correct = ex.answer.trim().toLowerCase();
    const verdict = $('verdict' + i);
    const hint = $('hint' + i);
    if (selectedText === correct) {
        opts[oi].classList.add('ex-correct');
        verdict.className = 'ex-ok';
        verdict.textContent = 'Верно!';
        hint.style.display = 'none';
        opts.forEach((o) => { o.disabled = true; });
    } else {
        opts[oi].classList.add('ex-wrong');
        verdict.className = 'ex-err';
        verdict.textContent = 'Неверно. Попробуйте ещё раз.';
        hint.style.display = 'block';
    }
}

// ---------- Stories ----------
async function generateStory() {
    const btn = $('genStory');
    const area = $('storyArea');
    btn.disabled = true;
    area.innerHTML = '<p class="muted">Сочиняю историю... (может занять время)</p>';
    try {
        const res = await fetch('api/story', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                lang: state.lang,
                theme: $('storyTheme').value.trim(),
                level: $('storyLevel').value,
                genre: $('storyGenre').value,
                length: $('storyLength').value,
            }),
        });
        if (!res.ok) throw new Error('server error');
        const story = await res.json();
        renderStory(story);
    } catch (e) {
        area.innerHTML = '<p class="ex-err">Не удалось сгенерировать историю.</p>';
    } finally {
        btn.disabled = false;
    }
}

function renderStory(story) {
    const area = $('storyArea');
    area.innerHTML = '';
    if (!story || !story.text) return;
    state.stories = [story];

    const box = document.createElement('div');
    box.className = 'story';
    box.innerHTML = `
        <h2 class="story-title">${escapeHtml(story.title || 'История')}</h2>
        <div class="story-text">${escapeHtml(story.text)}</div>`;

    if (story.glossary && story.glossary.length) {
        const gl = document.createElement('div');
        gl.className = 'story-glossary';
        gl.innerHTML = '<h3>Словарик</h3>';
        const ul = document.createElement('ul');
        story.glossary.forEach((g) => {
            const li = document.createElement('li');
            li.innerHTML = `<b>${escapeHtml(g.word)}</b> — ${escapeHtml(g.translation)}`;
            ul.appendChild(li);
        });
        gl.appendChild(ul);
        box.appendChild(gl);
    }

    if (story.questions && story.questions.length) {
        const qz = document.createElement('div');
        qz.className = 'story-questions';
        qz.innerHTML = '<h3>Проверьте понимание</h3>';
        story.questions.forEach((q, i) => {
            const item = document.createElement('div');
            item.className = 'story-question';
            item.innerHTML = `
                <div class="q">${i + 1}. ${escapeHtml(q.q)}</div>
                <div class="sq-row">
                    <input data-sq="${i}" placeholder="Ваш ответ" autocomplete="off">
                    <button data-sqcheck="${i}" class="sq-check"><i class="fa-solid fa-check"></i> Проверить</button>
                    <button data-sqshow="${i}" class="sq-show"><i class="fa-solid fa-eye"></i> Ответ</button>
                </div>
                <div class="sq-answer hidden" id="sqA${i}">${escapeHtml(q.a)}</div>
                <div class="sq-verdict" id="sqV${i}"></div>`;
            item.querySelector(`[data-sqcheck="${i}"]`).addEventListener('click', () => checkStoryAnswer(i));
            item.querySelector(`[data-sqshow="${i}"]`).addEventListener('click', () => {
                $('sqA' + i).classList.toggle('hidden');
            });
            item.querySelector(`[data-sq="${i}"]`).addEventListener('keydown', (e) => {
                if (e.key === 'Enter') checkStoryAnswer(i);
            });
            qz.appendChild(item);
        });
        box.appendChild(qz);
    }

    area.appendChild(box);
}

// ---------- Story answer checking ----------
function wordStem(word) {
    if (word.length > 4 && word.endsWith('ing')) return word.slice(0, -3);
    if (/[a-z]ed$/.test(word)) return word.slice(0, -2);
    if (word.endsWith('s') && word.length > 2) return word.slice(0, -1);
    return word;
}

function normalizeAnswer(s) {
    return s.toLowerCase()
        .replace(/[.,!?;:'"()]/g, ' ')
        .replace(/\b(the|a|an)\b/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
        .split(' ')
        .filter(Boolean)
        .map(wordStem)
        .filter((w) => w.length > 1);
}

function answersMatch(user, correct) {
    const u = normalizeAnswer(user);
    const c = normalizeAnswer(correct);
    if (!u.length || !c.length) return false;
    let hits = 0;
    c.forEach((w) => {
        if (u.includes(w)) hits++;
    });
    return hits / c.length >= 0.6;
}

function checkStoryAnswer(i) {
    const ex = state.stories[i];
    const input = document.querySelector(`[data-sq="${i}"]`);
    const verdict = $('sqV' + i);
    const answer = $('sqA' + i);
    const userText = (input.value || '').trim();
    if (!userText) {
        verdict.className = 'sq-verdict ex-err';
        verdict.textContent = 'Введите ответ.';
        return;
    }
    if (answersMatch(userText, ex.a)) {
        verdict.className = 'sq-verdict ex-ok';
        verdict.innerHTML = '<i class="fa-solid fa-circle-check"></i> Верно!';
        answer.classList.add('hidden');
    } else {
        verdict.className = 'sq-verdict ex-err';
        verdict.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> Не совсем. Правильный ответ: <b>${escapeHtml(ex.a)}</b>`;
        answer.classList.remove('hidden');
    }
}

// ---------- Pronunciation (Web Speech API) ----------
let recognition = null;

function setupRecognition() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
        $('recordBtn').disabled = true;
        $('recogStatus').textContent = 'Ваш браузер не поддерживает распознавание речи. Попробуйте Chrome/Edge.';
        return;
    }
    recognition = new SR();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
        $('recogStatus').textContent = 'Слушаю... говорите.';
    };
    recognition.onerror = (e) => {
        $('recogStatus').textContent = 'Ошибка: ' + e.error;
    };
    recognition.onresult = (e) => {
        const said = e.results[0][0].transcript;
        $('recogStatus').textContent = 'Распознано: ' + said;
        const expected = $('phraseText').value.trim().toLowerCase()
            .replace(/[.,!?]/g, '').replace(/\s+/g, ' ');
        const saidNorm = said.trim().toLowerCase().replace(/[.,!?]/g, ' ').replace(/\s+/g, ' ');
        const res = $('pronRes');
        if (saidNorm.includes(expected) || expected.includes(saidNorm)) {
            res.innerHTML = '<span class="ex-ok">Отличное произношение! 🎉</span>';
        } else {
            res.innerHTML = `Продолжайте тренироваться. Вы сказали: <em>"${escapeHtml(said)}"</em>`;
        }
    };
    recognition.onend = () => {
        $('recogStatus').textContent = 'Распознавание завершено.';
    };
}

$('recordBtn').addEventListener('click', () => {
    if (recognition) recognition.start();
});

// ---------- Utils ----------
function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
}

// ---------- Exam ----------
const exam = {
    sections: [],
    answers: {},
    timerStart: 0,
    timerId: null,
    elapsed: 0,
};

function collectExamTypes() {
    const types = [];
    if ($('examTypeGrammar').checked) types.push('grammar');
    if ($('examTypeReading').checked) types.push('reading');
    if ($('examTypeCustom').checked) types.push('custom');
    return types;
}

async function startExam() {
    const types = collectExamTypes();
    if (!types.length) {
        alert('Выберите хотя бы один тип задания.');
        return;
    }
    const level = $('examLevel').value;
    const perType = parseInt($('examPerType').value, 10);
    const source = $('examSourceText').value.trim();

    $('examStart').disabled = true;
    $('examRun').classList.add('hidden');
    $('examResult').classList.add('hidden');
    $('examBody').innerHTML = '<p class="muted">Генерирую экзамен... (может занять время)</p>';
    $('examRun').classList.remove('hidden');
    try {
        const res = await fetch('api/exam', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                lang: state.lang,
                level,
                types,
                per_type: perType,
                source_text: source,
            }),
        });
        if (!res.ok) throw new Error('server error');
        const data = await res.json();
        exam.sections = data.sections || [];
        exam.answers = {};
        if (!exam.sections.length) throw new Error('no sections');
        renderExam();
        startExamTimer();
    } catch (e) {
        $('examRun').classList.add('hidden');
        $('examBody').innerHTML = '<p class="ex-err">Не удалось сгенерировать экзамен.</p>';
    } finally {
        $('examStart').disabled = false;
    }
}

function renderExam() {
    const body = $('examBody');
    body.innerHTML = '';
    let qIndex = 0;
    exam.sections.forEach((sec, si) => {
        const box = document.createElement('div');
        box.className = 'exam-section';
        box.innerHTML = `<h3><i class="fa-solid fa-list-ol"></i> ${escapeHtml(sec.title || 'Секция')}</h3>`;
        if (sec.passage && sec.passage.trim()) {
            const p = document.createElement('div');
            p.className = 'exam-passage';
            p.textContent = sec.passage;
            box.appendChild(p);
        }
        (sec.questions || []).forEach((qu) => {
            const item = document.createElement('div');
            item.className = 'exam-question';
            item.innerHTML = `
                <div class="q">${qIndex + 1}. ${escapeHtml(qu.q)}</div>
                <div class="exam-options" data-q="${qIndex}"></div>`;
            const opts = item.querySelector('.exam-options');
            qu.options.forEach((opt) => {
                const b = document.createElement('button');
                b.type = 'button';
                b.className = 'exam-opt';
                b.textContent = opt;
                b.addEventListener('click', () => selectExamAnswer(qIndex, opt));
                opts.appendChild(b);
            });
            box.appendChild(item);
            qIndex++;
        });
        body.appendChild(box);
    });
    $('examProgress').textContent = `Вопросов: ${qIndex}`;
}

function selectExamAnswer(qIndex, opt) {
    // Allow only one selection per question.
    const containers = document.querySelectorAll(`.exam-options[data-q="${qIndex}"] .exam-opt`);
    containers.forEach((o) => o.classList.remove('exam-selected'));
    // mark the clicked one
    containers.forEach((o) => {
        if (o.textContent === opt) o.classList.add('exam-selected');
    });
    exam.answers[qIndex] = opt;
}

function startExamTimer() {
    exam.timerStart = Date.now();
    exam.elapsed = 0;
    if (exam.timerId) clearInterval(exam.timerId);
    exam.timerId = setInterval(() => {
        exam.elapsed = Math.floor((Date.now() - exam.timerStart) / 1000);
        const m = String(Math.floor(exam.elapsed / 60)).padStart(2, '0');
        const s = String(exam.elapsed % 60).padStart(2, '0');
        $('examTimer').innerHTML = `<i class="fa-solid fa-stopwatch"></i> ${m}:${s}`;
    }, 1000);
}

function finishExam() {
    clearInterval(exam.timerId);
    // Flatten questions in order.
    const flat = [];
    exam.sections.forEach((sec) => (sec.questions || []).forEach((qu) => flat.push(qu)));
    let correct = 0;
    const total = flat.length;
    flat.forEach((qu, i) => {
        const chosen = exam.answers[i];
        const isRight = chosen && chosen.trim().toLowerCase() === qu.answer.trim().toLowerCase();
        if (isRight) correct++;
        // Colorize UI for review.
        const cont = document.querySelectorAll(`.exam-options[data-q="${i}"] .exam-opt`);
        cont.forEach((o) => {
            o.disabled = true;
            if (o.textContent.trim().toLowerCase() === qu.answer.trim().toLowerCase()) {
                o.classList.add('exam-correct');
            } else if (o.textContent === chosen) {
                o.classList.add('exam-wrong');
            }
            o.classList.remove('exam-selected');
        });
    });
    const pct = total ? Math.round((correct / total) * 100) : 0;
    renderExamResult(correct, total, pct);
}

function renderExamResult(correct, total, pct) {
    const result = $('examResult');
    const level = $('examLevel').value;
    const mapping = ['a1', 'a2', 'b1', 'b2', 'c1', 'c2'];
    const idx = Math.max(0, Math.min(mapping.length - 1, Math.round((pct / 100) * 5)));
    const achieved = mapping[idx];
    const m = String(Math.floor(exam.elapsed / 60)).padStart(2, '0');
    const s = String(exam.elapsed % 60).padStart(2, '0');
    result.className = 'exam-result view';
    result.innerHTML = `
        <h2>Результат экзамена</h2>
        <div class="score">${correct} / ${total}</div>
        <div class="detail">Точность: ${pct}%</div>
        <div class="level-badge">Достигнутый уровень: ${achieved.toUpperCase()}</div>
        <div class="detail">Время: ${m}:${s}</div>
        ${pct < 60 ? '<div class="detail">Продолжайте практиковаться на более низком уровне и повторите тест.</div>'
          : pct < 85 ? '<div class="detail">Хороший результат! Попробуйте следующий уровень CEFR.</div>'
          : '<div class="detail">Отличный результат! Вы уверенно владеете выбранным уровнем.</div>'}
        <div class="exam-retry"><button id="examRetry"><i class="fa-solid fa-rotate"></i> Пройти ещё раз</button></div>`;
    result.querySelector('#examRetry').addEventListener('click', () => {
        result.classList.add('hidden');
        $('examRun').classList.add('hidden');
        $('examBody').innerHTML = '';
    });
    result.classList.remove('hidden');
}

async function extractFile() {
    const fileInput = $('examFile');
    if (!fileInput.files.length) {
        $('examExtractStatus').textContent = 'Сначала выберите файл.';
        return;
    }
    const file = fileInput.files[0];
    const useOcr = $('examOcr').checked;
    $('examExtractBtn').disabled = true;
    $('examExtractStatus').textContent = 'Извлекаю текст...';
    const fd = new FormData();
    fd.append('file', file);
    fd.append('use_ocr', useOcr ? 'true' : 'false');
    try {
        const res = await fetch('api/extract', { method: 'POST', body: fd });
        const data = await res.json();
        const text = (data.text || '').trim();
        if (text) {
            $('examSourceText').value = text;
            $('examExtractStatus').textContent = `Текст извлечён (${text.length} символов).`;
        } else {
            $('examExtractStatus').textContent = useOcr
                ? 'Не удалось распознать. Попробуйте PDF с текстовым слоем или чёткое изображение.'
                : 'Не удалось извлечь текст из PDF. Включите OCR (бета) для сканов/изображений.';
        }
    } catch (e) {
        $('examExtractStatus').textContent = 'Ошибка при извлечении текста.';
    } finally {
        $('examExtractBtn').disabled = false;
    }
}

// ---------- Init ----------
$('chatSend').addEventListener('click', sendChat);
$('chatText').addEventListener('keydown', (e) => { if (e.key === 'Enter') sendChat(); });
$('addCardBtn').addEventListener('click', addCard);
$('learnBtn').addEventListener('click', startLearning);
$('genExercises').addEventListener('click', generateExercises);
$('genStory').addEventListener('click', generateStory);
$('examStart').addEventListener('click', startExam);
$('examFinish').addEventListener('click', finishExam);
$('examExtractBtn').addEventListener('click', extractFile);

async function init() {
    await loadLangs();
    await loadModels();
    await initChat();
    await loadCards();
    await loadDueCount();
    setupRecognition();
    const saved = loadSavedHistory();
    if (saved && saved.lang === state.lang) {
        saved.messages.forEach((m) => appendMsg(m.role, m.content));
    }
}

function loadSavedHistory() {
    try { return JSON.parse(localStorage.getItem('linguaai_history') || 'null'); }
    catch { return null; }
}

init();