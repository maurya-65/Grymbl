# Grymbl terminal hook for PowerShell (Windows PowerShell 5.1 and PowerShell 7+).
# Load it from $PROFILE:
#   grymbl shell-hook powershell | Out-String | Invoke-Expression
#
# Captures each finished command and its exit code, only inside Grymbl-watched repos.
# Redaction happens in `grymbl capture-command` before anything is stored.

$global:__GrymblExe = (Get-Command grymbl -CommandType Application -ErrorAction SilentlyContinue |
    Select-Object -First 1).Source

if ($global:__GrymblExe -and -not $global:__GrymblOriginalPrompt) {
    $global:__GrymblOriginalPrompt = $function:prompt
    $global:__GrymblLastHistoryId = (Get-History -Count 1).Id

    function global:__GrymblInWatchedRepo {
        if ($PWD.Provider.Name -ne 'FileSystem') { return $false }
        $dir = $PWD.ProviderPath
        while ($dir) {
            if (Test-Path -LiteralPath (Join-Path $dir '.grymbl') -PathType Container) { return $true }
            $dir = Split-Path -Parent $dir
        }
        return $false
    }

    function global:__GrymblSend([string]$Command, [int]$ExitCode) {
        # Fire and forget so the prompt never waits; bytes are written as UTF-8 explicitly
        # because Windows PowerShell 5.1 cannot set the stdin encoding.
        $info = New-Object System.Diagnostics.ProcessStartInfo
        $info.FileName = $global:__GrymblExe
        $info.Arguments = "capture-command --exit-code $ExitCode"
        $info.WorkingDirectory = $PWD.ProviderPath
        $info.UseShellExecute = $false
        $info.CreateNoWindow = $true
        $info.RedirectStandardInput = $true
        try {
            $process = [System.Diagnostics.Process]::Start($info)
            $bytes = [System.Text.Encoding]::UTF8.GetBytes($Command)
            $process.StandardInput.BaseStream.Write($bytes, 0, $bytes.Length)
            $process.StandardInput.Close()
        } catch { }
    }

    function global:prompt {
        $succeeded = $?
        $exitCode = if ($succeeded) { 0 } elseif ($global:LASTEXITCODE) { $global:LASTEXITCODE } else { 1 }
        $entry = Get-History -Count 1
        if ($entry -and $entry.Id -ne $global:__GrymblLastHistoryId) {
            $global:__GrymblLastHistoryId = $entry.Id
            if (__GrymblInWatchedRepo) { __GrymblSend $entry.CommandLine $exitCode }
        }
        & $global:__GrymblOriginalPrompt
    }
}
