// OmniLLM Hub Client Application

(function () {
  // Global State
  const state = {
    sessionId: null,
    messages: [],
    models: [],
    selectedModel: "gemini",
    webSearchEnabled: false,
    attachedImages: [], // Array of base64 data URLs
    temperature: 0.7,
    systemPrompt: "",
    apiKeys: {},
    isStreaming: false,
    abortController: null,
  };

  // DOM Elements
  const DOM = {
    chatInput: document.getElementById("chat-input"),
    sendBtn: document.getElementById("send-message-btn"),
    messagesContainer: document.getElementById("messages-container"),
    messagesList: document.getElementById("messages-list"),
    welcomeHero: document.getElementById("welcome-hero"),
    imagePreviewsContainer: document.getElementById("image-previews-container"),
    imageUploadInput: document.getElementById("image-upload-input"),
    headerSearchToggle: document.getElementById("header-web-search-toggle"),
    inputSearchBtn: document.getElementById("input-web-search-btn"),
    searchStatusText: document.getElementById("search-status-text"),
    modelSelectBtn: document.getElementById("model-select-btn"),
    modelMenu: document.getElementById("model-menu"),
    modelsListItems: document.getElementById("models-list-items"),
    selectedModelName: document.getElementById("selected-model-name"),
    selectedModelBadge: document.getElementById("selected-model-badge"),
    selectedModelIcon: document.getElementById("selected-model-icon"),
    streamingStatusBar: document.getElementById("streaming-status-bar"),
    streamingStatusText: document.getElementById("streaming-status-text"),
    stopBtn: document.getElementById("stop-generation-btn"),
    newChatBtn: document.getElementById("new-chat-btn"),
    sessionsList: document.getElementById("sessions-list"),
    clearAllSessionsBtn: document.getElementById("clear-all-sessions-btn"),
    openSettingsBtn: document.getElementById("open-settings-btn"),
    closeSettingsBtn: document.getElementById("close-settings-btn"),
    settingsModal: document.getElementById("settings-modal"),
    saveSettingsBtn: document.getElementById("save-settings-btn"),
    tempSlider: document.getElementById("temp-slider"),
    tempValDisplay: document.getElementById("temp-val-display"),
    systemPromptInput: document.getElementById("system-prompt-input"),
    toggleSidebarBtn: document.getElementById("toggle-sidebar-btn"),
    closeSidebarBtn: document.getElementById("close-sidebar-btn"),
    sidebar: document.getElementById("sidebar"),
    sidebarOverlay: document.getElementById("sidebar-overlay"),
    exportChatBtn: document.getElementById("export-chat-btn"),
    voiceRecordBtn: document.getElementById("voice-record-btn"),
    voiceBtnText: document.getElementById("voice-btn-text"),
    imageGenBtn: document.getElementById("image-gen-btn"),
  };

  // Initialize
  async function init() {
    loadSettingsFromStorage();
    ArtifactsManager.init();
    setupEventListeners();
    await fetchModels();
    const sessions = await fetchSessions();
    if (sessions && sessions.length > 0) {
      await loadSession(sessions[0].id);
    } else {
      startNewChat();
    }
    lucide.createIcons();
  }

  // Load Settings from LocalStorage
  function loadSettingsFromStorage() {
    const savedKeys = localStorage.getItem("omni_api_keys");
    if (savedKeys) {
      try {
        state.apiKeys = JSON.parse(savedKeys);
      } catch (e) {
        console.error("Failed to parse saved keys", e);
      }
    }

    const savedModel = localStorage.getItem("omni_selected_model");
    if (savedModel) {
      const deprecatedModels = [
        "gemini-3-flash-preview", "gemini-3.5-flash", "gemini-flash-latest", "gemini-3.6-flash",
        "z-ai/glm-5.2:free", "qwen/qwen-2.5-vl-72b-instruct:free", "qwen/qwen3.8-27b:free",
        "meta-llama/llama-3.2-11b-vision-instruct:free", "openrouter/auto",
        "ollama/llama3.2-vision", "ollama/llama3.2"
      ];
      if (deprecatedModels.includes(savedModel)) {
        state.selectedModel = "gemini";
        localStorage.setItem("omni_selected_model", "gemini");
      } else {
        state.selectedModel = savedModel;
      }
    } else {
      state.selectedModel = "gemini";
    }

    const savedTemp = localStorage.getItem("omni_temperature");
    if (savedTemp) {
      state.temperature = parseFloat(savedTemp) || 0.7;
      if (DOM.tempSlider) DOM.tempSlider.value = state.temperature;
      if (DOM.tempValDisplay) DOM.tempValDisplay.textContent = state.temperature;
    }

    const savedPrompt = localStorage.getItem("omni_system_prompt");
    if (savedPrompt) {
      state.systemPrompt = savedPrompt;
      if (DOM.systemPromptInput) DOM.systemPromptInput.value = state.systemPrompt;
    }

    // Populate modal inputs
    ["gemini", "deepseek", "openai", "claude", "openrouter", "grok", "glm", "pollinations", "tavily", "puter", "atria", "codecraft", "agnes"].forEach((p) => {
      const input = document.getElementById(`key-${p}`);
      if (input && state.apiKeys[p]) {
        input.value = state.apiKeys[p];
      }
    });
  }

  // Save Settings
  function saveSettings() {
    const providers = ["gemini", "deepseek", "openai", "claude", "openrouter", "grok", "glm", "pollinations", "tavily", "puter", "atria", "codecraft", "agnes"];
    providers.forEach((p) => {
      const input = document.getElementById(`key-${p}`);
      if (input) {
        state.apiKeys[p] = input.value.trim();
      }
    });

    state.temperature = parseFloat(DOM.tempSlider.value) || 0.7;
    state.systemPrompt = DOM.systemPromptInput.value.trim();

    localStorage.setItem("omni_api_keys", JSON.stringify(state.apiKeys));
    localStorage.setItem("omni_temperature", state.temperature.toString());
    localStorage.setItem("omni_system_prompt", state.systemPrompt);

    renderModelList();
    DOM.settingsModal.classList.add("hidden");
    alert("تنظیمات با موفقیت ذخیره شد!");
  }

  // Event Listeners
  function setupEventListeners() {
    // Chat Input Auto-Resize & Keys
    DOM.chatInput.addEventListener("input", autoResizeTextarea);
    DOM.chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    DOM.sendBtn.addEventListener("click", sendMessage);
    DOM.stopBtn.addEventListener("click", stopGeneration);
    DOM.newChatBtn.addEventListener("click", startNewChat);

    // Web Search Toggles
    DOM.headerSearchToggle.addEventListener("click", toggleWebSearch);
    DOM.inputSearchBtn.addEventListener("click", toggleWebSearch);

    // Model Selector Dropdown
    DOM.modelSelectBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      DOM.modelMenu.classList.toggle("hidden");
    });
    DOM.modelMenu.addEventListener("click", (e) => {
      e.stopPropagation();
    });
    document.addEventListener("click", () => DOM.modelMenu.classList.add("hidden"));

    // Quick Prompts
    document.querySelectorAll(".quick-prompt").forEach((card) => {
      card.addEventListener("click", () => {
        const prompt = card.getAttribute("data-prompt");
        DOM.chatInput.value = prompt + " ";
        DOM.chatInput.focus();
        autoResizeTextarea();
      });
    });

    // Image Upload & Paste
    DOM.imageUploadInput.addEventListener("change", handleImageUpload);
    window.addEventListener("paste", handlePaste);
    window.addEventListener("dragover", (e) => e.preventDefault());
    window.addEventListener("drop", handleDrop);

    // Settings Modal
    DOM.openSettingsBtn.addEventListener("click", () => DOM.settingsModal.classList.remove("hidden"));
    DOM.closeSettingsBtn.addEventListener("click", () => DOM.settingsModal.classList.add("hidden"));
    DOM.saveSettingsBtn.addEventListener("click", saveSettings);
    DOM.tempSlider.addEventListener("input", (e) => (DOM.tempValDisplay.textContent = e.target.value));

    // Clear Sessions
    DOM.clearAllSessionsBtn.addEventListener("click", clearAllSessions);

    // Sidebar Mobile Toggle
    DOM.toggleSidebarBtn.addEventListener("click", () => {
      DOM.sidebar.classList.remove("translate-x-full");
      DOM.sidebarOverlay.classList.remove("hidden");
    });
    const closeSidebar = () => {
      DOM.sidebar.classList.add("translate-x-full");
      DOM.sidebarOverlay.classList.add("hidden");
    };
    DOM.closeSidebarBtn.addEventListener("click", closeSidebar);
    DOM.sidebarOverlay.addEventListener("click", closeSidebar);

    // Export Chat
    DOM.exportChatBtn.addEventListener("click", exportCurrentChat);

    // Voice & Image Generation Features
    setupVoiceRecognition();
    setupImageGenButton();

    // Image Lightbox Modal Listeners
    const lightboxModal = document.getElementById("image-lightbox-modal");
    const closeLightboxBtn = document.getElementById("close-lightbox-btn");
    if (closeLightboxBtn && lightboxModal) {
      closeLightboxBtn.addEventListener("click", () => lightboxModal.classList.add("hidden"));
      lightboxModal.addEventListener("click", (e) => {
        if (e.target === lightboxModal) lightboxModal.classList.add("hidden");
      });
      document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") lightboxModal.classList.add("hidden");
      });
    }
  }

  // Auto-resize input textarea
  function autoResizeTextarea() {
    DOM.chatInput.style.height = "auto";
    DOM.chatInput.style.height = Math.min(DOM.chatInput.scrollHeight, 192) + "px";
  }

  // Toggle Web Search
  function toggleWebSearch() {
    state.webSearchEnabled = !state.webSearchEnabled;
    const isSearch = state.webSearchEnabled;

    if (isSearch) {
      DOM.headerSearchToggle.classList.add("border-blue-500", "bg-blue-500/10", "text-blue-300");
      DOM.headerSearchToggle.classList.remove("border-slate-700", "bg-slate-800/60", "text-slate-400");
      DOM.searchStatusText.textContent = "روشن";
      DOM.searchStatusText.classList.add("text-blue-400");
      DOM.searchStatusText.classList.remove("text-slate-400");

      DOM.inputSearchBtn.classList.add("border-blue-500", "bg-blue-500/10", "text-blue-300");
      DOM.inputSearchBtn.classList.remove("border-slate-700/60", "text-slate-400");
    } else {
      DOM.headerSearchToggle.classList.remove("border-blue-500", "bg-blue-500/10", "text-blue-300");
      DOM.headerSearchToggle.classList.add("border-slate-700", "bg-slate-800/60", "text-slate-400");
      DOM.searchStatusText.textContent = "خاموش";
      DOM.searchStatusText.classList.remove("text-blue-400");
      DOM.searchStatusText.classList.add("text-slate-400");

      DOM.inputSearchBtn.classList.remove("border-blue-500", "bg-blue-500/10", "text-blue-300");
      DOM.inputSearchBtn.classList.add("border-slate-700/60", "text-slate-400");
    }
  }

  // Fetch Available Models
  async function fetchModels() {
    try {
      const res = await fetch("/api/models");
      const data = await res.json();
      state.models = data.models || [];
      renderModelList();
      const current = state.models.find((m) => m.id === state.selectedModel) || state.models[0];
      if (current) selectModel(current);
    } catch (e) {
      console.error("Failed to fetch models", e);
    }
  }

  // Render Model Dropdown Items
  function renderModelList() {
    DOM.modelsListItems.innerHTML = "";
    state.models.forEach((m) => {
      const item = document.createElement("button");
      item.setAttribute("type", "button");
      item.setAttribute("data-model-id", m.id);
      item.className =
        "w-full text-right p-2.5 rounded-xl hover:bg-slate-700/60 flex items-start gap-3 transition text-xs text-slate-200 border border-transparent hover:border-slate-600";
      if (m.id === state.selectedModel) {
        item.classList.add("bg-slate-700/50", "border-teal-500/40");
      }

      // Check if key is configured for this provider
      const hasKey = Boolean(state.apiKeys[m.provider]);
      const keyBadge = hasKey
        ? `<span class="text-[9px] bg-emerald-500/20 text-emerald-300 px-1 py-0.5 rounded border border-emerald-500/30">کلید فعال</span>`
        : m.supports_vision
        ? `<span class="text-[9px] bg-amber-500/15 text-amber-300 px-1 py-0.5 rounded border border-amber-500/30">نیازمند کلید</span>`
        : `<span class="text-[9px] bg-slate-800 text-slate-400 px-1 py-0.5 rounded border border-slate-700">عمومی</span>`;

      item.innerHTML = `
        <div class="p-1.5 rounded-lg bg-surface-900 text-teal-400 mt-0.5 shrink-0">
          <i data-lucide="${m.icon || 'bot'}" class="w-4 h-4"></i>
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center justify-between gap-1">
            <span class="font-bold text-white truncate">${m.name}</span>
            <div class="flex items-center gap-1 shrink-0">
              ${keyBadge}
              <span class="text-[10px] bg-slate-900 px-1.5 py-0.5 rounded text-slate-400 border border-slate-700">${m.badge || m.provider}</span>
            </div>
          </div>
          <p class="text-[11px] text-slate-400 line-clamp-1 mt-0.5">${m.description}</p>
        </div>
      `;

      item.addEventListener("click", (e) => {
        e.stopPropagation();
        selectModel(m);
        DOM.modelMenu.classList.add("hidden");
      });

      DOM.modelsListItems.appendChild(item);
    });
    lucide.createIcons();
  }

  // Update selection styling without destroying DOM
  function updateModelListSelection() {
    if (!DOM.modelsListItems) return;
    const items = DOM.modelsListItems.querySelectorAll("button[data-model-id]");
    items.forEach((btn) => {
      const mid = btn.getAttribute("data-model-id");
      if (mid === state.selectedModel) {
        btn.classList.add("bg-slate-700/50", "border-teal-500/40");
      } else {
        btn.classList.remove("bg-slate-700/50", "border-teal-500/40");
      }
    });
  }

  // Select Model
  function selectModel(model) {
    if (!model) return;
    state.selectedModel = model.id;
    localStorage.setItem("omni_selected_model", model.id);
    DOM.selectedModelName.textContent = model.name;
    DOM.selectedModelBadge.textContent = model.badge || model.category;
    DOM.selectedModelIcon.innerHTML = `<i data-lucide="${model.icon || 'bot'}" class="w-4 h-4"></i>`;
    updateModelListSelection();
    lucide.createIcons();
  }

  // Handle Image Upload
  async function handleImageUpload(e) {
    const files = Array.from(e.target.files);
    if (!files.length) return;
    await processImageFiles(files);
    DOM.imageUploadInput.value = "";
  }

  // Handle Paste
  async function handlePaste(e) {
    const items = (e.clipboardData || e.originalEvent.clipboardData).items;
    const imageFiles = [];
    for (let item of items) {
      if (item.kind === "file" && item.type.startsWith("image/")) {
        imageFiles.push(item.getAsFile());
      }
    }
    if (imageFiles.length) {
      e.preventDefault();
      await processImageFiles(imageFiles);
    }
  }

  // Handle Drag & Drop
  async function handleDrop(e) {
    e.preventDefault();
    if (e.dataTransfer && e.dataTransfer.files) {
      const imageFiles = Array.from(e.dataTransfer.files).filter((f) => f.type.startsWith("image/"));
      if (imageFiles.length) {
        await processImageFiles(imageFiles);
      }
    }
  }

  // Process and upload image files
  async function processImageFiles(files) {
    for (let file of files) {
      const formData = new FormData();
      formData.append("file", file);

      try {
        const res = await fetch("/api/upload", { method: "POST", body: formData });
        const data = await res.json();
        if (data.data_url) {
          state.attachedImages.push(data.data_url);
        }
      } catch (err) {
        console.error("Upload error", err);
      }
    }
    renderImagePreviews();
  }

  // Render Image Thumbnails Preview
  function renderImagePreviews() {
    if (!state.attachedImages.length) {
      DOM.imagePreviewsContainer.classList.add("hidden");
      DOM.imagePreviewsContainer.innerHTML = "";
      return;
    }

    DOM.imagePreviewsContainer.classList.remove("hidden");
    DOM.imagePreviewsContainer.innerHTML = "";

    state.attachedImages.forEach((imgUrl, index) => {
      const thumb = document.createElement("div");
      thumb.className = "relative group w-14 h-14 rounded-lg overflow-hidden border border-slate-700 shrink-0";
      thumb.innerHTML = `
        <img src="${imgUrl}" class="w-full h-full object-cover" />
        <button class="absolute top-0.5 right-0.5 bg-black/70 hover:bg-rose-600 text-white rounded-full p-0.5 transition" title="حذف تصویر">
          <i data-lucide="x" class="w-3 h-3"></i>
        </button>
      `;

      thumb.querySelector("button").addEventListener("click", (e) => {
        e.stopPropagation();
        state.attachedImages.splice(index, 1);
        renderImagePreviews();
      });

      DOM.imagePreviewsContainer.appendChild(thumb);
    });
    lucide.createIcons();
  }

  // Start New Chat
  function startNewChat() {
    stopGeneration();
    state.sessionId = "session_" + Date.now();
    state.messages = [];
    state.attachedImages = [];
    renderImagePreviews();
    DOM.messagesList.innerHTML = "";
    DOM.welcomeHero.classList.remove("hidden");
    DOM.chatInput.value = "";
    autoResizeTextarea();
  }

  // Send Message
  async function sendMessage() {
    const text = DOM.chatInput.value.trim();
    if (!text && !state.attachedImages.length) return;
    if (state.isStreaming) return;

    DOM.welcomeHero.classList.add("hidden");

    // Add User Message
    const userMessage = {
      role: "user",
      content: text || (state.attachedImages.length ? "لطفاً این تصویر را تحلیل کن" : ""),
      images: [...state.attachedImages],
      timestamp: Date.now(),
    };
    state.messages.push(userMessage);
    renderMessageItem(userMessage);

    // Reset input
    DOM.chatInput.value = "";
    state.attachedImages = [];
    renderImagePreviews();
    autoResizeTextarea();

    // Prepare Assistant Message Placeholder
    const trimmedLower = text.trim().toLowerCase();
    const isImageReq = ["/image", "/img", "/gemini_image", "تصویر بساز", "عکس بساز", "یک عکس از", "یک تصویر از"].some((k) =>
      trimmedLower.startsWith(k)
    );
    const assistantMessage = {
      role: "assistant",
      content: "",
      thinking: "",
      sources: [],
      model: state.selectedModel,
      timestamp: Date.now(),
      imageGenerating: isImageReq,
      imageStatusText: isImageReq ? "🎨 در حال آغاز تصویرسازی با هوش مصنوعی..." : "",
    };
    state.messages.push(assistantMessage);
    const assistantNode = renderMessageItem(assistantMessage);

    // Start Streaming
    state.isStreaming = true;
    DOM.sendBtn.disabled = true;
    DOM.streamingStatusBar.classList.remove("hidden");
    DOM.streamingStatusText.textContent = "در حال اتصال به هوش مصنوعی...";
    state.abortController = new AbortController();

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: state.abortController.signal,
        body: JSON.stringify({
          session_id: state.sessionId,
          model: state.selectedModel,
          messages: formatMessagesForApi(state.messages.slice(0, -1)),
          temperature: state.temperature,
          enable_web_search: state.webSearchEnabled,
          images: userMessage.images,
          api_keys: state.apiKeys,
          system_prompt: state.systemPrompt || undefined,
        }),
      });

      if (!response.ok) {
        throw new Error(`خطای ارتباط با سرور: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop(); // keep partial line in buffer

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith("data:")) continue;

          const dataStr = trimmed.substring(5).trim();
          if (dataStr === "[DONE]") {
            break;
          }

          try {
            const chunk = JSON.parse(dataStr);
            handleStreamChunk(chunk, assistantMessage, assistantNode);
          } catch (e) {
            console.error("Error parsing stream chunk:", dataStr, e);
          }
        }
      }
    } catch (err) {
      if (err.name === "AbortError") {
        console.log("Stream stopped by user.");
      } else {
        assistantMessage.content += `\n\n> ⚠️ **خطا در دریافت پاسخ:** ${err.message}`;
        updateAssistantDom(assistantNode, assistantMessage);
      }
    } finally {
      state.isStreaming = false;
      DOM.sendBtn.disabled = false;
      DOM.streamingStatusBar.classList.add("hidden");
      state.abortController = null;
      lucide.createIcons();

      // Save Session
      await saveCurrentSession();
      await fetchSessions();
    }
  }

  // Format Messages for API Request
  function formatMessagesForApi(messages) {
    return messages.map((m) => {
      const msg = {
        role: m.role,
        content: m.content,
      };
      if (m.images && m.images.length) {
        msg.images = m.images;
      }
      return msg;
    });
  }

  // Handle SSE chunk from server
  function handleStreamChunk(chunk, msgObj, domNode) {
    if (chunk.type === "status") {
      DOM.streamingStatusText.textContent = chunk.message;
      if (msgObj.imageGenerating || chunk.message.includes("در حال تصویرسازی") || chunk.message.includes("تولید تصویر") || chunk.message.includes("تولید عکس")) {
        msgObj.imageGenerating = true;
        msgObj.imageStatusText = chunk.message;
        updateAssistantDom(domNode, msgObj);
      }
    } else if (chunk.type === "sources") {
      msgObj.sources = chunk.sources;
      updateAssistantDom(domNode, msgObj);
    } else if (chunk.type === "thinking") {
      msgObj.thinking = (msgObj.thinking || "") + chunk.content;
      updateAssistantDom(domNode, msgObj);
    } else if (chunk.type === "content") {
      msgObj.content += chunk.content;
      updateAssistantDom(domNode, msgObj);
    } else if (chunk.type === "error") {
      msgObj.content += `\n\n> ⚠️ **خطا:** ${chunk.message}`;
      updateAssistantDom(domNode, msgObj);
    }

    scrollToBottom();
  }

  // Stop Generation
  function stopGeneration() {
    if (state.abortController) {
      state.abortController.abort();
    }
    state.isStreaming = false;
    DOM.sendBtn.disabled = false;
    DOM.streamingStatusBar.classList.add("hidden");
  }

  // Render a Single Message Item
  function renderMessageItem(msg) {
    const isUser = msg.role === "user";
    const container = document.createElement("div");
    container.className = `flex gap-3 sm:gap-4 ${isUser ? "flex-row-reverse" : "flex-row"} group`;

    // Avatar
    const avatar = document.createElement("div");
    avatar.className = `w-8 h-8 rounded-xl shrink-0 flex items-center justify-center text-xs font-bold shadow-md ${
      isUser
        ? "bg-gradient-to-tr from-slate-700 to-slate-600 text-white"
        : "bg-gradient-to-tr from-teal-500 to-indigo-600 text-white"
    }`;
    avatar.innerHTML = isUser
      ? `<i data-lucide="user" class="w-4 h-4"></i>`
      : `<i data-lucide="bot" class="w-4 h-4"></i>`;

    // Message Bubble Content
    const bubbleWrapper = document.createElement("div");
    bubbleWrapper.className = `max-w-[85%] sm:max-w-[78%] space-y-2 ${isUser ? "text-right" : "text-right"}`;

    if (isUser) {
      // User Bubble
      const bubble = document.createElement("div");
      bubble.className = "bg-teal-600/20 border border-teal-500/30 text-slate-100 px-4 py-3 rounded-2xl inline-block leading-relaxed text-sm";
      
      // Render attached images in user message if any
      if (msg.images && msg.images.length) {
        const imgGallery = document.createElement("div");
        imgGallery.className = "flex flex-wrap gap-2 mb-2 justify-end";
        msg.images.forEach((imgUrl) => {
          const imgEl = document.createElement("img");
          imgEl.src = imgUrl;
          imgEl.className = "max-w-[200px] max-h-[160px] rounded-lg border border-slate-700 object-cover shadow";
          imgGallery.appendChild(imgEl);
        });
        bubble.appendChild(imgGallery);
      }

      const textSpan = document.createElement("div");
      textSpan.className = "whitespace-pre-wrap";
      textSpan.textContent = msg.content;
      bubble.appendChild(textSpan);
      bubbleWrapper.appendChild(bubble);
    } else {
      // Assistant Bubble Container
      bubbleWrapper.innerHTML = `
        <div class="assistant-sources-container"></div>
        <div class="assistant-thinking-container"></div>
        <div class="assistant-content-container markdown-body text-sm leading-relaxed text-slate-200"></div>
        <div class="assistant-actions-container flex items-center gap-2 mt-2 pt-1.5 border-t border-slate-800/40 text-xs"></div>
      `;
    }

    container.appendChild(avatar);
    container.appendChild(bubbleWrapper);
    DOM.messagesList.appendChild(container);

    if (!isUser) {
      updateAssistantDom(bubbleWrapper, msg);
    }

    lucide.createIcons();
    scrollToBottom();
    return bubbleWrapper;
  }

  // Update Assistant DOM with markdown, thinking, sources
  function updateAssistantDom(bubbleWrapper, msg) {
    if (!bubbleWrapper) return;

    const sourcesContainer = bubbleWrapper.querySelector(".assistant-sources-container");
    const thinkingContainer = bubbleWrapper.querySelector(".assistant-thinking-container");
    const contentContainer = bubbleWrapper.querySelector(".assistant-content-container");

    // 1. Sources / Web Grounding Cards
    if (sourcesContainer) {
      if (msg.sources && msg.sources.length) {
        sourcesContainer.innerHTML = `
          <div class="sources-card">
            <div class="flex items-center gap-1.5 text-xs text-blue-400 font-semibold mb-2">
              <i data-lucide="globe" class="w-3.5 h-3.5"></i>
              <span>منابع وب‌سرچ زنده (${msg.sources.length} منبع):</span>
            </div>
            <div class="flex flex-wrap gap-1.5">
              ${msg.sources
                .map(
                  (s, idx) => `
                <a href="${s.url}" target="_blank" rel="noopener noreferrer" class="source-pill" title="${s.snippet}">
                  <span class="w-3.5 h-3.5 rounded bg-blue-500/20 text-blue-300 flex items-center justify-center text-[10px] font-bold">${idx + 1}</span>
                  <span class="truncate max-w-[140px]">${s.title}</span>
                </a>
              `
                )
                .join("")}
            </div>
          </div>
        `;
      } else {
        sourcesContainer.innerHTML = "";
      }
    }

    // 2. Reasoning / Thinking Box
    if (thinkingContainer) {
      if (msg.thinking) {
        thinkingContainer.innerHTML = `
          <details class="thinking-box" open>
            <summary>
              <i data-lucide="brain" class="w-4 h-4 text-indigo-400 pulse-icon"></i>
              <span>فرآیند استدلال و تفکر عمیق (Thinking Process)</span>
            </summary>
            <div class="thinking-content">${escapeHtml(msg.thinking)}</div>
          </details>
        `;
      } else {
        thinkingContainer.innerHTML = "";
      }
    }

    // 3. Markdown & Math Content
    if (contentContainer) {
      if (!msg.content && !msg.thinking) {
        if (msg.imageGenerating) {
          contentContainer.innerHTML = `
            <div class="image-gen-box max-w-sm sm:max-w-md my-2">
              <div class="w-12 h-12 rounded-2xl bg-gradient-to-tr from-fuchsia-500 to-indigo-600 flex items-center justify-center text-white mb-3 shadow-xl shadow-fuchsia-500/30 animate-pulse">
                <i data-lucide="sparkles" class="w-6 h-6"></i>
              </div>
              <div class="text-xs sm:text-sm font-semibold text-slate-100 mb-1 text-center">
                ${escapeHtml(msg.imageStatusText || "🎨 در حال تصویرسازی با هوش مصنوعی...")}
              </div>
              <p class="text-[11px] text-slate-400 text-center mb-3 max-w-xs">
                تنظیم زاویه دید، نورپردازی سینمایی و رندر با کیفیت ۱۰۲۴x۱۰۲۴...
              </p>
              <div class="w-48 h-1.5 bg-slate-700/60 rounded-full overflow-hidden">
                <div class="h-full bg-gradient-to-r from-fuchsia-500 via-indigo-500 to-teal-400 rounded-full animate-pulse w-full"></div>
              </div>
            </div>
          `;
          lucide.createIcons();
        } else {
          contentContainer.innerHTML = `
            <div class="flex items-center gap-2 text-slate-400 text-xs py-2">
              <span class="animate-spin"><i data-lucide="loader-2" class="w-4 h-4"></i></span>
              <span>در حال اندیشیدن و نگارش پاسخ...</span>
            </div>
          `;
        }
      } else {
        const rawHtml = marked.parse(msg.content || "");
        contentContainer.innerHTML = DOMPurify.sanitize(rawHtml);

        // Render Math Equations with KaTeX
        if (window.renderMathInElement) {
          renderMathInElement(contentContainer, {
            delimiters: [
              { left: "$$", right: "$$", display: true },
              { left: "$", right: "$", display: false },
              { left: "\\(", right: "\\)", display: false },
              { left: "\\[", right: "\\]", display: true },
            ],
            throwOnError: false,
          });
        }

        // Post-process Code Blocks: add headers, copy button, live preview button
        enhanceCodeBlocks(contentContainer);

        // Post-process Images: wrap in interactive card with Lightbox & Download
        enhanceImageCards(contentContainer);
      }
    }

    // 4. Action Toolbar (Voice Readout + Copy Message)
    const actionsContainer = bubbleWrapper.querySelector(".assistant-actions-container");
    if (actionsContainer) {
      if (msg.content && msg.content.trim()) {
        const hasImage = msg.content.includes("![") || msg.content.includes("### 🎨");
        actionsContainer.innerHTML = `
          <button class="speak-gemini-btn flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-purple-500/40 bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 transition text-[11px]" title="تولید صدای فوق‌العاده طبیعی با هوش مصنوعی گوگل جمینای">
            <i data-lucide="sparkles" class="w-3.5 h-3.5 text-purple-400"></i>
            <span>ویس جمینای</span>
          </button>
          <button class="speak-message-btn flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-slate-700/60 bg-slate-800/40 hover:bg-slate-700/60 text-slate-400 hover:text-teal-300 transition text-[11px]" title="شنیدن صوتی پاسخ با موتور مرورگر">
            <i data-lucide="volume-2" class="w-3.5 h-3.5"></i>
            <span>صدای مرورگر</span>
          </button>
          ${
            hasImage
              ? `<button class="edit-image-btn flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-teal-500/40 bg-teal-500/10 hover:bg-teal-500/20 text-teal-300 transition text-[11px]" title="اعمال تغییرات روی این تصویر در ادامه گفتگو">
                  <i data-lucide="paintbrush" class="w-3.5 h-3.5 text-teal-400"></i>
                  <span>تغییر این تصویر</span>
                </button>`
              : ""
          }
          <button class="copy-message-btn flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-slate-700/60 bg-slate-800/40 hover:bg-slate-700/60 text-slate-400 hover:text-white transition text-[11px]" title="کپی متن کامل پاسخ">
            <i data-lucide="copy" class="w-3.5 h-3.5"></i>
            <span>کپی پاسخ</span>
          </button>
        `;

        const geminiSpeakBtn = actionsContainer.querySelector(".speak-gemini-btn");
        if (geminiSpeakBtn) {
          geminiSpeakBtn.addEventListener("click", () => playGeminiTTS(msg.content, geminiSpeakBtn));
        }

        const speakBtn = actionsContainer.querySelector(".speak-message-btn");
        if (speakBtn) {
          speakBtn.addEventListener("click", () => toggleSpeech(msg.content, speakBtn));
        }

        const editImgBtn = actionsContainer.querySelector(".edit-image-btn");
        if (editImgBtn) {
          editImgBtn.addEventListener("click", () => {
            DOM.chatInput.value = "تغییر بده: ";
            DOM.chatInput.focus();
            DOM.chatInput.setSelectionRange(DOM.chatInput.value.length, DOM.chatInput.value.length);
            autoResizeTextarea();
          });
        }

        const copyBtn = actionsContainer.querySelector(".copy-message-btn");
        if (copyBtn) {
          copyBtn.addEventListener("click", () => {
            navigator.clipboard.writeText(msg.content);
            const span = copyBtn.querySelector("span");
            span.textContent = "کپی شد!";
            setTimeout(() => (span.textContent = "کپی پاسخ"), 2000);
          });
        }
      } else {
        actionsContainer.innerHTML = "";
      }
    }
  }

  // Enhance Code Blocks with Preview and Copy
  function enhanceCodeBlocks(container) {
    const preTags = container.querySelectorAll("pre");
    preTags.forEach((pre) => {
      if (pre.parentElement.classList.contains("code-block-container")) return;

      const codeTag = pre.querySelector("code");
      if (!codeTag) return;

      const langMatch = codeTag.className.match(/language-(\w+)/);
      const language = langMatch ? langMatch[1].toLowerCase() : "text";

      // Highlight with highlight.js
      hljs.highlightElement(codeTag);

      // Wrapper
      const wrapper = document.createElement("div");
      wrapper.className = "code-block-container";

      // Header
      const header = document.createElement("div");
      header.className = "code-block-header";
      
      const isWebSnippet = ["html", "javascript", "js", "svg"].includes(language);

      header.innerHTML = `
        <span class="font-bold text-slate-300 uppercase">${language}</span>
        <div class="flex items-center gap-2">
          ${
            isWebSnippet
              ? `<button class="preview-artifact-btn text-indigo-400 hover:text-indigo-300 text-xs flex items-center gap-1 bg-indigo-500/10 hover:bg-indigo-500/20 px-2 py-0.5 rounded border border-indigo-500/30 transition">
                  <i data-lucide="play" class="w-3 h-3"></i>
                  <span>پیش‌نمایش زنده</span>
                </button>`
              : ""
          }
          <button class="copy-code-btn text-slate-400 hover:text-white text-xs flex items-center gap-1 transition">
            <i data-lucide="copy" class="w-3 h-3"></i>
            <span>کپی</span>
          </button>
        </div>
      `;

      // Copy Code Action
      header.querySelector(".copy-code-btn").addEventListener("click", () => {
        navigator.clipboard.writeText(codeTag.textContent);
        const btnText = header.querySelector(".copy-code-btn span");
        btnText.textContent = "کپی شد!";
        setTimeout(() => (btnText.textContent = "کپی"), 2000);
      });

      // Preview Artifact Action
      const previewBtn = header.querySelector(".preview-artifact-btn");
      if (previewBtn) {
        previewBtn.addEventListener("click", () => {
          ArtifactsManager.openWithCode(codeTag.textContent, language);
        });
      }

      pre.parentNode.insertBefore(wrapper, pre);
      wrapper.appendChild(header);
      wrapper.appendChild(pre);
    });
  }

  // Enhance Image Cards with Lightbox, Zoom, and Download
  function enhanceImageCards(container) {
    const imgTags = container.querySelectorAll("img");
    imgTags.forEach((img) => {
      if (img.closest(".interactive-image-card")) return;

      const alt = img.alt || "تصویر هوش مصنوعی";
      const src = img.src;

      const card = document.createElement("div");
      card.className = "interactive-image-card";

      card.innerHTML = `
        <span class="image-tag-badge flex items-center gap-1">
          <i data-lucide="sparkles" class="w-3 h-3 text-fuchsia-400"></i>
          <span>کیفیت ۱۰۲۴x۱۰۲۴</span>
        </span>
        <img src="${src}" alt="${escapeHtml(alt)}" class="image-preview-clickable" loading="lazy" />
        <div class="image-overlay-bar">
          <span class="text-xs text-slate-200 truncate max-w-[200px]" title="${escapeHtml(alt)}">${escapeHtml(alt)}</span>
          <div class="flex items-center gap-2">
            <button class="zoom-img-btn flex items-center gap-1 px-2.5 py-1 bg-slate-800/90 hover:bg-slate-700 text-white rounded-lg text-xs transition" title="بزرگنمایی و نمایش تمام‌صفحه">
              <i data-lucide="maximize-2" class="w-3 h-3"></i>
              <span>بزرگنمایی</span>
            </button>
            <a href="${src}" target="_blank" download class="flex items-center gap-1 px-2.5 py-1 bg-teal-500 hover:bg-teal-400 text-white rounded-lg text-xs transition" title="دانلود کیفیت اصلی">
              <i data-lucide="download" class="w-3 h-3"></i>
              <span>دانلود</span>
            </a>
          </div>
        </div>
      `;

      // Zoom action opens Lightbox modal
      const openModal = () => {
        const modal = document.getElementById("image-lightbox-modal");
        const modalImg = document.getElementById("lightbox-img");
        const downloadBtn = document.getElementById("lightbox-download-btn");
        if (modal && modalImg) {
          modalImg.src = src;
          if (downloadBtn) downloadBtn.href = src;
          modal.classList.remove("hidden");
          lucide.createIcons();
        }
      };

      card.querySelector(".image-preview-clickable").addEventListener("click", openModal);
      card.querySelector(".zoom-img-btn").addEventListener("click", openModal);

      img.parentNode.replaceChild(card, img);
    });
    lucide.createIcons();
  }

  // Voice Input (Speech-to-Text STT)
  let speechRecognizer = null;
  let isRecordingVoice = false;

  function setupVoiceRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      if (DOM.voiceRecordBtn) {
        DOM.voiceRecordBtn.addEventListener("click", () => {
          alert("مرورگر شما از قابلیت تبدیل صدا به متن (Speech Recognition) پشتیبانی نمی‌کند. لطفاً از Google Chrome یا Microsoft Edge استفاده نمایید.");
        });
      }
      return;
    }

    try {
      speechRecognizer = new SpeechRecognition();
      speechRecognizer.continuous = true;
      speechRecognizer.interimResults = true;
      speechRecognizer.lang = "fa-IR";

      speechRecognizer.onresult = (event) => {
        let interimTranscript = "";
        let finalTranscript = "";
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          } else {
            interimTranscript += event.results[i][0].transcript;
          }
        }

        const baseVal = DOM.chatInput.value.replace(/\[در حال شنیدن:.*?\]$/, "").trim();
        if (finalTranscript) {
          DOM.chatInput.value = (baseVal ? baseVal + " " : "") + finalTranscript.trim() + " ";
        } else if (interimTranscript) {
          DOM.chatInput.value = (baseVal ? baseVal + " " : "") + `[در حال شنیدن: ${interimTranscript.trim()}]`;
        }
        autoResizeTextarea();
      };

      speechRecognizer.onerror = (event) => {
        console.warn("Speech recognition error:", event.error);
        stopVoiceRecording();
      };

      speechRecognizer.onend = () => {
        if (isRecordingVoice) {
          stopVoiceRecording();
        }
      };

      if (DOM.voiceRecordBtn) {
        DOM.voiceRecordBtn.addEventListener("click", toggleVoiceRecording);
      }
    } catch (e) {
      console.error("Speech recognition setup failed:", e);
    }
  }

  function toggleVoiceRecording() {
    if (!speechRecognizer) {
      alert("قابلیت تشخیص گفتار در این مرورگر در دسترس نیست.");
      return;
    }
    if (isRecordingVoice) {
      stopVoiceRecording();
    } else {
      startVoiceRecording();
    }
  }

  function startVoiceRecording() {
    try {
      speechRecognizer.start();
      isRecordingVoice = true;
      if (DOM.voiceRecordBtn) {
        DOM.voiceRecordBtn.classList.add("border-rose-500", "bg-rose-500/20", "text-rose-300", "ring-2", "ring-rose-500/40");
        DOM.voiceRecordBtn.classList.remove("border-slate-700/60", "text-slate-400");
      }
      if (DOM.voiceBtnText) DOM.voiceBtnText.textContent = "در حال ضبط...";
    } catch (e) {
      console.warn("Speech start error:", e);
    }
  }

  function stopVoiceRecording() {
    isRecordingVoice = false;
    try {
      if (speechRecognizer) speechRecognizer.stop();
    } catch (e) {}
    DOM.chatInput.value = DOM.chatInput.value.replace(/\[در حال شنیدن:.*?\]$/, "").trim();
    autoResizeTextarea();
    if (DOM.voiceRecordBtn) {
      DOM.voiceRecordBtn.classList.remove("border-rose-500", "bg-rose-500/20", "text-rose-300", "ring-2", "ring-rose-500/40");
      DOM.voiceRecordBtn.classList.add("border-slate-700/60", "text-slate-400");
    }
    if (DOM.voiceBtnText) DOM.voiceBtnText.textContent = "ویس";
  }

  // Voice Output (Text-to-Speech TTS)
  let activeSpeakingBtn = null;

  function toggleSpeech(text, btnElement) {
    if (!("speechSynthesis" in window)) {
      alert("مرورگر شما از قابلیت خواندن صوتی (Text-to-Speech) پشتیبانی نمی‌کند.");
      return;
    }

    if (window.speechSynthesis.speaking && activeSpeakingBtn === btnElement) {
      window.speechSynthesis.cancel();
      resetSpeakingButton(btnElement);
      activeSpeakingBtn = null;
      return;
    }

    if (window.speechSynthesis.speaking) {
      window.speechSynthesis.cancel();
      if (activeSpeakingBtn) resetSpeakingButton(activeSpeakingBtn);
    }

    let cleanText = text
      .replace(/```[\s\S]*?```/g, " قطعه کد. ")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/!\[.*?\]\(.*?\)/g, "")
      .replace(/\[(.*?)\]\(.*?\)/g, "$1")
      .replace(/[#*_~>]/g, "")
      .replace(/\n+/g, " ")
      .trim();

    if (!cleanText) return;

    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    const isPersian = /[\u0600-\u06FF]/.test(cleanText);
    utterance.lang = isPersian ? "fa-IR" : "en-US";

    const voices = window.speechSynthesis.getVoices();
    const voice = voices.find((v) => isPersian ? v.lang.startsWith("fa") : v.lang.startsWith("en"));
    if (voice) utterance.voice = voice;

    utterance.onstart = () => {
      activeSpeakingBtn = btnElement;
      btnElement.classList.add("text-rose-300", "bg-rose-500/20", "border-rose-500/50");
      btnElement.innerHTML = `<i data-lucide="square" class="w-3.5 h-3.5 fill-current text-rose-400"></i><span class="text-[11px]">توقف صوت</span>`;
      lucide.createIcons();
    };

    utterance.onend = () => {
      resetSpeakingButton(btnElement);
      activeSpeakingBtn = null;
    };

    utterance.onerror = () => {
      resetSpeakingButton(btnElement);
      activeSpeakingBtn = null;
    };

    window.speechSynthesis.speak(utterance);
  }

  function resetSpeakingButton(btnElement) {
    if (!btnElement) return;
    btnElement.classList.remove("text-rose-300", "bg-rose-500/20", "border-rose-500/50");
    btnElement.innerHTML = `<i data-lucide="volume-2" class="w-3.5 h-3.5"></i><span class="text-[11px]">صدای مرورگر</span>`;
    lucide.createIcons();
  }

  // Google Gemini Native Neural TTS
  let currentGeminiAudio = null;
  let activeGeminiBtn = null;

  async function playGeminiTTS(text, btnElement) {
    // If already playing from this button, stop
    if (currentGeminiAudio && !currentGeminiAudio.paused && activeGeminiBtn === btnElement) {
      currentGeminiAudio.pause();
      currentGeminiAudio = null;
      resetGeminiBtn(btnElement);
      activeGeminiBtn = null;
      return;
    }

    if (currentGeminiAudio) {
      currentGeminiAudio.pause();
      if (activeGeminiBtn) resetGeminiBtn(activeGeminiBtn);
      currentGeminiAudio = null;
    }

    // Clean text for speech
    let cleanText = text
      .replace(/```[\s\S]*?```/g, " قطعه کد. ")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/!\[.*?\]\(.*?\)/g, "")
      .replace(/\[(.*?)\]\(.*?\)/g, "$1")
      .replace(/[#*_~>]/g, "")
      .replace(/\n+/g, " ")
      .trim();

    if (!cleanText) return;
    if (cleanText.length > 800) cleanText = cleanText.substring(0, 800) + "...";

    // Set loading state
    activeGeminiBtn = btnElement;
    btnElement.classList.add("border-purple-500", "bg-purple-500/20", "text-purple-300");
    btnElement.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin text-purple-400"></i><span class="text-[11px]">در حال ساخت ویس...</span>`;
    lucide.createIcons();

    try {
      const res = await fetch("/api/tts/gemini", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: cleanText,
          voice: "kore",
          api_key: state.apiKeys["gemini"] || undefined
        })
      });

      if (!res.ok) {
        throw new Error(`خطای سرور (${res.status})`);
      }

      const data = await res.json();
      if (!data.audio_url) {
        throw new Error("فایل صوتی یافت نشد.");
      }

      const audio = new Audio(data.audio_url);
      currentGeminiAudio = audio;

      btnElement.innerHTML = `<i data-lucide="square" class="w-3.5 h-3.5 fill-current text-purple-400"></i><span class="text-[11px]">توقف ویس جمینای</span>`;
      lucide.createIcons();

      audio.onended = () => {
        resetGeminiBtn(btnElement);
        currentGeminiAudio = null;
        activeGeminiBtn = null;
      };

      audio.onerror = () => {
        resetGeminiBtn(btnElement);
        currentGeminiAudio = null;
        activeGeminiBtn = null;
      };

      await audio.play();
    } catch (err) {
      console.error("Gemini TTS error:", err);
      alert(`خطا در تولید صدای جمینای: ${err.message}`);
      resetGeminiBtn(btnElement);
      currentGeminiAudio = null;
      activeGeminiBtn = null;
    }
  }

  function resetGeminiBtn(btnElement) {
    if (!btnElement) return;
    btnElement.classList.remove("border-purple-500", "bg-purple-500/20", "text-purple-300");
    btnElement.innerHTML = `<i data-lucide="sparkles" class="w-3.5 h-3.5 text-purple-400"></i><span class="text-[11px]">ویس جمینای</span>`;
    lucide.createIcons();
  }

  // AI Image Generation Button Action (Google Gemini Exclusively)
  function setupImageGenButton() {
    if (!DOM.imageGenBtn) return;
    DOM.imageGenBtn.addEventListener("click", () => {
      const current = DOM.chatInput.value.trim();
      if (!current) {
        DOM.chatInput.value = "/gemini_image یک منظره رویایی و خیره‌کننده با سبک هوش مصنوعی Google Gemini ";
        DOM.chatInput.focus();
        DOM.chatInput.setSelectionRange(DOM.chatInput.value.length, DOM.chatInput.value.length);
        autoResizeTextarea();
      } else if (current.startsWith("/gemini_image") || current.startsWith("/gemini_img") || current.startsWith("/image") || current.startsWith("/img")) {
        sendMessage();
      } else {
        DOM.chatInput.value = `/gemini_image ${current}`;
        sendMessage();
      }
    });
  }

  // Scroll to Bottom
  function scrollToBottom() {
    DOM.messagesContainer.scrollTop = DOM.messagesContainer.scrollHeight;
  }

  // Escape HTML
  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  // Fetch Saved Sessions
  async function fetchSessions() {
    try {
      const res = await fetch("/api/sessions");
      const data = await res.json();
      const sessions = data.sessions || [];
      renderSessionsList(sessions);
      return sessions;
    } catch (e) {
      console.error("Failed to load sessions", e);
      return [];
    }
  }

  // Render Sessions in Sidebar
  function renderSessionsList(sessions) {
    DOM.sessionsList.innerHTML = `<div class="px-3 py-1.5 text-xs font-semibold text-slate-400">تاریخچه گفتگوها</div>`;
    if (!sessions.length) {
      DOM.sessionsList.innerHTML += `<div class="px-3 py-2 text-xs text-slate-500">گفتگویی وجود ندارد.</div>`;
      return;
    }

    sessions.forEach((s) => {
      const item = document.createElement("div");
      item.className =
        "group flex items-center justify-between p-2 rounded-xl text-xs hover:bg-slate-700/50 cursor-pointer transition text-slate-300";
      if (s.id === state.sessionId) {
        item.classList.add("bg-slate-700/60", "text-white");
      }

      item.innerHTML = `
        <div class="flex items-center gap-2 truncate flex-1 min-w-0">
          <i data-lucide="message-square" class="w-3.5 h-3.5 text-teal-400 shrink-0"></i>
          <span class="truncate">${escapeHtml(s.title)}</span>
        </div>
        <button class="delete-session-btn text-slate-500 hover:text-rose-400 p-1 opacity-0 group-hover:opacity-100 transition" title="حذف">
          <i data-lucide="trash" class="w-3.5 h-3.5"></i>
        </button>
      `;

      item.addEventListener("click", () => loadSession(s.id));
      item.querySelector(".delete-session-btn").addEventListener("click", (e) => {
        e.stopPropagation();
        deleteSession(s.id);
      });

      DOM.sessionsList.appendChild(item);
    });
    lucide.createIcons();
  }

  // Load a Saved Session
  async function loadSession(sessionId) {
    try {
      const res = await fetch(`/api/sessions/${sessionId}`);
      const data = await res.json();
      if (data) {
        state.sessionId = data.id;
        state.messages = data.messages || [];
        state.selectedModel = data.model || state.selectedModel;
        
        // Update Model Selector UI
        const modelObj = state.models.find((m) => m.id === state.selectedModel);
        if (modelObj) selectModel(modelObj);

        // Render Messages
        DOM.welcomeHero.classList.add("hidden");
        DOM.messagesList.innerHTML = "";
        state.messages.forEach((m) => renderMessageItem(m));
        scrollToBottom();
      }
    } catch (e) {
      console.error("Failed to load session", e);
    }
  }

  // Save Current Session to Server
  async function saveCurrentSession() {
    if (!state.sessionId || !state.messages.length) return;
    try {
      await fetch(`/api/sessions/${state.sessionId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: state.messages,
          model: state.selectedModel,
        }),
      });
    } catch (e) {
      console.error("Failed to save session", e);
    }
  }

  // Delete a Session
  async function deleteSession(sessionId) {
    if (!confirm("آیا از حذف این گفتگو اطمینان دارید؟")) return;
    try {
      await fetch(`/api/sessions/${sessionId}`, { method: "DELETE" });
      if (state.sessionId === sessionId) {
        startNewChat();
      }
      await fetchSessions();
    } catch (e) {
      console.error("Failed to delete session", e);
    }
  }

  // Clear All Sessions
  async function clearAllSessions() {
    if (!confirm("آیا مایلید تمام گفتگوها پاک شوند؟")) return;
    startNewChat();
    await fetchSessions();
  }

  // Export Current Chat as Markdown
  function exportCurrentChat() {
    if (!state.messages.length) {
      alert("گفتگویی برای دانلود وجود ندارد.");
      return;
    }

    let md = `# گفتگو با هوش مصنوعی (مدل: ${state.selectedModel})\n\n`;
    state.messages.forEach((m) => {
      const roleName = m.role === "user" ? "👤 کاربر" : "🤖 هوش مصنوعی";
      md += `### ${roleName}\n\n`;
      if (m.thinking) {
        md += `> **فرآیند فکر:**\n> ${m.thinking.replace(/\n/g, "\n> ")}\n\n`;
      }
      md += `${m.content}\n\n---\n\n`;
    });

    const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `chat-${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(a);
  }

  // Run on DOM ready
  document.addEventListener("DOMContentLoaded", init);
})();
