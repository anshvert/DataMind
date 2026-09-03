"""Visualization synthesis node generating Apache ECharts declarative JSON specifications."""
from typing import Any, Callable, Dict, List, Set
from naturallangdata.agents.bi_state import BIAgentState


def is_metric_column(key: str, data: List[Dict[str, Any]]) -> bool:
    """Determine whether a column represents a meaningful quantitative metric."""
    lower_k = key.lower()
    excluded_terms = ["year", "id", "code", "quarter", "zip", "phone", "date", "status", "active"]
    if any(term in lower_k for term in excluded_terms):
        return False

    first_val = data[0].get(key)
    if not isinstance(first_val, (int, float)):
        return False

    unique_vals: Set[Any] = {r.get(key) for r in data[:50]}
    if len(unique_vals) <= 2 and unique_vals.issubset({0, 1, 0.0, 1.0, None}):
        return False

    return True


def synthesize_echarts_spec(data: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
    """Generate Apache ECharts option JSON only when quantitative analytics exist."""
    if not data:
        return {"chartType": "none"}

    first_row = data[0]
    keys = list(first_row.keys())

    numeric_keys = [k for k in keys if is_metric_column(k, data)]
    string_keys = [k for k in keys if k not in numeric_keys]

    if not numeric_keys:
        return {"chartType": "none"}

    if len(data) == 1 and len(numeric_keys) == 1:
        num_key = numeric_keys[0]
        val = round(float(first_row[num_key] or 0.0), 2)
        return {
            "chartType": "metric_card",
            "title": {"text": query, "left": "center", "textStyle": {"color": "#475569", "fontSize": 13, "fontWeight": "normal"}},
            "graphic": [{
                "type": "text",
                "left": "center",
                "top": "middle",
                "style": {
                    "text": f"{val:,.2f}\n{num_key.replace('_', ' ').title()}",
                    "textAlign": "center",
                    "fill": "#0f766e",
                    "fontSize": 30,
                    "fontWeight": "bold",
                },
            }],
        }

    date_candidates = [
        k for k in string_keys
        if any(term in k.lower() for term in ["quarter", "date", "month", "year", "time", "day"])
    ]

    if date_candidates and len(data) > 1:
        x_key = date_candidates[0]
        unique_cats: List[str] = []
        aggregated: Dict[str, Dict[str, float]] = {}

        for row in data:
            cat = str(row.get(x_key, "")).strip()
            if cat not in aggregated:
                aggregated[cat] = {nk: 0.0 for nk in numeric_keys}
                unique_cats.append(cat)
            for nk in numeric_keys:
                try:
                    aggregated[cat][nk] += float(row.get(nk) or 0.0)
                except (ValueError, TypeError):
                    pass

        series_list: List[Dict[str, Any]] = []
        palette = ["#0f766e", "#0284c7", "#f59e0b", "#10b981"]

        for i, num_key in enumerate(numeric_keys[:3]):
            values = [round(aggregated[cat][num_key], 2) for cat in unique_cats]
            color = palette[i % len(palette)]
            series_list.append({
                "name": num_key.replace("_", " ").title(),
                "type": "line",
                "smooth": True,
                "data": values,
                "lineStyle": {"width": 3, "color": color},
                "itemStyle": {"color": color},
                "areaStyle": {"opacity": 0.08, "color": color},
                "symbolSize": 6,
            })

        return {
            "chartType": "line",
            "title": {"text": query, "left": "center", "textStyle": {"color": "#1e293b", "fontSize": 13, "fontWeight": 600}},
            "tooltip": {"trigger": "axis", "backgroundColor": "rgba(255, 255, 255, 0.95)", "borderColor": "#e2e8f0", "textStyle": {"color": "#1e293b"}},
            "legend": {"bottom": 0, "textStyle": {"color": "#64748b"}},
            "grid": {"left": "3%", "right": "4%", "bottom": "14%", "top": "16%", "containLabel": True},
            "xAxis": {"type": "category", "data": unique_cats, "axisLabel": {"color": "#64748b"}, "axisLine": {"lineStyle": {"color": "#cbd5e1"}}},
            "yAxis": {"type": "value", "axisLabel": {"color": "#64748b"}, "splitLine": {"lineStyle": {"color": "#f1f5f9"}}},
            "series": series_list,
        }

    if string_keys:
        x_key = string_keys[0]
        unique_cats = []
        aggregated = {}

        for row in data:
            cat = str(row.get(x_key, "")).strip()
            if cat not in aggregated:
                aggregated[cat] = {nk: 0.0 for nk in numeric_keys}
                unique_cats.append(cat)
            for nk in numeric_keys:
                try:
                    aggregated[cat][nk] += float(row.get(nk) or 0.0)
                except (ValueError, TypeError):
                    pass

        num_key = numeric_keys[0]
        sorted_cats = sorted(unique_cats, key=lambda c: aggregated[c][num_key], reverse=True)

        if len(sorted_cats) > 8:
            top_cats = sorted_cats[:7]
            other_sum = sum(aggregated[c][num_key] for c in sorted_cats[7:])
            aggregated["Other"] = {num_key: other_sum}
            display_cats = top_cats + ["Other"]
        else:
            display_cats = sorted_cats

        series_list = []
        palette = ["#0f766e", "#0284c7"]

        for i, nk in enumerate(numeric_keys[:2]):
            values = [round(aggregated[c].get(nk, 0.0), 2) for c in display_cats]
            series_list.append({
                "name": nk.replace("_", " ").title(),
                "type": "bar",
                "data": values,
                "itemStyle": {"borderRadius": [4, 4, 0, 0], "color": palette[i % len(palette)]},
            })

        return {
            "chartType": "bar",
            "title": {"text": query, "left": "center", "textStyle": {"color": "#1e293b", "fontSize": 13, "fontWeight": 600}},
            "tooltip": {"trigger": "axis", "backgroundColor": "rgba(255, 255, 255, 0.95)", "borderColor": "#e2e8f0", "textStyle": {"color": "#1e293b"}},
            "legend": {"bottom": 0, "textStyle": {"color": "#64748b"}},
            "grid": {"left": "3%", "right": "4%", "bottom": "16%", "top": "16%", "containLabel": True},
            "xAxis": {
                "type": "category",
                "data": display_cats,
                "axisLabel": {"color": "#64748b", "rotate": 20 if len(display_cats) > 4 else 0},
                "axisLine": {"lineStyle": {"color": "#cbd5e1"}},
            },
            "yAxis": {"type": "value", "axisLabel": {"color": "#64748b"}, "splitLine": {"lineStyle": {"color": "#f1f5f9"}}},
            "series": series_list,
        }

    return {"chartType": "none"}


def make_bi_visualizer_node() -> Callable[[BIAgentState], BIAgentState]:
    """Create a visualizer node instance generating ECharts configurations."""

    def visualizer_node(state: BIAgentState) -> BIAgentState:
        data = state.get("data_result", [])
        query = state.get("query", "")
        traces: List[Dict[str, Any]] = list(state.get("trace_steps", []))

        spec = synthesize_echarts_spec(data, query)
        chart_type = spec.get("chartType", "none")

        traces.append({
            "node": "visualizer",
            "message": f"Visualizer outcome: '{chart_type}'",
            "chart_type": chart_type,
        })

        return {
            **state,
            "chart_spec": spec,
            "trace_steps": traces,
        }

    return visualizer_node
