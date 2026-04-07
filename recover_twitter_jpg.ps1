param(
    [string]$InputDir = ".\twitter_dump",
    [string]$OutputDir = ".\twitter_recovered"
)

$ErrorActionPreference = "SilentlyContinue"

$goodDir = Join-Path $OutputDir "good"
$recoveredDir = Join-Path $OutputDir "recovered"
$badDir = Join-Path $OutputDir "bad"
$logFile = Join-Path $OutputDir "recovery_log.csv"

New-Item -ItemType Directory -Force -Path $goodDir | Out-Null
New-Item -ItemType Directory -Force -Path $recoveredDir | Out-Null
New-Item -ItemType Directory -Force -Path $badDir | Out-Null

$results = @()

function Find-Sequence {
    param(
        [byte[]]$Data,
        [byte[]]$Pattern,
        [int]$StartIndex = 0
    )

    if ($Data.Length -lt $Pattern.Length) { return -1 }

    for ($i = $StartIndex; $i -le $Data.Length - $Pattern.Length; $i++) {
        $matched = $true
        for ($j = 0; $j -lt $Pattern.Length; $j++) {
            if ($Data[$i + $j] -ne $Pattern[$j]) {
                $matched = $false
                break
            }
        }
        if ($matched) { return $i }
    }
    return -1
}

function Test-Jpeg {
    param([byte[]]$Bytes)

    if ($Bytes.Length -lt 4) { return $false }
    if ($Bytes[0] -eq 0xFF -and $Bytes[1] -eq 0xD8) {
        $end = $Bytes.Length - 2
        if ($Bytes[$end] -eq 0xFF -and $Bytes[$end + 1] -eq 0xD9) {
            return $true
        }
    }
    return $false
}

function Get-UniquePath {
    param(
        [string]$Directory,
        [string]$FileName
    )

    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($FileName)
    $ext = [System.IO.Path]::GetExtension($FileName)
    $dest = Join-Path $Directory $FileName
    $i = 1

    while (Test-Path $dest) {
        $dest = Join-Path $Directory ("{0}_{1}{2}" -f $baseName, $i, $ext)
        $i++
    }

    return $dest
}

$jpegStart = [byte[]](0xFF,0xD8)
$jpegEnd   = [byte[]](0xFF,0xD9)

$files = Get-ChildItem $InputDir -Recurse -File | Where-Object {
    $_.Extension -match '^\.(jpg|jpeg)$'
}

foreach ($file in $files) {
    Write-Host "[*] Checking $($file.FullName)"
    $status = ""
    $note = ""
    $outputPath = ""

    try {
        $bytes = [System.IO.File]::ReadAllBytes($file.FullName)

        if (Test-Jpeg $bytes) {
            $outputPath = Get-UniquePath -Directory $goodDir -FileName $file.Name
            Copy-Item $file.FullName $outputPath -Force
            $status = "good"
            $note = "valid jpeg"
        }
        else {
            $startIdx = Find-Sequence -Data $bytes -Pattern $jpegStart
            $endIdx = -1

            if ($startIdx -ge 0) {
                $endIdx = Find-Sequence -Data $bytes -Pattern $jpegEnd -StartIndex ($startIdx + 2)
            }

            if ($startIdx -ge 0 -and $endIdx -gt $startIdx) {
                $length = ($endIdx + 2) - $startIdx
                $recoveredBytes = New-Object byte[] $length
                [Array]::Copy($bytes, $startIdx, $recoveredBytes, 0, $length)

                if (Test-Jpeg $recoveredBytes) {
                    $newName = [System.IO.Path]::GetFileNameWithoutExtension($file.Name) + "_recovered.jpg"
                    $outputPath = Get-UniquePath -Directory $recoveredDir -FileName $newName
                    [System.IO.File]::WriteAllBytes($outputPath, $recoveredBytes)
                    $status = "recovered"
                    $note = "carved from embedded jpeg signature"
                }
                else {
                    $outputPath = Get-UniquePath -Directory $badDir -FileName $file.Name
                    Copy-Item $file.FullName $outputPath -Force
                    $status = "bad"
                    $note = "signature found but validation failed"
                }
            }
            else {
                $outputPath = Get-UniquePath -Directory $badDir -FileName $file.Name
                Copy-Item $file.FullName $outputPath -Force
                $status = "bad"
                $note = "no recoverable jpeg signature pair"
            }
        }
    }
    catch {
        $outputPath = Get-UniquePath -Directory $badDir -FileName $file.Name
        Copy-Item $file.FullName $outputPath -Force
        $status = "error"
        $note = $_.Exception.Message
    }

    $results += [PSCustomObject]@{
        Source = $file.FullName
        Status = $status
        Output = $outputPath
        Note   = $note
        Size   = $file.Length
    }
}

$results | Export-Csv $logFile -NoTypeInformation -Encoding UTF8

Write-Host ""
Write-Host "완료:"
Write-Host " good      : $goodDir"
Write-Host " recovered : $recoveredDir"
Write-Host " bad       : $badDir"
Write-Host " log       : $logFile"
