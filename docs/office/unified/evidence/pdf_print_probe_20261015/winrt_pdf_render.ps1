# Renders pages of a PDF to PNG with the Windows built-in WinRT PDF API (Windows.Data.Pdf). No install.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File winrt_pdf_render.ps1 <pdf> <outdir> <widthPx>
param([string]$Pdf, [string]$OutDir, [int]$Width = 900)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
$asTaskAction = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction' })[0]
function Await($op, [Type]$t) { $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op)); $task.Wait(); $task.Result }
function AwaitAction($op) { $task = $asTaskAction.Invoke($null, @($op)); $task.Wait() }

$sw = [Diagnostics.Stopwatch]::StartNew()
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync((Resolve-Path $Pdf).Path)) ([Windows.Storage.StorageFile])
$doc = Await ([Windows.Data.Pdf.PdfDocument]::LoadFromFileAsync($file)) ([Windows.Data.Pdf.PdfDocument])
$openMs = $sw.ElapsedMilliseconds
$rows = @()
for ($i = 0; $i -lt $doc.PageCount; $i++) {
    $t = [Diagnostics.Stopwatch]::StartNew()
    $page = $doc.GetPage($i)
    $opts = New-Object Windows.Data.Pdf.PdfPageRenderOptions
    $opts.DestinationWidth = $Width
    $stream = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
    AwaitAction ($page.RenderToStreamAsync($stream, $opts))
    $net = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($stream.GetInputStreamAt(0))
    $outPath = Join-Path $OutDir ("winrt_p{0}.png" -f ($i + 1))
    $fs = [System.IO.File]::Create($outPath); $net.CopyTo($fs); $fs.Close()
    $rows += @{ page = $i + 1; ms = $t.ElapsedMilliseconds; bytes = (Get-Item $outPath).Length }
    $page.Dispose()
}
@{ pages = $doc.PageCount; open_ms = $openMs; total_ms = $sw.ElapsedMilliseconds; rows = $rows } | ConvertTo-Json -Depth 4
