function createCuboidMeasurements(path, element, jobLink) {
    const button = element("button", "Khoảng cách");
    const view = element("div", "");
    view.className = "cuboid-measure";
    view.hidden = true;
    let open = false;
    let requestId = 0;

    async function request(action, frameIndex) {
        const result = await chrome.runtime.sendMessage({ action, path, frameIndex });
        if (!result || result.state === "error") {
            throw new Error(result?.message || "Không nhận được kết quả đo.");
        }
        return result;
    }

    function renderFrame(frame, target) {
        target.replaceChildren();
        if (frame.objects.length) {
            const table = element("table", "");
            const header = element("tr", "");
            for (const name of ["Cuboid", "Ngang (m)", "3D (m)"]) header.append(element("th", name));
            table.append(header);
            for (const object of frame.objects) {
                const row = element("tr", "");
                const ref = element("td", "");
                ref.append(jobLink(`${object.label} · ID ${object.idx}`, path, {
                    frame: frame.index, type: "shape", serverID: object.idx,
                }));
                row.append(ref, element("td", object.horizontal_m.toFixed(2)),
                    element("td", object.spatial_m.toFixed(2)));
                table.append(row);
            }
            target.append(table);
        } else {
            target.append(element("p", "Frame chưa có cuboid đã lưu."));
        }
        const measure = element("button", "Đo điểm LiDAR");
        const chart = element("div", "");
        target.append(measure, chart);
        measure.addEventListener("click", async () => {
            measure.disabled = true;
            chart.replaceChildren(element("p", "Đang tải point cloud của frame…"));
            try {
                const { points } = await request("points", frame.index);
                drawPointCloud(chart, points);
            } catch (error) {
                chart.replaceChildren(element("p", error.message));
            } finally {
                measure.disabled = false;
            }
        });
    }

    function drawPointCloud(target, points) {
        const canvas = element("canvas", "");
        canvas.width = canvas.height = 340;
        canvas.setAttribute("aria-label", "Point cloud nhìn từ trên xuống, phía trước ở trên.");
        const info = element("p", "Bấm một điểm để đo từ gốc LiDAR. Các vòng tương ứng 10, 30 và 50 m.");
        info.setAttribute("role", "status");
        target.replaceChildren(canvas, info);
        const ctx = canvas.getContext("2d");
        const center = canvas.width / 2;
        const scale = (center - 12) / 50;
        const position = ([x, y]) => [center - x * scale, center + y * scale];

        function draw(picked) {
            ctx.fillStyle = "#101724";
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            for (const point of points) {
                const [x, y] = position(point);
                ctx.fillStyle = point[2] > -1.45 ? "#9bccdc" : "#496277";
                ctx.fillRect(x, y, 1, 1);
            }
            ctx.strokeStyle = "#86a5bd";
            ctx.fillStyle = "#eef5fc";
            ctx.font = "11px system-ui";
            for (const distance of [10, 30, 50]) {
                ctx.beginPath();
                ctx.arc(center, center, distance * scale, 0, 2 * Math.PI);
                ctx.stroke();
                ctx.fillText(`${distance} m`, center + 4, center - distance * scale + 11);
            }
            ctx.fillRect(center - 2, center - 2, 4, 4);
            ctx.fillText("Trước (−Y)", center - 70, 13);
            ctx.fillText("Trái (+X)", 8, center - 6);
            if (picked) {
                const [x, y] = position(picked);
                ctx.strokeStyle = "#ffcc75";
                ctx.beginPath();
                ctx.moveTo(center, center);
                ctx.lineTo(x, y);
                ctx.stroke();
                ctx.fillStyle = "#ffcc75";
                ctx.fillRect(x - 3, y - 3, 6, 6);
            }
        }

        draw();
        canvas.addEventListener("click", event => {
            const bounds = canvas.getBoundingClientRect();
            const mouseX = (event.clientX - bounds.left) * canvas.width / bounds.width;
            const mouseY = (event.clientY - bounds.top) * canvas.height / bounds.height;
            let nearest;
            let best = 10 ** 2;
            for (const point of points) {
                const [x, y] = position(point);
                const delta = (x - mouseX) ** 2 + (y - mouseY) ** 2;
                if (delta < best) {
                    best = delta;
                    nearest = point;
                }
            }
            draw(nearest);
            if (nearest) {
                const [x, y, z] = nearest;
                info.textContent = `Ngang ≈ ${Math.hypot(x, y).toFixed(2)} m · 3D ≈ ${Math.hypot(x, y, z).toFixed(2)} m`;
            } else {
                info.textContent = "Chưa có điểm LiDAR gần vị trí bấm.";
            }
        });
    }

    button.addEventListener("click", async event => {
        if (!event.isTrusted) return;
        open = !open;
        const current = ++requestId;
        view.hidden = !open;
        if (!open) return;
        view.replaceChildren(element("p", "Đang đọc cuboid đã lưu…"));
        try {
            const { frames } = await request("distances");
            if (current !== requestId) return;
            const label = element("label", "Frame ");
            const selector = element("select", "");
            for (const frame of frames) {
                const option = element("option", frame.name);
                option.value = frame.index;
                selector.append(option);
            }
            const selectedFrame = new URLSearchParams(location.search).get("frame");
            if (selectedFrame !== null && frames.some(frame => frame.index === Number(selectedFrame))) {
                selector.value = selectedFrame;
            }
            const frameView = element("div", "");
            label.append(selector);
            view.replaceChildren(label, frameView);
            const show = () => renderFrame(frames.find(frame => frame.index === Number(selector.value)), frameView);
            selector.addEventListener("change", show);
            show();
        } catch (error) {
            if (current === requestId) view.replaceChildren(element("p", error.message));
        }
    });
    return { button, view };
}
