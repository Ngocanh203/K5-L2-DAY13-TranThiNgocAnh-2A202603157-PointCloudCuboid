importScripts("settings.js");

chrome.runtime.onMessage.addListener((message, sender, reply) => {
    const origin = sender.origin || new URL(sender.url || "about:blank").origin;
    if (!["http://localhost:8080", "http://127.0.0.1:8080"].includes(origin)) {
        reply({ state: "error", message: "Hãy mở job trên CVAT local ở cổng 8080." });
        return false;
    }
    // CVAT can change the current job via client-side navigation without reloading the document.
    const path = typeof message?.path === "string" ? message.path : "";
    const job = path.match(/^\/tasks\/\d+\/jobs\/([1-9]\d*)\/?$/);
    if (!job) {
        reply({ state: "error", message: "Không xác định được job CVAT. Hãy tải lại trang job." });
        return false;
    }
    if (!["status", "check", "prelabel", "distances", "points"].includes(message?.action)) {
        reply({ state: "error", message: "Thao tác không được hỗ trợ." });
        return false;
    }
    const action = message.action;
    if (action === "points" && (!Number.isSafeInteger(message.frameIndex) || message.frameIndex < 0)) {
        reply({ state: "error", message: "Số frame không hợp lệ." });
        return false;
    }
    const endpoint = action === "points" ? `/points/${message.frameIndex}` :
        action === "status" ? "" : `/${action}`;
    const route = `/jobs/${job[1]}${endpoint}`;
    fetch(`http://127.0.0.1:8765${route}`, {
        method: ["check", "prelabel"].includes(action) ? "POST" : "GET",
        headers: { Authorization: `Bearer ${PANEL_KEY}` },
        cache: "no-store",
    }).then(async response => {
        const payload = await response.json();
        reply(response.ok ? payload : { state: "error", message: payload.message });
    }).catch(() => reply({
        state: "error",
        message: "Không kết nối được dịch vụ CVAT trên máy.",
    }));
    return true;
});
