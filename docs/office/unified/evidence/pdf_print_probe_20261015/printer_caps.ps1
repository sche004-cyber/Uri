# Read-only printer capability query with the .NET Framework System.Drawing.Printing API built into Windows.
# Nothing is printed and no setting is changed.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$sw = [Diagnostics.Stopwatch]::StartNew()
$out = @()
foreach ($name in [System.Drawing.Printing.PrinterSettings]::InstalledPrinters) {
    $ps = New-Object System.Drawing.Printing.PrinterSettings
    $ps.PrinterName = $name
    $out += [ordered]@{
        name = $name; is_valid = $ps.IsValid; is_default = $ps.IsDefaultPrinter; can_duplex = $ps.CanDuplex
        supports_color = $ps.SupportsColor; max_copies = $ps.MaximumCopies; landscape_angle = $ps.LandscapeAngle
        paper_sizes = @($ps.PaperSizes | Select-Object -First 6 | ForEach-Object { $_.PaperName })
        paper_count = $ps.PaperSizes.Count
        resolutions = @($ps.PrinterResolutions | Select-Object -First 4 | ForEach-Object { "$($_.Kind) $($_.X)x$($_.Y)" })
        print_to_file_port = $ps.PrintToFile
    }
}
[ordered]@{ ms = $sw.ElapsedMilliseconds; printers = $out } | ConvertTo-Json -Depth 4
