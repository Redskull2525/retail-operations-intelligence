"""Generate the PBIR report definition (RetailOperations.Report) and the PBIP shell files.

Usage (from the repo root):  python powerbi/tools/build_report.py

Writes JSON that follows Microsoft's public PBIR schemas (report 3.1.0, page 2.0.0,
visualContainer 2.5.0). Re-running overwrites RetailOperations.Report/definition/ and the
custom theme; it does not touch the semantic model (see build_semantic_model.ps1).
"""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

PBI = Path(__file__).resolve().parent.parent
REPORT = PBI / "RetailOperations.Report"
MODEL = PBI / "RetailOperations.SemanticModel"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"
VC = f"{SCHEMA}/item/report/definition/visualContainer/2.5.0/schema.json"
NS = uuid.UUID("6f1d3c52-6b8e-4c1e-9a43-7f0b5d2e9a10")  # fixed -> stable logicalIds

BANNER_TEXT = "Synthetic data — portfolio demonstration"
NAVY, TEAL, AMBER, CORAL, SLATE = "#1F3A5F", "#2A9D8F", "#E9A23B", "#E76F51", "#6C7A89"
PAGE_BG = "#F3F5F8"
W, H, M = 1280, 720, 16  # canvas and outer margin


def write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- expression helpers
def lit(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def text_lit(s: str) -> dict:
    return lit("'" + s.replace("'", "''") + "'")


def color(hex_: str) -> dict:
    return {"solid": {"color": text_lit(hex_)}}


def measure(name: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": "_Measures"}}, "Property": name}}


def column(table: str, name: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}}


def qref(field: dict) -> str:
    kind = next(iter(field))
    return f"{field[kind]['Expression']['SourceRef']['Entity']}.{field[kind]['Property']}"


def proj(field: dict, active: bool = False, display: str | None = None) -> dict:
    p = {"field": field, "queryRef": qref(field), "nativeQueryRef": field[next(iter(field))]["Property"]}
    if active:
        p["active"] = True
    if display:
        p["displayName"] = display
    return p


def container(title: str | None, background: str | None = "#FFFFFF") -> dict:
    objs: dict = {}
    if title:
        objs["title"] = [{"properties": {
            "show": lit("true"), "text": text_lit(title),
            "fontColor": color(NAVY), "fontSize": lit("12D"), "bold": lit("true")}}]
    else:
        objs["title"] = [{"properties": {"show": lit("false")}}]
    if background:
        objs["background"] = [{"properties": {"show": lit("true"), "color": color(background),
                                              "transparency": lit("0D")}}]
    objs["border"] = [{"properties": {"show": lit("true"), "color": color("#DDE3EA"),
                                      "radius": lit("6D")}}]
    return objs


class Page:
    def __init__(self, name: str, display: str, subtitle: str):
        self.name, self.display, self.subtitle = name, display, subtitle
        self.visuals: list[dict] = []
        self.z = 0
        self.banner()

    def add(self, name: str, x, y, w, h, visual: dict) -> None:
        self.z += 1000
        self.visuals.append({
            "$schema": VC,
            "name": name[:20],
            "position": {"x": x, "y": y, "z": self.z, "height": h, "width": w, "tabOrder": self.z},
            "visual": visual,
        })

    # -- visual factories -------------------------------------------------------------
    def banner(self) -> None:
        paragraphs = [
            {"textRuns": [{"value": f"Retail Operations Intelligence  |  {self.display}",
                           "textStyle": {"fontWeight": "bold", "fontSize": "18pt", "color": "#FFFFFF"}}]},
            {"textRuns": [{"value": f"{BANNER_TEXT}  ·  {self.subtitle}",
                           "textStyle": {"fontSize": "11pt", "color": "#E6EDF5"}}]},
        ]
        vis = {"visualType": "textbox",
               "objects": {"general": [{"properties": {"paragraphs": paragraphs}}]},
               "visualContainerObjects": {
                   "title": [{"properties": {"show": lit("false")}}],
                   "background": [{"properties": {"show": lit("true"), "color": color(NAVY),
                                                  "transparency": lit("0D")}}]}}
        self.add("banner", 0, 0, W, 64, vis)

    def textbox(self, name, x, y, w, h, paragraphs) -> None:
        vis = {"visualType": "textbox",
               "objects": {"general": [{"properties": {"paragraphs": paragraphs}}]},
               "visualContainerObjects": container(None)}
        self.add(name, x, y, w, h, vis)

    def card(self, name, x, y, w, h, m: str, label: str) -> None:
        vis = {"visualType": "card",
               "query": {"queryState": {"Values": {"projections": [proj(measure(m), display=label)]}}},
               "objects": {
                   "labels": [{"properties": {"fontSize": lit("22D"), "labelDisplayUnits": lit("1D"),
                                              "color": color(NAVY)}}],
                   "categoryLabels": [{"properties": {"show": lit("true"), "fontSize": lit("10D")}}]},
               "visualContainerObjects": container(None)}
        self.add(name, x, y, w, h, vis)

    def slicer(self, name, x, y, w, h, table, col, header) -> None:
        f = column(table, col)
        vis = {"visualType": "slicer",
               "query": {"queryState": {"Values": {"projections": [proj(f, active=True)]}},
                         "sortDefinition": {"sort": [{"field": f, "direction": "Ascending"}],
                                            "isDefaultSort": True}},
               "objects": {"data": [{"properties": {"mode": text_lit("Dropdown")}}],
                           "header": [{"properties": {"text": text_lit(header), "show": lit("true")}}]},
               "visualContainerObjects": container(None)}
        self.add(name, x, y, w, h, vis)

    def chart(self, name, x, y, w, h, vtype, title, category, values, series=None, tooltips=None,
              sort=None, labels=False, extra_roles=None) -> None:
        qs: dict = {"Category": {"projections": [proj(category, active=True)]},
                    "Y": {"projections": [proj(v) for v in values]}}
        if series:
            qs["Series"] = {"projections": [proj(series)]}
        if tooltips:
            qs["Tooltips"] = {"projections": [proj(t) for t in tooltips]}
        if extra_roles:
            qs.update(extra_roles)
        query: dict = {"queryState": qs}
        if sort:
            query["sortDefinition"] = {"sort": [{"field": sort[0], "direction": sort[1]}], "isDefaultSort": True}
        objects: dict = {}
        if labels:
            objects["labels"] = [{"properties": {"show": lit("true")}}]
        vis = {"visualType": vtype, "query": query, "visualContainerObjects": container(title)}
        if objects:
            vis["objects"] = objects
        self.add(name, x, y, w, h, vis)

    def table(self, name, x, y, w, h, title, fields, font_rules=(), sort=None) -> None:
        query: dict = {"queryState": {"Values": {"projections": [
            proj(*f) if isinstance(f, tuple) else proj(f) for f in fields]}}}
        if sort:
            query["sortDefinition"] = {"sort": [{"field": sort[0], "direction": sort[1]}], "isDefaultSort": True}
        values = [{"properties": {"fontColor": {"solid": {"color": {"expr": measure(rule_measure)}}}},
                   "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}],
                                "metadata": qref(target)}}
                  for target, rule_measure in font_rules]
        objects: dict = {"total": [{"properties": {"totals": lit("true")}}]}
        if values:
            objects["values"] = values
        vis = {"visualType": "tableEx", "query": query, "objects": objects,
               "visualContainerObjects": container(title)}
        self.add(name, x, y, w, h, vis)

    def save(self, root: Path) -> None:
        pdir = root / self.name
        write(pdir / "page.json", {
            "$schema": f"{SCHEMA}/item/report/definition/page/2.0.0/schema.json",
            "name": self.name, "displayName": self.display, "displayOption": "FitToPage",
            "height": H, "width": W,
            "objects": {"background": [{"properties": {"color": color(PAGE_BG), "transparency": lit("0D")}}]},
        })
        for v in self.visuals:
            write(pdir / "visuals" / v["name"] / "visual.json", v)


# ---------------------------------------------------------------- layout helpers
def row(n: int, y: int, h: int, gap: int = 8):
    w = (W - 2 * M - gap * (n - 1)) / n
    return [(round(M + i * (w + gap), 1), y, round(w, 1), h) for i in range(n)]


def sales_slicers(p: Page, with_date=True, with_channel=True) -> None:
    specs = []
    if with_date:
        specs.append(("DimDate", "Month Year", "Month"))
    specs += [("DimRegion", "Region", "Region"), ("DimProduct", "Category", "Category")]
    if with_channel:
        specs.append(("FactSales", "Channel", "Channel"))
    for (t, c, hdr), (x, y, w, h) in zip(specs, row(len(specs), 72, 68)):
        p.slicer(f"sl_{c.replace(' ', '').lower()}", x, y, w, h, t, c, hdr)


def build_pages() -> list[Page]:
    month = column("DimDate", "Month Year")
    region = column("DimRegion", "Region")
    category = column("DimProduct", "Category")
    product = column("DimProduct", "Product")
    channel = column("FactSales", "Channel")
    status = column("FactInventory", "Stock Status")

    # 1. Executive overview ----------------------------------------------------------
    p1 = Page("Overview", "Executive Overview", "FY 2025 completed sales (returns excluded)")
    sales_slicers(p1)
    for (x, y, w, h), (m, lbl) in zip(row(5, 148, 86), [
            ("Total Revenue", "Revenue"), ("Gross Profit", "Gross Profit"), ("Gross Margin %", "Gross Margin %"),
            ("Orders", "Orders"), ("Avg Order Value", "Avg Order Value (AOV)")]):
        p1.card(f"kpi_{m.replace(' ', '').replace('%', 'pct').lower()}", x, y, w, h, m, lbl)
    (a, b) = row(2, 240, 228)
    p1.chart("revenue_trend", *a, "lineChart", "Monthly revenue", month, [measure("Total Revenue")],
             sort=(month, "Ascending"))
    p1.chart("mom_growth", *b, "clusteredColumnChart", "Month-over-month revenue growth %", month,
             [measure("MoM Growth %")], sort=(month, "Ascending"), labels=True)
    (a, b) = row(2, 476, 228)
    p1.chart("revenue_by_region", *a, "clusteredBarChart", "Revenue by region", region,
             [measure("Total Revenue")], tooltips=[measure("Revenue Share %"), measure("Gross Margin %")],
             sort=(measure("Total Revenue"), "Descending"), labels=True)
    p1.chart("channel_mix", *b, "donutChart", "Channel mix (share of revenue)", channel,
             [measure("Total Revenue")], tooltips=[measure("Revenue Share %")], labels=True)

    # 2. Product profitability ---------------------------------------------------------
    p2 = Page("Products", "Product Profitability", "Revenue and gross margin by product")
    sales_slicers(p2)
    p2.chart("top_products", M, 148, 470, 556, "clusteredBarChart", "Products ranked by revenue", product,
             [measure("Total Revenue")], tooltips=[measure("Gross Margin %")],
             sort=(measure("Total Revenue"), "Descending"))
    x2, w2 = M + 478, W - 2 * M - 478
    p2.chart("revenue_vs_margin", x2, 148, w2, 264, "scatterChart",
             "Revenue vs gross margin % (one dot per product, coloured by category)",
             product, [measure("Gross Margin %")], series=category,
             extra_roles={"X": {"projections": [proj(measure("Total Revenue"))]}})
    p2.table("product_table", x2, 416, w2, 288, "Product profitability (margin colour: green >= 38%, red < 32%)",
             [category, product, measure("Total Revenue"), measure("Gross Profit"),
              measure("Gross Margin %"), measure("Units Sold")],
             font_rules=[(measure("Gross Margin %"), "Margin Color")],
             sort=(measure("Total Revenue"), "Descending"))

    # 3. Inventory alerts ----------------------------------------------------------------
    p3 = Page("Inventory", "Inventory Alerts", "Stock snapshot 2025-12-31, value at cost")
    sales_slicers(p3, with_date=False, with_channel=False)
    for (x, y, w, h), (m, lbl) in zip(row(5, 148, 86), [
            ("Reorder Alerts", "Reorder alerts (rows)"), ("Overstock Alerts", "Overstock alerts (rows)"),
            ("Units To Reorder", "Units to reorder"), ("Excess Units", "Excess units"),
            ("Inventory Value", "Inventory value (at cost)")]):
        p3.card(f"kpi_{m.replace(' ', '').lower()}", x, y, w, h, m, lbl)
    p3.table("alert_table", M, 240, 820, 464,
             "Reorder / overstock items (red = Reorder, amber = Overstock)",
             [region, product, (status, False, "Status"), (measure("Alert On Hand Units"), False, "On hand"),
              (column("DimProduct", "Reorder Point"), False, "Reorder pt"),
              (column("DimProduct", "Target Stock"), False, "Target"),
              (measure("Units To Reorder"), False, "To reorder"), (measure("Excess Units"), False, "Excess"),
              (measure("Alert Inventory Value"), False, "Value (cost)")],
             font_rules=[(status, "Stock Status Color")],
             sort=(status, "Descending"))
    p3.chart("inventory_by_category", M + 828, 240, W - 2 * M - 828, 464, "barChart",
             "Inventory value by category and stock status", category, [measure("Inventory Value")],
             series=status, sort=(measure("Inventory Value"), "Descending"))

    # 4. Data quality ---------------------------------------------------------------------
    p4 = Page("Quality", "Data Quality", "What the Python pipeline found and fixed")
    for (x, y, w, h), (m, lbl) in zip(row(4, 72, 96), [
            ("Orders", "Clean sales rows (orders)"), ("Returned Lines", "Return lines kept aside"),
            ("Returns Units", "Units returned"), ("Returns Value", "Value of returns")]):
        p4.card(f"kpi_{m.replace(' ', '').lower()}", x, y, w, h, m, lbl)

    def para(text, bold=False, size="12pt", col="#1F2933"):
        style = {"fontSize": size, "color": col}
        if bold:
            style["fontWeight"] = "bold"
        return {"textRuns": [{"value": text, "textStyle": style}]}

    issues = [("Exact duplicate rows", "60", "Removed (kept first copy)"),
              ("Missing region", "15", "Kept the sale; region set to 'Unknown'"),
              ("Messy region text", "60", "Trimmed + fixed capitalisation"),
              ("Messy channel text", "60", "Trimmed + fixed capitalisation"),
              ("Negative quantity (returns)", "40", "Excluded from FactSales; kept in Returns"),
              ("Date outside 2025", "12", "Removed"),
              ("Zero qty / unknown product / bad discount / conflicting IDs", "0", "Checked, nothing found")]
    left = [para("Issues found in the raw file (injected on purpose)", bold=True, size="13pt", col=NAVY)]
    left += [para(f"• {c}: {n} rows → {h}") for c, n, h in issues]
    p4.textbox("issues_text", M, 176, 760, 236, left)
    right = [para("Row flow", bold=True, size="13pt", col=NAVY),
             para("6,060 raw rows"), para("→ 6,000 after removing duplicates"),
             para("→ 5,988 after the 2025 date filter"), para("→ 5,948 clean sales + 40 returns (87 units)")]
    p4.textbox("rowflow_text", M + 768, 176, W - 2 * M - 768, 236, right)
    notes = [para("Checks on the cleaned data: no duplicate order_id, all quantities > 0, no negative revenue, "
                  "all dates in 2025, standard regions/channels — all PASS.", bold=True),
             para("Returns are not linked to their original orders, so they are excluded from revenue KPIs and "
                  "reported separately here. Source: reports/data_quality_report.md (generated by src/pipeline.py)."),
             para(f"{BANNER_TEXT}: every number comes from src/generate_data.py with seed 42. "
                  "No real company, revenue or customer is represented.")]
    p4.textbox("notes_text", M, 420, W - 2 * M, 140, notes)
    return [p1, p2, p3, p4]


def theme() -> dict:
    return {
        "name": "RetailOpsTheme",
        "dataColors": [TEAL, NAVY, AMBER, CORAL, SLATE, "#7B6FA6", "#8AB17D", "#B56576"],
        "foreground": "#1F2933", "background": "#FFFFFF", "tableAccent": NAVY,
        "good": "#1B7F5B", "neutral": "#B9770E", "bad": "#C0392B",
        "textClasses": {
            "callout": {"fontSize": 22, "fontFace": "Segoe UI Semibold", "color": NAVY},
            "title": {"fontSize": 12, "fontFace": "Segoe UI Semibold", "color": NAVY},
            "label": {"fontSize": 10, "fontFace": "Segoe UI", "color": "#3E4C59"},
        },
    }


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--active-page", default=None, help="page name to open first (default: first page)")
    args = ap.parse_args()
    defn = REPORT / "definition"
    if defn.exists():
        shutil.rmtree(defn)
    pages = build_pages()
    for p in pages:
        p.save(defn / "pages")
    write(defn / "pages" / "pages.json", {
        "$schema": f"{SCHEMA}/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p.name for p in pages], "activePageName": args.active_page or pages[0].name})
    write(defn / "version.json", {
        "$schema": f"{SCHEMA}/item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    write(defn / "report.json", {
        "$schema": f"{SCHEMA}/item/report/definition/report/3.1.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": "CY24SU10",
                          "reportVersionAtImport": {"visual": "1.8.95", "report": "2.0.95", "page": "1.3.95"},
                          "type": "SharedResources"},
            "customTheme": {"name": "RetailOpsTheme.json",
                            "reportVersionAtImport": {"visual": "2.5.0", "report": "3.1.0", "page": "2.0.0"},
                            "type": "RegisteredResources"}},
        "objects": {"section": [{"properties": {"verticalAlignment": text_lit("Top")}}]},
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": "RetailOpsTheme.json", "path": "RetailOpsTheme.json", "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized",
                     "defaultDrillFilterOtherVisuals": True, "allowChangeFilterTypes": True,
                     "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True},
    })
    write(REPORT / "StaticResources" / "RegisteredResources" / "RetailOpsTheme.json", theme())
    base = REPORT / "StaticResources" / "SharedResources" / "BaseThemes" / "CY24SU10.json"
    if not base.exists():
        raise SystemExit(f"Missing base theme {base} (Microsoft CY24SU10 theme, MIT; see powerbi/README).")

    write(REPORT / "definition.pbir", {
        "$schema": f"{SCHEMA}/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": "../RetailOperations.SemanticModel"}}})
    platform = f"{SCHEMA}/gitIntegration/platformProperties/2.0.0/schema.json"
    write(REPORT / ".platform", {"$schema": platform,
                                 "metadata": {"type": "Report", "displayName": "RetailOperations"},
                                 "config": {"version": "2.0", "logicalId": str(uuid.uuid5(NS, "report"))}})
    write(MODEL / ".platform", {"$schema": platform,
                                "metadata": {"type": "SemanticModel", "displayName": "RetailOperations"},
                                "config": {"version": "2.0", "logicalId": str(uuid.uuid5(NS, "model"))}})
    write(MODEL / "definition.pbism", {
        "$schema": f"{SCHEMA}/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2", "settings": {}})
    write(PBI / "RetailOperations.pbip", {
        "$schema": f"{SCHEMA}/pbip/pbipProperties/1.0.0/schema.json", "version": "1.0",
        "artifacts": [{"report": {"path": "RetailOperations.Report"}}],
        "settings": {"enableAutoRecovery": True}})
    n = sum(len(p.visuals) for p in pages)
    print(f"Wrote {len(pages)} pages, {n} visuals to {REPORT}")


if __name__ == "__main__":
    main()
