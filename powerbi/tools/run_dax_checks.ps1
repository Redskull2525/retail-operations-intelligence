<#
.SYNOPSIS
  While RetailOperations.pbip is open in Power BI Desktop, connect to Desktop's local
  Analysis Services instance, optionally run a full refresh, and evaluate every measure with DAX.
  Writes the results to a JSON file that powerbi/tools/reconcile.py compares with SQL.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File powerbi\tools\run_dax_checks.ps1 -Refresh -Out powerbi\tools\dax_results.json
#>
param([switch]$Refresh, [string]$Out = (Join-Path $PSScriptRoot "dax_results.json"), [string]$PbiBin = "")
$ErrorActionPreference = "Stop"
if (-not $PbiBin) {
    $pkg = Get-AppxPackage -Name "Microsoft.MicrosoftPowerBIDesktop" -ErrorAction SilentlyContinue
    $PbiBin = if ($pkg) { Join-Path $pkg.InstallLocation "bin" } else { "C:\Program Files\Microsoft Power BI Desktop\bin" }
}
Add-Type -Path (Join-Path $PbiBin "Microsoft.PowerBI.Tabular.dll")
Add-Type -Path (Join-Path $PbiBin "Microsoft.PowerBI.AdomdClient.dll")

# Desktop writes the port of its private msmdsrv.exe into the newest workspace folder.
$roots = @("$env:USERPROFILE\Microsoft\Power BI Desktop Store App\AnalysisServicesWorkspaces",
           "$env:LOCALAPPDATA\Microsoft\Power BI Desktop\AnalysisServicesWorkspaces",
           "$env:LOCALAPPDATA\Packages\Microsoft.MicrosoftPowerBIDesktop_8wekyb3d8bbwe\LocalState\AnalysisServicesWorkspaces")
$portFile = $roots | ? { Test-Path $_ } | % { Get-ChildItem $_ -Recurse -Filter msmdsrv.port.txt } |
            sort LastWriteTime -Descending | select -First 1
if (-not $portFile) { throw "No running Power BI Desktop workspace found." }
$port = (Get-Content $portFile.FullName -Encoding Unicode -Raw).Trim()
$conn = "Data Source=localhost:$port"
Write-Host "Connected to $conn"

$srv = New-Object Microsoft.AnalysisServices.Tabular.Server
$srv.Connect($conn)
$db = $srv.Databases[0]
if ($Refresh) {
    $db.Model.RequestRefresh([Microsoft.AnalysisServices.Tabular.RefreshType]::Full)
    $t0 = Get-Date
    $res = $db.Model.SaveChanges()
    Write-Host ("Full refresh finished in {0:N1}s" -f ((Get-Date) - $t0).TotalSeconds)
    foreach ($r in $res.XmlaResults) { foreach ($m in $r.Messages) { Write-Host "  message: $($m.Description)" } }
}
$db.Refresh($true)
$tables = @{}
foreach ($t in $db.Model.Tables) {
    $tables[$t.Name] = @{ state = "$($t.Partitions[0].State)"; refreshed = "$($t.Partitions[0].RefreshedTime)" }
}
$measureErrors = @{}
foreach ($m in $db.Model.Tables["_Measures"].Measures) { if ($m.ErrorMessage) { $measureErrors[$m.Name] = $m.ErrorMessage } }
$dbName = $db.Name
$srv.Disconnect()

$cn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection "$conn;Initial Catalog=$dbName"
$cn.Open()
function Invoke-Dax([string]$q) {
    $cmd = $cn.CreateCommand(); $cmd.CommandText = $q
    $rd = $cmd.ExecuteReader(); $rows = @()
    while ($rd.Read()) {
        $o = [ordered]@{}
        for ($i = 0; $i -lt $rd.FieldCount; $i++) {
            $name = $rd.GetName($i) -replace '^.*\[(.*)\]$', '$1'
            $v = $rd.GetValue($i); if ($v -is [DBNull]) { $v = $null }
            $o[$name] = $v
        }
        $rows += [pscustomobject]$o
    }
    $rd.Close(); return ,$rows
}
$queries = [ordered]@{
  totals = @'
EVALUATE ROW (
  "Total Revenue", [Total Revenue], "Total Cost", [Total Cost], "Gross Profit", [Gross Profit],
  "Gross Margin %", [Gross Margin %], "Orders", [Orders], "Units Sold", [Units Sold],
  "Avg Order Value", [Avg Order Value], "Revenue Share %", [Revenue Share %],
  "Inventory Value", [Inventory Value], "On Hand Units", [On Hand Units],
  "Reorder Alerts", [Reorder Alerts], "Overstock Alerts", [Overstock Alerts], "Healthy Items", [Healthy Items],
  "Units To Reorder", [Units To Reorder], "Excess Units", [Excess Units],
  "Alert On Hand Units", [Alert On Hand Units], "Alert Inventory Value", [Alert Inventory Value],
  "Returns Units", [Returns Units], "Returned Lines", [Returned Lines], "Returns Value", [Returns Value],
  "Fact rows", COUNTROWS ( FactSales ), "Inventory rows", COUNTROWS ( FactInventory ), "Date rows", COUNTROWS ( DimDate )
)
'@
  by_month = @'
EVALUATE SUMMARIZECOLUMNS ( DimDate[Year Month],
  "Total Revenue", [Total Revenue], "Revenue PM", [Revenue PM], "MoM Growth %", [MoM Growth %], "Revenue YTD", [Revenue YTD] )
ORDER BY DimDate[Year Month]
'@
  by_category = @'
EVALUATE SUMMARIZECOLUMNS ( DimProduct[Category],
  "Total Revenue", [Total Revenue], "Gross Profit", [Gross Profit], "Gross Margin %", [Gross Margin %] )
'@
  by_channel = @'
EVALUATE SUMMARIZECOLUMNS ( FactSales[Channel],
  "Orders", [Orders], "Total Revenue", [Total Revenue], "Revenue Share %", [Revenue Share %], "Avg Order Value", [Avg Order Value] )
'@
  by_region = @'
EVALUATE SUMMARIZECOLUMNS ( DimRegion[Region],
  "Orders", [Orders], "Total Revenue", [Total Revenue], "Gross Profit", [Gross Profit], "Gross Margin %", [Gross Margin %], "Revenue Share %", [Revenue Share %] )
'@
  by_status = @'
EVALUATE SUMMARIZECOLUMNS ( FactInventory[Stock Status],
  "Rows", COUNTROWS ( FactInventory ), "On Hand Units", [On Hand Units], "Inventory Value", [Inventory Value] )
'@
}
$result = [ordered]@{ connection = $conn; tables = $tables; measure_errors = $measureErrors }
foreach ($k in $queries.Keys) { $result[$k] = Invoke-Dax $queries[$k] }
$cn.Close()
$result | ConvertTo-Json -Depth 6 | Set-Content -Path $Out -Encoding UTF8
Write-Host "DAX results written to $Out"
if ($measureErrors.Count) { Write-Host "MEASURE ERRORS:"; $measureErrors.GetEnumerator() | % { Write-Host "  $($_.Key): $($_.Value)" } }
