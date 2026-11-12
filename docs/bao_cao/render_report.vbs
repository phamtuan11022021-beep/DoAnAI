Option Explicit
Dim app, doc, item, styleId, style, source, destination
source = WScript.Arguments(0)
destination = WScript.Arguments(1)
On Error Resume Next
Set app = CreateObject("Word.Application")
app.Visible = False
app.DisplayAlerts = 0
app.AutomationSecurity = 3
Set doc = app.Documents.Open(source, False, False, False)
If Err.Number <> 0 Then
 WScript.Echo "Cannot open: " & Err.Description
 app.Quit
 WScript.Quit 1
End If
doc.Fields.Update
For Each item In doc.TablesOfContents
 item.Update
 item.Range.Font.Name = "Times New Roman"
 item.Range.Font.Size = 11
 item.Range.Font.Color = 0
 With item.Range.ParagraphFormat
  .LineSpacingRule = 0
  .SpaceBefore = 0
  .SpaceAfter = 3
  .FirstLineIndent = 0
  .KeepWithNext = False
  .PageBreakBefore = False
 End With
Next
For Each item In doc.TablesOfFigures
 item.Update
 item.Range.Font.Name = "Times New Roman"
 item.Range.Font.Size = 11
 item.Range.Font.Color = 0
 With item.Range.ParagraphFormat
  .LineSpacingRule = 0
  .SpaceBefore = 0
  .SpaceAfter = 3
  .FirstLineIndent = 0
  .KeepWithNext = False
  .PageBreakBefore = False
 End With
Next
doc.Repaginate
For Each item In doc.TablesOfContents
 item.UpdatePageNumbers
Next
For Each item In doc.TablesOfFigures
 item.UpdatePageNumbers
Next
doc.Save
doc.SaveAs2 destination, 17
If Err.Number <> 0 Then
 WScript.Echo "Render error: " & Err.Description
 doc.Close False
 app.Quit
 WScript.Quit 1
End If
doc.Close False
app.Quit
WScript.Echo "Word updated and PDF exported"
