Set WinScriptHost = CreateObject("WScript.Shell")
WinScriptHost.Run "pythonw.exe """D:\python exploration\news_feed_popup\main.py"""", 0, False
Set WinScriptHost = Nothing