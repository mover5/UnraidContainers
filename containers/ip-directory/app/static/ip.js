(function () {
  const script = document.currentScript;
  const api = script.dataset.api;
  const detailUrl = script.dataset.detail;
  const hoursSelect = document.getElementById("hours");

  function fmtBytes(n) {
    const units = ["B", "KB", "MB", "GB", "TB"];
    let i = 0;
    while (n >= 1000 && i < units.length - 1) { n /= 1000; i++; }
    return (i === 0 ? n.toFixed(0) : n.toFixed(1)) + " " + units[i];
  }

  function el(tag, attrs, text) {
    const e = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([k, v]) => e.setAttribute(k, v));
    if (text !== undefined) e.textContent = text;
    return e;
  }

  // Sent bars above the axis, received below — same layout as the Grafana panels.
  function drawChart(traffic) {
    const box = document.getElementById("chart");
    box.textContent = "";
    const sent = traffic.sent || [];
    const recv = traffic.received || [];
    const n = Math.max(sent.length, recv.length);
    if (!n) { box.appendChild(el("p", { class: "muted" }, "No samples in this range.")); return; }
    const max = Math.max(1, ...sent.map(p => p[1]), ...recv.map(p => p[1]));
    const W = 1000, H = 180, mid = H / 2, bw = W / n;
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.setAttribute("preserveAspectRatio", "none");
    const add = (x, y, h, color, title) => {
      const r = document.createElementNS(ns, "rect");
      r.setAttribute("x", x); r.setAttribute("y", y);
      r.setAttribute("width", Math.max(bw - 1, 1)); r.setAttribute("height", Math.max(h, 0));
      r.style.fill = color;
      const t = document.createElementNS(ns, "title"); t.textContent = title; r.appendChild(t);
      svg.appendChild(r);
    };
    for (let i = 0; i < n; i++) {
      const s = sent[i], r = recv[i];
      if (s && s[1] > 0) { const h = (s[1] / max) * (mid - 2); add(i * bw, mid - h, h, "var(--sent)", `${new Date(s[0]).toLocaleString()} sent ${fmtBytes(s[1])}`); }
      if (r && r[1] > 0) { const h = (r[1] / max) * (mid - 2); add(i * bw, mid, h, "var(--recv)", `${new Date(r[0]).toLocaleString()} received ${fmtBytes(r[1])}`); }
    }
    const axis = document.createElementNS(ns, "line");
    axis.setAttribute("x1", 0); axis.setAttribute("x2", W); axis.setAttribute("y1", mid); axis.setAttribute("y2", mid);
    axis.style.stroke = "var(--border)";
    svg.appendChild(axis);
    box.appendChild(svg);
    box.appendChild(el("p", { class: "muted" }, `Peak hour: ${fmtBytes(max)}`));
  }

  function table(rows, cols) {
    if (!rows.length) return el("p", { class: "muted" }, "None in this range.");
    const t = el("table");
    const head = el("tr");
    cols.forEach(c => head.appendChild(el("th", c.num ? { class: "num" } : {}, c.label)));
    t.appendChild(head);
    rows.forEach(r => {
      const tr = el("tr");
      cols.forEach(c => {
        const td = el("td", c.num ? { class: "num" } : {});
        const v = c.render(r);
        if (v instanceof Node) td.appendChild(v); else td.textContent = v;
        tr.appendChild(td);
      });
      t.appendChild(tr);
    });
    return t;
  }

  function load() {
    const hours = hoursSelect.value;
    ["peers", "ports"].forEach(id => { document.getElementById(id).textContent = "Loading…"; });
    fetch(`${api}?hours=${hours}`)
      .then(r => r.json())
      .then(data => {
        if (data.error) throw new Error(data.error);
        drawChart(data.traffic);
        const peers = document.getElementById("peers");
        peers.textContent = "";
        peers.classList.remove("muted");
        peers.appendChild(table(data.peers, [
          { label: "Peer", render: p => {
              const span = el("span");
              const a = el("a", { href: detailUrl.replace("__IP__", p.peer) }, p.name || p.peer);
              span.appendChild(a);
              if (p.name) { span.appendChild(el("br")); span.appendChild(el("span", { class: "muted mono" }, p.peer)); }
              return span;
          } },
          { label: "Sent to", num: true, render: p => fmtBytes(p.sent) },
          { label: "Received from", num: true, render: p => fmtBytes(p.received) },
        ]));
        const ports = document.getElementById("ports");
        ports.textContent = "";
        ports.classList.remove("muted");
        ports.appendChild(table(data.ports, [
          { label: "Port", render: p => String(p.port) },
          { label: "Bytes", num: true, render: p => fmtBytes(p.bytes) },
        ]));
      })
      .catch(err => {
        ["chart", "peers", "ports"].forEach(id => {
          const box = document.getElementById(id);
          box.textContent = "";
          box.appendChild(el("p", { class: "err" }, `Could not load: ${err.message}`));
        });
      });
  }

  hoursSelect.addEventListener("change", load);
  load();
})();
