' ============================================================
' novel-tts 隐藏窗口启动器
' 功能：双击后后台启动服务，不显示命令行窗口
' ============================================================

Option Explicit

Dim wsh, fso, scriptDir, pythonPath, envVars
Dim host, port, apiKey, outputDir, tempDir, dbUrl

' 默认值
host = "0.0.0.0"
port = "8008"
apiKey = "dev-local-key"
outputDir = ""
tempDir = ""
dbUrl = ""

Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' 尝试加载配置
If fso.FileExists(scriptDir & "\config.bat") Then
    LoadConfig scriptDir & "\config.bat"
End If

' 设置目录默认值
If outputDir = "" Then outputDir = scriptDir & "\data\audio"
If tempDir = "" Then tempDir = scriptDir & "\data\temp"
If dbUrl = "" Then dbUrl = "sqlite:///" & scriptDir & "\novel_tts.db"

' 创建必要目录
If Not fso.FolderExists(scriptDir & "\data") Then fso.CreateFolder(scriptDir & "\data")
If Not fso.FolderExists(outputDir) Then fso.CreateFolder(outputDir)
If Not fso.FolderExists(tempDir) Then fso.CreateFolder(tempDir)

' 构建环境变量字符串
envVars = "NOVEL_TTS_HOST=" & host & ";"
envVars = envVars & "NOVEL_TTS_PORT=" & port & ";"
envVars = envVars & "NOVEL_TTS_API_KEY=" & apiKey & ";"
envVars = envVars & "NOVEL_TTS_OUTPUT_DIR=" & outputDir & ";"
envVars = envVars & "NOVEL_TTS_TEMP_DIR=" & tempDir & ";"
envVars = envVars & "NOVEL_TTS_DB_URL=" & dbUrl

Set wsh = CreateObject("WScript.Shell")

' 后台启动 uvicorn，隐藏窗口
wsh.Run "cmd /c chcp 65001 >nul 2>&1 && set " & envVars & " && python -m uvicorn main:app --host " & host & " --port " & port & " --log-level info > \"" & scriptDir & "\novel-tts.log\" 2>&1", 0, False

' 等待服务启动
WScript.Sleep 2000

' 检查端口是否监听
Dim result
result = wsh.Run("cmd /c netstat -ano | findstr ":""" & port & """""" | findstr """LISTENING""" >nul 2>&1", 0, True)

If result = 0 Then
    MsgBox "novel-tts 服务已启动！" & vbCrLf & vbCrLf & _
           "API 地址: http://" & host & ":" & port & vbCrLf & _
           "日志文件: " & scriptDir & "\novel-tts.log", _
           vbInformation, "novel-tts"
Else
    MsgBox "服务启动失败，请检查日志: " & scriptDir & "\novel-tts.log", _
           vbCritical, "novel-tts 启动失败"
End If

Set wsh = Nothing
Set fso = Nothing

' ============================================================
' 辅助函数：从 config.bat 读取环境变量
' ============================================================
Sub LoadConfig(configPath)
    Dim stream, line, key, value
    Set stream = fso.OpenTextFile(configPath, 1, False)
    Do While Not stream.AtEndOfStream
        line = Trim(stream.ReadLine)
        ' 跳过注释和空行
        If Left(line, 3) = "set" Then
            line = Trim(Mid(line, 4))
            If InStr(line, "=") > 0 Then
                key = Trim(Split(line, "=")(0))
                value = Trim(Split(line, "=")(1))
                ' 去除引号
                If Left(value, 1) = Chr(34) Then value = Mid(value, 2)
                If Right(value, 1) = Chr(34) Then value = Left(value, Len(value) - 1)

                Select Case key
                    Case "NOVEL_TTS_HOST": host = value
                    Case "NOVEL_TTS_PORT": port = value
                    Case "NOVEL_TTS_API_KEY": apiKey = value
                    Case "NOVEL_TTS_OUTPUT_DIR": outputDir = value
                    Case "NOVEL_TTS_TEMP_DIR": tempDir = value
                    Case "NOVEL_TTS_DB_URL": dbUrl = value
                End Select
            End If
        End If
    Loop
    stream.Close
End Sub
