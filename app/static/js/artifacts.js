// Live Sandbox & Artifacts Drawer Manager
const ArtifactsManager = {
  drawer: null,
  iframe: null,
  codeView: null,
  toggleBtn: null,
  tabPreview: null,
  tabCode: null,
  currentCode: "",
  currentLanguage: "html",

  init() {
    this.drawer = document.getElementById("artifacts-drawer");
    this.iframe = document.getElementById("artifact-sandbox-iframe");
    this.codeView = document.getElementById("artifact-code-view");
    this.toggleBtn = document.getElementById("toggle-artifacts-btn");
    this.tabPreview = document.getElementById("tab-preview");
    this.tabCode = document.getElementById("tab-code");

    document.getElementById("close-artifacts-btn")?.addEventListener("click", () => this.close());
    this.toggleBtn?.addEventListener("click", () => this.open());
    
    this.tabPreview?.addEventListener("click", () => this.switchTab("preview"));
    this.tabCode?.addEventListener("click", () => this.switchTab("code"));

    document.getElementById("copy-artifact-btn")?.addEventListener("click", () => {
      if (this.currentCode) {
        navigator.clipboard.writeText(this.currentCode);
        alert("کد با موفقیت کپی شد!");
      }
    });
  },

  openWithCode(code, language = "html") {
    this.currentCode = code;
    this.currentLanguage = language;
    this.render();
    this.open();
    if (this.toggleBtn) this.toggleBtn.classList.remove("hidden");
  },

  open() {
    if (this.drawer) {
      this.drawer.classList.remove("-translate-x-full");
    }
  },

  close() {
    if (this.drawer) {
      this.drawer.classList.add("-translate-x-full");
    }
  },

  switchTab(tab) {
    if (tab === "preview") {
      this.tabPreview.classList.add("border-indigo-500", "text-indigo-400");
      this.tabPreview.classList.remove("border-transparent", "text-slate-400");
      this.tabCode.classList.remove("border-indigo-500", "text-indigo-400");
      this.tabCode.classList.add("border-transparent", "text-slate-400");

      this.iframe.classList.remove("hidden");
      this.codeView.classList.add("hidden");
    } else {
      this.tabCode.classList.add("border-indigo-500", "text-indigo-400");
      this.tabCode.classList.remove("border-transparent", "text-slate-400");
      this.tabPreview.classList.remove("border-indigo-500", "text-indigo-400");
      this.tabPreview.classList.add("border-transparent", "text-slate-400");

      this.codeView.classList.remove("hidden");
      this.iframe.classList.add("hidden");
    }
  },

  render() {
    if (!this.iframe || !this.codeView) return;

    // Update code view
    const codeTag = this.codeView.querySelector("code");
    if (codeTag) {
      codeTag.textContent = this.currentCode;
      hljs.highlightElement(codeTag);
    }

    // Build iframe HTML
    let fullHtml = "";
    if (this.currentLanguage === "svg") {
      fullHtml = `<!DOCTYPE html><html><body style="margin:0;display:flex;justify-content:center;align-items:center;min-height:100vh;background:#f8fafc;">${this.currentCode}</body></html>`;
    } else if (this.currentLanguage === "html") {
      fullHtml = this.currentCode;
    } else if (this.currentLanguage === "javascript" || this.currentLanguage === "js") {
      fullHtml = `<!DOCTYPE html><html><head><script src="https://cdn.tailwindcss.com"></script></head><body class="p-6 font-sans"><div id="app"></div><script>${this.currentCode}<\/script></body></html>`;
    } else {
      fullHtml = `<!DOCTYPE html><html><body><pre>${this.escapeHtml(this.currentCode)}</pre></body></html>`;
    }

    this.iframe.srcdoc = fullHtml;
  },

  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }
};

window.ArtifactsManager = ArtifactsManager;
