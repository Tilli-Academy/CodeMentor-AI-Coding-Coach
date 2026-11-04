// CodeMentor — Monaco editor integration (progressive enhancement).
//
// Mounts the vendored Monaco editor over the plain #code textarea and keeps the two
// in sync. Monaco is what the user sees and types in; the hidden #code textarea stays
// the single source app.js reads (codeEl.value) and the element whose "input" events
// drive resetHints / resetLearn. If Monaco fails to load for any reason, the textarea
// stays visible and everything keeps working — nothing in app.js changes.

(function () {
	const textarea = document.getElementById("code");
	const host = document.getElementById("monaco-editor");
	const workspace = document.getElementById("workspace");

	// No AMD loader (script missing/blocked) → silently keep the textarea fallback.
	if (!textarea || !host || typeof require === "undefined") return;

	const vendorBase = new URL("vendor/monaco/", document.baseURI).href;

	// Monaco web workers must be same-origin. Load them from a blob that importScripts
	// our vendored workerMain.js (the standard same-origin worker shim).
	window.MonacoEnvironment = {
		getWorkerUrl: function () {
			const js =
				"self.MonacoEnvironment={baseUrl:'" +
				vendorBase +
				"'};importScripts('" +
				vendorBase +
				"vs/base/worker/workerMain.js');";
			return URL.createObjectURL(new Blob([js], { type: "text/javascript" }));
		},
	};

	require.config({ paths: { vs: vendorBase + "vs" } });

	require(
		["vs/editor/editor.main"],
		function () {
			let syncing = false;

			const editor = monaco.editor.create(host, {
				value: textarea.value,
				language: "python",
				theme: "vs-dark",
				automaticLayout: true, // reflow when the tab/container is shown/resized
				minimap: { enabled: false },
				scrollBeyondLastLine: false,
				fontSize: 14,
				tabSize: 4,
				lineNumbers: "on",
				renderWhitespace: "none",
			});

			// Monaco -> textarea: mirror edits into #code and fire the input event so
			// the existing reset logic (resetHints / resetLearn) runs exactly as before.
			editor.onDidChangeModelContent(function () {
				syncing = true;
				textarea.value = editor.getValue();
				textarea.dispatchEvent(new Event("input", { bubbles: true }));
				syncing = false;
			});

			// textarea -> Monaco: if #code is ever set programmatically, reflect it.
			// Skip the echo from our own dispatch above (guarded by `syncing`).
			textarea.addEventListener("input", function () {
				if (!syncing && textarea.value !== editor.getValue()) {
					editor.setValue(textarea.value);
				}
			});

			workspace.classList.add("monaco-ready"); // CSS hides textarea, shows Monaco
		},
		function () {
			// require() error callback — leave the textarea fallback in place.
			console.warn("Monaco failed to load; using the plain textarea editor.");
		},
	);
})();
