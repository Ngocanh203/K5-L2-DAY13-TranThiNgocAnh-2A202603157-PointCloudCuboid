(() => {
    const panelId = "local-cvat-cuboid-tools";
    let jobPath = "";
    let dispose = () => {};

    function element(tag, text) {
        const node = document.createElement(tag);
        node.textContent = text;
        return node;
    }

    function jobLink(text, path, query) {
        const link = element("a", text);
        link.href = `${path}?${new URLSearchParams(query)}`;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        return link;
    }

    function mount(path) {
        const root = element("details", "");
        root.id = panelId;
        const title = element("summary", "Công cụ cuboid 3D");
        const body = element("section", "");
        const status = element("p", "Kiểm các Shape đã Save trong CVAT.");
        status.setAttribute("role", "status");
        const actions = element("div", "");
        actions.className = "cuboid-actions";
        const check = element("button", "Kiểm lỗi");
        const prelabel = element("button", "Gán nhãn sơ bộ");
        const output = element("div", "");
        const measure = createCuboidMeasurements(path, element, jobLink);
        actions.append(check, prelabel, measure.button);
        body.append(actions, measure.view, status, output);
        root.append(title, body);
        document.body.append(root);

        let timer;
        let active = true;
        let requestId = 0;

        function render(result) {
            output.replaceChildren();
            const running = result.state === "running";
            check.disabled = prelabel.disabled = running;
            if (running) {
                status.textContent = result.action === "prelabel" ?
                    "Đang gán nhãn sơ bộ…" : "Đang kiểm Shape đã lưu…";
                timer = setTimeout(() => send("status"), 1000);
                return;
            }
            status.textContent = result.message || "Kiểm các Shape đã Save trong CVAT.";
            if (result.report) {
                const report = element("p", `CSV: ${result.report}`);
                report.className = "cuboid-report";
                output.append(report);
            }
            if (result.reload) {
                output.append(element("p", "Tải lại trang CVAT để xem nhãn mới."));
            }
            if (result.flags?.length) {
                const list = element("ul", "");
                for (const row of result.flags) {
                    const item = element("li", "");
                    const query = { frame: row.frame_index };
                    item.append(jobLink(row.frame, path, query));
                    if (result.action === "check" && Number.isInteger(row.idx)) {
                        const track = row.object_type === "track";
                        const id = jobLink(`${track ? "Track" : "Cuboid"} ID ${row.idx}`, path, {
                            ...query, type: track ? "track" : "shape", serverID: row.idx,
                        });
                        id.title = "Mở CVAT và lọc theo ID trên server";
                        item.append(document.createTextNode(" · "), id, document.createTextNode(` · ${row.label}`));
                    } else if (row.label) {
                        item.append(document.createTextNode(` · ${row.label} · Dự đoán #${row.idx}`));
                    }
                    item.append(document.createTextNode(` · ${row.flags}`));
                    list.append(item);
                }
                output.append(list);
            }
            if (result.manual_review?.length) {
                const guide = element("details", "");
                guide.className = "cuboid-manual";
                const list = element("ul", "");
                for (const rule of result.manual_review) {
                    list.append(element("li", rule));
                }
                guide.append(element("summary", "Kiểm thủ công theo guideline"), list);
                output.append(guide);
            }
        }

        async function send(action) {
            clearTimeout(timer);
            const current = ++requestId;
            check.disabled = prelabel.disabled = true;
            let result;
            try {
                result = await chrome.runtime.sendMessage({ action, path });
            } catch {
                result = { state: "error", message: "Hãy tải lại trang sau khi bật tiện ích." };
            }
            if (active && current === requestId) {
                render(result || {
                    state: "error",
                    message: "Tiện ích chưa phản hồi. Bấm Reload cho CVAT Cuboid Tools trong edge://extensions, rồi tải lại job.",
                });
            }
        }

        check.addEventListener("click", event => {
            if (event.isTrusted) send("check");
        });
        prelabel.addEventListener("click", event => {
            if (event.isTrusted && confirm("Đã Save các chỉnh sửa trong CVAT? Thêm dự đoán mới vào job đang mở?")) {
                send("prelabel");
            }
        });
        root.addEventListener("toggle", () => {
            if (root.open) send("status");
        });

        return () => {
            active = false;
            clearTimeout(timer);
            root.remove();
        };
    }

    function syncLocation() {
        const next = /^\/tasks\/\d+\/jobs\/[1-9]\d*\/?$/.test(location.pathname) ?
            location.pathname : "";
        if (next === jobPath || !document.body) return;
        dispose();
        dispose = next ? mount(next) : () => {};
        jobPath = next;
    }

    syncLocation();
    setInterval(syncLocation, 500);
})();
