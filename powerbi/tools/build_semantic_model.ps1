<#
.SYNOPSIS
  Generates RetailOperations.SemanticModel/definition (TMDL) with the Tabular Object Model (TOM)
  that ships inside Power BI Desktop, so the TMDL is written by Microsoft's own serializer.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File powerbi\tools\build_semantic_model.ps1
  powershell -ExecutionPolicy Bypass -File powerbi\tools\build_semantic_model.ps1 -DataFolder "D:\repos\retail-operations-intelligence\data\processed"

  Windows PowerShell 5.1 is required (the TOM DLLs in Power BI Desktop target .NET Framework).
#>
param(
    [string]$DataFolder = (Resolve-Path (Join-Path $PSScriptRoot "..\..\data\processed")).Path,
    [string]$OutFolder  = (Join-Path $PSScriptRoot "..\RetailOperations.SemanticModel\definition"),
    [string]$PbiBin     = ""
)
$ErrorActionPreference = "Stop"

if (-not $PbiBin) {
    $pkg = Get-AppxPackage -Name "Microsoft.MicrosoftPowerBIDesktop" -ErrorAction SilentlyContinue
    if ($pkg) { $PbiBin = Join-Path $pkg.InstallLocation "bin" }
    elseif (Test-Path "C:\Program Files\Microsoft Power BI Desktop\bin") { $PbiBin = "C:\Program Files\Microsoft Power BI Desktop\bin" }
    else { throw "Power BI Desktop not found; pass -PbiBin" }
}
Add-Type -Path (Join-Path $PbiBin "Microsoft.PowerBI.Tabular.dll")
$NS = "Microsoft.AnalysisServices.Tabular"
$Rs = [string][char]0x20B9   # Indian rupee sign

$db = New-Object "$NS.Database"
$db.Name = "RetailOperations"
$db.ID = "RetailOperations"
$db.CompatibilityLevel = 1601
$model = New-Object "$NS.Model"
$model.Name = "Model"
$model.Culture = "en-US"
$model.DefaultPowerBIDataSourceVersion = [Microsoft.AnalysisServices.Tabular.PowerBIDataSourceVersion]::PowerBI_V3
$model.DiscourageImplicitMeasures = $true
$model.Description = "Retail Operations Intelligence - SYNTHETIC data (seed 42) for portfolio demonstration."
$db.Model = $model
# Turn off "Auto date/time" so Desktop does not add hidden LocalDateTable_* tables; DimDate is used instead.
$ann = New-Object "$NS.Annotation"; $ann.Name = "__PBI_TimeIntelligenceEnabled"; $ann.Value = "0"
$model.Annotations.Add($ann)

# ---- DataFolder parameter (M) ---------------------------------------------------------------
$folderLiteral = $DataFolder.TrimEnd('\').Replace('"', '""')
$param = New-Object "$NS.NamedExpression"
$param.Name = "DataFolder"
$param.Kind = [Microsoft.AnalysisServices.Tabular.ExpressionKind]::M
$param.Description = "Absolute path of the repo's data\processed folder (no trailing backslash). Change it after cloning: Transform data > Edit parameters."
$param.Expression = "`"$folderLiteral`" meta [IsParameterQuery=true, Type=`"Text`", IsParameterQueryRequired=true]"
$model.Expressions.Add($param)

function New-CsvM([string]$file, [string]$types, [string]$renames, [string]$extra = "", [string]$last = "Renamed") {
    if ($extra) { $extra = ",`n" + $extra.TrimEnd() }
@"
let
    Source = Csv.Document(File.Contents(DataFolder & "\$file"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {$types}, "en-US"),
    Renamed = Table.RenameColumns(Typed, {$renames})$extra
in
    $last
"@
}

function Add-Table([string]$name, [string]$m, [string]$desc) {
    $t = New-Object "$NS.Table"
    $t.Name = $name
    $t.Description = $desc
    $p = New-Object "$NS.Partition"
    $p.Name = "$name-partition"
    $p.Mode = [Microsoft.AnalysisServices.Tabular.ModeType]::Import
    $src = New-Object "$NS.MPartitionSource"
    $src.Expression = $m
    $p.Source = $src
    $t.Partitions.Add($p)
    $model.Tables.Add($t)
    return $t
}

function Add-Col($table, [string]$name, [string]$type, [switch]$Hidden, [string]$Format = "", [string]$SortBy = "", [switch]$Key, [string]$Desc = "") {
    $c = New-Object "$NS.DataColumn"
    $c.Name = $name
    $c.SourceColumn = $name
    $c.DataType = [Enum]::Parse([Microsoft.AnalysisServices.Tabular.DataType], $type)
    $c.SummarizeBy = [Microsoft.AnalysisServices.Tabular.AggregateFunction]::None
    if ($Hidden) { $c.IsHidden = $true }
    if ($Format) { $c.FormatString = $Format }
    if ($Key) { $c.IsKey = $true }
    if ($Desc) { $c.Description = $Desc }
    $table.Columns.Add($c)
    if ($SortBy) { $c.SortByColumn = $table.Columns[$SortBy] }
    return $c
}

# ---- DimDate (from dim_date.csv, marked as date table) ---------------------------------------
$m = New-CsvM "dim_date.csv" `
  '{"date_key", Int64.Type}, {"full_date", type date}, {"year", Int64.Type}, {"quarter", Int64.Type}, {"month", Int64.Type}, {"month_name", type text}, {"year_month", type text}, {"day_of_week", type text}' `
  '{"date_key", "Date Key"}, {"full_date", "Date"}, {"year", "Year"}, {"quarter", "Quarter Number"}, {"month", "Month Number"}, {"month_name", "Month"}, {"year_month", "Year Month"}, {"day_of_week", "Weekday"}' `
  @"
    AddQuarter = Table.AddColumn(Renamed, "Quarter", each "Q" & Text.From([Quarter Number]), type text),
    AddMonthYear = Table.AddColumn(AddQuarter, "Month Year", each Date.ToText([Date], "MMM yyyy", "en-US"), type text),
    AddYearMonthNumber = Table.AddColumn(AddMonthYear, "Year Month Number", each [Year] * 100 + [Month Number], Int64.Type)
"@ "AddYearMonthNumber"
$dimDate = Add-Table "DimDate" $m "Calendar for 2025 from data/processed/dim_date.csv. Marked as the model's date table (Date column)."
$dimDate.DataCategory = "Time"
Add-Col $dimDate "Date Key" "Int64" -Hidden | Out-Null
Add-Col $dimDate "Date" "DateTime" -Key -Format "yyyy-mm-dd" | Out-Null
Add-Col $dimDate "Year" "Int64" -Format "0" | Out-Null
Add-Col $dimDate "Quarter Number" "Int64" -Hidden | Out-Null
Add-Col $dimDate "Quarter" "String" -SortBy "Quarter Number" | Out-Null
Add-Col $dimDate "Month Number" "Int64" -Hidden | Out-Null
Add-Col $dimDate "Month" "String" -SortBy "Month Number" | Out-Null
Add-Col $dimDate "Year Month" "String" | Out-Null
Add-Col $dimDate "Year Month Number" "Int64" -Hidden | Out-Null
Add-Col $dimDate "Month Year" "String" -SortBy "Year Month Number" | Out-Null
Add-Col $dimDate "Weekday" "String" | Out-Null

# ---- DimProduct --------------------------------------------------------------------------------
$m = New-CsvM "dim_product.csv" `
  '{"product_id", type text}, {"product_name", type text}, {"category", type text}, {"unit_cost", Currency.Type}, {"unit_price", Currency.Type}, {"reorder_point", Int64.Type}, {"target_stock", Int64.Type}' `
  '{"product_id", "Product ID"}, {"product_name", "Product"}, {"category", "Category"}, {"unit_cost", "Unit Cost"}, {"unit_price", "List Price"}, {"reorder_point", "Reorder Point"}, {"target_stock", "Target Stock"}'
$dimProduct = Add-Table "DimProduct" $m "One row per product (20 products, 4 categories)."
Add-Col $dimProduct "Product ID" "String" -Hidden | Out-Null
Add-Col $dimProduct "Product" "String" | Out-Null
Add-Col $dimProduct "Category" "String" | Out-Null
Add-Col $dimProduct "Unit Cost" "Decimal" -Format "$Rs#,0" | Out-Null
Add-Col $dimProduct "List Price" "Decimal" -Format "$Rs#,0" | Out-Null
Add-Col $dimProduct "Reorder Point" "Int64" -Format "#,0" -Desc "Reorder when on-hand units fall to this level." | Out-Null
Add-Col $dimProduct "Target Stock" "Int64" -Format "#,0" -Desc "Ideal stock level; above it the row is Overstock." | Out-Null

# ---- DimRegion ---------------------------------------------------------------------------------
$m = New-CsvM "dim_region.csv" '{"region_key", Int64.Type}, {"region_name", type text}' '{"region_key", "Region Key"}, {"region_name", "Region"}'
$dimRegion = Add-Table "DimRegion" $m "Sales regions incl. 'Unknown' for sales whose region was missing in the raw file."
Add-Col $dimRegion "Region Key" "Int64" -Hidden | Out-Null
Add-Col $dimRegion "Region" "String" | Out-Null

# ---- FactSales ---------------------------------------------------------------------------------
$m = New-CsvM "fact_sales.csv" `
  '{"order_id", type text}, {"date_key", Int64.Type}, {"order_date", type date}, {"product_id", type text}, {"region_key", Int64.Type}, {"channel", type text}, {"quantity", Int64.Type}, {"unit_price", Currency.Type}, {"discount_pct", type number}, {"revenue", Currency.Type}, {"cost", Currency.Type}, {"gross_profit", Currency.Type}' `
  '{"order_id", "Order ID"}, {"date_key", "Date Key"}, {"order_date", "Order Date"}, {"product_id", "Product ID"}, {"region_key", "Region Key"}, {"channel", "Channel"}, {"quantity", "Quantity"}, {"unit_price", "Unit Price"}, {"discount_pct", "Discount %"}, {"revenue", "Revenue"}, {"cost", "Cost"}, {"gross_profit", "Gross Profit"}'
$factSales = Add-Table "FactSales" $m "One row per completed order line (5,948 rows). Returns are excluded (see Returns)."
Add-Col $factSales "Order ID" "String" | Out-Null
Add-Col $factSales "Date Key" "Int64" -Hidden | Out-Null
Add-Col $factSales "Order Date" "DateTime" -Hidden -Format "yyyy-mm-dd" | Out-Null
Add-Col $factSales "Product ID" "String" -Hidden | Out-Null
Add-Col $factSales "Region Key" "Int64" -Hidden | Out-Null
Add-Col $factSales "Channel" "String" | Out-Null
Add-Col $factSales "Quantity" "Int64" -Hidden -Format "#,0" | Out-Null
Add-Col $factSales "Unit Price" "Decimal" -Hidden -Format "$Rs#,0" | Out-Null
Add-Col $factSales "Discount %" "Double" -Hidden -Format "0%" | Out-Null
Add-Col $factSales "Revenue" "Decimal" -Hidden -Format "$Rs#,0.00" | Out-Null
Add-Col $factSales "Cost" "Decimal" -Hidden -Format "$Rs#,0.00" | Out-Null
Add-Col $factSales "Gross Profit" "Decimal" -Hidden -Format "$Rs#,0.00" | Out-Null

# ---- FactInventory -----------------------------------------------------------------------------
$m = New-CsvM "fact_inventory.csv" `
  '{"snapshot_date_key", Int64.Type}, {"product_id", type text}, {"region_key", Int64.Type}, {"on_hand_units", Int64.Type}, {"inventory_value", Currency.Type}, {"stock_status", type text}' `
  '{"snapshot_date_key", "Snapshot Date Key"}, {"product_id", "Product ID"}, {"region_key", "Region Key"}, {"on_hand_units", "On Hand Units"}, {"inventory_value", "Inventory Value"}, {"stock_status", "Stock Status"}' `
  @"
    AddSnapshotDate = Table.AddColumn(Renamed, "Snapshot Date", each #date(Number.IntegerDivide([Snapshot Date Key], 10000), Number.Mod(Number.IntegerDivide([Snapshot Date Key], 100), 100), Number.Mod([Snapshot Date Key], 100)), type date)
"@ "AddSnapshotDate"
$factInv = Add-Table "FactInventory" $m "One row per product per region on the 2025-12-31 snapshot (80 rows). Inventory value is at cost."
Add-Col $factInv "Snapshot Date Key" "Int64" -Hidden | Out-Null
Add-Col $factInv "Product ID" "String" -Hidden | Out-Null
Add-Col $factInv "Region Key" "Int64" -Hidden | Out-Null
Add-Col $factInv "On Hand Units" "Int64" -Hidden -Format "#,0" | Out-Null
Add-Col $factInv "Inventory Value" "Decimal" -Hidden -Format "$Rs#,0" | Out-Null
Add-Col $factInv "Stock Status" "String" -Desc "Reorder if on hand <= reorder point; Overstock if on hand > target stock; else Healthy." | Out-Null
Add-Col $factInv "Snapshot Date" "DateTime" -Hidden -Format "yyyy-mm-dd" | Out-Null

# ---- Returns (rows the pipeline excluded from revenue) -----------------------------------------
$m = New-CsvM "returns_excluded.csv" `
  '{"order_id", type text}, {"order_date", type date}, {"region", type text}, {"channel", type text}, {"product_id", type text}, {"quantity", Int64.Type}, {"unit_price", Currency.Type}, {"discount_pct", type number}' `
  '{"order_id", "Order ID"}, {"order_date", "Return Date"}, {"region", "Region Name"}, {"channel", "Channel"}, {"product_id", "Product ID"}, {"quantity", "Quantity"}, {"unit_price", "Unit Price"}, {"discount_pct", "Discount %"}' `
  @"
    AddReturnValue = Table.AddColumn(Renamed, "Return Value", each -[Quantity] * [Unit Price] * (1 - [#"Discount %"]), Currency.Type)
"@ "AddReturnValue"
$returns = Add-Table "Returns" $m "Return lines (negative quantity) that the pipeline kept out of FactSales: 40 rows, 87 units."
Add-Col $returns "Order ID" "String" | Out-Null
Add-Col $returns "Return Date" "DateTime" -Hidden -Format "yyyy-mm-dd" | Out-Null
Add-Col $returns "Region Name" "String" -Hidden | Out-Null
Add-Col $returns "Channel" "String" | Out-Null
Add-Col $returns "Product ID" "String" -Hidden | Out-Null
Add-Col $returns "Quantity" "Int64" -Hidden -Format "#,0" | Out-Null
Add-Col $returns "Unit Price" "Decimal" -Hidden -Format "$Rs#,0" | Out-Null
Add-Col $returns "Discount %" "Double" -Hidden -Format "0%" | Out-Null
Add-Col $returns "Return Value" "Decimal" -Hidden -Format "$Rs#,0.00" | Out-Null
$rk = New-Object "$NS.CalculatedColumn"
$rk.Name = "Region Key"
$rk.Expression = "LOOKUPVALUE ( DimRegion[Region Key], DimRegion[Region], Returns[Region Name] )"
$rk.DataType = [Microsoft.AnalysisServices.Tabular.DataType]::Int64
$rk.IsHidden = $true
$rk.SummarizeBy = [Microsoft.AnalysisServices.Tabular.AggregateFunction]::None
$rk.Description = "Region key looked up from the region name, so Returns can share the DimRegion slicer."
$returns.Columns.Add($rk)

# ---- _Measures ---------------------------------------------------------------------------------
$mt = Add-Table "_Measures" "let`n    Source = #table(type table [#`"Measure Placeholder`" = text], {})`nin`n    Source" "Home table for all report measures."
Add-Col $mt "Measure Placeholder" "String" -Hidden | Out-Null

function Add-Measure([string]$name, [string]$expr, [string]$fmt, [string]$folder, [string]$desc, [switch]$Hidden) {
    $ms = New-Object "$NS.Measure"
    $ms.Name = $name
    $ms.Expression = $expr
    if ($fmt) { $ms.FormatString = $fmt }
    $ms.DisplayFolder = $folder
    $ms.Description = $desc
    if ($Hidden) { $ms.IsHidden = $true }
    $mt.Measures.Add($ms)
}
$cur0 = "$Rs#,0"; $cur2 = "$Rs#,0.00"; $pct = "0.0%"; $int = "#,0"
Add-Measure "Total Revenue" "SUM ( FactSales[Revenue] )" $cur0 "Sales" "Completed-sale revenue: sum of quantity x unit price x (1 - discount). Returns are excluded."
Add-Measure "Total Cost" "SUM ( FactSales[Cost] )" $cur0 "Sales" "Cost of goods sold: quantity x catalogue unit cost."
Add-Measure "Gross Profit" "[Total Revenue] - [Total Cost]" $cur0 "Sales" "Revenue minus cost of goods sold (not net profit)."
Add-Measure "Gross Margin %" "DIVIDE ( [Gross Profit], [Total Revenue] )" $pct "Sales" "Gross profit as a share of revenue; BLANK when there is no revenue."
Add-Measure "Orders" "DISTINCTCOUNT ( FactSales[Order ID] )" $int "Sales" "Number of distinct order IDs."
Add-Measure "Units Sold" "SUM ( FactSales[Quantity] )" $int "Sales" "Units sold on completed orders."
Add-Measure "Avg Order Value" "DIVIDE ( [Total Revenue], [Orders] )" $cur2 "Sales" "Average order value (AOV) = revenue / orders. One product per order in this dataset."
Add-Measure "Revenue PM" "CALCULATE ( [Total Revenue], DATEADD ( DimDate[Date], -1, MONTH ) )" $cur0 "Time intelligence" "Revenue for the previous month, using DATEADD on the marked DimDate table."
Add-Measure "MoM Growth %" "VAR PrevMonthRevenue = [Revenue PM]`nRETURN`n    IF ( NOT ISBLANK ( PrevMonthRevenue ), DIVIDE ( [Total Revenue] - PrevMonthRevenue, PrevMonthRevenue ) )" $pct "Time intelligence" "Month-over-month revenue growth; BLANK for January 2025 because there is no December 2024."
Add-Measure "Revenue YTD" "TOTALYTD ( [Total Revenue], DimDate[Date] )" $cur0 "Time intelligence" "Year-to-date running revenue (matches SQL Q8)."
Add-Measure "Revenue Share %" "DIVIDE ( [Total Revenue], CALCULATE ( [Total Revenue], REMOVEFILTERS ( FactSales[Channel] ), REMOVEFILTERS ( DimRegion ) ) )" $pct "Sales" "Share of revenue across all channels and regions (other filters such as date and product are kept)."
Add-Measure "Inventory Value" "SUM ( FactInventory[Inventory Value] )" $cur0 "Inventory" "Stock value at cost on the 2025-12-31 snapshot."
Add-Measure "On Hand Units" "SUM ( FactInventory[On Hand Units] )" $int "Inventory" "Units on hand on the snapshot date."
Add-Measure "Reorder Alerts" "COALESCE ( CALCULATE ( COUNTROWS ( FactInventory ), KEEPFILTERS ( FactInventory[Stock Status] = `"Reorder`" ) ), 0 )" $int "Inventory" "Product-region rows at or below their reorder point."
Add-Measure "Overstock Alerts" "COALESCE ( CALCULATE ( COUNTROWS ( FactInventory ), KEEPFILTERS ( FactInventory[Stock Status] = `"Overstock`" ) ), 0 )" $int "Inventory" "Product-region rows holding more than their target stock."
Add-Measure "Healthy Items" "COALESCE ( CALCULATE ( COUNTROWS ( FactInventory ), KEEPFILTERS ( FactInventory[Stock Status] = `"Healthy`" ) ), 0 )" $int "Inventory" "Product-region rows between reorder point and target stock."
Add-Measure "Units To Reorder" "SUMX ( FILTER ( FactInventory, FactInventory[Stock Status] = `"Reorder`" ), RELATED ( DimProduct[Target Stock] ) - FactInventory[On Hand Units] )" $int "Inventory" "Units needed to bring Reorder rows back to target stock."
Add-Measure "Excess Units" "SUMX ( FILTER ( FactInventory, FactInventory[Stock Status] = `"Overstock`" ), FactInventory[On Hand Units] - RELATED ( DimProduct[Target Stock] ) )" $int "Inventory" "Units above target stock on Overstock rows."
Add-Measure "Alert On Hand Units" "CALCULATE ( [On Hand Units], KEEPFILTERS ( FactInventory[Stock Status] IN { `"Reorder`", `"Overstock`" } ) )" $int "Inventory" "On-hand units for Reorder and Overstock rows only (drives the alert table)."
Add-Measure "Alert Inventory Value" "CALCULATE ( [Inventory Value], KEEPFILTERS ( FactInventory[Stock Status] IN { `"Reorder`", `"Overstock`" } ) )" $cur0 "Inventory" "Inventory value at cost for Reorder and Overstock rows only."
Add-Measure "Returns Units" "-SUM ( Returns[Quantity] )" $int "Returns" "Units returned (positive number); excluded from revenue KPIs."
Add-Measure "Returned Lines" "COUNTROWS ( Returns )" $int "Returns" "Number of return lines kept aside by the pipeline."
Add-Measure "Returns Value" "SUM ( Returns[Return Value] )" $cur0 "Returns" "Value of returned units at the original discounted price."
Add-Measure "Margin Color" "VAR Margin = [Gross Margin %]`nRETURN`n    SWITCH ( TRUE (), ISBLANK ( Margin ), BLANK (), Margin >= 0.38, `"#1B7F5B`", Margin < 0.32, `"#C0392B`", `"#B9770E`" )" "" "Formatting" "Font colour for margin cells: green >= 38%, red < 32%, amber otherwise." -Hidden
Add-Measure "Stock Status Color" "SWITCH ( SELECTEDVALUE ( FactInventory[Stock Status] ), `"Reorder`", `"#C0392B`", `"Overstock`", `"#B9770E`", `"Healthy`", `"#1B7F5B`" )" "" "Formatting" "Font colour for the stock status column." -Hidden

# ---- Relationships (single direction, many-to-one) ----------------------------------------------
function Add-Rel($fromTable, [string]$fromCol, $toTable, [string]$toCol) {
    $r = New-Object "$NS.SingleColumnRelationship"
    $r.Name = "$($fromTable.Name)_$($fromCol)_$($toTable.Name)".Replace(' ', '')
    $r.FromColumn = $fromTable.Columns[$fromCol]
    $r.ToColumn = $toTable.Columns[$toCol]
    $r.FromCardinality = [Microsoft.AnalysisServices.Tabular.RelationshipEndCardinality]::Many
    $r.ToCardinality = [Microsoft.AnalysisServices.Tabular.RelationshipEndCardinality]::One
    $r.CrossFilteringBehavior = [Microsoft.AnalysisServices.Tabular.CrossFilteringBehavior]::OneDirection
    $model.Relationships.Add($r)
}
Add-Rel $factSales "Order Date" $dimDate "Date"
Add-Rel $factSales "Product ID" $dimProduct "Product ID"
Add-Rel $factSales "Region Key" $dimRegion "Region Key"
Add-Rel $factInv "Snapshot Date" $dimDate "Date"
Add-Rel $factInv "Product ID" $dimProduct "Product ID"
Add-Rel $factInv "Region Key" $dimRegion "Region Key"
Add-Rel $returns "Return Date" $dimDate "Date"
Add-Rel $returns "Product ID" $dimProduct "Product ID"
Add-Rel $returns "Region Key" $dimRegion "Region Key"

# ---- Serialize to TMDL --------------------------------------------------------------------------
if (Test-Path $OutFolder) { Remove-Item $OutFolder -Recurse -Force }
[Microsoft.AnalysisServices.Tabular.TmdlSerializer]::SerializeDatabaseToFolder($db, $OutFolder)

# Round-trip check: the folder must deserialize back into an equivalent model.
$back = [Microsoft.AnalysisServices.Tabular.TmdlSerializer]::DeserializeDatabaseFromFolder($OutFolder)
"TMDL written to $OutFolder"
"Round-trip OK: {0} tables, {1} measures, {2} relationships, DataFolder = {3}" -f $back.Model.Tables.Count, $back.Model.Tables["_Measures"].Measures.Count, $back.Model.Relationships.Count, $folderLiteral
