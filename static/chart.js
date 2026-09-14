/* Chart renderer bersama: dipakai halaman detail dan laporan PDF.
   Ekspos window.renderBIChart(el, type, rows). */
(function () {
  var PIE_COLORS = ["#1985a0", "#e67e22", "#27ae60", "#c0392b", "#8e44ad", "#95a5a6"];
  var STATUS_COLORS = {
    CO: "#1985a0",
    RE: "#e67e22",
    CL: "#27ae60",
    IP: "#c0392b",
    DR: "#8e44ad",
  };
  var COMPLIANCE_COLORS = {
    "Tepat Jadwal": "#27ae60",
    "Dikerjakan Lebih Awal": "#1985a0",
    "Terlambat": "#e67e22",
    "Belum Dikerjakan": "#c0392b",
  };

  function fmt(value) {
    return Number(value).toLocaleString("id-ID", { maximumFractionDigits: 0 });
  }
  function fmtA(v) {
    var n = Number(v);
    if (!isFinite(n)) return "-";
    if (Math.abs(n) >= 1e9) return (n / 1e9).toLocaleString("id-ID", { maximumFractionDigits: 2 }) + " M";
    if (Math.abs(n) >= 1e6) return (n / 1e6).toLocaleString("id-ID", { maximumFractionDigits: 1 }) + " jt";
    if (Math.abs(n) >= 1e3) return n.toLocaleString("id-ID", { maximumFractionDigits: 0 });
    return String(n);
  }
  function fmtH(v) {
    return (v === null || v === undefined ? "-" : Number(v).toLocaleString("id-ID", { maximumFractionDigits: 1 }) + " hari");
  }
  function baseGrid(top) {
    return { left: 8, right: 16, top: top || 40, bottom: 8, containLabel: true };
  }

  window.renderBIChart = function (el, type, rows) {
    if (!el) return null;
    if (type === "none" || !rows || !rows.length) {
      el.innerHTML = '<div class="empty">Tidak ada data untuk ditampilkan</div>';
      return null;
    }
    var chart = echarts.init(el);
    if (type === "pie") {
      chart.setOption({
        tooltip: { trigger: "item", formatter: function (p) { return p.name + ": " + fmt(p.value) + " (" + p.percent + "%)"; } },
        legend: { orient: "horizontal", bottom: 0, itemWidth: 14, itemHeight: 14 },
        color: PIE_COLORS,
        series: [{
          type: "pie",
          radius: ["42%", "68%"],
          center: ["50%", "44%"],
          data: rows.map(function (r) { return { name: r.x, value: Number(r.y), itemStyle: { color: STATUS_COLORS[r.x] || COMPLIANCE_COLORS[r.x] || "#95a5a6" } }; }),
          label: { formatter: "{b}\n{d}%", fontSize: 12 },
          labelLine: { length: 12, length2: 8 },
        }],
      });
    } else if (type === "line") {
      var names0 = rows.map(function (r) { return r.x; });
      var series = [{
        name: "Total", type: "line", data: rows.map(function (r) { return Number(r.total); }),
        smooth: true, itemStyle: { color: "#1985a0" }, lineStyle: { width: 3 },
      }, {
        name: "SCH", type: "line", data: rows.map(function (r) { return Number(r.sch); }),
        smooth: true, itemStyle: { color: "#27ae60" },
      }];
      if (rows.some(function (r) { return r.req !== undefined; })) {
        series.push({ name: "REQ", type: "line", data: rows.map(function (r) { return Number(r.req); }), smooth: true, itemStyle: { color: "#e67e22" } });
      }
      chart.setOption({
        tooltip: { trigger: "axis" },
        legend: { top: 0, right: 8, itemWidth: 14, itemHeight: 10, textStyle: { fontSize: 12 } },
        grid: baseGrid(),
        xAxis: { type: "category", data: names0, axisLabel: { fontSize: 11 } },
        yAxis: { type: "value", axisLabel: { formatter: fmt } },
        series: series,
      });
    } else if (type === "pareto") {
      var namesP = rows.map(function (r) { return r.x; });
      var clas = function (c) { return (c <= 80 ? "#c0392b" : (c <= 95 ? "#e67e22" : "#27ae60")); };
      chart.setOption({
        tooltip: { trigger: "axis" },
        legend: { top: 0, right: 8, itemWidth: 14, itemHeight: 10, textStyle: { fontSize: 12 } },
        grid: { left: 8, right: 8, top: 40, bottom: 8, containLabel: true },
        xAxis: { type: "category", data: namesP, axisLabel: { fontSize: 10, rotate: 40, interval: 0 } },
        yAxis: [
          { name: "Qty", type: "value", axisLabel: { formatter: fmt } },
          { name: "% Kumulatif", type: "value", max: 100, position: "right" },
        ],
        series: [
          { name: "Qty", type: "bar", data: rows.map(function (r) { return { value: Number(r.y), itemStyle: { color: clas(Number(r.cum)) } }; }), barWidth: 14 },
          {
            name: "% Kumulatif", type: "line", yAxisIndex: 1,
            data: rows.map(function (r) { return Number(r.cum); }),
            itemStyle: { color: "#1985a0" }, lineStyle: { width: 2 }, smooth: false,
            markLine: { symbol: "none", data: [{ yAxis: 80, lineStyle: { type: "dashed", color: "#c0392b" }, label: { formatter: "80%", position: "insideEndTop" } }] },
          },
        ],
      });
    } else if (type === "mtbf_mttr") {
      var namesM = rows.map(function (r) { return r.x; });
      chart.setOption({
        tooltip: {
          trigger: "axis", axisPointer: { type: "shadow" },
          formatter: function (p) { return p[0].name + "<br>" + p.map(function (s) { return s.marker + s.seriesName + ": <b>" + fmtH(s.value) + "</b>"; }).join("<br>"); },
        },
        legend: { top: 0, right: 8, itemWidth: 14, itemHeight: 10, textStyle: { fontSize: 12 } },
        grid: baseGrid(),
        xAxis: { type: "category", data: namesM, axisLabel: { fontSize: 10, rotate: 40, interval: 0 } },
        yAxis: { type: "value", axisLabel: { formatter: fmt } },
        series: [
          { name: "MTTR (hari)", type: "bar", data: rows.map(function (r) { return r.mttr; }), itemStyle: { color: "#e67e22" }, barWidth: 12 },
          { name: "MTBF (hari)", type: "bar", data: rows.map(function (r) { return r.mtbf; }), itemStyle: { color: "#1985a0" }, barWidth: 12 },
        ],
      });
    } else if (type === "teknisi") {
      var techs = Object.keys(rows[0] || {}).filter(function (k) { return k !== "bulan"; });
      chart.setOption({
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
        legend: { top: 0, right: 8, itemWidth: 14, itemHeight: 10, textStyle: { fontSize: 12 } },
        grid: baseGrid(),
        xAxis: { type: "category", data: rows.map(function (r) { return r.bulan; }), axisLabel: { fontSize: 10 } },
        yAxis: { type: "value", axisLabel: { formatter: fmt } },
        series: techs.map(function (t, i) {
          return { name: t, type: "bar", stack: "wl", data: rows.map(function (r) { return Number(r[t]); }), itemStyle: { color: PIE_COLORS[i % PIE_COLORS.length] } };
        }),
      });
    } else {
      var names = rows.map(function (r) { return r.x; });
      var values = rows.map(function (r) { return Number(r.y) || 0; });
      var max = Math.max.apply(null, values.concat([1]));
      chart.setOption({
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, formatter: function (p) { return p[0].name + "<br><b>" + fmt(p[0].value) + "</b>"; } },
        grid: { left: 8, right: 86, top: 16, bottom: 8, containLabel: true },
        xAxis: {
          type: "value",
          axisLabel: { formatter: fmtA, color: "#8a94a3" },
          splitLine: { lineStyle: { type: "dashed", color: "#e8eef2" } },
        },
        yAxis: {
          type: "category",
          data: names.slice().reverse(),
          axisLabel: { fontSize: 12, color: "#33414f", width: 170, overflow: "truncate" },
          axisLine: { show: false },
          axisTick: { show: false },
        },
        series: [{
          type: "bar",
          barWidth: "56%",
          data: values.slice().reverse().map(function (v) {
            return {
              value: v,
              itemStyle: {
                borderRadius: [0, 12, 12, 0],
                color: {
                  type: "linear", x: 0, y: 0, x2: 1, y2: 0,
                  colorStops: [
                    { offset: 0, color: v === max ? "#e67e22" : "#0c5c72" },
                    { offset: 1, color: v === max ? "#f5b342" : "#0fa3ad" },
                  ],
                },
              },
            };
          }),
          label: { show: true, position: "right", distance: 6, fontSize: 11, fontWeight: 600, color: "#33414f", formatter: function (p) { return fmtA(p.value); } },
          showBackground: true,
          backgroundStyle: { color: "#f2f7f9", borderRadius: [0, 12, 12, 0] },
        }],
      });
    }
    return chart;
  };
})();