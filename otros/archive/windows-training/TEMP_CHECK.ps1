$vids = Get-ChildItem "C:\Users\JHON\Desktop\PROYECTO DE YOLO\ENTRENAMIENTO\DataSet5\Videos"
$total = ($vids | Measure-Object -Property Length -Sum).Sum
Write-Host "Total size: $([math]::Round($total/1GB,2)) GB"
Write-Host "Video count: $($vids.Count)"
Write-Host "First 3:"
$vids | Select-Object -First 3 | ForEach-Object { Write-Host "  $($_.Name): $([math]::Round($_.Length/1MB,1)) MB" }
