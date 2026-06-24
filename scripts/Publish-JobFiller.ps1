param(
    [string]$RepositoryName = "jobfiller",
    [string]$Owner = "",
    [ValidateSet("public", "private", "internal")]
    [string]$Visibility = "public"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Push-Location $Root
try {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw "GitHub CLI is required. Install gh, then run gh auth login."
    }

    gh auth status | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub CLI is not authenticated. Run gh auth login first."
    }

    $dirty = git status --porcelain
    if ($dirty) {
        throw "Refusing to publish with uncommitted changes. Commit or stash local changes first."
    }

    $branch = (git branch --show-current).Trim()
    if (-not $branch) {
        throw "Could not determine current git branch."
    }

    $remote = git remote get-url origin 2>$null
    if ($LASTEXITCODE -eq 0 -and $remote) {
        Write-Host "Pushing existing origin on branch $branch."
        git push -u origin $branch
        exit $LASTEXITCODE
    }

    $repoArg = if ($Owner) { "$Owner/$RepositoryName" } else { $RepositoryName }
    $visibilityFlag = "--$Visibility"
    Write-Host "Creating GitHub repository $repoArg and pushing $branch."
    gh repo create $repoArg $visibilityFlag --source $Root --remote origin --push
} finally {
    Pop-Location
}
