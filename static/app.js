(() => {
  const $ = (sel) => document.querySelector(sel);

  const sidebar = $("#sidebar");
  const backdrop = $("#sidebarBackdrop");
  const btnMenu = $("#btnMenu");
  const btnNewChat = $("#btnNewChat");
  const btnMic = $("#btnMic");
  const btnSupport = $("#btnSupport");
  const composer = $("#composer");
  const input = $("#userInput");
  const btnSend = $("#btnSend");
  const btnAttach = $("#btnAttach");
  const imageInput = $("#imageInput");
  const composerPreview = $("#composerPreview");
  const composerPreviewCards = $("#composerPreviewCards");
  const composerPreviewLabel = $("#composerPreviewLabel");
  const btnRemoveImage = $("#btnRemoveImage");
  let selectedImages = [];
  const welcome = $("#welcome");
  const welcomeProducts = $("#welcomeProducts");
  const welcomePrompts = $("#welcomePrompts");
  const messagesEl = $("#messages");
  const chatStage = $("#chatStage");
  const chatList = $("#chatList");
  const chatListEmpty = $("#chatListEmpty");
  const toast = $("#toast");
  const appEl = document.querySelector(".app");

  const btnScrollBottom = $("#btnScrollBottom");
  const sidebarSearchInput = $("#sidebarSearchInput");
  const sidebarSearchClear = $("#sidebarSearchClear");
  const deleteModal = $("#deleteModal");
  const btnCancelDelete = $("#btnCancelDelete");
  const btnConfirmDelete = $("#btnConfirmDelete");
  const renameModal = $("#renameModal");
  const renameInput = $("#renameInput");
  const btnCancelRename = $("#btnCancelRename");
  const btnSaveRename = $("#btnSaveRename");
  const imageLightbox = $("#imageLightbox");
  const lightboxImg = $("#lightboxImg");
  const lightboxClose = $("#lightboxClose");
  const lightboxBackdrop = $("#lightboxBackdrop");

  let pendingDeleteChatId = null;
  let pendingRenameChatId = null;
  let lastUserPrompt = "";
  let cachedChats = [];
  const PRODUCT_IDEAS = [
    { icon: "shoe", title: "Running shoes", desc: "Everyday trainers & performance kicks", prompt: "Show me running shoes" },
    { icon: "hoodie", title: "Hoodies", desc: "Soft layers for daily wear", prompt: "Show me hoodies" },
    { icon: "watch", title: "Smart watches", desc: "Track fitness & stay connected", prompt: "Show me smart watches" },
    { icon: "bag", title: "Backpacks", desc: "Work, college & travel bags", prompt: "Show me backpacks" },
    { icon: "shirt", title: "T-shirts", desc: "Fresh fits for every mood", prompt: "Show me t-shirts" },
    { icon: "cap", title: "Caps & hats", desc: "Finish the look with headwear", prompt: "Show me caps" },
    { icon: "sock", title: "Socks", desc: "Comfort for long days", prompt: "Show me socks" },
    { icon: "short", title: "Shorts", desc: "Light & breathable bottoms", prompt: "Show me shorts" },
    { icon: "sneaker", title: "Sneakers", desc: "Casual street-ready styles", prompt: "Show me sneakers" },
    { icon: "glass", title: "Sunglasses", desc: "Shade with style", prompt: "Show me sunglasses" },
    { icon: "jeans", title: "Jeans", desc: "Classic denim picks", prompt: "Show me jeans" },
    { icon: "acc", title: "Accessories", desc: "Belts, wallets & more", prompt: "Show me accessories" },
  ];

  const PROMPT_IDEAS = [
    "Where is my order?",
    "Recommend a running shoe under ₹3000",
    "What's in my cart?",
    "Show bestselling sneakers",
    "Track my latest delivery",
    "Suggest gifts for him under ₹2000",
    "Any offers on hoodies?",
    "Help me find a formal look",
    "Compare black vs white sneakers",
    "Add something trendy to my wishlist",
    "What size should I pick for shoes?",
    "Show new arrivals this week",
  ];

  const PRODUCT_ICON_SVG = {
    shoe: '<path d="M4 14.5c1.5-.8 3.2-1.5 6-1.5h5.5c1.2 0 2.2.7 2.7 1.8L20 18H4v-3.5z"/><path d="M8 13l1.2-4.2A2 2 0 0 1 11.1 7H13"/><path d="M14 18v1.5M17 18v1.5"/>',
    hoodie: '<path d="M8.5 8.5A3.5 3.5 0 0 1 12 5a3.5 3.5 0 0 1 3.5 3.5V10"/><path d="M9 10H7l-2 10h14L17 10h-2"/><path d="M9 10v1.5a3 3 0 0 0 6 0V10"/>',
    watch: '<rect x="8" y="7" width="8" height="10" rx="2.2"/><path d="M10 3.5h4v3.5M10 17h4v3.5M12 11v2.2l1.5.8"/>',
    bag: '<path d="M6.5 9h11l-.8 11.2a1.5 1.5 0 0 1-1.5 1.3H8.8a1.5 1.5 0 0 1-1.5-1.3L6.5 9z"/><path d="M9.5 9V7.2A2.5 2.5 0 0 1 12 4.7 2.5 2.5 0 0 1 14.5 7.2V9"/><path d="M10 13h4"/>',
    shirt: '<path d="M9.2 4.5 12 6.8l2.8-2.3 3.7 2.6-2.2 2.2V19.5H7.7V9.3L5.5 7.1l3.7-2.6z"/><path d="M9.5 10.5h5"/>',
    cap: '<path d="M5 14.5a7 7 0 0 1 14 0"/><path d="M3.5 14.5h17v2.2a1 1 0 0 1-1 1h-15a1 1 0 0 1-1-1v-2.2z"/><path d="M12 7.5v2"/>',
    sock: '<path d="M10 3.5h4v8.2l1.8 1.8a3.2 3.2 0 1 1-4.5 4.5L10 16.3V3.5z"/><path d="M10 8.5h4"/>',
    short: '<path d="M6.5 7.5h11l-.7 9.5H14l-.8-3.8L12 16.2l-1.2-3L9.9 17H7.2L6.5 7.5z"/><path d="M9 7.5v2.2M15 7.5v2.2"/>',
    sneaker: '<path d="M3.5 15.2 11 13l4.2.8 5.3 2.4v2.3H3.5v-3.3z"/><path d="M7.5 14.2c1.2-.6 2.6-1 4-1"/><path d="M13.5 18.5v1M17 18.5v1"/>',
    glass: '<path d="M3 12h2.2"/><path d="M18.8 12H21"/><path d="M10.2 12h3.6"/><circle cx="7.2" cy="12" r="3.2"/><circle cx="16.8" cy="12" r="3.2"/>',
    jeans: '<path d="M8.2 3.5h7.6l1 17H13.5l-.7-7.5-.8 7.5H7.2l1-17z"/><path d="M12 3.5v5.5"/><path d="M9.2 8.5h5.6"/>',
    acc: '<rect x="4.5" y="8.5" width="15" height="10" rx="2"/><path d="M8 8.5V7a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v1.5"/><circle cx="12" cy="13.5" r="1.4"/>',
  };

  function productIconHtml(key) {
    const paths = PRODUCT_ICON_SVG[key] || PRODUCT_ICON_SVG.acc;
    return `<svg class="welcome-product-svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;
  }

  function shuffle(list) {
    const arr = list.slice();
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  }

  function pickRandom(list, count) {
    return shuffle(list).slice(0, count);
  }

  async function useSuggestion(text) {
    const next = String(text || "").trim();
    if (!next || busy) return;
    input.value = next;
    await sendMessage();
  }

  function renderWelcomeSuggestions() {
    if (!welcomeProducts || !welcomePrompts) return;

    const products = pickRandom(PRODUCT_IDEAS, 4);
    welcomeProducts.innerHTML = "";
    for (const item of products) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "welcome-product";
      btn.innerHTML = `
        <span class="welcome-product-icon">${productIconHtml(item.icon)}</span>
        <span class="welcome-product-body">
          <span class="welcome-product-title"></span>
          <span class="welcome-product-desc"></span>
        </span>
      `;
      btn.querySelector(".welcome-product-title").textContent = item.title;
      btn.querySelector(".welcome-product-desc").textContent = item.desc;
      btn.addEventListener("click", () => useSuggestion(item.prompt));
      welcomeProducts.appendChild(btn);
    }

    const prompts = pickRandom(PROMPT_IDEAS, 4);
    welcomePrompts.innerHTML = "";
    for (const text of prompts) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "welcome-prompt";
      btn.textContent = text;
      btn.addEventListener("click", () => useSuggestion(text));
      welcomePrompts.appendChild(btn);
    }
  }

  let chatId = null;
  let busy = false;
  let recognition = null;

  function getChatIdFromUrl() {
    try {
      const p = new URLSearchParams(window.location.search);
      const id = (p.get("chat_id") || "").trim();
      return id || null;
    } catch {
      return null;
    }
  }

  function setChatIdInUrl(id, { replace = true } = {}) {
    const next = (id || "").trim();
    const url = new URL(window.location.href);
    if (next) url.searchParams.set("chat_id", next);
    else url.searchParams.delete("chat_id");
    const method = replace ? "replaceState" : "pushState";
    window.history[method]({ chat_id: next || null }, "", url.pathname + url.search + url.hash);
  }

  function rememberChatId(id) {
    chatId = id || null;
    if (chatId) {
      localStorage.setItem("welfog_chat_id", chatId);
      setChatIdInUrl(chatId);
    } else {
      localStorage.removeItem("welfog_chat_id");
      setChatIdInUrl(null);
    }
  }

  // Only open a thread when URL has ?chat_id= — home `/` stays blank
  chatId = getChatIdFromUrl() || null;

  const PROVIDER_LABELS = {
    gemini: "Welfog Ai",
  };
  let provider = "gemini";
  localStorage.setItem("welfog_provider", "gemini");

  const modelSwitch = $("#modelSwitch");
  const btnModel = $("#btnModel");
  const modelLabel = $("#modelLabel");

  function setProvider(_next) {
    provider = "gemini";
    localStorage.setItem("welfog_provider", "gemini");
    if (modelLabel) modelLabel.textContent = "Welfog Ai";
  }

  setProvider("gemini");
  if (btnModel) {
    btnModel.addEventListener("click", (e) => {
      e.stopPropagation();
      // Gemini only — no model menu
    });
  }

  // Theme
  const savedTheme = localStorage.getItem("welfog_theme") || "light";
  document.documentElement.setAttribute("data-theme", savedTheme);
  updateThemeMeta(savedTheme);

  $("#btnTheme").addEventListener("click", () => {
    const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("welfog_theme", next);
    updateThemeMeta(next);
  });

  function updateThemeMeta(theme) {
    const meta = document.querySelector('meta[name="theme-color"]');
    if (!meta) return;
    if (document.documentElement.classList.contains("splash-lock")) {
      meta.content = "#ff5a1f";
      return;
    }
    meta.content = theme === "dark" ? "#121214" : "#ffffff";
  }

  // Mobile splash / flash screen
  function isMobileViewport() {
    return window.matchMedia("(max-width: 820px)").matches;
  }

  let stickToBottom = true;

  function lockPageScroll() {
    window.scrollTo(0, 0);
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
  }

  function syncMobileViewport() {
    const vv = window.visualViewport;
    const height = vv ? vv.height : window.innerHeight;
    const offsetTop = vv ? vv.offsetTop : 0;
    const root = document.documentElement;
    root.style.setProperty("--app-h", `${Math.round(height)}px`);
    root.style.setProperty("--app-offset-top", `${Math.round(offsetTop)}px`);
    root.classList.toggle("keyboard-open", window.innerHeight - height > 80);
    if (isMobileViewport()) lockPageScroll();
  }

  function isNearBottom(el, px = 96) {
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight <= px;
  }

  function scrollChat(force) {
    const stage = chatStage || document.querySelector(".chat-stage");
    if (!stage) return;
    if (document.querySelector(".msg.user.is-anchor")) return;
    if (!force && !stickToBottom) return;
    stage.scrollTop = stage.scrollHeight;
  }

  function getReplySpacer() {
    let el = document.getElementById("replySpacer");
    if (!el) {
      el = document.createElement("div");
      el.id = "replySpacer";
      el.className = "reply-spacer";
      el.setAttribute("aria-hidden", "true");
    }
    return el;
  }

  function placeSpacerAtEnd() {
    if (!messagesEl) return;
    messagesEl.appendChild(getReplySpacer());
  }

  function updateReplySpacer() {
    const stage = chatStage || document.querySelector(".chat-stage");
    const spacer = getReplySpacer();
    const userEl = document.querySelector(".msg.user.is-anchor");
    if (!stage || !spacer) return;
    if (!userEl || !messagesEl || messagesEl.hidden) {
      spacer.style.height = "0px";
      return;
    }
    placeSpacerAtEnd();
    let below = 0;
    let node = userEl.nextElementSibling;
    while (node && node !== spacer) {
      below += node.offsetHeight;
      node = node.nextElementSibling;
    }
    const gap = parseFloat(getComputedStyle(messagesEl).gap) || 18;
    const needed = Math.max(0, stage.clientHeight - userEl.offsetHeight - below - gap - 10);
    spacer.style.height = `${Math.round(needed)}px`;
  }

  function pinUserToTop(userEl) {
    document.querySelectorAll(".msg.user.is-anchor").forEach((el) => {
      if (el !== userEl) el.classList.remove("is-anchor");
    });
    if (userEl) userEl.classList.add("is-anchor");
    stickToBottom = false;
    const run = () => {
      updateReplySpacer();
      const stage = chatStage || document.querySelector(".chat-stage");
      if (!stage || !userEl) return;
      const stageRect = stage.getBoundingClientRect();
      const elRect = userEl.getBoundingClientRect();
      stage.scrollTop = Math.max(0, stage.scrollTop + (elRect.top - stageRect.top) - 6);
    };
    requestAnimationFrame(() => {
      run();
      requestAnimationFrame(run);
    });
  }

  if (window.ResizeObserver && messagesEl) {
    const replySpaceWatch = new ResizeObserver(() => {
      if (document.querySelector(".msg.user.is-anchor")) updateReplySpacer();
    });
    replySpaceWatch.observe(messagesEl);
  }

  syncMobileViewport();
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", () => {
      syncMobileViewport();
      updateReplySpacer();
    });
    window.visualViewport.addEventListener("scroll", () => {
      if (isMobileViewport()) lockPageScroll();
    });
  }
  window.addEventListener("resize", syncMobileViewport);
  window.addEventListener(
    "scroll",
    () => {
      if (isMobileViewport()) lockPageScroll();
    },
    { passive: true }
  );
  if (chatStage) {
    chatStage.addEventListener(
      "scroll",
      () => {
        if (!busy) stickToBottom = isNearBottom(chatStage);
        if (btnScrollBottom) {
          const dist = chatStage.scrollHeight - chatStage.scrollTop - chatStage.clientHeight;
          btnScrollBottom.hidden = dist < 160;
        }
      },
      { passive: true }
    );
  }

  btnScrollBottom?.addEventListener("click", () => {
    stickToBottom = true;
    scrollChat(true);
  });

  function autoResizeInput() {
    if (!input || !composer) return;
    input.style.height = "24px";
    const scrollH = input.scrollHeight;
    if (scrollH > 32) {
      const newH = Math.min(scrollH, 120);
      input.style.height = newH + "px";
      input.style.overflowY = scrollH > 120 ? "auto" : "hidden";
      composer.classList.add("is-expanded");
    } else {
      input.style.height = "24px";
      input.style.overflowY = "hidden";
      composer.classList.remove("is-expanded");
    }
    updateReplySpacer();
  }

  input.addEventListener("input", autoResizeInput);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  input.addEventListener("focus", () => {
    setTimeout(() => {
      syncMobileViewport();
      lockPageScroll();
      if (messagesEl && !messagesEl.hidden && !document.querySelector(".msg.user.is-anchor")) {
        scrollChat();
      }
    }, 50);
    setTimeout(() => {
      syncMobileViewport();
      lockPageScroll();
    }, 320);
  });

  function dismissSplash() {
    const splash = $("#splash");
    if (!splash || splash.hidden) {
      document.documentElement.classList.remove("splash-lock");
      updateThemeMeta(document.documentElement.getAttribute("data-theme") || "light");
      return;
    }
    splash.classList.add("is-hiding");
    const finish = () => {
      splash.hidden = true;
      splash.classList.remove("is-hiding");
      document.documentElement.classList.remove("splash-lock");
      updateThemeMeta(document.documentElement.getAttribute("data-theme") || "light");
    };
    splash.addEventListener("transitionend", finish, { once: true });
    setTimeout(finish, 350);
  }

  function runMobileSplash() {
    const splash = $("#splash");
    if (!splash || !isMobileViewport()) {
      if (splash) splash.hidden = true;
      document.documentElement.classList.remove("splash-lock");
      return Promise.resolve();
    }
    splash.hidden = false;
    document.documentElement.classList.add("splash-lock");
    updateThemeMeta("light");
    return new Promise((resolve) => {
      setTimeout(() => {
        dismissSplash();
        resolve();
      }, 850);
    });
  }

  // Sidebar toggle (mobile)
  function openSidebar() {
    if (!sidebar) return;
    sidebar.classList.add("open");
    if (backdrop) backdrop.classList.add("show");
    if (btnMenu) btnMenu.setAttribute("aria-expanded", "true");
  }
  function closeSidebar() {
    if (!sidebar) return;
    sidebar.classList.remove("open");
    if (backdrop) backdrop.classList.remove("show");
    if (btnMenu) btnMenu.setAttribute("aria-expanded", "false");
  }
  function toggleSidebar(e) {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    if (isMobileViewport()) {
      if (sidebar && sidebar.classList.contains("open")) closeSidebar();
      else openSidebar();
      return;
    }
    if (appEl) appEl.classList.toggle("sidebar-closed");
  }
  if (btnMenu) {
    btnMenu.addEventListener("click", toggleSidebar);
  }
  if (backdrop) backdrop.addEventListener("click", closeSidebar);

  btnSupport.addEventListener("click", () => {
    const promptText =
      "I need help. I would like to contact support and connect with your team regarding an issue.";
    input.value = promptText;
    input.focus({ preventScroll: true });
    try {
      input.setSelectionRange(promptText.length, promptText.length);
    } catch (_) {}
    showToast("Message ready — press Send");
  });

  // Voice (Web Speech API where available)
  function setMicListening(on) {
    btnMic.classList.toggle("listening", on);
    btnMic.setAttribute("aria-pressed", on ? "true" : "false");
    btnMic.setAttribute("aria-label", on ? "Listening… tap to stop" : "Voice input");
    btnMic.title = on ? "Listening…" : "Voice";
    composer.classList.toggle("listening-active", on);
  }

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.lang = "en-IN";
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.onresult = (e) => {
      const text = e.results[0][0].transcript;
      input.value = (input.value + " " + text).trim();
      setMicListening(false);
    };
    recognition.onerror = () => setMicListening(false);
    recognition.onend = () => setMicListening(false);
  }
  btnMic.addEventListener("click", () => {
    if (!recognition) {
      showToast("Voice not supported in this browser");
      return;
    }
    if (btnMic.classList.contains("listening")) {
      try {
        recognition.stop();
      } catch (_) {}
      setMicListening(false);
      return;
    }
    try {
      setMicListening(true);
      recognition.start();
    } catch (_) {
      setMicListening(false);
    }
  });

  function clearImageSelection() {
    selectedImages = [];
    if (imageInput) imageInput.value = "";
    if (composerPreviewCards) composerPreviewCards.innerHTML = "";
    if (composerPreview) composerPreview.hidden = true;
    updateReplySpacer();
  }

  function renderImagePreviews() {
    if (!composerPreview || !composerPreviewCards) return;
    if (selectedImages.length === 0) {
      composerPreview.hidden = true;
      composerPreviewCards.innerHTML = "";
      updateReplySpacer();
      return;
    }
    composerPreviewCards.innerHTML = "";
    selectedImages.forEach((imgSrc, idx) => {
      const card = document.createElement("div");
      card.className = "composer-preview-card";
      card.innerHTML = `
        <img class="composer-preview-img" src="${imgSrc}" alt="Photo ${idx + 1}" />
        <button type="button" class="composer-preview-del" data-del-idx="${idx}" aria-label="Remove photo ${idx + 1}" title="Remove photo">✕</button>
      `;
      const delBtn = card.querySelector(".composer-preview-del");
      delBtn?.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        selectedImages.splice(idx, 1);
        renderImagePreviews();
      });
      composerPreviewCards.appendChild(card);
    });

    if (composerPreviewLabel) {
      composerPreviewLabel.textContent =
        selectedImages.length === 1
          ? "1 photo attached"
          : `${selectedImages.length}/3 photos attached`;
    }
    composerPreview.hidden = false;
    updateReplySpacer();
  }

  function compressImage(file, maxDimension = 1280, quality = 0.82) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = reject;
      reader.onload = (e) => {
        const img = new Image();
        img.onerror = reject;
        img.onload = () => {
          let { width, height } = img;
          if (width > maxDimension || height > maxDimension) {
            if (width > height) {
              height = Math.round((height * maxDimension) / width);
              width = maxDimension;
            } else {
              width = Math.round((width * maxDimension) / height);
              height = maxDimension;
            }
          }
          const canvas = document.createElement("canvas");
          canvas.width = width;
          canvas.height = height;
          const ctx = canvas.getContext("2d");
          ctx.drawImage(img, 0, 0, width, height);
          const dataUrl = canvas.toDataURL("image/jpeg", quality);
          resolve(dataUrl);
        };
        img.src = e.target.result;
      };
      reader.readAsDataURL(file);
    });
  }

  btnAttach?.addEventListener("click", (e) => {
    e.preventDefault();
    if (selectedImages.length >= 3) {
      showToast("Maximum 3 photos allowed");
      return;
    }
    if (imageInput) imageInput.click();
  });

  imageInput?.addEventListener("change", async (e) => {
    const rawFiles = Array.from(e.target.files || []);
    if (rawFiles.length === 0) return;
    const imgFiles = rawFiles.filter((f) => f.type && f.type.startsWith("image/"));
    if (imgFiles.length === 0) {
      showToast("Please choose image files (JPG, PNG, WEBP)");
      if (imageInput) imageInput.value = "";
      return;
    }
    const availableSlots = 3 - selectedImages.length;
    if (availableSlots <= 0) {
      showToast("Maximum 3 photos allowed");
      if (imageInput) imageInput.value = "";
      return;
    }
    let toProcess = imgFiles;
    if (imgFiles.length > availableSlots) {
      showToast(`Maximum 3 photos allowed (taking first ${availableSlots})`);
      toProcess = imgFiles.slice(0, availableSlots);
    }
    try {
      showToast(toProcess.length > 1 ? `Optimizing ${toProcess.length} photos…` : "Optimizing photo…");
      const compressedList = await Promise.all(toProcess.map((f) => compressImage(f)));
      selectedImages.push(...compressedList);
      renderImagePreviews();
      if (!isMobileViewport()) input.focus({ preventScroll: true });
    } catch (err) {
      console.error("[image] compression error:", err);
      showToast("Could not process one or more images");
    } finally {
      if (imageInput) imageInput.value = "";
    }
  });

  btnRemoveImage?.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    clearImageSelection();
  });

  btnNewChat.addEventListener("click", async () => {
    await goHome();
    closeSidebar();
  });

  composer.addEventListener("submit", async (e) => {
    e.preventDefault();
    // Touch path already sent via pointerup — skip duplicate submit/click
    if (sendTouchArmed) {
      sendTouchArmed = false;
      return;
    }
    await sendMessage();
  });

  // Mobile: tapping Send while keyboard is open first blurs the input → viewport
  // grows → composer jumps → the click misses. Capture send on the touch itself
  // (preventDefault keeps focus until we blur inside sendMessage).
  let sendTouchArmed = false;
  let sendPointerId = null;

  btnSend?.addEventListener(
    "pointerdown",
    (e) => {
      clearBtnSelect();
      if (e.pointerType === "mouse") return;
      if (busy || (!input.value.trim() && selectedImages.length === 0)) return;
      e.preventDefault();
      sendTouchArmed = true;
      sendPointerId = e.pointerId;
      try {
        btnSend.setPointerCapture(e.pointerId);
      } catch (_) {}
    },
    { passive: false }
  );

  btnSend?.addEventListener(
    "pointerup",
    (e) => {
      if (e.pointerType === "mouse") return;
      if (sendPointerId == null || e.pointerId !== sendPointerId) return;
      sendPointerId = null;
      e.preventDefault();
      e.stopPropagation();
      if (!sendTouchArmed) return;
      sendTouchArmed = false;
      sendMessage();
    },
    { passive: false }
  );

  btnSend?.addEventListener("pointercancel", (e) => {
    if (sendPointerId != null && e.pointerId === sendPointerId) {
      sendPointerId = null;
      sendTouchArmed = false;
    }
  });

  function showToast(text) {
    toast.textContent = text;
    toast.hidden = false;
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => {
      toast.hidden = true;
    }, 2600);
  }

  function setWelcomeVisible(show) {
    welcome.hidden = !show;
    messagesEl.hidden = show;
    if (show) renderWelcomeSuggestions();
  }

  function escapeHtml(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function displayBrand(shop) {
    const s = String(shop ?? "").trim();
    if (!s) return "";
    const norm = s.toLowerCase().replace(/[\s\-_/]+/g, "");
    if (["nobrand", "nobrands", "na", "n/a", "none", "null", "undefined"].includes(norm)) {
      return "";
    }
    return s;
  }

  function formatText(text) {
    const safe = escapeHtml(text);
    return safe
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\n/g, "<br>");
  }

  function badgeClass(tone) {
    if (tone === "ok") return "badge badge-ok";
    if (tone === "warn") return "badge badge-warn";
    if (tone === "bad") return "badge badge-bad";
    return "badge badge-neutral";
  }

  const IMG_CDN = "https://image.welfog.com/";
  const BAD_IMG_PREFIXES = [
    "https://welfog.com/images/",
    "http://welfog.com/images/",
    "https://www.welfog.com/images/",
    "https://welfog.com/",
    "http://welfog.com/",
  ];

  function mediaUrl(path) {
    if (!path) return "";
    let s = String(path).trim();
    if (!s) return "";
    for (const bad of BAD_IMG_PREFIXES) {
      if (s.startsWith(bad)) {
        s = s.slice(bad.length);
        break;
      }
    }
    if (/^https?:\/\//i.test(s)) {
      s = s.replace(/^https?:\/\/d1f02fefkbso7w\.cloudfront\.net\//i, IMG_CDN);
      if (s.includes("image.welfog.com")) return s;
      const m = s.match(/\/(?:images|uploads)\/(.+)$/i);
      if (m) {
        const rest = m[1];
        return IMG_CDN + (s.toLowerCase().includes("/uploads/") ? "uploads/" + rest : rest);
      }
      return s;
    }
    return IMG_CDN + s.replace(/^\/+/, "");
  }

  function productImageHtml(item) {
    const src = mediaUrl(item.image);
    if (!src) {
      return `<div class="wf-product-media"><div class="wf-thumb-ph" aria-hidden="true"></div></div>`;
    }
    return `
      <div class="wf-product-media">
        <img
          class="wf-product-img"
          src="${escapeHtml(src)}"
          alt="${escapeHtml(item.name || "Product")}"
          loading="lazy"
          decoding="async"
          onerror="this.closest('.wf-product-media').classList.add('is-broken'); this.remove();"
        />
        <div class="wf-thumb-ph wf-thumb-fallback" aria-hidden="true"></div>
      </div>`;
  }

  const WEB_BASE = "https://welfog.com";

  function productHref(item) {
    if (!item) return "";
    const pid = String(item.id || item.pro_id || item.pid || item.product_id || "").trim();
    const toDetails = (raw) => {
      let s = String(raw || "").trim();
      if (!s) return "";
      s = s.replace(/\/product\//i, "/product_details/");
      let path = "";
      const m = s.match(/\/product_details\/([^?#]+)/i);
      if (m) path = m[1].replace(/^\/+|\/+$/g, "");
      else {
        s = s.replace(/^\/+/, "");
        const low = s.toLowerCase();
        if (low.startsWith("product_details/")) path = s.split("/").slice(1).join("/").split("?")[0];
        else if (low.startsWith("product/")) path = s.slice("product/".length).split("?")[0];
        else path = s.split("?")[0];
      }
      const parts = path.split("/").filter(Boolean);
      let id = pid;
      let slug = "";
      if (parts.length >= 2 && /^\d+$/.test(parts[0])) {
        id = id || parts[0];
        slug = parts.slice(1).join("/");
      } else {
        slug = parts.join("/");
        if (!id) {
          const tail = slug.match(/-(\d+)$/);
          if (tail) id = tail[1];
        }
      }
      if (id && slug) return `${WEB_BASE}/product_details/${encodeURIComponent(id)}/${slug}`;
      if (slug) return `${WEB_BASE}/product_details/${slug}`;
      if (id) return `${WEB_BASE}/product_details/${encodeURIComponent(id)}`;
      return "";
    };

    if (item.href) {
      const href = toDetails(item.href);
      if (href) return href;
    }
    const slug = String(item.slug || item.link || "").trim();
    if (slug) return toDetails(slug);
    if (pid) return `${WEB_BASE}/product_details/${encodeURIComponent(pid)}`;
    return "";
  }

  function orderHref(item) {
    if (!item) return "";
    if (item.href && /^https?:\/\//i.test(item.href)) {
      const legacy = String(item.href).match(/\/purchase_history\/details\/([^/?#]+)/i);
      if (legacy) {
        return `${WEB_BASE}/account/order_details?id=${encodeURIComponent(legacy[1])}`;
      }
      return item.href;
    }
    const id = item.order_id;
    if (!id) return "";
    return `${WEB_BASE}/account/order_details?id=${encodeURIComponent(id)}`;
  }

  function linkWrap(href, inner, extraClass = "") {
    if (!href) return inner;
    return `<a class="wf-card-link ${extraClass}" href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${inner}</a>`;
  }

  function renderUI(ui) {
    if (!ui || !ui.length) return "";
    const productParts = [];
    const pickParts = [];
    const otherParts = [];
    const featureParts = [];
    const reelParts = [];
    for (const item of ui) {
      if (item.type === "feature_filters") {
        const groups = Array.isArray(item.groups) ? item.groups : [];
        if (!groups.length) continue;
        const baseQ = String(item.base_query || "").trim();
        const applied = item.applied || {};
        const groupBits = [];
        for (const g of groups) {
          const opts = Array.isArray(g.options) ? g.options : [];
          if (!opts.length) continue;
          const key = String(g.key || g.label || "").trim();
          const labelKey = String(g.label || g.key || "Feature").trim();
          const valBits = [];
          for (const o of opts) {
            const val = String(o.value || "").trim();
            if (!val) continue;
            const q = String(o.query || `${key}: ${val}`).trim();
            const msg = baseQ
              ? `Filter ${baseQ} by ${key}: ${val}`
              : `Filter by ${key}: ${val}`;
            const isOn =
              applied &&
              String(applied.key || "").toLowerCase() === key.toLowerCase() &&
              String(applied.value || "").toLowerCase() === val.toLowerCase();
            valBits.push(
              `<button type="button" class="wf-feat-chip ${isOn ? "is-active" : ""}" data-filter-msg="${escapeHtml(msg)}" title="${escapeHtml(q)}">${escapeHtml(val)}</button>`
            );
          }
          if (!valBits.length) continue;
          groupBits.push(
            `<span class="wf-feat-group"><span class="wf-feat-k">${escapeHtml(labelKey)}</span> : ${valBits.join('<span class="wf-feat-comma">, </span>')}</span>`
          );
        }
        if (!groupBits.length) continue;
        featureParts.push(`
          <div class="wf-feat-panel">
            <div class="wf-feat-row"><span class="wf-feat-title">Filters</span><span class="wf-feat-sep" aria-hidden="true">|</span>${groupBits.join('<span class="wf-feat-sep" aria-hidden="true">|</span>')}</div>
          </div>`);
        continue;
      }
      if (item.type === "order") {
        const thumb = item.image
          ? `<img class="wf-order-img" src="${escapeHtml(mediaUrl(item.image))}" alt="" loading="lazy" onerror="this.closest('.wf-order-img-wrap')?.classList.add('is-broken'); this.remove();"/>`
          : "";
        const tracking = Array.isArray(item.tracking) ? item.tracking : [];
        const trackingHtml = tracking.length
          ? `<div class="wf-track">
              <div class="wf-track-title">Order tracking</div>
              <ol class="wf-track-list">
                ${tracking
                  .map(
                    (step) => `
                  <li class="wf-track-step ${step.done ? "is-done" : ""}">
                    <span class="wf-track-dot"></span>
                    <div class="wf-track-body">
                      <div class="wf-track-name">${escapeHtml(step.title || "")}</div>
                      ${step.date ? `<div class="wf-track-date">${escapeHtml(step.date)}</div>` : ""}
                      ${step.reason ? `<div class="wf-track-reason">${escapeHtml(step.reason)}</div>` : ""}
                    </div>
                  </li>`
                  )
                  .join("")}
              </ol>
            </div>`
          : "";

        otherParts.push(
          linkWrap(
            orderHref(item),
            `<article class="wf-card wf-order ${tracking.length ? "wf-order-detail" : ""}">
            <div class="wf-order-main">
              <div class="wf-order-img-wrap">
                ${thumb || `<div class="wf-order-img wf-order-img-ph"></div>`}
              </div>
              <div class="wf-order-info">
                <div class="wf-order-id">Order #${escapeHtml(item.order_id)}</div>
                ${item.title ? `<div class="wf-order-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</div>` : ""}
                <div class="wf-order-price">${escapeHtml(item.total || "—")}</div>
                <div class="wf-card-meta">
                  ${item.status ? `<span class="${badgeClass(item.status_tone)}">${escapeHtml(item.status)}</span>` : ""}
                  ${item.payment_status ? `<span class="${badgeClass(item.payment_tone)}">${escapeHtml(item.payment_status)}</span>` : ""}
                </div>
                ${item.date ? `<div class="wf-order-date">${escapeHtml(item.date)}</div>` : ""}
              </div>
            </div>
            ${trackingHtml}
          </article>`
          )
        );
        continue;
      }
      if (item.type === "order_detail") {
        const costs = item.costs || {};
        const addr = item.address || {};
        const tracking = Array.isArray(item.tracking) ? item.tracking : [];
        const infoRows = [
          ["Order ID", `#${item.order_id}`],
          ["Order date", item.date],
          ["Status", item.status],
          ["Total order amount", item.total],
          ["Payment Method", item.payment_type],
          ["Payment Status", item.payment_status],
        ]
          .filter(([, v]) => v != null && v !== "")
          .map(
            ([k, v]) =>
              `<div class="wf-kv"><span>${escapeHtml(k)}</span><strong>${escapeHtml(v)}</strong></div>`
          )
          .join("");

        const costRows = [
          ["Subtotal", costs.subtotal],
          ["Shipping cost", costs.shipping ? `+ ${costs.shipping}` : costs.shipping],
          ["COD cost", costs.cod ? `+ ${costs.cod}` : costs.cod],
          ["Coupon", costs.coupon ? `- ${costs.coupon}` : costs.coupon],
          ["Total", costs.total],
        ]
          .filter(([, v]) => v != null && v !== "")
          .map(
            ([k, v], i, arr) =>
              `<div class="wf-kv ${i === arr.length - 1 ? "is-total" : ""}"><span>${escapeHtml(k)}</span><strong>${escapeHtml(v)}</strong></div>`
          )
          .join("");

        const specs = [];
        if (item.color) specs.push(`<span class="wf-chip"><b>Color</b> ${escapeHtml(item.color)}</span>`);
        if (item.size) specs.push(`<span class="wf-chip"><b>Size</b> ${escapeHtml(item.size)}</span>`);

        const trackingHtml = tracking.length
          ? `<div class="wf-track">
              <div class="wf-section-title">Order tracking</div>
              <ol class="wf-track-list">
                ${tracking
                  .map(
                    (step) => `
                  <li class="wf-track-step ${step.done ? "is-done" : ""}">
                    <span class="wf-track-dot"></span>
                    <div class="wf-track-body">
                      <div class="wf-track-name">${escapeHtml(step.title || "")}</div>
                      ${step.date ? `<div class="wf-track-date">${escapeHtml(step.date)}</div>` : ""}
                    </div>
                  </li>`
                  )
                  .join("")}
              </ol>
            </div>`
          : "";

        otherParts.push(`
          <article class="wf-card wf-order-full">
            <div class="wf-section">
              <div class="wf-section-title">Order Information</div>
              ${infoRows}
            </div>

            <div class="wf-section">
              <div class="wf-section-title">Product</div>
              ${linkWrap(
                item.product_href || productHref(item),
                `<div class="wf-order-product">
                <div class="wf-order-img-wrap">
                  ${
                    item.image
                      ? `<img class="wf-order-img" src="${escapeHtml(mediaUrl(item.image))}" alt="" loading="lazy" onerror="this.remove()"/>`
                      : `<div class="wf-order-img wf-order-img-ph"></div>`
                  }
                </div>
                <div class="wf-order-product-info">
                  <div class="wf-order-title">${escapeHtml(item.product_name || "Product")}</div>
                  ${specs.length ? `<div class="wf-specs">${specs.join("")}</div>` : ""}
                  <div class="wf-order-product-meta">
                    <span>${escapeHtml(item.unit_price || "—")}</span>
                    <span>× ${escapeHtml(item.quantity || 1)}</span>
                    <strong>${escapeHtml(item.line_total || item.total || "—")}</strong>
                  </div>
                </div>
              </div>`
              )}
            </div>

            <div class="wf-section">
              <div class="wf-section-title">Shipping Address</div>
              ${addr.name ? `<div class="wf-addr-name">${escapeHtml(addr.name)}</div>` : ""}
              ${addr.phone ? `<div class="wf-card-sub">Phone: ${escapeHtml(addr.phone)}</div>` : ""}
              ${addr.email ? `<div class="wf-card-sub">Email: ${escapeHtml(addr.email)}</div>` : ""}
              ${addr.line ? `<div class="wf-card-line">${escapeHtml(addr.line)}</div>` : ""}
            </div>

            <div class="wf-section">
              <div class="wf-section-title">Bill summary</div>
              ${costRows}
            </div>

            ${trackingHtml}
          </article>`);
        continue;
      }
      if (item.type === "product") {
        const priceHtml = item.has_discount && item.mrp
          ? `<span class="wf-price-now">${escapeHtml(item.price || "—")}</span>
             <span class="wf-price-mrp">${escapeHtml(item.mrp)}</span>
             <span class="wf-price-off">(${escapeHtml(item.off_percent)}% OFF)</span>`
          : `<span class="wf-price-now">${escapeHtml(item.price || "—")}</span>`;

        const pickPrice = item.has_discount && item.mrp
          ? `<span class="wf-price-now">${escapeHtml(item.price || "—")}</span>
             <span class="wf-price-mrp">${escapeHtml(item.mrp)}</span>`
          : `<span class="wf-price-now">${escapeHtml(item.price || "—")}</span>`;

        if (item.featured) {
          const thumb = item.image
            ? `<img class="wf-pick-img" src="${escapeHtml(mediaUrl(item.image))}" alt="" loading="lazy" onerror="this.classList.add('wf-pick-img-ph');this.removeAttribute('src')"/>`
            : `<div class="wf-pick-img wf-pick-img-ph"></div>`;
          pickParts.push(
            linkWrap(
              productHref(item),
              `<div class="wf-pick">
              ${thumb}
              <div class="wf-pick-body">
                <div class="wf-pick-name" title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</div>
                <div class="wf-pick-price">${pickPrice}</div>
              </div>
            </div>`
            )
          );
        }

        productParts.push(`
          <div class="wf-slider-item">
            ${linkWrap(
              productHref(item),
              `<article class="wf-card wf-product">
              ${productImageHtml(item)}
              <div class="wf-product-body">
                <div class="wf-card-title" title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</div>
                ${displayBrand(item.shop) ? `<div class="wf-card-sub">${escapeHtml(displayBrand(item.shop))}</div>` : ""}
                <div class="wf-price-line">${priceHtml}</div>
              </div>
            </article>`
            )}
          </div>`);
        continue;
      }
      if (item.type === "address") {
        otherParts.push(`
          <article class="wf-card wf-address">
            <div class="wf-card-top">
              <div class="wf-card-title">${escapeHtml(item.name)}</div>
              ${item.default ? `<span class="badge badge-ok">Default</span>` : ""}
            </div>
            ${item.phone ? `<div class="wf-card-sub">${escapeHtml(item.phone)}</div>` : ""}
            <div class="wf-card-line">${escapeHtml(item.line || "")}</div>
          </article>`);
        continue;
      }
      if (item.type === "profile") {
        const meta = [];
        if (item.email) meta.push(`<div class="wf-card-sub">${escapeHtml(item.email)}</div>`);
        if (item.phone) meta.push(`<div class="wf-card-sub">${escapeHtml(item.phone)}</div>`);
        if (item.dob) meta.push(`<div class="wf-card-sub">DOB: ${escapeHtml(item.dob)}</div>`);
        if (item.gender) meta.push(`<div class="wf-card-sub">Gender: ${escapeHtml(item.gender)}</div>`);
        if (item.marital_status) meta.push(`<div class="wf-card-sub">Marital: ${escapeHtml(item.marital_status)}</div>`);
        otherParts.push(`
          <article class="wf-card wf-profile">
            <div class="wf-avatar">${escapeHtml((item.name || "U").slice(0, 1).toUpperCase())}</div>
            <div>
              <div class="wf-card-title">${escapeHtml(item.name)}</div>
              ${meta.join("")}
            </div>
          </article>`);
        continue;
      }
      if (item.type === "summary") {
        const rows = (item.rows || [])
          .map(
            (r) =>
              `<div class="wf-sum-row"><span>${escapeHtml(r.label)}</span><strong>${escapeHtml(r.value)}</strong></div>`
          )
          .join("");
        otherParts.push(`
          <article class="wf-card wf-summary">
            <div class="wf-card-title">${escapeHtml(item.title || "Summary")}</div>
            ${rows}
          </article>`);
        continue;
      }
      if (item.type === "play_profile") {
        const avatar = item.profile_picture
          ? `<img class="wf-play-avatar-img" src="${escapeHtml(mediaUrl(item.profile_picture))}" alt="${escapeHtml(item.name)}" onerror="this.remove()"/>`
          : `<div class="wf-avatar wf-play-avatar">${escapeHtml((item.name || "P").slice(0, 1).toUpperCase())}</div>`;
        const editBtn = item.is_self
          ? `<button type="button" class="wf-btn-edit-play" data-action="edit-play-profile">✏️ Edit Profile</button>`
          : "";
        otherParts.push(`
          <article class="wf-card wf-play-profile-card">
            <div class="wf-play-header">
              <span class="wf-play-badge">WELFOG PLAY</span>
            </div>
            <div class="wf-play-main">
              <div class="wf-play-avatar-wrap">
                ${avatar}
              </div>
              <div class="wf-play-info">
                <div class="wf-card-title">${escapeHtml(item.name || "Play User")}</div>
                ${item.username ? `<div class="wf-play-handle">@${escapeHtml(item.username)}</div>` : ""}
              </div>
            </div>
            ${item.bio ? `<div class="wf-play-bio">${escapeHtml(item.bio)}</div>` : ""}
            <div class="wf-play-stats">
              <div class="wf-play-stat"><span class="wf-play-stat-val">${escapeHtml(item.post_count ?? 0)}</span><span class="wf-play-stat-lbl">Posts</span></div>
              <div class="wf-play-stat"><span class="wf-play-stat-val">${escapeHtml(item.followers_count ?? 0)}</span><span class="wf-play-stat-lbl">Followers</span></div>
              <div class="wf-play-stat"><span class="wf-play-stat-val">${escapeHtml(item.following_count ?? 0)}</span><span class="wf-play-stat-lbl">Following</span></div>
            </div>
            ${editBtn}
          </article>`);
        continue;
      }
      if (item.type === "play_user") {
        const avatar = item.profile_picture
          ? `<img class="wf-play-avatar-img" src="${escapeHtml(mediaUrl(item.profile_picture))}" alt="" onerror="this.remove()"/>`
          : `<div class="wf-avatar wf-play-avatar">${escapeHtml((item.name || "P").slice(0, 1).toUpperCase())}</div>`;
        otherParts.push(`
          <article class="wf-card wf-play-user-card">
            <div class="wf-play-main">
              <div class="wf-play-avatar-wrap">${avatar}</div>
              <div class="wf-play-info">
                <div class="wf-card-title">${escapeHtml(item.name)}</div>
                ${item.username ? `<div class="wf-play-handle">@${escapeHtml(item.username)}</div>` : ""}
                ${item.bio ? `<div class="wf-card-sub" title="${escapeHtml(item.bio)}">${escapeHtml(item.bio)}</div>` : ""}
                <div class="wf-card-sub"><b>${escapeHtml(item.followers_count ?? 0)}</b> followers</div>
              </div>
            </div>
          </article>`);
        continue;
      }
      if (item.type === "play_reel") {
        const thumb = item.thumbnail
          ? `<img class="wf-reel-img" src="${escapeHtml(mediaUrl(item.thumbnail))}" alt="${escapeHtml(item.caption)}" loading="lazy" onerror="this.closest('.wf-reel-media')?.classList.add('wf-reel-media-ph'); this.remove();"/>`
          : `<div class="wf-reel-img-ph"></div>`;
        const href = item.href || "";
        const creator = item.creator_name || (item.username ? `@${item.username}` : "Play Reel");
        const cardHtml = `
          <article class="wf-card wf-reel-card">
            <div class="wf-reel-media">
              ${thumb}
              <div class="wf-reel-badge-top">PLAY</div>
              <div class="wf-reel-overlay">
                ${item.views ? `<span class="wf-reel-chip">▶ ${escapeHtml(item.views)}</span>` : ""}
                ${item.likes ? `<span class="wf-reel-chip">♥ ${escapeHtml(item.likes)}</span>` : ""}
              </div>
            </div>
            <div class="wf-reel-body">
              <div class="wf-reel-creator">${escapeHtml(creator)}</div>
              ${item.caption ? `<div class="wf-reel-caption" title="${escapeHtml(item.caption)}">${escapeHtml(item.caption)}</div>` : ""}
              ${href ? `<span class="wf-reel-open-btn"><svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg> Play</span>` : ""}
            </div>
          </article>`;
        reelParts.push(linkWrap(href, cardHtml, "wf-reel-link"));
        continue;
      }
    }

    let html = "";
    if (pickParts.length) {
      html += `<div class="wf-picks">${pickParts.join("")}</div>`;
    }
    if (productParts.length) {
      html += `
        <div class="wf-slider">
          <button type="button" class="wf-slider-btn prev" aria-label="Previous">‹</button>
          <div class="wf-slider-track">${productParts.join("")}</div>
          <button type="button" class="wf-slider-btn next" aria-label="Next">›</button>
        </div>`;
    }
    if (reelParts.length) {
      if (reelParts.length > 1) {
        html += `
          <div class="wf-slider wf-reels-slider">
            <button type="button" class="wf-slider-btn prev" aria-label="Previous">‹</button>
            <div class="wf-slider-track">${reelParts.map((r) => `<div class="wf-slider-item wf-reel-slider-item">${r}</div>`).join("")}</div>
            <button type="button" class="wf-slider-btn next" aria-label="Next">›</button>
          </div>`;
      } else {
        html += `<div class="wf-reels-single">${reelParts.join("")}</div>`;
      }
    }
    if (featureParts.length) {
      html += featureParts.join("");
    }
    if (otherParts.length) {
      html += `<div class="wf-grid">${otherParts.join("")}</div>`;
    }
    return html;
  }

  function syncSliderNav(slider) {
    if (!slider) return;
    const track = slider.querySelector(".wf-slider-track");
    const prev = slider.querySelector(".wf-slider-btn.prev");
    const next = slider.querySelector(".wf-slider-btn.next");
    if (!track || !prev || !next) return;
    const maxScroll = track.scrollWidth - track.clientWidth;
    const canScroll = maxScroll > 4;
    slider.classList.toggle("is-scrollable", canScroll);
    prev.classList.toggle("is-hidden", !canScroll || track.scrollLeft <= 2);
    next.classList.toggle("is-hidden", !canScroll || track.scrollLeft >= maxScroll - 2);
    prev.disabled = prev.classList.contains("is-hidden");
    next.disabled = next.classList.contains("is-hidden");
  }

  function bindSlider(slider) {
    if (!slider || slider.dataset.bound === "1") return;
    slider.dataset.bound = "1";
    const track = slider.querySelector(".wf-slider-track");
    if (!track) return;
    track.addEventListener("scroll", () => syncSliderNav(slider), { passive: true });
    window.addEventListener("resize", () => syncSliderNav(slider));
    requestAnimationFrame(() => syncSliderNav(slider));
  }

  function initSliders(root) {
    (root || document).querySelectorAll(".wf-slider").forEach(bindSlider);
  }

  messagesEl.addEventListener("click", (e) => {
    const editPlayBtn = e.target.closest(".wf-btn-edit-play");
    if (editPlayBtn) {
      e.preventDefault();
      input.value = "meri play profile edit karni hai";
      input.focus();
      return;
    }
    const feat = e.target.closest(".wf-feat-chip");
    if (feat) {
      e.preventDefault();
      const msg = feat.getAttribute("data-filter-msg") || "";
      if (!msg || busy) return;
      input.value = msg;
      sendMessage();
      return;
    }
    const btn = e.target.closest(".wf-slider-btn");
    if (!btn || btn.disabled) return;
    const slider = btn.closest(".wf-slider");
    const track = slider?.querySelector(".wf-slider-track");
    if (!track) return;
    const step = Math.max(track.clientWidth * 0.75, 160);
    track.scrollBy({ left: btn.classList.contains("prev") ? -step : step, behavior: "smooth" });
    requestAnimationFrame(() => syncSliderNav(slider));
  });

  const CARD_SPLIT = "<<<CARDS>>>";

  function splitCardText(content) {
    const raw = String(content || "")
      // Hide raw id dumps the model sometimes pastes
      .replace(/\[\s*\d{5,}(?:\s*,\s*\d{5,})*\s*\]/g, "")
      .replace(/(?:^|\n)\s*\d{5,}(?:\s*,\s*\d{5,})+\s*(?=\n|$)/g, "\n")
      .replace(/\b(?:product[_\s-]?ids?|pro[_\s-]?ids?|stock[_\s-]?ids?)\s*[:=]\s*[\d,\s]+/gi, "")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
    if (!raw.includes(CARD_SPLIT)) {
      return { before: raw.trim(), after: "" };
    }
    const idx = raw.indexOf(CARD_SPLIT);
    return {
      before: raw.slice(0, idx).trim(),
      after: raw.slice(idx + CARD_SPLIT.length).trim(),
    };
  }

  function appendMessage(role, content, ui, images = null) {
    setWelcomeVisible(false);
    const wrap = document.createElement("div");
    wrap.className = `msg ${role}`;
    const roleLabel = role === "user" ? "You" : "Welfog AI";
    wrap.innerHTML = `<div class="msg-role">${roleLabel}</div><div class="msg-bubble"></div>`;
    const bubble = wrap.querySelector(".msg-bubble");

    if (role === "user") {
      const imgList = Array.isArray(images) ? images : (images ? [images] : []);
      if (imgList.length > 0) {
        const galleryEl = document.createElement("div");
        galleryEl.className = `msg-user-gallery msg-user-gallery--${Math.min(imgList.length, 3)}`;
        for (const src of imgList) {
          const imgEl = document.createElement("img");
          imgEl.className = "msg-user-img";
          imgEl.src = src;
          imgEl.alt = "Uploaded photo";
          imgEl.loading = "lazy";
          galleryEl.appendChild(imgEl);
        }
        bubble.appendChild(galleryEl);
      }
      if (content) {
        const textNode = document.createElement("div");
        textNode.className = "msg-user-text";
        textNode.textContent = content;
        bubble.appendChild(textNode);
      }
      if (imgList.length === 0 && !content) {
        bubble.textContent = "";
      }
    } else {
      const { before, after } = splitCardText(content);
      const uiHtml = renderUI(ui);
      const parts = [];
      if (before) parts.push(`<div class="msg-text">${formatText(before)}</div>`);
      if (uiHtml) parts.push(uiHtml);
      if (after) parts.push(`<div class="msg-text msg-text-after">${formatText(after)}</div>`);
      bubble.innerHTML = parts.join("") || "";
      initSliders(wrap);
      appendMsgActions(wrap, [before, after].filter(Boolean).join("\n\n"));
    }

    messagesEl.appendChild(wrap);
    placeSpacerAtEnd();
    if (role !== "user") scrollChat(true);
    return wrap;
  }

  function appendMsgActions(wrap, textToCopy) {
    if (!wrap || wrap.querySelector(".msg-actions")) return;
    const actions = document.createElement("div");
    actions.className = "msg-actions";
    actions.innerHTML = `
      <button type="button" class="msg-action-btn btn-copy" title="Copy message" aria-label="Copy message">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
        </svg>
        <span>Copy</span>
      </button>
      <button type="button" class="msg-action-btn btn-retry" title="Regenerate response" aria-label="Regenerate response">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M23 4v6h-6"></path>
          <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
        </svg>
        <span>Regenerate</span>
      </button>
    `;

    const copyBtn = actions.querySelector(".btn-copy");
    copyBtn?.addEventListener("click", async () => {
      const bubble = wrap.querySelector(".msg-bubble");
      const text = textToCopy || (bubble ? bubble.innerText : "") || "";
      if (!text.trim()) return;
      try {
        await navigator.clipboard.writeText(text.trim());
        copyBtn.classList.add("is-copied");
        copyBtn.innerHTML = `
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
          <span>Copied!</span>
        `;
        showToast("Copied to clipboard");
        setTimeout(() => {
          copyBtn.classList.remove("is-copied");
          copyBtn.innerHTML = `
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
            </svg>
            <span>Copy</span>
          `;
        }, 2000);
      } catch (_) {
        showToast("Failed to copy");
      }
    });

    const retryBtn = actions.querySelector(".btn-retry");
    retryBtn?.addEventListener("click", () => {
      if (busy) return;
      let promptToRetry = "";
      let prev = wrap.previousElementSibling;
      while (prev) {
        if (prev.classList.contains("user")) {
          const txt = prev.querySelector(".msg-user-text");
          promptToRetry = (txt ? txt.textContent : prev.innerText || "").trim();
          break;
        }
        prev = prev.previousElementSibling;
      }
      if (!promptToRetry) {
        promptToRetry = lastUserPrompt;
      }
      if (!promptToRetry) {
        showToast("No question found to regenerate");
        return;
      }
      showToast("Regenerating response…");
      input.value = promptToRetry;
      autoResizeInput();
      sendMessage();
    });

    wrap.appendChild(actions);
  }

  function showTyping() {
    hideTyping();
    const wrap = document.createElement("div");
    wrap.className = "msg assistant typing";
    wrap.id = "typingRow";
    wrap.innerHTML = `
      <div class="msg-role">Welfog AI</div>
      <div class="msg-bubble">
        <span class="dot"></span><span class="dot"></span><span class="dot"></span>
      </div>
    `;
    messagesEl.appendChild(wrap);
    placeSpacerAtEnd();
  }

  function setTypingStatus(_text) {
    // Keep classic dots — status stream still runs in background for timing.
  }

  function hideTyping() {
    const el = $("#typingRow");
    if (el) el.remove();
  }

  function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  async function typeAssistantReply(content, ui) {
    hideTyping();
    setWelcomeVisible(false);
    const wrap = document.createElement("div");
    wrap.className = "msg assistant is-streaming";
    wrap.innerHTML = `
      <div class="msg-role">Welfog AI</div>
      <div class="msg-bubble"></div>
    `;
    const bubble = wrap.querySelector(".msg-bubble");
    messagesEl.appendChild(wrap);
    placeSpacerAtEnd();
    updateReplySpacer();

    const { before, after } = splitCardText(content);
    const uiHtml = ui && ui.length ? renderUI(ui) : "";
    if (!before && !after && !uiHtml) {
      wrap.remove();
      return wrap;
    }

    async function typeInto(el, text) {
      const full = String(text || "");
      if (!full) return;
      const parts = full.match(/\S+\s*|\s+/g) || [full];
      let partial = "";
      const step = full.length > 700 ? 3 : full.length > 350 ? 2 : 1;
      for (let i = 0; i < parts.length; i += step) {
        partial += parts.slice(i, i + step).join("");
        el.innerHTML = formatText(partial) + '<span class="caret" aria-hidden="true"></span>';
        updateReplySpacer();
        const delay = full.length > 900 ? 10 : full.length > 400 ? 14 : 20;
        await sleep(delay + Math.floor(Math.random() * 10));
      }
      el.innerHTML = formatText(full);
    }

    if (before) {
      const textEl = document.createElement("div");
      textEl.className = "msg-text";
      bubble.appendChild(textEl);
      await typeInto(textEl, before);
    }

    if (uiHtml) {
      const uiHost = document.createElement("div");
      uiHost.className = "msg-ui-fade";
      uiHost.innerHTML = uiHtml;
      bubble.appendChild(uiHost);
      initSliders(wrap);
      updateReplySpacer();
      await sleep(120);
    }

    if (after) {
      const textEl = document.createElement("div");
      textEl.className = "msg-text msg-text-after";
      bubble.appendChild(textEl);
      await typeInto(textEl, after);
    }

    wrap.classList.remove("is-streaming");
    appendMsgActions(wrap, [before, after].filter(Boolean).join("\n\n"));
    updateReplySpacer();
    return wrap;
  }

  async function streamChat(text, images = null) {
    const payload = { message: text, chat_id: chatId, provider };
    const imgList = Array.isArray(images) ? images : (images ? [images] : []);
    if (imgList.length > 0) {
      payload.images = imgList;
      payload.image = imgList[0];
    }
    const res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(payload),
    });
    if (!res.ok || !res.body) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.message || data.error || "Something went wrong.");
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let donePayload = null;

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() || "";
      for (const chunk of chunks) {
        const line = chunk
          .split("\n")
          .map((l) => l.trim())
          .find((l) => l.startsWith("data:"));
        if (!line) continue;
        let evt;
        try {
          evt = JSON.parse(line.slice(5).trim());
        } catch (_) {
          continue;
        }
        if (evt.type === "status" && evt.text) {
          setTypingStatus(evt.text);
        } else if (evt.type === "done") {
          donePayload = evt;
        }
      }
    }
    if (!donePayload) throw new Error("Empty response from server.");
    return donePayload;
  }

  async function goHome() {
    rememberChatId(null);
    messagesEl.innerHTML = "";
    clearImageSelection();
    setWelcomeVisible(true);
    input.value = "";
    input.focus({ preventScroll: true });
    await refreshChatList();
  }

  async function createNewChat() {
    await goHome();
  }

  function renderFilteredChats(filterText = "") {
    chatList.querySelectorAll(".chat-item").forEach((n) => n.remove());
    const query = (filterText || "").toLowerCase().trim();
    const chats = query
      ? cachedChats.filter((c) => (c.title || "New chat").toLowerCase().includes(query))
      : cachedChats;

    if (!cachedChats.length) {
      chatListEmpty.textContent = "No recent chats";
      chatListEmpty.hidden = false;
      return;
    }

    if (!chats.length) {
      chatListEmpty.textContent = "No matching chats";
      chatListEmpty.hidden = false;
      return;
    }

    chatListEmpty.hidden = true;

    for (const c of chats) {
      const row = document.createElement("div");
      row.className = "chat-item" + (c.chat_id === chatId ? " active" : "");
      row.dataset.id = c.chat_id;

      const openBtn = document.createElement("button");
      openBtn.type = "button";
      openBtn.className = "chat-item-open";
      openBtn.textContent = c.title || "New chat";

      const actions = document.createElement("div");
      actions.className = "chat-item-actions";

      const editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.className = "chat-item-edit";
      editBtn.title = "Rename chat";
      editBtn.setAttribute("aria-label", "Rename chat");
      editBtn.innerHTML = `
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
        </svg>
      `;
      editBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        promptRenameChat(c.chat_id, c.title);
      });

      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "chat-item-del";
      delBtn.title = "Delete chat";
      delBtn.setAttribute("aria-label", "Delete chat");
      delBtn.textContent = "×";
      delBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        promptDeleteChat(c.chat_id);
      });

      openBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        loadChat(c.chat_id);
        closeSidebar();
      });

      actions.appendChild(editBtn);
      actions.appendChild(delBtn);

      row.appendChild(openBtn);
      row.appendChild(actions);
      chatList.appendChild(row);
    }
  }

  async function refreshChatList() {
    try {
      const res = await fetch("/api/chats");
      const data = await res.json();
      cachedChats = data.chats || [];
      renderFilteredChats(sidebarSearchInput ? sidebarSearchInput.value.trim() : "");
    } catch (_) {}
  }

  if (sidebarSearchClear) sidebarSearchClear.hidden = true;

  sidebarSearchInput?.addEventListener("input", (e) => {
    const val = (e.target.value || "").trim();
    if (sidebarSearchClear) sidebarSearchClear.hidden = val.length === 0;
    renderFilteredChats(val);
  });

  sidebarSearchClear?.addEventListener("click", () => {
    if (sidebarSearchInput) {
      sidebarSearchInput.value = "";
      sidebarSearchInput.focus();
    }
    if (sidebarSearchClear) sidebarSearchClear.hidden = true;
    renderFilteredChats("");
  });

  function promptDeleteChat(id) {
    pendingDeleteChatId = id;
    if (deleteModal) deleteModal.hidden = false;
  }

  btnConfirmDelete?.addEventListener("click", async () => {
    if (!pendingDeleteChatId) return;
    const id = pendingDeleteChatId;
    pendingDeleteChatId = null;
    if (deleteModal) deleteModal.hidden = true;
    await deleteChat(id);
  });

  btnCancelDelete?.addEventListener("click", () => {
    pendingDeleteChatId = null;
    if (deleteModal) deleteModal.hidden = true;
  });

  deleteModal?.addEventListener("click", (e) => {
    if (e.target === deleteModal) {
      pendingDeleteChatId = null;
      deleteModal.hidden = true;
    }
  });

  function promptRenameChat(id, currentTitle) {
    pendingRenameChatId = id;
    if (renameInput) {
      renameInput.value = currentTitle || "New chat";
    }
    if (renameModal) {
      renameModal.hidden = false;
      setTimeout(() => {
        renameInput?.focus();
        renameInput?.select();
      }, 50);
    }
  }

  async function saveRenameChat() {
    if (!pendingRenameChatId || !renameInput) return;
    const id = pendingRenameChatId;
    const newTitle = renameInput.value.trim();
    if (!newTitle) {
      showToast("Please enter a title");
      return;
    }
    pendingRenameChatId = null;
    if (renameModal) renameModal.hidden = true;
    try {
      const res = await fetch(`/api/chat/${encodeURIComponent(id)}/rename`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: newTitle }),
      });
      if (!res.ok) throw new Error("Rename failed");
      showToast("Chat renamed");
      await refreshChatList();
    } catch (_) {
      showToast("Could not rename chat");
    }
  }

  btnSaveRename?.addEventListener("click", saveRenameChat);
  renameInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      saveRenameChat();
    } else if (e.key === "Escape") {
      pendingRenameChatId = null;
      if (renameModal) renameModal.hidden = true;
    }
  });

  btnCancelRename?.addEventListener("click", () => {
    pendingRenameChatId = null;
    if (renameModal) renameModal.hidden = true;
  });

  renameModal?.addEventListener("click", (e) => {
    if (e.target === renameModal) {
      pendingRenameChatId = null;
      renameModal.hidden = true;
    }
  });

  async function deleteChat(id) {
    const target = String(id || "").trim();
    if (!target) return;
    try {
      let res = await fetch(`/api/chat/${encodeURIComponent(target)}`, { method: "DELETE" });
      if (!res.ok) {
        res = await fetch(`/api/chat/${encodeURIComponent(target)}/delete`, { method: "POST" });
      }
      if (!res.ok) throw new Error("Delete failed");
    } catch (_) {
      showToast("Could not delete chat");
      return;
    }
    showToast("Chat deleted");
    if (chatId === target) {
      await goHome();
    } else {
      await refreshChatList();
    }
  }

  async function loadChat(id) {
    const res = await fetch(`/api/chat/${id}`);
    if (!res.ok) {
      await goHome();
      return;
    }
    const data = await res.json();
    rememberChatId(data.chat_id);
    messagesEl.innerHTML = "";
    const msgs = data.messages || [];
    if (!msgs.length) {
      setWelcomeVisible(true);
    } else {
      setWelcomeVisible(false);
      for (const m of msgs) {
        appendMessage(m.role === "user" ? "user" : "assistant", m.content, m.ui || [], m.images || (m.image ? [m.image] : null));
        if (m.role === "user" && m.content) {
          lastUserPrompt = m.content;
        }
      }
      stickToBottom = true;
      scrollChat(true);
    }
    await refreshChatList();
  }

  async function sendMessage() {
    const text = input.value.trim();
    const imgs = [...selectedImages];
    if ((!text && imgs.length === 0) || busy) return;

    if (text) lastUserPrompt = text;
    busy = true;
    btnSend.disabled = true;
    input.value = "";
    autoResizeInput();
    clearImageSelection();
    input.blur();
    const userWrap = appendMessage("user", text, null, imgs);
    showTyping();
    pinUserToTop(userWrap);

    try {
      const data = await streamChat(text, imgs);
      rememberChatId(data.chat_id);
      await typeAssistantReply(data.reply || "", data.ui || []);
      updateReplySpacer();
      await refreshChatList();
    } catch (err) {
      hideTyping();
      const msg = (err && err.message) || "Network error. Is the server running?";
      appendMessage("assistant", msg);
    } finally {
      busy = false;
      btnSend.disabled = false;
      if (isMobileViewport()) {
        input.blur();
      } else {
        input.focus({ preventScroll: true });
      }
    }
  }

  // Boot — URL ?chat_id= first, then saved id, else new chat
  (async () => {
    const splashDone = runMobileSplash();

    // Clean URL query params if auth tokens were passed so they do not linger in address bar / history
    try {
      const sp = new URLSearchParams(window.location.search);
      const authKeys = ["token", "access_token", "authToken", "auth_token"];
      let hasAuth = false;
      for (const k of authKeys) {
        if (sp.has(k)) {
          sp.delete(k);
          hasAuth = true;
        }
      }
      if (hasAuth) {
        sp.delete("userId");
        sp.delete("user_id");
        sp.delete("uid");
        sp.delete("mobile");
        sp.delete("phone");
        sp.delete("user_phone");
        sp.delete("userName");
        sp.delete("user_name");
        sp.delete("name");
        sp.delete("reset");
        sp.delete("force_new");
        const cleanSearch = sp.toString();
        const cleanUrl = window.location.pathname + (cleanSearch ? "?" + cleanSearch : "") + window.location.hash;
        window.history.replaceState({ chat_id: getChatIdFromUrl() || null }, "", cleanUrl);
      }
    } catch (_) {}

    const fromUrl = getChatIdFromUrl();
    if (fromUrl) {
      await loadChat(fromUrl);
    } else {
      await goHome();
    }
    await splashDone;
  })();

  // Listen for auth messages from Flutter/Android InAppWebView postMessage
  window.addEventListener("message", async (event) => {
    try {
      let data = event.data;
      if (typeof data === "string" && (data.startsWith("{") || data.startsWith("["))) {
        data = JSON.parse(data);
      }
      if (!data || typeof data !== "object") return;
      if (data.type === "WELFOG_AUTH" || data.type === "welfog_auth" || data.action === "login") {
        const token = data.token || data.access_token || data.authToken;
        const uid = data.user_id || data.userId || data.uid || data.id;
        if (token && uid) {
          const res = await fetch("/api/auth/app-login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              access_token: token,
              user_id: uid,
              name: data.name || data.userName || data.user_name || "",
              phone: data.phone || data.userPhone || data.user_phone || data.mobile || "",
              email: data.email || data.userEmail || data.user_email || "",
              force_new_session: true,
            }),
          });
          if (res.ok) {
            await refreshChatList();
          }
        }
      } else if (data.type === "WELFOG_LOGOUT" || data.action === "logout") {
        await fetch("/api/auth/logout", { method: "POST" });
        await goHome();
      }
    } catch (_) {}
  });

  window.addEventListener("popstate", async () => {
    const id = getChatIdFromUrl();
    if (id && id !== chatId) await loadChat(id);
    else if (!id) await goHome();
  });

  function isComposerField(el) {
    if (!el || !el.closest) return false;
    const node = el.closest("input, textarea, [contenteditable='true']");
    return !!(node && node.closest(".composer"));
  }

  document.addEventListener("selectstart", (e) => {
    if (!isComposerField(e.target)) e.preventDefault();
  });
  document.addEventListener("dragstart", (e) => {
    if (!isComposerField(e.target)) e.preventDefault();
  });
  document.addEventListener("copy", (e) => {
    if (isComposerField(e.target)) return;
    e.preventDefault();
    try {
      e.clipboardData.setData("text/plain", "");
    } catch (_) {}
  });
  document.addEventListener("cut", (e) => {
    if (isComposerField(e.target)) return;
    e.preventDefault();
    try {
      e.clipboardData.setData("text/plain", "");
    } catch (_) {}
  });
  document.addEventListener("contextmenu", (e) => {
    if (!isComposerField(e.target)) e.preventDefault();
  });

  // Image Lightbox Viewer
  function openLightbox(src) {
    if (!src || !imageLightbox || !lightboxImg) return;
    lightboxImg.src = src;
    imageLightbox.hidden = false;
  }

  function closeLightbox() {
    if (!imageLightbox) return;
    imageLightbox.hidden = true;
    if (lightboxImg) lightboxImg.src = "";
  }

  lightboxClose?.addEventListener("click", closeLightbox);
  lightboxBackdrop?.addEventListener("click", closeLightbox);

  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeLightbox();
      if (deleteModal) deleteModal.hidden = true;
      if (renameModal) renameModal.hidden = true;
    }
  });

  document.addEventListener("click", (e) => {
    const target = e.target;
    if (!target || target.tagName !== "IMG") return;
    if (
      target.matches(".msg-user-img") ||
      target.matches(".composer-preview-img") ||
      target.matches(".wf-order-img") ||
      target.closest(".wf-product-media") ||
      target.closest(".wf-pick-card")
    ) {
      const src = target.currentSrc || target.src;
      if (src) {
        e.preventDefault();
        openLightbox(src);
      }
    }
  });

  function clearBtnSelect() {
    try {
      window.getSelection()?.removeAllRanges();
    } catch (_) {}
  }
  btnMic?.addEventListener("pointerdown", clearBtnSelect);
  btnSend?.addEventListener("pointerdown", clearBtnSelect);
  btnMic?.addEventListener("click", clearBtnSelect);
  btnSend?.addEventListener("click", clearBtnSelect);
})();
