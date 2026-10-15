# Print worker (amendment A1 §A4, phase O2P). Prints approved pages of one PDF with approved settings, using the .NET
# Framework System.Drawing.Printing API and the Windows printer driver; pages are drawn as Windows.Data.Pdf rasters.
# Started by the service per job as:
#   powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File <run copy> <work root>
# inside a Job Object (memory limit). The service checks this file's hash first. All parameters arrive as ONE JSON
# line on stdin, never on the command line (review A1-m2). Output: JSON lines.
#
#   {"op":"info", "printer", "paper", "landscape"}      -> {ok, paper_mm:[w,h], printable_mm:[x,y,w,h], hard_mm:[x,y]}
#   {"op":"print", "pdf", "pages":[..], "printer", "document_name", "copies", "collate", "landscape", "paper",
#    "duplex":"simplex|long|short", "color":bool, "fit":"fit|actual", "dpi":300, "output_file":null|path}
#        -> {"event":"page","n":k} ... {"event":"done","pages":n,"ms":t} or {"ok":false,"error":...}
# `output_file` is used only for printers whose port asks for a file (Microsoft Print to PDF), so no Save dialog
# ever opens. The StandardPrintController shows no progress window.
param([Parameter(Mandatory = $true)][string]$WorkRoot)
$ErrorActionPreference = 'Stop'
function Reply($obj) { [Console]::Out.WriteLine(($obj | ConvertTo-Json -Compress -Depth 5)); [Console]::Out.Flush() }
if ($ExecutionContext.SessionState.LanguageMode -ne 'FullLanguage') { Reply @{ ok = $false; error = 'CLM_ACTIVE' }; exit 3 }
Add-Type -AssemblyName System.Drawing
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

function Settings($req) {
    $ps = New-Object System.Drawing.Printing.PrinterSettings
    $ps.PrinterName = [string]$req.printer
    if (-not $ps.IsValid) { throw 'PRINTER_NOT_FOUND' }
    $page = $ps.DefaultPageSettings
    if ($req.paper) {
        $match = $ps.PaperSizes | Where-Object { $_.PaperName -eq [string]$req.paper } | Select-Object -First 1
        if ($null -eq $match) { throw 'PAPER_NOT_SUPPORTED' }
        $page.PaperSize = $match
    }
    $page.Landscape = [bool]$req.landscape
    return @($ps, $page)
}

$line = [Console]::In.ReadLine()
try {
    $req = $line | ConvertFrom-Json
    if ($req.op -eq 'info') {
        $ps, $page = Settings $req
        $pa = $page.PrintableArea          # hundredths of an inch, portrait orientation
        $toMm = 0.254
        Reply @{ ok = $true; paper_mm = @([math]::Round($page.PaperSize.Width * $toMm, 1), [math]::Round($page.PaperSize.Height * $toMm, 1));
                 printable_mm = @([math]::Round($pa.X * $toMm, 1), [math]::Round($pa.Y * $toMm, 1),
                                  [math]::Round($pa.Width * $toMm, 1), [math]::Round($pa.Height * $toMm, 1));
                 hard_mm = @([math]::Round($page.HardMarginX * $toMm, 1), [math]::Round($page.HardMarginY * $toMm, 1)) }
        exit 0
    }
    if ($req.op -ne 'print') { Reply @{ ok = $false; error = 'BAD_REQUEST' }; exit 2 }
    $pdfPath = [System.IO.Path]::GetFullPath([string]$req.pdf)
    if (-not (Norm $pdfPath).StartsWith($root + '\')) { Reply @{ ok = $false; error = 'PATH_REFUSED' }; exit 2 }
    $name = [string]$req.document_name
    if ($name -notmatch '^URI Office [0-9a-f]{16}$') { Reply @{ ok = $false; error = 'BAD_REQUEST' }; exit 2 }
    $dpi = [int]$req.dpi
    if ($dpi -lt 96 -or $dpi -gt 600) { Reply @{ ok = $false; error = 'BAD_REQUEST' }; exit 2 }
    $ps, $page = Settings $req
    $ps.Copies = [int16][math]::Max(1, [int]$req.copies)
    $ps.Collate = [bool]$req.collate
    $ps.Duplex = switch ([string]$req.duplex) { 'long' { [System.Drawing.Printing.Duplex]::Vertical }
                                                 'short' { [System.Drawing.Printing.Duplex]::Horizontal }
                                                 default { [System.Drawing.Printing.Duplex]::Simplex } }
    $page.Color = [bool]$req.color
    if ($req.output_file) {
        $ps.PrintToFile = $true
        $ps.PrintFileName = [string]$req.output_file
    }
    $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($pdfPath)) ([Windows.Storage.StorageFile])
    $doc = Await ([Windows.Data.Pdf.PdfDocument]::LoadFromFileAsync($file)) ([Windows.Data.Pdf.PdfDocument])
    $pages = @($req.pages | ForEach-Object { [int]$_ } | Where-Object { $_ -ge 1 -and $_ -le $doc.PageCount })
    if ($pages.Count -eq 0) { Reply @{ ok = $false; error = 'NO_PAGES' }; exit 2 }
    $state = @{ i = 0 }
    $pd = New-Object System.Drawing.Printing.PrintDocument
    $pd.PrinterSettings = $ps
    $pd.DefaultPageSettings = $page
    $pd.DocumentName = $name
    $pd.PrintController = New-Object System.Drawing.Printing.StandardPrintController
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $pd.add_PrintPage({
        param($sender, $e)
        $n = $pages[$state.i]
        $pg = $doc.GetPage($n - 1)
        $bounds = $e.PageBounds                       # hundredths of an inch, current orientation
        $opts = New-Object Windows.Data.Pdf.PdfPageRenderOptions
        $opts.DestinationWidth = [uint32][math]::Round($bounds.Width / 100.0 * $dpi)
        $opts.BackgroundColor = [Windows.UI.Color]::FromArgb(255, 255, 255, 255)
        $stream = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
        AwaitAction ($pg.RenderToStreamAsync($stream, $opts))
        $net = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($stream.GetInputStreamAt(0))
        $img = [System.Drawing.Image]::FromStream($net)
        try {
            $e.Graphics.PageUnit = [System.Drawing.GraphicsUnit]::Display
            if ([string]$req.fit -eq 'actual') {
                $w = $pg.Size.Width / 96.0 * 100; $h = $pg.Size.Height / 96.0 * 100
                $e.Graphics.DrawImage($img, [single](-$e.PageSettings.HardMarginX), [single](-$e.PageSettings.HardMarginY), [single]$w, [single]$h)
            } else {
                # Fit to the printer's printable area, not to default 1-inch margins (review round 3, M2). The graphics
                # origin is the printable area's top-left corner; PrintableArea is not rotated for landscape.
                $pa = $e.PageSettings.PrintableArea
                $pw = $pa.Width; $ph = $pa.Height
                if ($e.PageSettings.Landscape) { $pw = $pa.Height; $ph = $pa.Width }
                $iw = $pg.Size.Width; $ih = $pg.Size.Height
                $scale = [math]::Min($pw / $iw, $ph / $ih)
                $w = $iw * $scale; $h = $ih * $scale
                $x = ($pw - $w) / 2
                $y = ($ph - $h) / 2
                $e.Graphics.DrawImage($img, [single]$x, [single]$y, [single]$w, [single]$h)
            }
        } finally { $img.Dispose(); $net.Dispose(); $stream.Dispose(); $pg.Dispose() }
        Reply @{ event = 'page'; n = $n }
        $state.i++
        $e.HasMorePages = $state.i -lt $pages.Count
    })
    $pd.Print()
    $peak = [math]::Round([System.Diagnostics.Process]::GetCurrentProcess().PeakWorkingSet64 / 1MB, 1)
    Reply @{ event = 'done'; ok = $true; pages = $pages.Count; ms = $sw.ElapsedMilliseconds; peak_ws_mb = $peak }
}
catch {
    $msg = [string]$_.Exception.Message
    $code = if ($msg -in @('PRINTER_NOT_FOUND', 'PAPER_NOT_SUPPORTED')) { $msg } else { 'PRINT_FAILED' }
    Reply @{ ok = $false; error = $code; detail = $_.Exception.GetType().Name }
    exit 1
}
