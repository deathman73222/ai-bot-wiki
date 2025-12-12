; NSIS installer script for AI Bot
; Staging directory (created by scripts/build_installer.ps1): staging\

Name "AI Bot"
OutFile "AI-Bot-Installer.exe"
InstallDir "$PROGRAMFILES\\AI Bot"
RequestExecutionLevel admin

!include "MUI2.nsh"

Page components
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

Section "Install"
  SetOutPath "$INSTDIR"
  ; Install all staged files
  File /r "staging\*.*"

  ; Create Start Menu and Desktop shortcuts
  CreateDirectory "$SMPROGRAMS\\AI Bot"
  CreateShortcut "$SMPROGRAMS\\AI Bot\\AI Bot.lnk" "$INSTDIR\\AI Bot.exe"
  CreateShortcut "$DESKTOP\\AI Bot.lnk" "$INSTDIR\\AI Bot.exe"

  ; Write uninstall information
  WriteUninstaller "$INSTDIR\\uninstall.exe"
SectionEnd

Section "Uninstall"
  Delete "$INSTDIR\\AI Bot.exe"
  Delete "$INSTDIR\\uninstall.exe"
  RMDir /r "$INSTDIR"
  Delete "$DESKTOP\\AI Bot.lnk"
  Delete "$SMPROGRAMS\\AI Bot\\AI Bot.lnk"
  RMDir /r "$SMPROGRAMS\\AI Bot"
SectionEnd
