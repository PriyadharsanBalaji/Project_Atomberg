"""
Rate-limited Atomberg “Smart Fan” Share-of-Voice Agent
"""
import time, re, json
from typing import TypedDict, List, Dict
from textblob import TextBlob

from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.rate_limiters import InMemoryRateLimiter
from tavily import TavilyClient

from config import Config


# ---------------------------------------------------------------------------
# State passed between graph nodes
# ---------------------------------------------------------------------------
class AgentState(TypedDict):
    query: str
    search_results: List[Dict]
    processed_results: List[Dict]
    sov_analysis: Dict
    insights: List[str]
    batch_size: int


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
class RateLimitedSmartFanSoVAgent:
    def __init__(self):
        # Gemini free tier ⇒ keep ≤4 req/min
        self._llm_rl = InMemoryRateLimiter(
            requests_per_second=0.067, check_every_n_seconds=1, max_bucket_size=5
        )
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=Config.GEMINI_API_KEY,
            temperature=0.1,
            rate_limiter=self._llm_rl,
        )

        self.tavily = TavilyClient(api_key=Config.TAVILY_API_KEY)

        self.atomberg_kw = [
            "atomberg", "atom berg", "atomberg fan",
            "atomberg smart fan", "atomberg ceiling fan", "atomberg bldc"
        ]
        self.competitor_kw = [
            "havells", "orient", "bajaj", "crompton",
            "usha", "luminous", "superfan", "gorilla fan", "fanzart"
        ]

        # tunables
        self.max_queries          = 3           # search queries
        self.max_results_per_qry  = 8           # Tavily items per query
        self.processing_batch_size = 5          # results per LLM batch

    # --------------------------------------------------------------------- #
    # 1. Search (Tavily)
    # --------------------------------------------------------------------- #
    def _search(self, state: AgentState) -> AgentState:
        query = state["query"]
        templates = [
            f"{query}",
            f"{query} review 2024",
            f"best {query}"
        ]

        docs: List[Dict] = []
        for q in templates:
            # enforce Tavily rate-limit
            if not Config.TAVILY_RATE_LIMITER.can_make_request():
                wait = Config.TAVILY_RATE_LIMITER.wait_time_needed()
                time.sleep((wait or 1) + 1)

            try:
                res = self.tavily.search(
                    query=q,
                    max_results=self.max_results_per_qry,
                    search_depth="basic",
                    include_raw_content=False
                )
                Config.TAVILY_RATE_LIMITER.record_request()

                for itm in res.get("results", []):
                    docs.append({
                        "title":   itm.get("title", ""),
                        "url":     itm.get("url", ""),
                        "content": itm.get("content", ""),
                        "score":   itm.get("score", 0.0),
                        "search_q": q
                    })
                time.sleep(0.5)           # light pause between searches
            except Exception as e:
                print("Tavily error:", e)

        # de-dupe & cap at 20 docs
        seen, uniq = set(), []
        for d in docs:
            if d["url"] not in seen and len(uniq) < 20:
                uniq.append(d)
                seen.add(d["url"])

        state["search_results"] = uniq
        return state

    # --------------------------------------------------------------------- #
    # helper – manual keyword & sentiment tally (no API cost)
    # --------------------------------------------------------------------- #
    def _manual_analysis(self, doc: Dict) -> Dict:
        txt = (doc["title"] + " " + doc["content"]).lower()
        atom_ct = sum(len(re.findall(fr"\b{k}\b", txt)) for k in self.atomberg_kw)

        comp_ct: Dict[str, int] = {}
        for c in self.competitor_kw:
            n = len(re.findall(fr"\b{c}\b", txt))
            if n:
                comp_ct[c] = n

        sent = TextBlob(txt).sentiment.polarity
        return {"atomberg_mentions": atom_ct, "competitor_mentions": comp_ct, "sentiment": sent}

    # --------------------------------------------------------------------- #
    # 2. Process content (batched LLM prompt + manual fallback)
    # --------------------------------------------------------------------- #
    def _process(self, state: AgentState) -> AgentState:
        docs = state["search_results"]
        processed: List[Dict] = []
        batches = [docs[i:i + self.processing_batch_size] for i in range(0, len(docs), self.processing_batch_size)]

        sys_prompt = ChatPromptTemplate.from_template(
            "For each result below give JSON with brands & sentiment.\n{batch}"
        )

        for b in batches:
            # Gemini rate-limit
            if not Config.GEMINI_RATE_LIMITER.can_make_request():
                wait = Config.GEMINI_RATE_LIMITER.wait_time_needed()
                time.sleep((wait or 1) + 1)

            batch_txt = "\n---\n".join(
                f"Title: {d['title']}\nContent: {d['content'][:500]}..." for d in b
            )

            try:
                self.llm.invoke(sys_prompt.format(batch=batch_txt))
                Config.GEMINI_RATE_LIMITER.record_request()
            except Exception as e:
                # ignore – manual analysis still happens
                print("Gemini error (ignored):", e)

            for d in b:
                ma = self._manual_analysis(d)
                processed.append({**d, "manual": ma, "sentiment": ma["sentiment"]})

            time.sleep(1)

        state["processed_results"] = processed
        return state

    # --------------------------------------------------------------------- #
    # 3. Calculate SoV
    # --------------------------------------------------------------------- #
    def _calc_sov(self, state: AgentState) -> AgentState:
        docs = state["processed_results"]

        total, atom, atom_sent_sum, atom_sent_ct = 0, 0, 0.0, 0
        comp_map: Dict[str, int] = {}
        tot_eng, atom_eng = 0.0, 0.0

        for d in docs:
            ma = d["manual"]
            a = ma["atomberg_mentions"]
            c_total = sum(ma["competitor_mentions"].values())

            total += a + c_total
            atom  += a

            for k, v in ma["competitor_mentions"].items():
                comp_map[k] = comp_map.get(k, 0) + v

            if a:
                atom_sent_sum += ma["sentiment"] * a
                atom_sent_ct  += a

            eng = d["score"] * len(d["content"])
            tot_eng += eng
            if a:
                atom_eng += eng

        sov            = (atom / total * 100) if total else 0
        eng_sov        = (atom_eng / tot_eng * 100) if tot_eng else 0
        avg_sent       = (atom_sent_sum / atom_sent_ct) if atom_sent_ct else 0
        atom_docs      = [d for d in docs if d["manual"]["atomberg_mentions"]]
        pos_share      = (sum(1 for d in atom_docs if d["manual"]["sentiment"] > 0.1)
                          / len(atom_docs) * 100) if atom_docs else 0

        state["sov_analysis"] = {
            "docs_analyzed": len(docs),
            "total_mentions": total,
            "atomberg_mentions": atom,
            "competitor_mentions": comp_map,
            "sov_pct": round(sov, 2),
            "engagement_sov_pct": round(eng_sov, 2),
            "avg_sentiment": round(avg_sent, 3),
            "positive_sentiment_share_pct": round(pos_share, 2),
            "top_competitors": sorted(comp_map.items(), key=lambda x: x[1], reverse=True)[:5],
        }
        return state

    # --------------------------------------------------------------------- #
    # 4. Insights (rule-based to save tokens)
    # --------------------------------------------------------------------- #
    def _insights(self, state: AgentState) -> AgentState:
        s = state["sov_analysis"]
        out: List[str] = []

        if s["sov_pct"] < 20:
            out.append("Low SoV (<20 %)—invest in SEO, influencer unboxings and comparison videos.")
        if s["avg_sentiment"] < 0:
            out.append("Net negative sentiment—launch satisfaction-driven testimonial campaigns.")
        if s["avg_sentiment"] > 0.3:
            out.append("Strong positive sentiment—amplify user reviews and case-studies.")
        if s["top_competitors"]:
            top = s["top_competitors"][0]
            out.append(f"Primary competitor online: {top.title()} ({top[1]} mentions).")

        state["insights"] = out
        return state

    # ------------------------------------------------------------------ #
    # Build LangGraph workflow
    # ------------------------------------------------------------------ #
    def _graph(self):
        g = StateGraph(AgentState)
        g.add_node("search",   self._search)
        g.add_node("process",  self._process)
        g.add_node("analyze",  self._calc_sov)
        g.add_node("insights", self._insights)

        g.add_edge("search",   "process")
        g.add_edge("process",  "analyze")
        g.add_edge("analyze",  "insights")
        g.add_edge("insights", END)

        g.set_entry_point("search")
        return g.compile()

    # ------------------------------------------------------------------ #
    # Public entry
    # ------------------------------------------------------------------ #
    def run(self, query: str = "smart fan") -> Dict:
        wf   = self._graph()
        init = AgentState(
            query=query,
            search_results=[], processed_results=[],
            sov_analysis={}, insights=[],
            batch_size=self.processing_batch_size
        )
        t0   = time.time()
        res  = wf.invoke(init)
        res["execution_sec"] = round(time.time() - t0, 2)
        return res
