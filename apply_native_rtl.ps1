# PowerShell script to apply true native PowerPoint RTL to every text frame and table
$ppt = New-Object -ComObject PowerPoint.Application
$ppt.Visible = [Microsoft.Office.Core.MsoTriState]::msoFalse

$filePath = "C:\Users\Sadeghi\OneDrive\Desktop\New folder (7)\Events_After_Balance_Sheet_Date.pptx"
$pres = $ppt.Presentations.Open($filePath, [Microsoft.Office.Core.MsoTriState]::msoFalse, [Microsoft.Office.Core.MsoTriState]::msoFalse, [Microsoft.Office.Core.MsoTriState]::msoFalse)

foreach ($slide in $pres.Slides) {
    foreach ($shape in $slide.Shapes) {
        if ($shape.HasTextFrame) {
            try {
                $tr = $shape.TextFrame.TextRange
                $tr.ParagraphFormat.TextDirection = 2 # ppDirectionRightToLeft
            } catch {}
        }
        if ($shape.HasTable) {
            try {
                $shape.Table.TableDirection = 2 # ppDirectionRightToLeft
                for ($r = 1; $r -le $shape.Table.Rows.Count; $r++) {
                    for ($c = 1; $c -le $shape.Table.Columns.Count; $c++) {
                        $cell = $shape.Table.Cell($r, $c)
                        $cell.Shape.TextFrame.TextRange.ParagraphFormat.TextDirection = 2
                    }
                }
            } catch {}
        }
    }
}

$pres.Save()
$outDir = "C:\Users\Sadeghi\OneDrive\Desktop\New folder (7)\slides_preview_rtl"
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }
$pres.SaveAs($outDir, 17) # Export PNG/JPG to verify
$pres.Close()
$ppt.Quit()
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($ppt) | Out-Null
Write-Host "Post processing and export complete!"
