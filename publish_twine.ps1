param(
    [string]$RepoUrl = "https://artifactory.yourorg.com/api/pypi/pypi-local/",
    [string]$Username,
    [string]$Password
)

# Clean old builds
Remove-Item -Recurse -Force dist, build, *.egg-info -ErrorAction Ignore

# Build the package
python -m build

# Upload via Twine
twine upload --repository-url $RepoUrl dist/* -u $Username -p $Password
