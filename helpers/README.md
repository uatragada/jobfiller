# JobFiller Helpers

These helper scripts support local application-material workflows. They do not submit applications; they only assist with selecting a local file in an already-open browser file picker.

## Local App

Start the dashboard from the project root:

```powershell
.\Start-JobFiller.ps1
```

The backend port is auto-detected and printed by the startup script. The dashboard runs at `http://127.0.0.1:5173`.

Run backend tests with the Python interpreter for your environment:

```powershell
python -m pytest
```

## Resume Upload File Picker

`Upload-ResumeFileDialog.ps1` waits for a Windows file picker, sets the file name field to an explicit local file path, and clicks the dialog's Open button.

`-FilePath` is required:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\helpers\Upload-ResumeFileDialog.ps1 `
  -FilePath ".\artifacts\candidate-resume.pdf"
```

The script writes progress to `artifacts\upload-helper.log` by default. Override that with `-LogPath` when needed.

## LinkedIn Resume Upload

`Start-LinkedInResumeUpload.ps1` runs the file-picker helper and clicks the currently visible LinkedIn `Upload resume` button through Windows accessibility.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\helpers\Start-LinkedInResumeUpload.ps1 `
  -FilePath ".\artifacts\candidate-resume.pdf"
```

After it finishes, verify that the browser shows the intended file as selected before continuing.

## Generic Browser Resume Upload

`Start-BrowserResumeUpload.ps1` runs the same file-picker helper, then clicks a visible browser button by accessible name. This works for sites that expose an `Attach`, `Upload`, or similar file button through Windows accessibility.

Example:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\helpers\Start-BrowserResumeUpload.ps1 `
  -FilePath ".\artifacts\candidate-resume.pdf" `
  -ButtonName "Attach" `
  -ButtonIndex 0
```

Use `-ButtonIndex 1` for the second matching button, such as an optional cover-letter attach control.
