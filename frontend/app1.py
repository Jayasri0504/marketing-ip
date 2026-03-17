import json

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components


st.set_page_config(page_title="AI Marketing Dashboard UI", layout="wide")


BACKEND_STREAM_URL = "http://127.0.0.1:8000/stream-crawl"


def inject_streamlit_shell():
    st.markdown(
        """
        <style>
            .stApp {
                background:
                    radial-gradient(circle at top left, rgba(59, 130, 246, 0.20), transparent 28%),
                    radial-gradient(circle at top right, rgba(168, 85, 247, 0.22), transparent 30%),
                    linear-gradient(135deg, #07111f 0%, #0a1730 46%, #121f48 100%);
                color: #e5eefb;
            }

            [data-testid="stHeader"] {
                background: transparent;
            }

            .main .block-container {
                max-width: 1500px;
                padding-top: 1.5rem;
                padding-bottom: 2rem;
            }

            div[data-testid="stForm"],
            div[data-testid="stDataFrame"],
            div[data-testid="stAlert"] {
                border-radius: 22px;
            }

            div[data-testid="stDataFrame"] {
                border: 1px solid rgba(255, 255, 255, 0.12);
                overflow: hidden;
                background: rgba(10, 17, 37, 0.72);
                box-shadow: 0 24px 80px rgba(2, 6, 23, 0.30);
            }

            .stTextInput > div > div > input {
                background: rgba(10, 17, 37, 0.72);
                border: 1px solid rgba(255, 255, 255, 0.12);
                color: #e5eefb;
                border-radius: 16px;
            }

            .stButton > button {
                border-radius: 16px;
                min-height: 3rem;
                border: 1px solid rgba(255, 255, 255, 0.10);
                background: linear-gradient(135deg, #2563eb, #7c3aed);
                color: white;
                font-weight: 600;
            }

            .stCaption, .stMarkdown, label {
                color: #dbe7ff;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state():
    if "app1_products" not in st.session_state:
        st.session_state.app1_products = []
    if "app1_error" not in st.session_state:
        st.session_state.app1_error = None


def normalize_products(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["rating", "review_count", "avg_sentiment"]:
        if col not in df.columns:
            df[col] = 0.0
    if "availability" not in df.columns:
        df["availability"] = "Unknown"

    df["rating"] = pd.to_numeric(df["rating"], errors="coerce").fillna(0)
    df["review_count"] = pd.to_numeric(df["review_count"], errors="coerce").fillna(0)
    df["avg_sentiment"] = pd.to_numeric(df["avg_sentiment"], errors="coerce").fillna(0)

    dedup_col = "product_url" if "product_url" in df.columns else "product_name"
    df = df.drop_duplicates(subset=[dedup_col]).reset_index(drop=True)

    max_reviews = df["review_count"].max() or 1
    df["ranking_score"] = (
        df["rating"] * 0.4
        + (df["review_count"] / (max_reviews + 1)) * 0.3
        + df["avg_sentiment"] * 0.3
    )
    df = df.sort_values("ranking_score", ascending=False).reset_index(drop=True)
    df["Rank"] = df.index + 1

    def classify_status(row):
        rating = row["rating"]
        sentiment = row["avg_sentiment"]
        reviews = row["review_count"]
        if rating >= 4 and sentiment > 0.3 and reviews >= 20:
            return "Promote"
        if reviews >= 30 and sentiment < 0:
            return "Improve"
        if reviews < 10 and sentiment > 0.2:
            return "Advertise More"
        return "Rework"

    df["marketing_status"] = df.apply(classify_status, axis=1)

    if "marketing_recommendation" in df.columns:
        def pick_value(rec, key):
            return rec.get(key) if isinstance(rec, dict) else None

        for key in [
            "primary_platform",
            "secondary_platform",
            "platform_confidence",
            "secondary_confidence",
            "category",
            "rules_triggered",
        ]:
            df[key] = df["marketing_recommendation"].apply(lambda rec: pick_value(rec, key))

    if "sentiment_source" not in df.columns:
        df["sentiment_source"] = "none"

    return df


def fetch_products(url: str) -> list[dict]:
    response = requests.get(
        BACKEND_STREAM_URL,
        params={"url": url},
        stream=True,
        timeout=600,
    )
    response.raise_for_status()

    all_products = []
    status_placeholder = st.empty()
    table_placeholder = st.empty()

    status_placeholder.markdown(
        """
        <div style="
            background: rgba(10, 17, 37, 0.72);
            border: 1px solid rgba(255,255,255,0.10);
            box-shadow: 0 24px 80px rgba(2, 6, 23, 0.30);
            backdrop-filter: blur(18px);
            border-radius: 24px;
            padding: 18px 20px;
            color: #e5eefb;
        ">
            <div style="font-size: 0.78rem; letter-spacing: 0.22em; text-transform: uppercase; color: #9fb3d9;">Live Analysis</div>
            <div style="margin-top: 8px; font-size: 1.05rem; font-weight: 600;">Scraping in progress. Products will populate the dashboard as they stream from the backend.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for line in response.iter_lines(decode_unicode=True):
        if not line or line.startswith(":") or not line.startswith("data: "):
            continue

        raw = line[6:].strip()
        if not raw:
            continue

        try:
            product = json.loads(raw)
        except Exception:
            continue

        if "error" in product:
            st.warning(product["error"])
            continue

        all_products.append(product)
        df_live = pd.DataFrame(all_products)
        status_placeholder.markdown(
            f"""
            <div style="
                background: rgba(10, 17, 37, 0.72);
                border: 1px solid rgba(255,255,255,0.10);
                box-shadow: 0 24px 80px rgba(2, 6, 23, 0.30);
                backdrop-filter: blur(18px);
                border-radius: 24px;
                padding: 18px 20px;
                color: #e5eefb;
            ">
                <div style="font-size: 0.78rem; letter-spacing: 0.22em; text-transform: uppercase; color: #9fb3d9;">Live Analysis</div>
                <div style="margin-top: 8px; font-size: 1.05rem; font-weight: 600;">{len(df_live)} products analyzed so far.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        live_cols = [
            col for col in ["product_name", "price", "rating", "review_count", "avg_sentiment"]
            if col in df_live.columns
        ]
        if live_cols:
            table_placeholder.dataframe(df_live[live_cols], use_container_width=True, hide_index=True)

    return all_products


def make_matrix_points(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []

    reviews_min = float(df["review_count"].min())
    reviews_max = float(df["review_count"].max())
    sentiment_min = float(df["avg_sentiment"].min())
    sentiment_max = float(df["avg_sentiment"].max())

    def scale_review(value: float) -> float:
        if reviews_max == reviews_min:
            return 50.0
        return 18 + ((value - reviews_min) / (reviews_max - reviews_min)) * 64

    def scale_sentiment(value: float) -> float:
        if sentiment_max == sentiment_min:
            return 50.0
        return 18 + ((sentiment_max - value) / (sentiment_max - sentiment_min)) * 58

    color_map = {
        "Promote": "bg-emerald-400",
        "Advertise More": "bg-sky-400",
        "Improve": "bg-amber-400",
        "Rework": "bg-rose-400",
    }

    points = []
    for _, row in df.iterrows():
        points.append(
            {
                "name": row.get("product_name", "Product"),
                "x": round(scale_review(float(row.get("review_count", 0))), 1),
                "y": round(scale_sentiment(float(row.get("avg_sentiment", 0))), 1),
                "color": color_map.get(row.get("marketing_status", "Rework"), "bg-slate-400"),
            }
        )
    return points


def build_payload(products: list[dict]) -> dict:
    if not products:
        return {
            "hasData": False,
            "metrics": [],
            "topProducts": [],
            "products": [],
            "recommendationBuckets": [],
            "aiContent": [],
            "performanceBars": [],
            "sentimentMix": [],
            "matrixDots": [],
            "budgetAllocation": [],
        }

    df = normalize_products(pd.DataFrame(products))

    avg_rating = round(df["rating"].replace(0, pd.NA).mean(), 2) if not df.empty else 0
    avg_sentiment = round(df["avg_sentiment"].mean(), 3) if not df.empty else 0
    total_reviews = int(df["review_count"].sum()) if not df.empty else 0

    top_channel = (
        df["primary_platform"].fillna("Unavailable").value_counts().idxmax()
        if "primary_platform" in df.columns and not df["primary_platform"].dropna().empty
        else "Unavailable"
    )
    top_product = df.iloc[0]["product_name"] if not df.empty else "Unavailable"

    metrics = [
        {"label": "Products Analyzed", "value": str(len(df)), "change": "Live crawl results from backend"},
        {"label": "Average Rating", "value": str(avg_rating), "change": f"{total_reviews} total reviews collected"},
        {"label": "Average Sentiment", "value": str(avg_sentiment), "change": "Calculated from reviews or text signals"},
        {"label": "Top Channel", "value": str(top_channel), "change": f"Highest-fit product: {top_product}"},
    ]

    top_products = []
    for _, row in df.head(10).iterrows():
        top_products.append(
            {
                "Rank": f"#{int(row['Rank'])}",
                "Product": row.get("product_name", "-"),
                "Channel": row.get("primary_platform", "-"),
                "Score": round(float(row.get("ranking_score", 0)) * 20, 1),
                "Rating": round(float(row.get("rating", 0)), 2),
                "Reviews": int(row.get("review_count", 0)),
            }
        )

    products_table = []
    for _, row in df.iterrows():
        products_table.append(
            {
                "Product": row.get("product_name", "-"),
                "Category": row.get("category", row.get("brand", "-")),
                "Rating": round(float(row.get("rating", 0)), 2),
                "Reviews": int(row.get("review_count", 0)),
                "Sentiment": round(float(row.get("avg_sentiment", 0)), 3),
                "Status": row.get("marketing_status", "-"),
                "Channel": row.get("primary_platform", "-"),
            }
        )

    recommendation_buckets = []
    for status, color in [
        ("Promote", "emerald"),
        ("Advertise More", "sky"),
        ("Improve", "amber"),
        ("Rework", "rose"),
    ]:
        group = df[df["marketing_status"] == status]
        recommendation_buckets.append(
            {
                "title": status,
                "color": color,
                "copy": f"{len(group)} product(s) currently fall into the {status.lower()} bucket based on rating, reviews, and sentiment.",
                "items": group["product_name"].tolist(),
            }
        )

    ai_content = []
    for _, row in df.iterrows():
        recommendation = row.get("marketing_recommendation")
        generated = recommendation.get("generated_content") if isinstance(recommendation, dict) else None
        if not isinstance(generated, dict):
            continue
        ai_content.append(
            {
                "product": row.get("product_name", "-"),
                "channel": row.get("primary_platform", "-"),
                "caption": generated.get("caption", "Not available"),
                "promo_copy": generated.get("promo_copy", "Not available"),
                "ad_description": generated.get("ad_description", "Not available"),
                "cta": generated.get("call_to_action", "Not available"),
                "hashtags": generated.get("hashtags", []),
            }
        )
    performance_bars = []
    if "primary_platform" in df.columns:
        channel_counts = df["primary_platform"].fillna("Unknown").value_counts()
        max_count = channel_counts.max() if not channel_counts.empty else 1
        for channel, count in channel_counts.head(6).items():
            performance_bars.append(
                {
                    "label": str(channel),
                    "value": round((count / max_count) * 100),
                }
            )

    sentiment_mix = [
        {
            "label": "Positive",
            "value": int((df["avg_sentiment"] > 0.05).sum()),
            "color": "from-emerald-400 to-emerald-500",
        },
        {
            "label": "Neutral",
            "value": int(((df["avg_sentiment"] >= -0.05) & (df["avg_sentiment"] <= 0.05)).sum()),
            "color": "from-sky-400 to-sky-500",
        },
        {
            "label": "Negative",
            "value": int((df["avg_sentiment"] < -0.05).sum()),
            "color": "from-rose-400 to-rose-500",
        },
    ]

    budget_allocation = []
    if "primary_platform" in df.columns and not df["primary_platform"].dropna().empty:
        channel_counts = df["primary_platform"].fillna("Unknown").value_counts()
        total = int(channel_counts.sum()) or 1
        for channel, count in channel_counts.head(6).items():
            budget_allocation.append(
                {
                    "label": str(channel),
                    "value": f"{round((count / total) * 100, 1)}%",
                }
            )

    return {
        "hasData": True,
        "metrics": metrics,
        "topProducts": top_products,
        "products": products_table,
        "recommendationBuckets": recommendation_buckets,
        "aiContent": ai_content,
        "performanceBars": performance_bars,
        "sentimentMix": sentiment_mix,
        "matrixDots": make_matrix_points(df),
        "budgetAllocation": budget_allocation,
    }


def build_html(payload: dict) -> str:
    payload_json = json.dumps(payload)
    return (
        """
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>AI Marketing Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script crossorigin src="https://unpkg.com/react@18/umd/react.development.js"></script>
    <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <style>
      body {{ margin: 0; font-family: Inter, ui-sans-serif, system-ui, sans-serif; background:
        radial-gradient(circle at top left, rgba(59,130,246,.20), transparent 28%),
        radial-gradient(circle at top right, rgba(168,85,247,.22), transparent 30%),
        linear-gradient(135deg, #07111f 0%, #0a1730 46%, #121f48 100%); color: #e5eefb; }}
      * {{ box-sizing: border-box; }}
      .glass {{ background: rgba(10,17,37,.72); border: 1px solid rgba(255,255,255,.10); box-shadow: 0 24px 80px rgba(2,6,23,.30); backdrop-filter: blur(18px); }}
      .scrollbar-soft::-webkit-scrollbar {{ width: 10px; height: 10px; }}
      .scrollbar-soft::-webkit-scrollbar-thumb {{ background: rgba(148,163,184,.32); border-radius: 999px; }}
      .grid-pattern {{ background-image: linear-gradient(rgba(255,255,255,.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.04) 1px, transparent 1px); background-size: 28px 28px; }}
    </style>
  </head>
  <body class="min-h-screen">
    <div id="root"></div>
    <script>window.__DASHBOARD_DATA__ = __PAYLOAD__;</script>
    <script type="text/babel">
      const {{ useMemo, useState }} = React;
      const dashboardData = window.__DASHBOARD_DATA__;
      const navItems = [
        {{ id: "dashboard", label: "Dashboard", icon: "home" }},
        {{ id: "performance", label: "Performance Metrics", icon: "chart" }},
        {{ id: "top10", label: "Top 10 Products", icon: "trophy" }},
        {{ id: "products", label: "All Products", icon: "cube" }},
        {{ id: "recommendations", label: "Marketing Recommendation", icon: "megaphone" }},
        {{ id: "content", label: "AI Content Generation", icon: "sparkles" }},
      ];

      function Icon({{ name, className = "h-5 w-5" }}) {{
        const props = {{ className, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "1.8", strokeLinecap: "round", strokeLinejoin: "round" }};
        const icons = {{
          home: <svg {{...props}}><path d="M3 10.5 12 3l9 7.5" /><path d="M5 9.5V21h14V9.5" /></svg>,
          chart: <svg {{...props}}><path d="M4 20h16" /><path d="M7 16v-5" /><path d="M12 16V6" /><path d="M17 16v-8" /></svg>,
          trophy: <svg {{...props}}><path d="M8 21h8" /><path d="M12 17v4" /><path d="M7 4h10v4a5 5 0 0 1-10 0V4Z" /><path d="M7 6H4a3 3 0 0 0 3 3" /><path d="M17 6h3a3 3 0 0 1-3 3" /></svg>,
          cube: <svg {{...props}}><path d="m12 3 8 4.5v9L12 21 4 16.5v-9L12 3Z" /><path d="m12 12 8-4.5" /><path d="m12 12-8-4.5" /><path d="M12 12v9" /></svg>,
          megaphone: <svg {{...props}}><path d="m3 11 13-5v12L3 13v-2Z" /><path d="M16 8c2.2 0 4 1.8 4 4s-1.8 4-4 4" /><path d="M6 13v4a2 2 0 0 0 2 2h1" /></svg>,
          sparkles: <svg {{...props}}><path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8L12 3Z" /><path d="M19 4v4" /><path d="M21 6h-4" /><path d="M5 16v5" /><path d="M7.5 18.5h-5" /></svg>,
        }};
        return icons[name] || icons.home;
      }}

      function SidebarItem({{ item, active, onClick }}) {{
        return <button onClick={{() => onClick(item.id)}} className={{[
          "group flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left transition-all duration-200",
          active ? "bg-gradient-to-r from-blue-500/25 to-violet-500/25 text-white shadow-lg shadow-blue-950/30 ring-1 ring-white/10" : "text-slate-300 hover:bg-white/8 hover:text-white"
        ].join(" ")}}>
          <span className={{["flex h-10 w-10 items-center justify-center rounded-xl border transition-all duration-200", active ? "border-white/15 bg-white/10" : "border-white/10 bg-white/5 group-hover:border-white/20"].join(" ")}}><Icon name={{item.icon}} /></span>
          <div><div className="text-sm font-semibold">{{item.label}}</div><div className="text-xs text-slate-400">{{item.id === "dashboard" ? "Overview and performance" : "Open section"}}</div></div>
        </button>;
      }}

      function MetricCard({{ label, value, change }}) {{
        return <div className="glass rounded-3xl p-5 transition duration-300 hover:-translate-y-1 hover:border-white/20">
          <p className="text-xs uppercase tracking-[0.22em] text-slate-400">{{label}}</p>
          <div className="mt-3 text-3xl font-semibold tracking-tight text-white">{{value}}</div>
          <p className="mt-2 text-sm text-slate-300">{{change}}</p>
        </div>;
      }}

      function Panel({{ title, subtitle, action, children }}) {{
        return <div className="glass rounded-[28px] p-6">
          <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div><h3 className="text-lg font-semibold text-white">{{title}}</h3>{{subtitle ? <p className="mt-1 text-sm text-slate-300">{{subtitle}}</p> : null}}</div>
            {{action}}
          </div>
          {{children}}
        </div>;
      }}

      function EmptyState() {{
        return <div className="glass rounded-[32px] p-10 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-gradient-to-br from-blue-500/20 to-violet-500/20 text-white"><Icon name="sparkles" className="h-8 w-8" /></div>
          <h2 className="mt-5 text-2xl font-semibold text-white">Ready to analyze a website</h2>
          <p className="mx-auto mt-3 max-w-2xl text-sm leading-7 text-slate-300">Start a scrape from the controls above. The same dashboard theme stays visible while the backend streams products, and the React views will populate with the full live result set after analysis completes.</p>
        </div>;
      }}

      function ProgressChart() {{
        const items = dashboardData.performanceBars || [];
        if (!items.length) return <div className="rounded-2xl border border-dashed border-white/15 bg-white/5 p-8 text-sm text-slate-300">No channel performance data available.</div>;
        return <div className="space-y-4">{{items.map((item) => <div key={{item.label}}>
          <div className="mb-2 flex items-center justify-between text-sm text-slate-300"><span>{{item.label}}</span><span>{{item.value}}%</span></div>
          <div className="h-3 rounded-full bg-slate-800/80"><div className="h-3 rounded-full bg-gradient-to-r from-cyan-400 via-blue-500 to-violet-500" style={{{{ width: `${{item.value}}%` }}}} /></div>
        </div>)}}</div>;
      }}

      function SentimentCard() {{
        const items = dashboardData.sentimentMix || [];
        const total = items.reduce((sum, item) => sum + item.value, 0);
        if (!items.length || total === 0) return <div className="rounded-2xl border border-dashed border-white/15 bg-white/5 p-8 text-sm text-slate-300">No sentiment distribution data available.</div>;
        return <div className="grid gap-5 lg:grid-cols-[180px_1fr]">
          <div className="mx-auto flex h-44 w-44 items-center justify-center rounded-full border border-white/10 bg-[conic-gradient(from_210deg,_#22c55e_0deg,_#22c55e_223deg,_#38bdf8_223deg,_#38bdf8_309deg,_#fb7185_309deg,_#fb7185_360deg)] p-3">
            <div className="flex h-full w-full flex-col items-center justify-center rounded-full bg-slate-950/90 text-center"><div className="text-3xl font-semibold text-white">{{total}}</div><div className="text-xs uppercase tracking-[0.2em] text-slate-400">Products</div></div>
          </div>
          <div className="space-y-4">{{items.map((item) => <div key={{item.label}} className="rounded-2xl border border-white/10 bg-white/5 p-4">
            <div className="flex items-center justify-between"><span className="text-sm font-medium text-white">{{item.label}}</span><span className="text-sm text-slate-300">{{item.value}}</span></div>
            <div className="mt-3 h-2.5 rounded-full bg-slate-800"><div className={{`h-2.5 rounded-full bg-gradient-to-r ${{item.color}}`}} style={{{{ width: `${{Math.max((item.value / total) * 100, 6)}}%` }}}} /></div>
          </div>)}}</div>
        </div>;
      }}

      function OpportunityMatrix() {{
        const dots = dashboardData.matrixDots || [];
        return <div className="relative h-[320px] overflow-hidden rounded-[24px] border border-white/10 bg-slate-950/60 p-6">
          <div className="grid-pattern absolute inset-0 opacity-60" />
          <div className="absolute left-1/2 top-0 h-full w-px border-l border-dashed border-white/20" />
          <div className="absolute left-0 top-1/2 h-px w-full border-t border-dashed border-white/20" />
          <div className="absolute left-6 top-6 text-xs uppercase tracking-[0.2em] text-slate-400">Sentiment High</div>
          <div className="absolute bottom-6 right-6 text-xs uppercase tracking-[0.2em] text-slate-400">Review Volume High</div>
          <div className="absolute right-6 top-8 rounded-full bg-emerald-400/10 px-3 py-1 text-xs text-emerald-300">Promote</div>
          <div className="absolute right-6 bottom-8 rounded-full bg-amber-400/10 px-3 py-1 text-xs text-amber-300">Improve</div>
          <div className="absolute left-6 top-8 rounded-full bg-sky-400/10 px-3 py-1 text-xs text-sky-300">Advertise More</div>
          <div className="absolute left-6 bottom-8 rounded-full bg-rose-400/10 px-3 py-1 text-xs text-rose-300">Re-evaluate</div>
          {{dots.map((dot) => <div key={{dot.name}} className="group absolute" style={{{{ left: `${{dot.x}}%`, top: `${{dot.y}}%` }}}}>
            <div className={{`h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full ${{dot.color}} shadow-[0_0_22px_rgba(96,165,250,0.45)]`}} />
            <div className="pointer-events-none absolute left-3 top-0 hidden rounded-xl border border-white/10 bg-slate-950/95 px-3 py-2 text-xs text-slate-200 group-hover:block">{{dot.name}}</div>
          </div>)}}
        </div>;
      }}

      function ProductTable({{ rows, compact = false }}) {{
        if (!rows.length) return <div className="rounded-2xl border border-dashed border-white/15 bg-white/5 p-8 text-sm text-slate-300">No rows available.</div>;
        return <div className="overflow-hidden rounded-[24px] border border-white/10 bg-slate-950/50">
          <div className="overflow-x-auto scrollbar-soft">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-white/10 bg-white/5 text-slate-300"><tr>{{Object.keys(rows[0]).map((key) => <th key={{key}} className="px-4 py-3 font-medium">{{key}}</th>)}}</tr></thead>
              <tbody>{{rows.map((row, index) => <tr key={{index}} className="border-b border-white/5 text-slate-200 transition hover:bg-white/5">
                {{Object.values(row).map((value, valueIndex) => <td key={{valueIndex}} className={{compact ? "px-4 py-3" : "px-4 py-4"}}>{{value}}</td>)}}
              </tr>)}}</tbody>
            </table>
          </div>
        </div>;
      }}

      function RecommendationCard({{ bucket }}) {{
        const colorMap = {{ emerald: "from-emerald-500/25 to-emerald-400/10 border-emerald-400/20", sky: "from-sky-500/25 to-sky-400/10 border-sky-400/20", amber: "from-amber-500/25 to-amber-400/10 border-amber-400/20", rose: "from-rose-500/25 to-rose-400/10 border-rose-400/20" }};
        return <div className={{`rounded-[24px] border bg-gradient-to-br p-5 ${{colorMap[bucket.color]}} transition duration-300 hover:-translate-y-1`}}>
          <div className="text-lg font-semibold text-white">{{bucket.title}}</div>
          <p className="mt-2 text-sm text-slate-200">{{bucket.copy}}</p>
          <div className="mt-4 rounded-2xl border border-white/10 bg-slate-950/30 p-3">
            {{(bucket.items || []).length ? <div className="max-h-64 space-y-2 overflow-y-auto pr-1 scrollbar-soft">
              {{bucket.items.map((item, index) => <div key={{item + index}} className="rounded-xl border border-white/8 bg-white/8 px-3 py-2 text-sm text-slate-100">{{item}}</div>)}}
            </div> : <span className="text-xs text-slate-300">No products in this bucket.</span>}}
          </div>
        </div>;
      }}

      function DashboardHome() {{
        return <div className="space-y-6">
          <section className="glass relative overflow-hidden rounded-[32px] p-8">
            <div className="absolute -right-16 -top-16 h-48 w-48 rounded-full bg-violet-500/20 blur-3xl" />
            <div className="absolute -left-12 bottom-0 h-40 w-40 rounded-full bg-blue-500/20 blur-3xl" />
            <div className="relative">
              <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.24em] text-slate-200"><Icon name="sparkles" className="h-4 w-4" />AI Marketing Command Center</div>
              <h1 className="mt-5 max-w-3xl text-4xl font-semibold tracking-tight text-white md:text-5xl">Real backend-connected marketing analytics dashboard</h1>
              <p className="mt-4 max-w-2xl text-base leading-7 text-slate-300">This React UI is powered by the live FastAPI crawl stream and the same product analytics flow your backend already produces.</p>
            </div>
          </section>
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">{{dashboardData.metrics.map((metric) => <MetricCard key={{metric.label}} {{...metric}} />)}}</div>
          <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
            <Panel title="Top 10 Product Snapshot" subtitle="Highest scoring products across rating, reviews, and platform fit."><ProductTable compact rows={{dashboardData.topProducts}} /></Panel>
            <Panel title="Channel Momentum" subtitle="Relative strength by recommended channel in the current dataset."><ProgressChart /></Panel>
          </div>
        </div>;
      }}

      function PerformanceView() {{
        const [showCharts, setShowCharts] = useState(false);
        return <div className="space-y-6">
          <Panel title="Performance Metrics" subtitle="Charts and matrix stay hidden until the user chooses to reveal them." action={<button onClick={{() => setShowCharts((value) => !value)}} className="rounded-2xl bg-gradient-to-r from-blue-500 to-violet-500 px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-950/30 transition hover:scale-[1.02]">{{showCharts ? "Hide Charts & Matrix" : "Show Charts & Matrix"}}</button>}>
            <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">{{dashboardData.metrics.map((metric) => <MetricCard key={{metric.label}} {{...metric}} />)}}</div>
          </Panel>
          {{showCharts ? <div className="space-y-6">
            <div className="grid gap-6 xl:grid-cols-2">
              <Panel title="Performance by Channel" subtitle="Live distribution of recommended channels from backend results."><ProgressChart /></Panel>
              <Panel title="Sentiment Distribution" subtitle="Derived from reviews, descriptions, or product names when needed."><SentimentCard /></Panel>
            </div>
            <Panel title="Opportunity Matrix" subtitle="Products positioned by review volume and sentiment."><OpportunityMatrix /></Panel>
          </div> : <Panel title="Charts Hidden" subtitle="Click the button above to reveal all charts and the matrix view for this section."><div className="rounded-[24px] border border-dashed border-white/15 bg-white/5 px-6 py-10 text-center text-slate-300">Charts and matrix are hidden until the user opens them.</div></Panel>}}
        </div>;
      }}

      function Top10View() {{ return <Panel title="Top 10 Products" subtitle="Ranked directly from the live crawl dataset."><ProductTable rows={{dashboardData.topProducts}} /></Panel>; }}
      function ProductsView() {{ return <Panel title="All Products" subtitle="Every product received from the backend, normalized and scored for the dashboard."><ProductTable rows={{dashboardData.products}} /></Panel>; }}

      function RecommendationsView() {{
        return <div className="space-y-6">
          <Panel title="Marketing Recommendation" subtitle="Bucketed actions based on product status and backend recommendation output.">
            <div className="grid gap-5 md:grid-cols-2">{{dashboardData.recommendationBuckets.map((bucket) => <RecommendationCard key={{bucket.title}} bucket={{bucket}} />)}}</div>
          </Panel>
          <Panel title="Budget Guidance" subtitle="Suggested share by recommended channel in the current dataset.">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">{{(dashboardData.budgetAllocation || []).map((item) => <div key={{item.label}} className="rounded-3xl border border-white/10 bg-white/5 p-5 transition hover:-translate-y-1"><div className="text-sm text-slate-400">{{item.label}}</div><div className="mt-2 text-3xl font-semibold text-white">{{item.value}}</div></div>)}}</div>
          </Panel>
        </div>;
      }}

      function ContentView() {{
        return <Panel title="AI Content Generation" subtitle="Generated content is pulled from the backend recommendation payload.">
          <div className="grid gap-5 lg:grid-cols-3">
            {{(dashboardData.aiContent || []).length ? dashboardData.aiContent.map((item) => <details key={{item.product}} className="group rounded-[26px] border border-white/10 bg-white/5 p-5 transition duration-300 open:border-white/20 hover:-translate-y-1 hover:border-white/20">
              <summary className="list-none cursor-pointer">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-3"><div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500/30 to-violet-500/30"><Icon name="sparkles" className="h-5 w-5 text-white" /></div><div><div className="font-semibold text-white">{{item.product}}</div><div className="text-sm text-slate-400">{{item.channel}}</div></div></div>
                  <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300 transition group-open:bg-white/10"><span className="group-open:hidden">Show Details</span><span className="hidden group-open:inline">Hide Details</span></div>
                </div>
                <p className="mt-5 text-sm leading-7 text-slate-300">{{item.caption}}</p>
              </summary>
              <div className="mt-5 space-y-4 border-t border-white/10 pt-5">
                <div className="rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-sm text-slate-100"><div className="mb-2 text-xs uppercase tracking-[0.2em] text-slate-400">Promotional Copy</div><div>{{item.promo_copy}}</div></div>
                <div className="rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-sm text-slate-100"><div className="mb-2 text-xs uppercase tracking-[0.2em] text-slate-400">Ad Description</div><div>{{item.ad_description}}</div></div>
                <div className="rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-sm text-slate-100"><div className="mb-2 text-xs uppercase tracking-[0.2em] text-slate-400">Call To Action</div><div>{{item.cta}}</div></div>
                <div className="rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-sm text-slate-100"><div className="mb-3 text-xs uppercase tracking-[0.2em] text-slate-400">Hashtags</div><div className="flex flex-wrap gap-2">{{(item.hashtags || []).length ? item.hashtags.map((tag) => <span key={{tag}} className="rounded-full border border-white/10 bg-white/8 px-3 py-1 text-xs text-slate-100">{{tag}}</span>) : <span className="text-slate-300">No hashtags available.</span>}}</div></div>
              </div>
            </details>) : <div className="rounded-2xl border border-dashed border-white/15 bg-white/5 p-8 text-sm text-slate-300">No AI-generated content is available in the current results.</div>}}
          </div>
        </Panel>;
      }}

      function App() {{
        const [active, setActive] = useState("dashboard");
        if (!dashboardData.hasData) return <div className="min-h-screen p-4 md:p-6"><div className="mx-auto max-w-[1400px]"><EmptyState /></div></div>;

        const currentView = useMemo(() => {{
          if (active === "dashboard") return <DashboardHome />;
          if (active === "performance") return <PerformanceView />;
          if (active === "top10") return <Top10View />;
          if (active === "products") return <ProductsView />;
          if (active === "recommendations") return <RecommendationsView />;
          if (active === "content") return <ContentView />;
          return <DashboardHome />;
        }}, [active]);

        return <div className="min-h-screen p-4 md:p-6">
          <div className="mx-auto flex min-h-[92vh] max-w-[1600px] flex-col gap-6 lg:flex-row">
            <aside className="glass w-full rounded-[32px] p-5 lg:w-[320px] lg:flex-shrink-0">
              <div className="rounded-[28px] border border-white/10 bg-gradient-to-br from-blue-500/20 via-sky-500/10 to-violet-500/20 p-5">
                <div className="flex items-center gap-3"><div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/10 text-white"><Icon name="sparkles" className="h-6 w-6" /></div><div><div className="text-lg font-semibold text-white">AI Marketing Compaign</div><div className="text-sm text-slate-300">Dashboard</div></div></div>
              </div>
              <div className="mt-6 space-y-2">{{navItems.map((item) => <SidebarItem key={{item.id}} item={{item}} active={{active === item.id}} onClick={{setActive}} />)}}</div>
            </aside>
            <main className="flex-1">{{currentView}}</main>
          </div>
        </div>;
      }}

      ReactDOM.createRoot(document.getElementById("root")).render(<App />);
    </script>
  </body>
</html>
"""
        .replace("__PAYLOAD__", payload_json)
        .replace("{{", "{")
        .replace("}}", "}")
    )


def main():
    init_state()

    st.title("AI Marketing Compaign ")
    #st.caption("React dashboard linked to the real FastAPI backend. `frontend/app.py` remains unchanged.")

    with st.container(border=True):
        col1, col2 = st.columns([4, 1])
        with col1:
            url = st.text_input("Website URL", placeholder="https://example.com")
        with col2:
            st.markdown("<div style='height: 1.95rem;'></div>", unsafe_allow_html=True)
            analyze = st.button("Analyze Website", type="primary", use_container_width=True)

        if analyze:
            if not url:
                st.warning("Please enter a valid URL.")
            else:
                try:
                    st.session_state.app1_error = None
                    products = fetch_products(url)
                    st.session_state.app1_products = products
                    if not products:
                        st.warning("No products were returned from the backend.")
                    else:
                        st.success(f"Analysis complete. Loaded {len(products)} products into the React dashboard.")
                except requests.exceptions.RequestException as exc:
                    st.session_state.app1_error = (
                        "Could not reach the FastAPI backend. Make sure it is running on "
                        f"`{BACKEND_STREAM_URL}`. Error: {exc}"
                    )
                except Exception as exc:
                    st.session_state.app1_error = f"Unexpected error while loading backend data: {exc}"

    if st.session_state.app1_error:
        st.error(st.session_state.app1_error)

    payload = build_payload(st.session_state.app1_products)
    components.html(build_html(payload), height=3200, scrolling=True)


main()
