# Janela de PowerShell para as capturas de ecra do relatorio: corre um comando real e avisa quando termina.
# Usado por docs/relatorio/capturar_ecra.py; nao e preciso chama-lo a mao.
param([string]$Titulo, [string]$Comando, [string]$Marcador, [int]$Colunas = 170, [int]$Linhas = 62, [int]$Fonte = 10)

$Host.UI.RawUI.WindowTitle = $Titulo
Add-Type @"
using System; using System.Runtime.InteropServices;
public class Consola {
  [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
  public struct FONTINFO { public int cbSize; public int nFont; public short X; public short Y; public int FontFamily;
    public int FontWeight; [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string FaceName; }
  [DllImport("kernel32.dll")] public static extern IntPtr GetStdHandle(int h);
  [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] public static extern bool SetCurrentConsoleFontEx(IntPtr h, bool max, ref FONTINFO f);
}
"@
$f = New-Object Consola+FONTINFO
$f.cbSize = [Runtime.InteropServices.Marshal]::SizeOf($f)
$f.Y = $Fonte; $f.FontFamily = 54; $f.FontWeight = 400; $f.FaceName = "Consolas"
[Consola]::SetCurrentConsoleFontEx([Consola]::GetStdHandle(-11), $false, [ref]$f) | Out-Null

$ui = $Host.UI.RawUI
$ui.BackgroundColor = "Black"; $ui.ForegroundColor = "Gray"
$max = $ui.MaxPhysicalWindowSize
$c = [Math]::Min($Colunas, $max.Width); $l = [Math]::Min($Linhas, $max.Height)
try { $ui.WindowSize = New-Object Management.Automation.Host.Size([Math]::Min($c, $ui.WindowSize.Width), [Math]::Min($l, $ui.WindowSize.Height)) } catch {}
try { $ui.BufferSize = New-Object Management.Automation.Host.Size($c, 3000) } catch {}
try { $ui.WindowSize = New-Object Management.Automation.Host.Size($c, $l) } catch {}
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
Clear-Host

Set-Location (Resolve-Path "$PSScriptRoot\..\..")
foreach ($cmd in $Comando -split ";;") {
    Write-Host ("PS " + (Get-Location) + "> ") -NoNewline
    Write-Host $cmd.Trim() -ForegroundColor Yellow
    Invoke-Expression $cmd
}
# Avisa que terminou e diz se a saida coube na janela (linhas usadas / linhas visiveis).
Set-Content -Path $Marcador -Value ("{0} {1}" -f $ui.CursorPosition.Y, $ui.WindowSize.Height)
# Se a saida nao coube, o capturador pede para rolar a vista ate ao inicio e fotografa outra vez.
$fim = (Get-Date).AddMinutes(15)
while (-not (Test-Path "$Marcador.topo") -and (Get-Date) -lt $fim) { Start-Sleep -Milliseconds 200 }
$ui.WindowPosition = New-Object Management.Automation.Host.Coordinates(0, 0)
Set-Content -Path "$Marcador.topo.ok" -Value "ok"
Start-Sleep -Seconds 900
