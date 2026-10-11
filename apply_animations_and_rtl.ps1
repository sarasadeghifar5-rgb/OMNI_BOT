# Apply Animations, Slide Transitions, and Native RTL Formatting
$ppt = New-Object -ComObject PowerPoint.Application

$filePath = "C:\Users\Sadeghi\OneDrive\Desktop\New folder (7)\Events_After_Balance_Sheet_Date.pptx"
$pres = $ppt.Presentations.Open($filePath, [Microsoft.Office.Core.MsoTriState]::msoFalse, [Microsoft.Office.Core.MsoTriState]::msoFalse, [Microsoft.Office.Core.MsoTriState]::msoFalse)

$slideIndex = 1
foreach ($slide in $pres.Slides) {
    # 1. Slide Transitions (انتقال‌های اسلاید)
    if ($slideIndex -eq 1) {
        $slide.SlideShowTransition.EntryEffect = 769 # ppEffectFade
        $slide.SlideShowTransition.Duration = 1.0
    } elseif ($slideIndex -eq 2) {
        $slide.SlideShowTransition.EntryEffect = 769 # ppEffectFade
        $slide.SlideShowTransition.Duration = 0.75
    } elseif ($slideIndex -eq 17) {
        $slide.SlideShowTransition.EntryEffect = 769 # ppEffectFade
        $slide.SlideShowTransition.Duration = 1.0
    } else {
        $slide.SlideShowTransition.EntryEffect = 769 # ppEffectFade
        $slide.SlideShowTransition.Duration = 0.6
    }
    $slide.SlideShowTransition.AdvanceOnClick = [Microsoft.Office.Core.MsoTriState]::msoTrue

    # 2. RTL Text and Shape Animations
    $seq = $slide.TimeLine.MainSequence
    $cardOrder = 0

    foreach ($shape in $slide.Shapes) {
        # Format text frames
        if ($shape.HasTextFrame) {
            try {
                $tr = $shape.TextFrame.TextRange
                $tr.ParagraphFormat.TextDirection = 2 # ppDirectionRightToLeft
            } catch {}
        }
        
        # Format tables
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

        # 3. Shape Entrance Animations (انیمیشن ورود کارت‌ها و المان‌ها)
        # Apply to content cards (rounded rectangles not background)
        if ($slideIndex -gt 1 -and $slideIndex -lt 17) {
            if ($shape.Type -eq 1 -and $shape.AutoShapeType -eq 5) { # msoShapeRoundedRectangle
                # Exclude background strip (height < 0.2 inch)
                if ($shape.Height -gt 50 -and $shape.Top -gt 80) {
                    try {
                        $eff = $seq.AddEffect($shape, 10, 0, 1) # 10 = msoAnimEffectFade
                        $eff.Timing.Duration = 0.45
                        if ($cardOrder -eq 0) {
                            $eff.Timing.TriggerType = 3 # msoAnimTriggerAfterPrevious
                            $eff.Timing.TriggerDelayTime = 0.2
                        } else {
                            $eff.Timing.TriggerType = 3 # msoAnimTriggerAfterPrevious
                            $eff.Timing.TriggerDelayTime = 0.15
                        }
                        $cardOrder++
                    } catch {}
                }
            }
        }
    }
    $slideIndex++
}

# Save updated presentation
$pres.Save()

# Re-export slides preview
$outDir = "C:\Users\Sadeghi\OneDrive\Desktop\New folder (7)\slides_preview_rtl"
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }
$pres.SaveAs($outDir, 17) # 17 = ppSaveAsPNG/JPG

$pres.Close()
$ppt.Quit()
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($ppt) | Out-Null

# Copy to Persian named file and Desktop
Copy-Item "C:\Users\Sadeghi\OneDrive\Desktop\New folder (7)\Events_After_Balance_Sheet_Date.pptx" "C:\Users\Sadeghi\OneDrive\Desktop\New folder (7)\رویدادهای_بعد_از_تاریخ_ترازنامه.pptx" -Force
Copy-Item "C:\Users\Sadeghi\OneDrive\Desktop\New folder (7)\Events_After_Balance_Sheet_Date.pptx" "C:\Users\Sadeghi\OneDrive\Desktop\رویدادهای_بعد_از_تاریخ_ترازنامه.pptx" -Force
Copy-Item "C:\Users\Sadeghi\OneDrive\Desktop\New folder (7)\Events_After_Balance_Sheet_Date.pptx" "C:\Users\Sadeghi\OneDrive\Desktop\Events_After_Balance_Sheet_Date.pptx" -Force

Write-Host "Animations, RTL formatting, and re-export complete!"
