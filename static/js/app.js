async function run() {
  const q = document.getElementById("q").value.trim() || "smart fan";
  document.getElementById("loading").classList.remove("hidden");
  document.getElementById("results").classList.add("hidden");

  const res = await fetch("/analyze", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({query: q})
  });
  const data = await res.json();
  document.getElementById("loading").classList.add("hidden");

  if (!res.ok) { alert(data.error || "Error"); return; }

  // Metrics
  const m = data.metrics;
  id("sov").textContent      = m.sov_pct + "%";
  id("eng_sov").textContent  = m.engagement_sov_pct + "%";
  id("sent").textContent     = m.avg_sentiment;
  id("pos").textContent      = m.positive_sentiment_share_pct + "%";

  // Insights
  const ul = id("ins"); ul.innerHTML="";
  data.insights.forEach(t => { const li=document.createElement("li"); li.textContent=t; ul.appendChild(li); });

  // Charts
  if (window.pie) { window.pie.destroy(); window.bar.destroy(); }
  const ctx1 = id("pie"), ctx2 = id("bar");
  window.pie = new Chart(ctx1, {
    type:"doughnut",
    data:{labels:["Atomberg","Others"],
          datasets:[{data:[m.sov_pct,100-m.sov_pct],backgroundColor:["#4f46e5","#cbd5e1"]}]},
    options:{plugins:{legend:{position:"bottom"}}}
  });
  const compLabels = m.top_competitors.map(c=>c[0]);
  const compVals   = m.top_competitors.map(c=>c[1]);
  window.bar = new Chart(ctx2, {
    type:"bar",
    data:{labels:compLabels,datasets:[{label:"Mentions",data:compVals,backgroundColor:"#6366f1"}]},
    options:{scales:{y:{beginAtZero:true}}}
  });

  document.getElementById("results").classList.remove("hidden");
}
function id(x){return document.getElementById(x);}
