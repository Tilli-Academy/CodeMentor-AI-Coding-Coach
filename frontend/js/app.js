// CodeMentor frontend logic.
//
// Talks to the FastAPI backend over HTTP using fetch() + JSON:
//   POST {API_BASE}/api/ai/explain          body: { code, error_message }   -> { explanation }
//   POST {API_BASE}/api/ai/hints            body: { code, question, level } -> { hint, level }
//   POST {API_BASE}/api/ai/learn/question   body: { code?, topic? }         -> { question }
//   POST {API_BASE}/api/ai/learn/evaluate   body: { question, answer, code?, topic? }
//                                                 -> { verdict, feedback, follow_up }
//
// The backend validates the JSON against its Pydantic schemas and calls the
// local Ollama model.

// Base URL of the FastAPI backend. The frontend is served through the dev
// proxy, which forwards /proxy/8010 to uvicorn on port 8010 (same host:port
// as the page, so window.location.origin keeps it working behind the proxy).
const API_BASE = window.location.origin + "/proxy/8010";

const form = document.getElementById("explain-form");
const codeEl = document.getElementById("code");
const errorEl = document.getElementById("error");
const submitBtn = document.getElementById("submit-btn");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");
const explanationEl = document.getElementById("explanation");

function showStatus(message, kind) {
	statusEl.textContent = message;
	statusEl.className = "status " + (kind || "");
	statusEl.hidden = false;
}

function hide(el) {
	el.hidden = true;
}

// ---- Markdown rendering ----
// The AI returns Markdown; these helpers render a safe subset to HTML. The input
// is untrusted model output, so everything is HTML-escaped FIRST and only known
// tags are emitted — and no links/images are parsed, so there is no href/src
// injection surface. This is the one place we use innerHTML, and only with the
// controlled string renderMarkdown() builds.

function escapeHtml(s) {
	return String(s)
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;");
}

// Inline formatting on ALREADY-escaped text. Split on inline-code spans so bold/
// italic never reach code contents; format only the non-code segments.
function renderInline(text) {
	return text
		.split(/(`[^`]+`)/g)
		.map((part) => {
			if (part.length >= 2 && part.startsWith("`") && part.endsWith("`")) {
				return "<code>" + part.slice(1, -1) + "</code>";
			}
			return part
				.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
				.replace(/\*([^*\n]+)\*/g, "<em>$1</em>")
				.replace(/_([^_\n]+)_/g, "<em>$1</em>");
		})
		.join("");
}

// Render a safe subset of Markdown (headings, bold/italic, inline + fenced code,
// bullet/numbered lists, paragraphs) to an HTML string with no stray newlines
// outside <pre>.
function renderMarkdown(src) {
	if (!src) return "";
	const lines = String(src).replace(/\r\n?/g, "\n").split("\n");
	let html = "";
	let listType = null; // 'ul' | 'ol' | null
	let para = [];
	let i = 0;

	const closeList = () => {
		if (listType) {
			html += "</" + listType + ">";
			listType = null;
		}
	};
	const flushPara = () => {
		if (para.length) {
			html += "<p>" + para.map(renderInline).join("<br>") + "</p>";
			para = [];
		}
	};

	while (i < lines.length) {
		const line = lines[i];

		if (/^\s*```/.test(line)) {
			flushPara();
			closeList();
			i++;
			const buf = [];
			while (i < lines.length && !/^\s*```/.test(lines[i])) {
				buf.push(lines[i]);
				i++;
			}
			i++; // skip the closing fence
			html += "<pre><code>" + escapeHtml(buf.join("\n")) + "</code></pre>";
			continue;
		}

		const h = line.match(/^(#{1,6})\s+(.*)$/);
		if (h) {
			flushPara();
			closeList();
			const level = Math.min(h[1].length + 2, 6); // #->h3, ##->h4, ...
			html +=
				"<h" + level + ">" + renderInline(escapeHtml(h[2].trim())) + "</h" + level + ">";
			i++;
			continue;
		}

		const ul = line.match(/^\s*[-*]\s+(.*)$/);
		if (ul) {
			flushPara();
			if (listType !== "ul") {
				closeList();
				html += "<ul>";
				listType = "ul";
			}
			html += "<li>" + renderInline(escapeHtml(ul[1])) + "</li>";
			i++;
			continue;
		}

		const ol = line.match(/^\s*\d+\.\s+(.*)$/);
		if (ol) {
			flushPara();
			if (listType !== "ol") {
				closeList();
				html += "<ol>";
				listType = "ol";
			}
			html += "<li>" + renderInline(escapeHtml(ol[1])) + "</li>";
			i++;
			continue;
		}

		if (/^\s*$/.test(line)) {
			flushPara();
			closeList();
			i++;
			continue;
		}

		closeList();
		para.push(escapeHtml(line.trim()));
		i++;
	}
	flushPara();
	closeList();
	return html;
}

// Render model Markdown into an element as safe HTML; `markdown` class enables
// the CSS that styles the generated headings/lists/code.
function setMarkdown(el, text) {
	el.innerHTML = renderMarkdown(text);
	el.classList.add("markdown");
}

form.addEventListener("submit", async (event) => {
	event.preventDefault();

	const code = codeEl.value.trim();
	const errorMessage = errorEl.value.trim();

	if (!code) {
		showStatus("Please paste some code first.", "error");
		return;
	}

	submitBtn.disabled = true;
	hide(resultEl);
	showStatus("Asking CodeMentor…", "loading");

	try {
		const res = await fetch(`${API_BASE}/api/ai/explain`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({
				code,
				error_message: errorMessage || null,
			}),
		});

		const data = await res.json().catch(() => ({}));

		if (!res.ok) {
			// FastAPI puts the message in `detail` (a string, or a list for 422).
			const detail =
				typeof data.detail === "string"
					? data.detail
					: JSON.stringify(data.detail || `HTTP ${res.status}`);
			showStatus(`Error: ${detail}`, "error");
			return;
		}

		setMarkdown(explanationEl, data.explanation || "(empty response)");
		resultEl.hidden = false;
		hide(statusEl);
		loadHistory(); // this activity was just saved — refresh the list
	} catch (err) {
		// Network error / backend not running / CORS.
		showStatus(
			`Could not reach the backend at ${API_BASE}. Is the server running?`,
			"error",
		);
	} finally {
		submitBtn.disabled = false;
	}
});

// ---- Progressive Hints ----
// POST {API_BASE}/api/ai/hints  body: { code, question, level }  ->  { hint, level }
// One hint per request; "Next Hint" steps the level 1 -> 2 -> 3. Reuses the code
// textarea above; the sequence resets whenever the code or the question changes.

const questionEl = document.getElementById("question");
const hintBtn = document.getElementById("hint-btn");
const nextHintBtn = document.getElementById("next-hint-btn");
const hintStatusEl = document.getElementById("hint-status");
const hintResultEl = document.getElementById("hint-result");
const hintLevelEl = document.getElementById("hint-level");
const hintContentEl = document.getElementById("hint-content");
const hintDoneEl = document.getElementById("hint-done");

const MAX_HINT_LEVEL = 3;
let currentLevel = 0; // last successfully shown hint level (0 = none yet)
let hintLoading = false;

function showHintStatus(message, kind) {
	hintStatusEl.textContent = message;
	hintStatusEl.className = "status " + (kind || "");
	hintStatusEl.hidden = false;
}

function setHintLoading(loading) {
	hintLoading = loading;
	hintBtn.disabled = loading;
	nextHintBtn.disabled = loading;
}

// Back to "no hints yet" — called when the code or question changes.
function resetHints() {
	currentLevel = 0;
	hide(hintResultEl);
	hide(hintStatusEl);
	hide(hintDoneEl);
	hide(nextHintBtn);
	hintBtn.hidden = false;
	setHintLoading(false);
}

async function requestHint(level) {
	if (hintLoading) return; // only one hint request at a time

	const code = codeEl.value.trim();
	const question = questionEl.value.trim();
	if (!code) {
		showHintStatus("Please paste some code first.", "error");
		return;
	}
	if (!question) {
		showHintStatus("Please describe what you're stuck on.", "error");
		return;
	}

	setHintLoading(true);
	showHintStatus(`Getting hint ${level}…`, "loading");

	try {
		const res = await fetch(`${API_BASE}/api/ai/hints`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ code, question, level }),
		});

		const data = await res.json().catch(() => ({}));

		if (!res.ok) {
			// FastAPI puts the message in `detail` (a string, or a list for 422).
			const detail =
				typeof data.detail === "string"
					? data.detail
					: JSON.stringify(data.detail || `HTTP ${res.status}`);
			showHintStatus(`Error: ${detail}`, "error");
			return;
		}

		// Success — show the hint and advance the button state.
		currentLevel = data.level || level;
		hintLevelEl.textContent = currentLevel;
		setMarkdown(hintContentEl, data.hint || "(empty hint)");
		hintResultEl.hidden = false;
		hide(hintStatusEl);
		loadHistory(); // this hint was just saved — refresh the list

		hintBtn.hidden = true;
		if (currentLevel >= MAX_HINT_LEVEL) {
			hide(nextHintBtn);
			hintDoneEl.hidden = false;
		} else {
			nextHintBtn.hidden = false;
			hide(hintDoneEl);
		}
	} catch (err) {
		// Network error / backend not running / CORS.
		showHintStatus(
			`Could not reach the backend at ${API_BASE}. Is the server running?`,
			"error",
		);
	} finally {
		setHintLoading(false);
	}
}

hintBtn.addEventListener("click", () => requestHint(1));
nextHintBtn.addEventListener("click", () => requestHint(currentLevel + 1));

// Reset the hint sequence when the code or the problem changes (requirement 10).
codeEl.addEventListener("input", resetHints);
questionEl.addEventListener("input", resetHints);

// ---- Learning Mode ----
// Two-step quiz flow against the backend:
//   POST {API_BASE}/api/ai/learn/question   body: { code?, topic? }        -> { question }
//   POST {API_BASE}/api/ai/learn/evaluate   body: { question, answer, code?, topic? }
//                                                 -> { verdict, feedback, follow_up }
// Reuses the code textarea above; a topic can be supplied instead/as well. The
// flow resets whenever the code or topic changes so questions stay relevant.

const learnTopicEl = document.getElementById("learn-topic");
const learnQuestionBtn = document.getElementById("learn-question-btn");
const learnStatusEl = document.getElementById("learn-status");
const learnQaEl = document.getElementById("learn-qa");
const learnQuestionEl = document.getElementById("learn-question");
const learnAnswerEl = document.getElementById("learn-answer");
const learnAnswerBtn = document.getElementById("learn-answer-btn");
const learnFeedbackEl = document.getElementById("learn-feedback");
const learnVerdictEl = document.getElementById("learn-verdict");
const learnFeedbackTextEl = document.getElementById("learn-feedback-text");
const learnFollowupWrapEl = document.getElementById("learn-followup-wrap");
const learnFollowupEl = document.getElementById("learn-followup");
const learnFollowupBtn = document.getElementById("learn-followup-btn");
const learnNewBtn = document.getElementById("learn-new-btn");

const VERDICT_LABELS = {
	correct: "Correct",
	partially_correct: "Partially correct",
	incorrect: "Incorrect",
};
const VERDICT_CLASSES = {
	correct: "verdict-correct",
	partially_correct: "verdict-partial",
	incorrect: "verdict-incorrect",
};

let learnCurrentQuestion = ""; // the question currently being answered
let pendingFollowup = ""; // follow-up offered by the last evaluation, if any
let learnLoading = false;

function showLearnStatus(message, kind) {
	learnStatusEl.textContent = message;
	learnStatusEl.className = "status " + (kind || "");
	learnStatusEl.hidden = false;
}

function setLearnLoading(loading) {
	learnLoading = loading;
	learnQuestionBtn.disabled = loading;
	learnAnswerBtn.disabled = loading;
	learnFollowupBtn.disabled = loading;
	learnNewBtn.disabled = loading;
}

// Pull the error text out of a FastAPI JSON body (string detail, or 422 list).
function errorDetail(data, res) {
	return typeof data.detail === "string"
		? data.detail
		: JSON.stringify(data.detail || `HTTP ${res.status}`);
}

// The code/topic context both learn endpoints share. Blank fields are omitted so
// the backend's "code or topic required" rule is honored.
function learnContext() {
	const code = codeEl.value.trim();
	const topic = learnTopicEl.value.trim();
	const ctx = {};
	if (code) ctx.code = code;
	if (topic) ctx.topic = topic;
	return ctx;
}

// Back to "no question yet" — called when the code or topic changes.
function resetLearn() {
	learnCurrentQuestion = "";
	pendingFollowup = "";
	hide(learnQaEl);
	hide(learnFeedbackEl);
	hide(learnFollowupWrapEl);
	hide(learnStatusEl);
	setLearnLoading(false);
}

async function requestQuestion() {
	if (learnLoading) return; // only one request at a time

	const ctx = learnContext();
	if (!ctx.code && !ctx.topic) {
		showLearnStatus("Add some code above or enter a topic first.", "error");
		return;
	}

	setLearnLoading(true);
	showLearnStatus("Thinking of a question…", "loading");

	try {
		const res = await fetch(`${API_BASE}/api/ai/learn/question`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(ctx),
		});

		const data = await res.json().catch(() => ({}));

		if (!res.ok) {
			showLearnStatus(`Error: ${errorDetail(data, res)}`, "error");
			return;
		}

		learnCurrentQuestion = data.question || "(empty question)";
		setMarkdown(learnQuestionEl, learnCurrentQuestion);
		learnAnswerEl.value = "";
		hide(learnFeedbackEl);
		learnQaEl.hidden = false;
		hide(learnStatusEl);
		// Land the cursor in the answer box so "Get a Question" / "New Question"
		// visibly does something even if the question scrolls above the fold.
		learnAnswerEl.focus();
		loadHistory(); // this learning question was just saved — refresh the list
	} catch (err) {
		showLearnStatus(
			`Could not reach the backend at ${API_BASE}. Is the server running?`,
			"error",
		);
	} finally {
		setLearnLoading(false);
	}
}

async function submitAnswer() {
	if (learnLoading) return; // only one request at a time

	if (!learnCurrentQuestion) {
		showLearnStatus("Get a question first.", "error");
		return;
	}
	const answer = learnAnswerEl.value.trim();
	if (!answer) {
		showLearnStatus("Please type an answer first.", "error");
		return;
	}

	setLearnLoading(true);
	showLearnStatus("Checking your answer…", "loading");

	try {
		const res = await fetch(`${API_BASE}/api/ai/learn/evaluate`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({
				question: learnCurrentQuestion,
				answer,
				...learnContext(),
			}),
		});

		const data = await res.json().catch(() => ({}));

		if (!res.ok) {
			showLearnStatus(`Error: ${errorDetail(data, res)}`, "error");
			return;
		}

		const verdict = data.verdict || "partially_correct";
		learnVerdictEl.textContent = VERDICT_LABELS[verdict] || verdict;
		learnVerdictEl.className = VERDICT_CLASSES[verdict] || "";
		setMarkdown(learnFeedbackTextEl, data.feedback || "(no feedback)");

		pendingFollowup = data.follow_up || "";
		if (pendingFollowup) {
			setMarkdown(learnFollowupEl, pendingFollowup);
			learnFollowupWrapEl.hidden = false;
		} else {
			hide(learnFollowupWrapEl);
		}

		learnFeedbackEl.hidden = false;
		hide(learnStatusEl);
		loadHistory(); // this evaluation was just saved — refresh the list
	} catch (err) {
		showLearnStatus(
			`Could not reach the backend at ${API_BASE}. Is the server running?`,
			"error",
		);
	} finally {
		setLearnLoading(false);
	}
}

// Promote the offered follow-up to the current question and answer it.
function answerFollowup() {
	if (!pendingFollowup) return;
	learnCurrentQuestion = pendingFollowup;
	pendingFollowup = "";
	learnQuestionEl.textContent = learnCurrentQuestion;
	learnAnswerEl.value = "";
	hide(learnFeedbackEl);
	hide(learnStatusEl);
	learnQaEl.hidden = false;
	learnAnswerEl.focus();
}

learnQuestionBtn.addEventListener("click", requestQuestion);
learnAnswerBtn.addEventListener("click", submitAnswer);
learnFollowupBtn.addEventListener("click", answerFollowup);
learnNewBtn.addEventListener("click", requestQuestion); // "New Question" = fetch another

// Reset the learning flow when the code or the topic changes (keep questions relevant).
codeEl.addEventListener("input", resetLearn);
learnTopicEl.addEventListener("input", resetLearn);

// ---- History ----
// Lists saved activities from GET {API_BASE}/api/history, lets the user open a
// full record or delete one via DELETE {API_BASE}/api/history/{id}. Rendered with
// textContent (never innerHTML) so stored code / AI text cannot inject markup.

const historyRefreshBtn = document.getElementById("history-refresh-btn");
const historyStatusEl = document.getElementById("history-status");
const historyListEl = document.getElementById("history-list");
const historyDetailEl = document.getElementById("history-detail");
const historyDetailTitleEl = document.getElementById("history-detail-title");
const historyDetailBodyEl = document.getElementById("history-detail-body");
const historyDetailCloseBtn = document.getElementById("history-detail-close");

const ACTIVITY_LABELS = {
	explain: "Explain",
	hints: "Hint",
	learn_question: "Learning question",
	learn_evaluate: "Answer evaluation",
};

const HISTORY_EMPTY_MSG =
	"No activity yet — try Explain, a Hint, or Learning Mode above.";

function showHistoryStatus(message, kind) {
	historyStatusEl.textContent = message;
	historyStatusEl.className = "status " + (kind || "");
	historyStatusEl.hidden = false;
}

function activityLabel(type) {
	return ACTIVITY_LABELS[type] || type;
}

// created_at is ISO-8601 UTC; show it in the viewer's local time when parseable.
function formatTimestamp(iso) {
	const d = new Date(iso);
	return isNaN(d.getTime()) ? iso : d.toLocaleString();
}

function previewText(item) {
	const source = item.ai_response || item.code || item.question || "";
	const oneLine = source.replace(/\s+/g, " ").trim();
	return oneLine.length > 120 ? oneLine.slice(0, 120) + "…" : oneLine;
}

async function loadHistory() {
	showHistoryStatus("Loading history…", "loading");
	hide(historyDetailEl);
	try {
		const res = await fetch(`${API_BASE}/api/history?limit=50`);
		if (!res.ok) {
			const data = await res.json().catch(() => ({}));
			showHistoryStatus(`Error: ${errorDetail(data, res)}`, "error");
			return;
		}
		const items = await res.json().catch(() => []);
		renderHistory(items);
	} catch (err) {
		showHistoryStatus(
			`Could not reach the backend at ${API_BASE}. Is the server running?`,
			"error",
		);
	}
}

function renderHistory(items) {
	historyListEl.innerHTML = "";
	if (!Array.isArray(items) || items.length === 0) {
		showHistoryStatus(HISTORY_EMPTY_MSG, "");
		return;
	}
	hide(historyStatusEl);
	for (const item of items) {
		historyListEl.appendChild(buildHistoryRow(item));
	}
}

function buildHistoryRow(item) {
	const li = document.createElement("li");
	li.className = "history-item";

	const meta = document.createElement("div");
	meta.className = "history-meta";
	const type = document.createElement("span");
	type.className = "history-type";
	type.textContent = activityLabel(item.activity_type);
	const time = document.createElement("span");
	time.className = "history-time";
	time.textContent = formatTimestamp(item.created_at);
	meta.append(type, time);

	const preview = document.createElement("p");
	preview.className = "history-preview";
	preview.textContent = previewText(item);

	const actions = document.createElement("div");
	actions.className = "history-item-actions";
	const viewBtn = document.createElement("button");
	viewBtn.type = "button";
	viewBtn.textContent = "View";
	viewBtn.addEventListener("click", () => showHistoryDetail(item));
	const deleteBtn = document.createElement("button");
	deleteBtn.type = "button";
	deleteBtn.className = "history-delete-btn";
	deleteBtn.textContent = "Delete";
	deleteBtn.addEventListener("click", () => deleteHistory(item, li));
	actions.append(viewBtn, deleteBtn);

	li.append(meta, preview, actions);
	return li;
}

function showHistoryDetail(item) {
	historyDetailTitleEl.textContent =
		activityLabel(item.activity_type) + " — " + formatTimestamp(item.created_at);

	historyDetailBodyEl.innerHTML = "";
	const addField = (label, value, asMarkdown = false) => {
		if (value === null || value === undefined || value === "") return;
		const field = document.createElement("div");
		field.className = "history-field";
		const heading = document.createElement("h4");
		heading.textContent = label;
		const body = document.createElement("div");
		body.className = "history-field-value";
		// Code/Question stay literal (textContent); only the AI response is Markdown.
		if (asMarkdown) setMarkdown(body, String(value));
		else body.textContent = String(value);
		field.append(heading, body);
		historyDetailBodyEl.appendChild(field);
	};

	addField("Code", item.code);
	addField("Question / topic", item.question);
	if (item.hint_level !== null && item.hint_level !== undefined) {
		addField("Hint level", item.hint_level);
	}
	addField("AI response", item.ai_response, true);

	historyDetailEl.hidden = false;
	historyDetailEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function deleteHistory(item, li) {
	try {
		const res = await fetch(`${API_BASE}/api/history/${item.id}`, {
			method: "DELETE",
		});
		if (!res.ok) {
			const data = await res.json().catch(() => ({}));
			showHistoryStatus(`Error: ${errorDetail(data, res)}`, "error");
			return;
		}
		li.remove();
		hide(historyDetailEl); // close the detail panel in case it showed this item
		if (historyListEl.children.length === 0) {
			showHistoryStatus(HISTORY_EMPTY_MSG, "");
		}
	} catch (err) {
		showHistoryStatus(
			`Could not reach the backend at ${API_BASE}. Is the server running?`,
			"error",
		);
	}
}

historyRefreshBtn.addEventListener("click", loadHistory);
historyDetailCloseBtn.addEventListener("click", () => hide(historyDetailEl));

// Load history on startup so the section is populated without a manual refresh.
loadHistory();

// ---- Tab navigation ----
// Switches the four feature panels (Explain / Hints / Learning Mode / History)
// without reloading. Panels and the shared code workspace stay in the DOM, so all
// input state and the existing handlers above are preserved — this only toggles
// visibility and the active nav state, and keeps the URL hash in sync.

const navTabs = document.querySelectorAll(".nav-tab");
const panels = document.querySelectorAll(".panel");
const appEl = document.getElementById("app");
const VALID_TABS = ["explain", "hints", "learn", "history"];

function activateTab(name) {
	if (!VALID_TABS.includes(name)) name = "explain";

	navTabs.forEach((btn) => {
		const on = btn.dataset.tab === name;
		btn.classList.toggle("active", on);
		btn.setAttribute("aria-selected", on ? "true" : "false");
		// Roving tabindex: only the selected tab is in the Tab order; the others
		// are reached with the arrow keys (WAI-ARIA tabs pattern).
		btn.tabIndex = on ? 0 : -1;
	});
	panels.forEach((panel) => {
		panel.classList.toggle("active", panel.dataset.panel === name);
	});
	// History needs no code editor, so it gets the full width.
	appEl.classList.toggle("history-active", name === "history");

	if (location.hash.slice(1) !== name) {
		history.replaceState(null, "", "#" + name);
	}
	// Refresh history whenever its tab is opened so it reflects new activity.
	if (name === "history") loadHistory();
}

navTabs.forEach((btn) => {
	btn.addEventListener("click", () => activateTab(btn.dataset.tab));
});

// Keyboard navigation for the tablist: Left/Right (and Home/End) move between
// tabs, wrapping around, and activate the focused tab (WAI-ARIA tabs pattern).
function focusTab(index) {
	const tab = navTabs[index];
	activateTab(tab.dataset.tab);
	tab.focus();
}

navTabs.forEach((btn, index) => {
	btn.addEventListener("keydown", (e) => {
		let next = null;
		if (e.key === "ArrowRight" || e.key === "ArrowDown") {
			next = (index + 1) % navTabs.length;
		} else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
			next = (index - 1 + navTabs.length) % navTabs.length;
		} else if (e.key === "Home") {
			next = 0;
		} else if (e.key === "End") {
			next = navTabs.length - 1;
		}
		if (next !== null) {
			e.preventDefault();
			focusTab(next);
		}
	});
});

window.addEventListener("hashchange", () => activateTab(location.hash.slice(1)));

// Open the tab named in the URL hash (deep link), defaulting to Explain.
activateTab(location.hash.slice(1) || "explain");
