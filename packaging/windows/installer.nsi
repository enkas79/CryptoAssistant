; Installer NSIS per CryptoAssistant
; Impacchetta l'intera cartella dist\CryptoAssistant\ generata da PyInstaller (onedir)
; in un setup.exe per Windows. La versione viene passata da CI con /DVERSION=x.y.z

!ifndef VERSION
!define VERSION "0.0.0"
!endif

Name "CryptoAssistant"
OutFile "CryptoAssistant-Setup-${VERSION}.exe"
InstallDir "$PROGRAMFILES64\CryptoAssistant"
RequestExecutionLevel admin

Page directory
Page instfiles

Section "Install"
  SetOutPath "$INSTDIR"
  File /r "..\..\dist\CryptoAssistant\*.*"

  CreateDirectory "$SMPROGRAMS\CryptoAssistant"
  CreateShortCut "$SMPROGRAMS\CryptoAssistant\CryptoAssistant.lnk" "$INSTDIR\CryptoAssistant.exe"
  CreateShortCut "$DESKTOP\CryptoAssistant.lnk" "$INSTDIR\CryptoAssistant.exe"

  WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir /r "$INSTDIR"
  Delete "$SMPROGRAMS\CryptoAssistant\CryptoAssistant.lnk"
  RMDir "$SMPROGRAMS\CryptoAssistant"
  Delete "$DESKTOP\CryptoAssistant.lnk"
SectionEnd
