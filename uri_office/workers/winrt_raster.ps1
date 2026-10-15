# PDF page raster worker (amendment A1 §A3). Renders PDF pages to PNG with Windows.Data.Pdf, built into Windows.
# Started by the service as: powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File <run copy> <work root>
# inside a Job Object (memory limit, kill on close). The service checks this file's hash before every start.
#
# Protocol: one JSON object per line on stdin, one per line on stdout.
#   {"id":..,"op":"info","pdf":<path>}                                   -> {id, ok, pages, sizes:[[w,h],..]} (points)
#   {"id":..,"op":"render","pdf":<path>,"out_dir":<path>,"pages":[1,2],"width":880}
#                                                     -> {id, ok, rendered:[{page, file, ms}], pages}
#   {"id":..,"op":"quit"}
# Both paths must be inside the work root. Files are written as p<page>_w<width>.png. No script, link, launch action or
# attachment in the PDF is run or opened: Windows.Data.Pdf only rasterizes.
param([Parameter(Mandatory = $true)][string]$WorkRoot)
$ErrorActionPreference = 'Stop'
if ($ExecutionContext.SessionState.LanguageMode -ne 'FullLanguage') {
    [Console]::Out.WriteLine('{"id":null,"ok":false,"error":"CLM_ACTIVE"}'); exit 3
}
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

function Norm([string]$p) { [System.IO.Path]::GetFullPath($p).TrimEnd('\').ToLowerInvariant() }
$root = Norm $WorkRoot
function Inside([string]$p) {
    if (-not $p) { return $false }
    $n = Norm $p
    if (-not ($n -eq $root -or $n.StartsWith($root + '\'))) { return $false }
    # Refuse anything reached through a reparse point (junction or symlink) below the root.
    $cur = [System.IO.Path]::GetFullPath($p)
    while ($cur -and (Norm $cur) -ne $root) {
        if ((Test-Path -LiteralPath $cur) -and ((Get-Item -LiteralPath $cur -Force).Attributes -band
                [System.IO.FileAttributes]::ReparsePoint)) { return $false }
        $cur = [System.IO.Path]::GetDirectoryName($cur)
    }
    return $true
}
function Reply($obj) { [Console]::Out.WriteLine(($obj | ConvertTo-Json -Compress -Depth 5)); [Console]::Out.Flush() }

$cache = @{ path = $null; doc = $null }
function Open-Pdf([string]$path) {
    if ($cache.path -ne $path) {
        $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($path)) ([Windows.Storage.StorageFile])
        $cache.doc = Await ([Windows.Data.Pdf.PdfDocument]::LoadFromFileAsync($file)) ([Windows.Data.Pdf.PdfDocument])
        $cache.path = $path
    }
    return $cache.doc
}

Reply @{ id = $null; ok = $true; ready = $true }
while ($true) {
    $line = [Console]::In.ReadLine()
    if ($null -eq $line) { break }
    $req = $null
    try { $req = $line | ConvertFrom-Json } catch { Reply @{ id = $null; ok = $false; error = 'BAD_REQUEST' }; continue }
    $rid = $req.id
    if ($req.op -eq 'quit') { break }
    try {
        if (-not (Inside $req.pdf)) { Reply @{ id = $rid; ok = $false; error = 'PATH_REFUSED' }; continue }
        $full = [System.IO.Path]::GetFullPath($req.pdf)
        if ($req.op -eq 'info') {
            $doc = Open-Pdf $full
            $sizes = @()
            for ($i = 0; $i -lt $doc.PageCount; $i++) {
                $pg = $doc.GetPage($i); $s = $pg.Size
                # Size is in DIPs (1/96 in); points = DIP * 0.75
                $sizes += , @([math]::Round($s.Width * 0.75, 2), [math]::Round($s.Height * 0.75, 2))
                $pg.Dispose()
            }
            Reply @{ id = $rid; ok = $true; pages = [int]$doc.PageCount; sizes = $sizes }
        }
        elseif ($req.op -eq 'render') {
            if (-not (Inside $req.out_dir)) { Reply @{ id = $rid; ok = $false; error = 'PATH_REFUSED' }; continue }
            $width = [int]$req.width
            if ($width -lt 16 -or $width -gt 5000) { Reply @{ id = $rid; ok = $false; error = 'BAD_REQUEST' }; continue }
            $doc = Open-Pdf $full
            $pages = @($req.pages)
            if ($pages.Count -eq 0 -or $null -eq $req.pages) { $pages = 1..([int]$doc.PageCount) }
            $out = @()
            foreach ($n in $pages) {
                $n = [int]$n
                if ($n -lt 1 -or $n -gt $doc.PageCount) { continue }
                $t = [Diagnostics.Stopwatch]::StartNew()
                $page = $doc.GetPage($n - 1)
                $opts = New-Object Windows.Data.Pdf.PdfPageRenderOptions
                $opts.DestinationWidth = $width
                $opts.BackgroundColor = [Windows.UI.Color]::FromArgb(255, 255, 255, 255)
                $stream = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
                AwaitAction ($page.RenderToStreamAsync($stream, $opts))
                $net = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($stream.GetInputStreamAt(0))
                $name = 'p{0}_w{1}.png' -f $n, $width
                $tmp = Join-Path ([System.IO.Path]::GetFullPath($req.out_dir)) ($name + '.part')
                $fs = [System.IO.File]::Open($tmp, [System.IO.FileMode]::CreateNew)
                try { $net.CopyTo($fs) } finally { $fs.Close(); $net.Dispose(); $stream.Dispose(); $page.Dispose() }
                $final = Join-Path ([System.IO.Path]::GetFullPath($req.out_dir)) $name
                if (Test-Path -LiteralPath $final) { Remove-Item -LiteralPath $tmp } else { Move-Item -LiteralPath $tmp $final }
                $out += @{ page = $n; file = $name; ms = $t.ElapsedMilliseconds }
            }
            Reply @{ id = $rid; ok = $true; pages = [int]$doc.PageCount; rendered = $out }
        }
        else { Reply @{ id = $rid; ok = $false; error = 'BAD_REQUEST' } }
    }
    catch {
        $cache.path = $null; $cache.doc = $null
        Reply @{ id = $rid; ok = $false; error = 'RENDER_FAILED'; detail = $_.Exception.GetType().Name }
    }
}
